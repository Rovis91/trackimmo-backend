import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import os
import dotenv
from pathlib import Path

from .processor_base import ProcessorBase
from trackimmo.modules.db_manager import DBManager

# Load environment variables
dotenv.load_dotenv()

class PriceEstimationService(ProcessorBase):
    """Processeur pour estimer les prix actuels des propriétés."""
    
    # Facteurs d'ajustement DPE
    DPE_FACTORS = {
        'A': 0.05,   # +5%
        'B': 0.03,   # +3%
        'C': 0.01,   # +1%
        'D': 0.00,   # référence
        'E': -0.02,  # -2%
        'F': -0.05,  # -5%
        'G': -0.08   # -8%
    }
    
    # Évolution annuelle par défaut si pas de données
    DEFAULT_ANNUAL_GROWTH = 0.03  # 3%
    
    # Plafond d'évolution
    MAX_ANNUAL_GROWTH = 0.10  # 10%
    MIN_ANNUAL_GROWTH = -0.10  # -10%
    
    def __init__(self, input_path: str = None, output_path: str = None,
                 db_url: str = None):
        super().__init__(input_path, output_path)
        self.db_url = db_url  # Conservé pour compatibilité mais non utilisé
        self.db_manager = None
        self.current_date = datetime.now().date()
    
    def process(self, **kwargs) -> bool:
        """
        Estime les prix actuels des propriétés.
        
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        # Charger les données
        df = self.load_csv()
        if df is None:
            return False
        
        # Initialiser le gestionnaire de base de données
        try:
            self.db_manager = DBManager()
            self.logger.info("Connexion à la base de données établie")
        except Exception as e:
            self.logger.error(f"Erreur de connexion à la base de données: {str(e)}")
            return False
        
        # Statistiques initiales
        initial_count = len(df)
        self.logger.info(f"Début de l'estimation des prix pour {initial_count} propriétés")
        
        try:
            # Ajouter les colonnes d'estimation
            df['estimated_price'] = 0
            df['price_evolution_rate'] = 0.0
            df['estimation_confidence'] = 0.0
            
            # Récupérer les taux d'évolution par ville et type de bien
            city_ids = df['city_id'].dropna().unique().tolist()
            city_growth_rates = self.get_city_growth_rates(city_ids)
            
            # Convertir sale_date en datetime de manière sécurisée
            self.logger.info("Conversion des dates de vente")
            df['sale_date_dt'] = pd.to_datetime(df['sale_date'], errors='coerce')
            
            # Vérifier les dates manquantes ou invalides et leur assigner une date par défaut
            invalid_dates = df['sale_date_dt'].isna()
            if invalid_dates.any():
                self.logger.warning(f"Dates de vente manquantes ou invalides pour {invalid_dates.sum()} propriétés - utilisation de la date actuelle")
                df.loc[invalid_dates, 'sale_date_dt'] = datetime.now()
            
            # Calculer l'âge de la vente en années de manière sécurisée
            df['sale_age_years'] = df['sale_date_dt'].apply(
                lambda x: (self.current_date - x.date()).days / 365.25 if pd.notna(x) else 0
            )
            
            # Pour chaque propriété, estimer le prix actuel
            for idx, row in df.iterrows():
                # Si vente récente (< 6 mois), conserver le prix original
                if row['sale_age_years'] < 0.5:
                    df.loc[idx, 'estimated_price'] = row['price']
                    df.loc[idx, 'price_evolution_rate'] = 0.0
                    df.loc[idx, 'estimation_confidence'] = 1.0
                    continue
                
                # Récupérer le taux d'évolution pour cette ville et ce type de bien
                city_id = row['city_id']
                property_type = row['property_type']
                
                if pd.isna(city_id) or pd.isna(property_type):
                    # Utiliser le taux par défaut si données manquantes
                    growth_rate = self.DEFAULT_ANNUAL_GROWTH
                else:
                    city_key = f"{city_id}_{property_type}"
                    growth_rate = city_growth_rates.get(city_key, self.DEFAULT_ANNUAL_GROWTH)
                
                # Calculer l'évolution totale
                years = row['sale_age_years']
                total_growth = (1 + growth_rate) ** years - 1
                
                # Plafonner l'évolution totale
                max_growth = (1 + self.MAX_ANNUAL_GROWTH) ** years - 1
                min_growth = (1 + self.MIN_ANNUAL_GROWTH) ** years - 1
                
                total_growth = min(max(total_growth, min_growth), max_growth)
                
                # Ajuster selon DPE si disponible
                dpe_adjustment = 0.0
                if pd.notna(row['dpe_energy_class']) and row['dpe_energy_class'] in self.DPE_FACTORS:
                    dpe_adjustment = self.DPE_FACTORS[row['dpe_energy_class']]
                
                # Calculer le prix estimé
                base_price = row['price']
                estimated_price = base_price * (1 + total_growth) * (1 + dpe_adjustment)
                
                # Arrondir le prix estimé
                estimated_price = round(estimated_price / 1000) * 1000
                
                # Mettre à jour le DataFrame
                df.loc[idx, 'estimated_price'] = estimated_price
                df.loc[idx, 'price_evolution_rate'] = total_growth
                
                # Calculer le score de confiance
                confidence = self.calculate_confidence_score(row, years, dpe_adjustment != 0)
                df.loc[idx, 'estimation_confidence'] = confidence
            
            # Nettoyer les colonnes temporaires
            df = df.drop(columns=['sale_date_dt', 'sale_age_years'])
            
            # Statistiques finales
            avg_evolution = df['price_evolution_rate'].mean() * 100
            avg_confidence = df['estimation_confidence'].mean() * 100
            
            self.logger.info(f"Estimation terminée: évolution moyenne de {avg_evolution:.1f}%, confiance moyenne de {avg_confidence:.1f}%")
            
            # Sauvegarder le résultat
            return self.save_csv(df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'estimation des prix: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def get_city_growth_rates(self, city_ids: List[str]) -> Dict[str, float]:
        """
        Get growth rates using city average prices.
        
        Args:
            city_ids: List of city IDs
            
        Returns:
            Dict mapping city_id_property_type to growth rate
        """
        if not city_ids or len(city_ids) == 0:
            return {}
            
        result = {}
        
        try:
            with self.db_manager as db:
                supabase_client = db.get_client()
                
                # Fetch city price data directly
                self.logger.info(f"Retrieving average prices for {len(city_ids)} cities")
                
                response = supabase_client.table("cities").select(
                    "city_id,house_price_avg,apartment_price_avg"
                ).in_("city_id", city_ids).execute()
                
                if not response.data:
                    self.logger.warning("No average price data found for cities")
                    return {}
                
                # Process each city's price data
                for city in response.data:
                    city_id = city.get('city_id')
                    
                    # Create growth rates for house prices
                    if city.get('house_price_avg') is not None and city.get('house_price_avg') > 0:
                        key = f"{city_id}_house"
                        # Use default annual growth rate
                        result[key] = self.DEFAULT_ANNUAL_GROWTH
                    
                    # Create growth rates for apartment prices
                    if city.get('apartment_price_avg') is not None and city.get('apartment_price_avg') > 0:
                        key = f"{city_id}_apartment"
                        # Use default annual growth rate
                        result[key] = self.DEFAULT_ANNUAL_GROWTH
                        
                self.logger.info(f"Retrieved price data for {len(result)} city/property type combinations")
                return result
                    
        except Exception as e:
            self.logger.error(f"Error retrieving city price data: {str(e)}")
            return {}
        
    def calculate_confidence_score(self, property_data: pd.Series, age_years: float, has_dpe: bool) -> float:
        """
        Calcule un score de confiance pour l'estimation.
        
        Args:
            property_data: Données de la propriété
            age_years: Âge de la vente en années
            has_dpe: Si la propriété a un DPE avec ajustement
            
        Returns:
            float: Score de confiance (0-1)
        """
        # Score de base
        score = 0.8
        
        # Pénalité d'âge (plus c'est ancien, moins c'est fiable)
        age_penalty = min(age_years * 0.05, 0.6)  # Max 60% de pénalité
        score -= age_penalty
        
        # Bonus DPE
        if has_dpe:
            score += 0.05
        
        # Bonus qualité géocodage
        geocoding_score = property_data.get('geocoding_score', 0)
        if geocoding_score > 0.8:
            score += 0.05
        
        # Bonus si le type de bien est spécifié
        if pd.notna(property_data.get('property_type')):
            score += 0.05
        
        # Plafonner le score entre 0 et 1
        return max(0.0, min(1.0, score))


if __name__ == "__main__":
    import argparse
    
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Analyser les arguments
    parser = argparse.ArgumentParser(description="Estimation des prix actuels")
    parser.add_argument("--input", help="Fichier CSV d'entrée", required=True)
    parser.add_argument("--output", help="Fichier CSV de sortie", required=False)
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_price_estimated.csv")
    
    # Exécuter le processeur
    estimator = PriceEstimationService(args.input, output)
    success = estimator.process()
    
    exit(0 if success else 1) 