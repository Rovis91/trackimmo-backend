import unicodedata
import re
import pandas as pd
from datetime import datetime
from typing import Optional

from .processor_base import ProcessorBase

class DataNormalizer(ProcessorBase):
    """Processeur pour normaliser et nettoyer les données immobilières brutes."""
    
    # Colonnes requises dans les données d'entrée
    REQUIRED_COLUMNS = ['address', 'city', 'price', 'sale_date']
    
    # Mapping des types de propriétés français vers les types de la base de données
    PROPERTY_TYPE_MAPPING = {
        # French mappings
        'maison': 'house',
        'appartement': 'apartment',
        'terrain': 'land',
        'local commercial': 'commercial',
        'autre': 'other',
        # English mappings (already normalized from scraper)
        'house': 'house',
        'apartment': 'apartment',
        'land': 'land',
        'commercial': 'commercial',
        'other': 'other'
    }
    
    def __init__(self, input_path: str = None, output_path: str = None):
        super().__init__(input_path, output_path)
    
    def process(self, **kwargs) -> bool:
        """
        Normalise et nettoie les données brutes.
        
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        # Charger les données
        df = self.load_csv()
        if df is None:
            return False
            
        # Vérifier les colonnes requises
        missing_columns = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_columns:
            self.logger.error(f"Colonnes manquantes: {missing_columns}")
            return False
        
        # Statistiques initiales
        initial_count = len(df)
        self.logger.info(f"Début du traitement avec {initial_count} lignes")
        
        # Appliquer les transformations
        try:
            # Normaliser les adresses et villes
            df['address_raw'] = df['address'].apply(self.normalize_address)
            df['city_name'] = df['city'].apply(self.normalize_city)
            
            # Convertir les types numériques
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).astype(int)
            df['surface'] = pd.to_numeric(df['surface'], errors='coerce').fillna(0).astype(int)
            df['rooms'] = pd.to_numeric(df['rooms'], errors='coerce').fillna(0).astype(int)
            
            # Normaliser les dates
            df['sale_date_parsed'] = df['sale_date'].apply(self.parse_date)
            invalid_dates = df['sale_date_parsed'].isna()
            
            if invalid_dates.any():
                invalid_count = invalid_dates.sum()
                self.logger.warning(f"Suppression de {invalid_count} propriétés avec dates invalides")
                df = df[~invalid_dates]
            
            df['sale_date'] = df['sale_date_parsed'].dt.strftime('%Y-%m-%d')
            df = df.drop(columns=['sale_date_parsed'])
            
            # Mapper les types de propriétés
            df['property_type'] = df['property_type'].str.lower().map(
                self.PROPERTY_TYPE_MAPPING).fillna('other')
            
            # Renommer la colonne property_url pour cohérence
            if 'property_url' in df.columns:
                df = df.rename(columns={'property_url': 'source_url'})
            else:
                df['source_url'] = ""
            
            # Supprimer les colonnes originales non nécessaires et garder seulement les colonnes finales
            df = df[['address_raw', 'city_name', 'price', 'surface', 'rooms', 
                     'sale_date', 'property_type', 'source_url']]
            
            # Valider les données
            df = self.validate_data(df)
            
            # Statistiques finales
            final_count = len(df)
            rejected_count = initial_count - final_count
            self.logger.info(f"Traitement terminé: {final_count} lignes valides, {rejected_count} rejetées")
            
            # Sauvegarder le résultat
            return self.save_csv(df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la normalisation: {str(e)}")
            return False
    
    def normalize_address(self, address: str) -> str:
        """
        Normalise une adresse (supprime accents, met en majuscules).
        
        Args:
            address: Adresse brute
            
        Returns:
            str: Adresse normalisée
        """
        if not isinstance(address, str):
            return ""
            
        # Supprimer les accents
        address = unicodedata.normalize('NFKD', address).encode('ASCII', 'ignore').decode('utf-8')
        
        # Mettre en majuscules
        address = address.upper()
        
        # Supprimer les caractères spéciaux non pertinents
        address = re.sub(r'[^\w\s]', ' ', address)
        
        # Supprimer les espaces multiples
        address = re.sub(r'\s+', ' ', address).strip()
        
        return address
    
    def normalize_city(self, city: str) -> str:
        """
        Normalise un nom de ville (supprime accents, met en majuscules).
        
        Args:
            city: Nom de ville brut
            
        Returns:
            str: Nom de ville normalisé
        """
        if not isinstance(city, str):
            return ""
            
        # Supprimer les accents
        city = unicodedata.normalize('NFKD', city).encode('ASCII', 'ignore').decode('utf-8')
        
        # Mettre en majuscules
        city = city.upper()
        
        # Supprimer les caractères spéciaux et tirets
        city = re.sub(r'[^\w\s]', ' ', city)
        
        # Supprimer les espaces multiples
        city = re.sub(r'\s+', ' ', city).strip()
        
        return city
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse une date au format DD/MM/YYYY.
        
        Args:
            date_str: Chaîne de date
            
        Returns:
            Optional[datetime]: Objet datetime ou None si invalide
        """
        if not isinstance(date_str, str):
            return None
            
        try:
            return datetime.strptime(date_str.strip(), '%d/%m/%Y')
        except ValueError:
            return None
    
    def validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Valide et filtre les données.
        
        Args:
            df: DataFrame à valider
            
        Returns:
            pd.DataFrame: DataFrame filtré
        """
        # Rejeter les propriétés sans adresse ou ville
        valid_address = df['address_raw'].str.strip() != ""
        valid_city = df['city_name'].str.strip() != ""
        
        # Rejeter les propriétés sans prix ou avec prix nul/négatif
        valid_price = df['price'] > 0
        
        # Filtrer
        valid_mask = valid_address & valid_city & valid_price
        
        if (~valid_mask).any():
            invalid_count = (~valid_mask).sum()
            self.logger.warning(f"Suppression de {invalid_count} propriétés avec données invalides")
        
        return df[valid_mask]

if __name__ == "__main__":
    import argparse
    import logging
    
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Analyser les arguments
    parser = argparse.ArgumentParser(description="Normalisation des données immobilières")
    parser.add_argument("--input", help="Fichier CSV d'entrée", required=True)
    parser.add_argument("--output", help="Fichier CSV de sortie", required=False)
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_normalized.csv")
    
    # Exécuter le processeur
    normalizer = DataNormalizer(args.input, output)
    success = normalizer.process()
    
    exit(0 if success else 1) 