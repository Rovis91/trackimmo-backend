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
        Récupère les taux d'évolution annuels par ville et type de bien.
        
        Args:
            city_ids: Liste des IDs de villes
            
        Returns:
            Dict[str, float]: Dictionnaire {city_id_property_type: taux_annuel}
        """
        if not city_ids or len(city_ids) == 0:
            return {}
            
        result = {}
        
        try:
            with self.db_manager as db:
                supabase_client = db.get_client()
                
                # Récupérer les adresses pour les villes spécifiées
                self.logger.info(f"Récupération des adresses pour {len(city_ids)} villes")
                
                # Récupérer toutes les données avec les ventes d'adresses par année
                # Note: On ne peut pas faire une requête SQL complexe directement, on va calculer en Python
                addresses = []
                
                # Limite à 100 villes par requête pour éviter de surcharger l'API
                batch_size = 100
                for i in range(0, len(city_ids), batch_size):
                    city_batch = city_ids[i:i + batch_size]
                    self.logger.info(f"Récupération du lot {i//batch_size + 1} de villes ({len(city_batch)} villes)")
                    
                    # Récupérer les adresses avec les champs nécessaires pour calculer l'évolution
                    response = supabase_client.table("addresses").select(
                        "city_id,property_type,sale_date,price,surface"
                    ).in_("city_id", city_batch).execute()
                    
                    if response.data:
                        addresses.extend(response.data)
                
                self.logger.info(f"Récupéré {len(addresses)} adresses des villes spécifiées")
                
                if not addresses:
                    self.logger.warning("Aucune adresse trouvée pour calculer les taux d'évolution")
                    return {}
                
                # Convertir en DataFrame pour faciliter l'analyse
                df_addresses = pd.DataFrame(addresses)
                
                # Convertir les dates en datetime pour l'extraction d'année
                df_addresses['sale_date'] = pd.to_datetime(df_addresses['sale_date'], errors='coerce')
                df_addresses['year'] = df_addresses['sale_date'].dt.year
                
                # Filtrer les entrées invalides
                df_valid = df_addresses.dropna(subset=['year', 'price', 'surface', 'city_id', 'property_type'])
                df_valid = df_valid[df_valid['surface'] > 0]
                
                if df_valid.empty:
                    self.logger.warning("Aucune donnée valide pour calculer les taux d'évolution")
                    return {}
                
                # Calculer le prix moyen par m² pour chaque ville, type et année
                yearly_averages = df_valid.groupby(['city_id', 'property_type', 'year']).apply(
                    lambda x: (x['price'] / x['surface']).mean()
                ).reset_index(name='avg_price_per_m2')
                
                # Trier pour faciliter le calcul des taux d'évolution
                yearly_averages = yearly_averages.sort_values(['city_id', 'property_type', 'year'])
                
                # Calculer les taux d'évolution annuels
                growth_rates = []
                
                # Regrouper par ville et type de bien
                for (city, prop_type), group in yearly_averages.groupby(['city_id', 'property_type']):
                    # S'assurer qu'il y a au moins deux années pour calculer l'évolution
                    if len(group) >= 2:
                        # Trier par année
                        sorted_group = group.sort_values('year')
                        
                        # Calculer les taux de croissance entre années consécutives
                        for i in range(len(sorted_group) - 1):
                            current_year = sorted_group.iloc[i]
                            next_year = sorted_group.iloc[i + 1]
                            
                            if current_year['avg_price_per_m2'] > 0 and next_year['avg_price_per_m2'] > 0:
                                growth = (next_year['avg_price_per_m2'] / current_year['avg_price_per_m2']) - 1
                                
                                growth_rates.append({
                                    'city_id': city,
                                    'property_type': prop_type,
                                    'year': current_year['year'],
                                    'growth': growth
                                })
                
                # Convertir en DataFrame pour l'agrégation
                df_growth = pd.DataFrame(growth_rates)
                
                if not df_growth.empty:
                    # Calculer la moyenne des taux de croissance par ville et type
                    avg_growth = df_growth.groupby(['city_id', 'property_type'])['growth'].mean().reset_index()
                    
                    # Convertir en dictionnaire avec le format attendu
                    for _, row in avg_growth.iterrows():
                        city_id = row['city_id']
                        property_type = row['property_type']
                        growth_rate = row['growth']
                        
                        # Plafonner le taux
                        growth_rate = min(max(growth_rate, self.MIN_ANNUAL_GROWTH), self.MAX_ANNUAL_GROWTH)
                        result[f"{city_id}_{property_type}"] = growth_rate
                
                return result
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des taux d'évolution: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
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