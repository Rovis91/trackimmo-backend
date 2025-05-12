# Documentation du Module d'Enrichissement des Données Immobilières

Cette documentation détaille l'implémentation du module d'enrichissement des données immobilières pour le projet TrackImmo. Elle suit une approche modulaire où chaque étape du processus correspond à un fichier Python distinct.

## Structure générale

Le module d'enrichissement est conçu selon l'architecture suivante:

```
trackimmo/
└── modules/
    └── enrichment/
        ├── __init__.py
        ├── processor_base.py                # Classe de base pour tous les processeurs
        ├── 01_data_normalizer.py            # Normalisation des données brutes
        ├── 02_city_resolver.py              # Résolution des villes et codes postaux
        ├── 03_geocoding_service.py          # Géocodage des adresses
        ├── 04_dpe_enrichment.py             # Enrichissement avec données DPE
        ├── 05_price_estimator.py            # Estimation des prix actuels
        ├── 06_db_integrator.py              # Intégration en base de données
        └── enrichment_orchestrator.py       # Orchestration du processus complet
```

## Classe de base (processor_base.py)

Tous les processeurs héritent d'une classe de base commune qui définit l'interface standard et les méthodes utilitaires.

```python
import logging
import os
import pandas as pd
from typing import Optional, Dict, Any, List

class ProcessorBase:
    """Classe de base pour tous les processeurs d'enrichissement."""
    
    def __init__(self, input_path: str = None, output_path: str = None):
        """
        Initialise le processeur avec les chemins d'entrée/sortie.
        
        Args:
            input_path: Chemin du fichier d'entrée (CSV)
            output_path: Chemin du fichier de sortie (CSV)
        """
        self.input_path = input_path
        self.output_path = output_path
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process(self, **kwargs) -> bool:
        """
        Traite les données d'entrée et produit les données de sortie.
        À implémenter dans les classes dérivées.
        
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        raise NotImplementedError("La méthode process() doit être implémentée")
    
    def load_csv(self, file_path: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Charge un fichier CSV en DataFrame.
        
        Args:
            file_path: Chemin du fichier à charger (utilise self.input_path si None)
            
        Returns:
            Optional[pd.DataFrame]: DataFrame chargé ou None en cas d'erreur
        """
        path = file_path or self.input_path
        if not path:
            self.logger.error("Aucun chemin de fichier spécifié")
            return None
            
        try:
            df = pd.read_csv(path)
            self.logger.info(f"Chargé {len(df)} lignes depuis {path}")
            return df
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de {path}: {str(e)}")
            return None
    
    def save_csv(self, df: pd.DataFrame, file_path: Optional[str] = None) -> bool:
        """
        Sauvegarde un DataFrame en CSV.
        
        Args:
            df: DataFrame à sauvegarder
            file_path: Chemin de sauvegarde (utilise self.output_path si None)
            
        Returns:
            bool: True si la sauvegarde a réussi, False sinon
        """
        path = file_path or self.output_path
        if not path:
            self.logger.error("Aucun chemin de sortie spécifié")
            return False
            
        try:
            # Créer le répertoire si nécessaire
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            df.to_csv(path, index=False)
            self.logger.info(f"Sauvegardé {len(df)} lignes dans {path}")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde dans {path}: {str(e)}")
            return False
```

## 1. Normalisation des données (01_data_normalizer.py)

Ce processeur est responsable du nettoyage et de la normalisation des données brutes.

### Entrée
CSV brut avec les colonnes:
```
address,city,price,surface,rooms,sale_date,property_type,property_url
```

### Sortie
CSV normalisé avec les colonnes:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url
```

### Implémentation

```python
import unicodedata
import re
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

from .processor_base import ProcessorBase

class DataNormalizer(ProcessorBase):
    """Processeur pour normaliser et nettoyer les données immobilières brutes."""
    
    # Colonnes requises dans les données d'entrée
    REQUIRED_COLUMNS = ['address', 'city', 'price', 'sale_date']
    
    # Mapping des types de propriétés français vers les types de la base de données
    PROPERTY_TYPE_MAPPING = {
        'maison': 'house',
        'appartement': 'apartment',
        'terrain': 'land',
        'local commercial': 'commercial',
        'autre': 'other'
    }
    
    def __init__(self, input_path: str = "data/raw/properties.csv", 
                 output_path: str = "data/processing/normalized.csv"):
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
            df = df.rename(columns={'property_url': 'source_url'})
            
            # Supprimer les colonnes originales non nécessaires
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
```

## 2. Résolution des villes et codes postaux (02_city_resolver.py)

Ce processeur est responsable de la résolution des villes et de la récupération des codes postaux et INSEE.

### Entrée
CSV normalisé avec les colonnes:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url
```

### Sortie
CSV avec villes résolues:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department
```

### Implémentation

```python
import pandas as pd
import requests
import io
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy import create_engine, text
from collections import Counter

from .processor_base import ProcessorBase

class CityResolver(ProcessorBase):
    """Processeur pour résoudre les villes et obtenir les codes postaux."""
    
    # URL de l'API de géocodage
    GEOCODING_API = "https://api-adresse.data.gouv.fr/search/csv/"
    
    def __init__(self, input_path: str = "data/processing/normalized.csv", 
                 output_path: str = "data/processing/cities_resolved.csv",
                 db_url: str = "postgresql://user:password@localhost/trackimmo"):
        super().__init__(input_path, output_path)
        self.db_url = db_url
        self.db_engine = None
    
    def process(self, **kwargs) -> bool:
        """
        Résout les villes et récupère les codes postaux.
        
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        # Charger les données
        df = self.load_csv()
        if df is None:
            return False
        
        # Initialiser le moteur de base de données
        try:
            self.db_engine = create_engine(self.db_url)
            self.logger.info("Connexion à la base de données établie")
        except Exception as e:
            self.logger.error(f"Erreur de connexion à la base de données: {str(e)}")
            return False
        
        # Statistiques initiales
        initial_count = len(df)
        self.logger.info(f"Début du traitement avec {initial_count} lignes")
        
        try:
            # Regrouper par ville
            city_groups = df.groupby('city_name')
            distinct_cities = city_groups.size().reset_index(name='count')
            self.logger.info(f"Traitement de {len(distinct_cities)} villes distinctes")
            
            # Récupérer les villes existantes dans la base de données
            existing_cities = self.get_existing_cities(distinct_cities['city_name'].tolist())
            self.logger.info(f"Trouvé {len(existing_cities)} villes existantes en base")
            
            # Identifier les villes manquantes
            existing_city_names = {city['name'].upper() for city in existing_cities}
            missing_cities = distinct_cities[~distinct_cities['city_name'].isin(existing_city_names)]
            
            if not missing_cities.empty:
                self.logger.info(f"Résolution de {len(missing_cities)} villes manquantes")
                resolved_cities = self.resolve_missing_cities(missing_cities, df)
                
                # Ajouter les villes résolues à la base de données
                if resolved_cities:
                    self.add_cities_to_db(resolved_cities)
                    
                # Mettre à jour la liste des villes existantes
                all_cities = existing_cities + resolved_cities
            else:
                all_cities = existing_cities
            
            # Créer un dictionnaire de correspondance ville → données
            city_data = {city['name'].upper(): city for city in all_cities}
            
            # Enrichir le DataFrame avec les données de ville
            df['city_id'] = df['city_name'].map(lambda x: city_data.get(x, {}).get('city_id'))
            df['postal_code'] = df['city_name'].map(lambda x: city_data.get(x, {}).get('postal_code'))
            df['insee_code'] = df['city_name'].map(lambda x: city_data.get(x, {}).get('insee_code'))
            df['department'] = df['city_name'].map(lambda x: city_data.get(x, {}).get('department'))
            
            # Filtrer les propriétés sans ville résolue
            valid_mask = df['city_id'].notna()
            invalid_count = (~valid_mask).sum()
            
            if invalid_count > 0:
                self.logger.warning(f"Suppression de {invalid_count} propriétés sans ville résolue")
                df = df[valid_mask]
            
            # Statistiques finales
            final_count = len(df)
            self.logger.info(f"Traitement terminé: {final_count} lignes valides")
            
            # Sauvegarder le résultat
            return self.save_csv(df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la résolution des villes: {str(e)}")
            return False
    
    def get_existing_cities(self, city_names: List[str]) -> List[Dict[str, Any]]:
        """
        Récupère les villes existantes dans la base de données.
        
        Args:
            city_names: Liste des noms de villes à rechercher
            
        Returns:
            List[Dict[str, Any]]: Liste des villes trouvées
        """
        if not city_names:
            return []
            
        try:
            # Convertir les noms de villes en majuscules pour la comparaison
            upper_names = [name.upper() for name in city_names]
            
            # Préparer la requête SQL
            query = text("""
                SELECT city_id, name, postal_code, insee_code, department
                FROM cities
                WHERE UPPER(name) IN :city_names
            """)
            
            # Exécuter la requête
            with self.db_engine.connect() as conn:
                result = conn.execute(query, {"city_names": tuple(upper_names)})
                cities = [
                    {
                        "city_id": row[0],
                        "name": row[1],
                        "postal_code": row[2],
                        "insee_code": row[3],
                        "department": row[4]
                    }
                    for row in result
                ]
                
            return cities
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des villes: {str(e)}")
            return []
    
    def resolve_missing_cities(self, missing_cities: pd.DataFrame, 
                              all_properties: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Résout les villes manquantes en utilisant l'API de géocodage.
        
        Args:
            missing_cities: DataFrame des villes manquantes
            all_properties: DataFrame de toutes les propriétés
            
        Returns:
            List[Dict[str, Any]]: Liste des villes résolues
        """
        resolved_cities = []
        
        for _, city_row in missing_cities.iterrows():
            city_name = city_row['city_name']
            
            # Obtenir toutes les propriétés pour cette ville
            city_properties = all_properties[all_properties['city_name'] == city_name]
            
            if city_properties.empty:
                continue
                
            self.logger.info(f"Résolution de la ville: {city_name} ({len(city_properties)} propriétés)")
            
            # Créer un CSV temporaire avec les adresses et la ville
            temp_df = pd.DataFrame({
                'address': city_properties['address_raw'],
                'city': city_name
            })
            
            # Récupérer les codes postaux via l'API de géocodage
            postal_codes, insee_codes = self.get_city_codes_from_geocoding(temp_df)
            
            if postal_codes and insee_codes:
                # Prendre le code postal et INSEE le plus fréquent
                postal_code = postal_codes[0][0]
                insee_code = insee_codes[0][0]
                department = postal_code[:2]
                
                resolved_cities.append({
                    "name": city_name,
                    "postal_code": postal_code,
                    "insee_code": insee_code,
                    "department": department
                })
                
                self.logger.info(f"Ville résolue: {city_name} → CP: {postal_code}, INSEE: {insee_code}")
            else:
                self.logger.warning(f"Impossible de résoudre la ville: {city_name}")
        
        return resolved_cities
    
    def get_city_codes_from_geocoding(self, addresses_df: pd.DataFrame) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
        """
        Obtient les codes postaux et INSEE en envoyant les adresses à l'API de géocodage.
        
        Args:
            addresses_df: DataFrame contenant les colonnes 'address' et 'city'
            
        Returns:
            Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]: 
                Codes postaux et INSEE les plus fréquents (triés par fréquence)
        """
        try:
            # Convertir le DataFrame en CSV
            csv_buffer = io.StringIO()
            addresses_df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()
            
            # Appeler l'API de géocodage
            response = requests.post(
                self.GEOCODING_API,
                files={'data': ('addresses.csv', csv_content.encode('utf-8'), 'text/csv')},
                data={'columns': 'address,city'}
            )
            
            if response.status_code != 200:
                self.logger.error(f"Erreur API géocodage: {response.status_code}")
                return [], []
            
            # Parser la réponse CSV
            result_df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            # Compter les codes postaux et INSEE
            postal_counts = Counter(result_df['result_postcode'].dropna())
            insee_counts = Counter(result_df['result_citycode'].dropna())
            
            # Trier par fréquence décroissante
            postal_codes = sorted(postal_counts.items(), key=lambda x: x[1], reverse=True)
            insee_codes = sorted(insee_counts.items(), key=lambda x: x[1], reverse=True)
            
            return postal_codes, insee_codes
            
        except Exception as e:
            self.logger.error(f"Erreur lors du géocodage: {str(e)}")
            return [], []
    
    def add_cities_to_db(self, cities: List[Dict[str, Any]]) -> bool:
        """
        Ajoute les villes résolues à la base de données.
        
        Args:
            cities: Liste des villes à ajouter
            
        Returns:
            bool: True si l'ajout a réussi, False sinon
        """
        if not cities:
            return True
            
        try:
            # Préparer la requête d'insertion
            query = text("""
                INSERT INTO cities (name, postal_code, insee_code, department, created_at, updated_at)
                VALUES (:name, :postal_code, :insee_code, :department, NOW(), NOW())
                ON CONFLICT (insee_code) DO UPDATE
                SET postal_code = EXCLUDED.postal_code,
                    department = EXCLUDED.department,
                    updated_at = NOW()
                RETURNING city_id
            """)
            
            with self.db_engine.connect() as conn:
                with conn.begin():
                    for city in cities:
                        result = conn.execute(query, city)
                        city_id = result.scalar()
                        city['city_id'] = city_id
            
            self.logger.info(f"Ajouté {len(cities)} villes à la base de données")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'ajout des villes: {str(e)}")
            return False
```

## 3. Géocodage des adresses (03_geocoding_service.py)

Ce processeur est responsable du géocodage des adresses pour obtenir les coordonnées géographiques.

### Entrée
CSV avec villes résolues:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department
```

### Sortie
CSV avec coordonnées:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department,latitude,longitude,address_normalized,geocoding_score
```

### Implémentation

```python
import pandas as pd
import requests
import io
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

from .processor_base import ProcessorBase

class GeocodingService(ProcessorBase):
    """Processeur pour géocoder les adresses."""
    
    # Configuration de l'API
    GEOCODING_API = "https://api-adresse.data.gouv.fr/search/csv/"
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # secondes
    CHUNK_SIZE = 5000  # nombre d'adresses par lot
    
    def __init__(self, input_path: str = "data/processing/cities_resolved.csv", 
                 output_path: str = "data/processing/geocoded.csv",
                 original_bbox: Optional[Dict[str, float]] = None):
        super().__init__(input_path, output_path)
        self.original_bbox = original_bbox  # Rectangle de la zone de scraping
    
    def process(self, **kwargs) -> bool:
        """
        Géocode les adresses pour obtenir leurs coordonnées.
        
        Args:
            **kwargs: Arguments additionnels
                - original_bbox: Rectangle de la zone de scraping (optionnel)
                - distance_threshold: Distance maximale (en km) pour filtrer les résultats (défaut: 5)
                
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        # Récupérer les paramètres
        original_bbox = kwargs.get('original_bbox', self.original_bbox)
        distance_threshold = kwargs.get('distance_threshold', 5.0)  # km
        
        # Charger les données
        df = self.load_csv()
        if df is None:
            return False
        
        # Statistiques initiales
        initial_count = len(df)
        self.logger.info(f"Début du géocodage avec {initial_count} propriétés")
        
        try:
            # Traiter par lots
            chunks = [df[i:i+self.CHUNK_SIZE] for i in range(0, len(df), self.CHUNK_SIZE)]
            self.logger.info(f"Traitement en {len(chunks)} lots de {self.CHUNK_SIZE} adresses maximum")
            
            # Initialiser le DataFrame résultat
            result_df = pd.DataFrame()
            
            for i, chunk_df in enumerate(chunks):
                self.logger.info(f"Traitement du lot {i+1}/{len(chunks)} ({len(chunk_df)} adresses)")
                
                # Préparer les données pour le géocodage
                geocoding_df = pd.DataFrame({
                    'address': chunk_df['address_raw'],
                    'city': chunk_df['city_name'],
                    'postcode': chunk_df['postal_code']
                })
                
                # Géocoder le lot
                geocoded_df = self.geocode_batch(geocoding_df)
                
                if geocoded_df is not None and not geocoded_df.empty:
                    # Combiner avec les données originales
                    chunk_result = chunk_df.copy()
                    
                    # Ajouter les colonnes de géocodage
                    chunk_result['latitude'] = geocoded_df['latitude']
                    chunk_result['longitude'] = geocoded_df['longitude']
                    chunk_result['address_normalized'] = geocoded_df['result_label']
                    chunk_result['geocoding_score'] = geocoded_df['result_score']
                    
                    # Valider et filtrer
                    chunk_result = self.validate_geocoding(chunk_result, original_bbox, distance_threshold)
                    
                    # Ajouter au résultat
                    result_df = pd.concat([result_df, chunk_result])
                
                # Attendre un peu pour respecter les limites de l'API
                time.sleep(0.1)
            
            # Statistiques finales
            final_count = len(result_df)
            rejected_count = initial_count - final_count
            
            self.logger.info(f"Géocodage terminé: {final_count} adresses valides, {rejected_count} rejetées")
            
            if final_count == 0:
                self.logger.error("Aucune adresse géocodée avec succès")
                return False
            
            # Sauvegarder le résultat
            return self.save_csv(result_df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du géocodage: {str(e)}")
            return False
    
    def geocode_batch(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Géocode un lot d'adresses.
        
        Args:
            df: DataFrame avec colonnes 'address', 'city' et 'postcode'
            
        Returns:
            Optional[pd.DataFrame]: DataFrame avec les résultats du géocodage ou None si échec
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Convertir le DataFrame en CSV
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_content = csv_buffer.getvalue()
                
                # Appeler l'API de géocodage
                response = requests.post(
                    self.GEOCODING_API,
                    files={'data': ('addresses.csv', csv_content.encode('utf-8'), 'text/csv')},
                    data={'columns': 'address,city,postcode'}
                )
                
                if response.status_code == 200:
                    # Parser la réponse CSV
                    result_df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
                    return result_df
                else:
                    self.logger.warning(f"Erreur API ({response.status_code}) - Tentative {attempt}/{self.MAX_RETRIES}")
                    
            except Exception as e:
                self.logger.warning(f"Erreur de requête - Tentative {attempt}/{self.MAX_RETRIES}: {str(e)}")
            
            # Attendre avant de réessayer
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY * attempt)  # Délai exponentiel
        
        self.logger.error("Échec du géocodage après plusieurs tentatives")
        return None
    
    def validate_geocoding(self, df: pd.DataFrame, original_bbox: Optional[Dict[str, float]], 
                          distance_threshold: float) -> pd.DataFrame:
        """
        Valide et filtre les résultats de géocodage.
        
        Args:
            df: DataFrame avec les résultats de géocodage
            original_bbox: Rectangle de la zone de scraping
            distance_threshold: Distance maximale (en km) pour filtrer les résultats
            
        Returns:
            pd.DataFrame: DataFrame filtré
        """
        # Convertir les colonnes de coordonnées en numérique
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        
        # Convertir les scores en numérique
        df['geocoding_score'] = pd.to_numeric(df['geocoding_score'], errors='coerce')
        
        # Filtrer les lignes sans coordonnées
        valid_coords = df['latitude'].notna() & df['longitude'].notna()
        invalid_coords_count = (~valid_coords).sum()
        
        if invalid_coords_count > 0:
            self.logger.warning(f"Suppression de {invalid_coords_count} adresses sans coordonnées")
            df = df[valid_coords]
        
        # Filtrer par score minimal (0.5)
        low_score = df['geocoding_score'] < 0.5
        low_score_count = low_score.sum()
        
        if low_score_count > 0:
            self.logger.warning(f"Suppression de {low_score_count} adresses avec score faible (<0.5)")
            df = df[~low_score]
        
        # Si un rectangle de scraping est fourni, filtrer par distance
        if original_bbox and not df.empty:
            # Calculer les limites étendues (original + seuil)
            min_lat = original_bbox.get('min_lat', 0) - (distance_threshold / 111.0)  # 1° ≈ 111km
            max_lat = original_bbox.get('max_lat', 0) + (distance_threshold / 111.0)
            min_lon = original_bbox.get('min_lon', 0) - (distance_threshold / (111.0 * 0.7))  # Ajuster pour longitude
            max_lon = original_bbox.get('max_lon', 0) + (distance_threshold / (111.0 * 0.7))
            
            # Filtrer
            in_bounds = (
                (df['latitude'] >= min_lat) & 
                (df['latitude'] <= max_lat) & 
                (df['longitude'] >= min_lon) & 
                (df['longitude'] <= max_lon)
            )
            
            out_of_bounds_count = (~in_bounds).sum()
            
            if out_of_bounds_count > 0:
                self.logger.warning(f"Suppression de {out_of_bounds_count} adresses hors zone de scraping (+/-{distance_threshold}km)")
                df = df[in_bounds]
        
        return df
```

## 4. Enrichissement DPE (04_dpe_enrichment.py)

Ce processeur est responsable de l'enrichissement des propriétés avec des données de diagnostic énergétique.

### Entrée
CSV avec coordonnées:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department,latitude,longitude,address_normalized,geocoding_score
```

### Sortie
CSV avec DPE:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department,latitude,longitude,address_normalized,geocoding_score,dpe_number,dpe_date,dpe_energy_class,dpe_ges_class,construction_year,dpe_match_level,dpe_match_score
```

### Implémentation

```python
import os
import re
import unicodedata
import pandas as pd
import requests
import time
import difflib
import Levenshtein
import jellyfish
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

from .processor_base import ProcessorBase

class DPEEnrichmentService(ProcessorBase):
    """Processeur pour enrichir les propriétés avec les données DPE."""
    
    # APIs ADEME
    EXISTING_BUILDINGS_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines"
    NEW_BUILDINGS_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-neufs/lines"
    
    # Configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # secondes
    SIMILARITY_THRESHOLD = 0.8  # seuil pour le matching d'adresses
    
    # Mapping des champs DPE
    DPE_FIELDS = {
        'N°DPE': 'dpe_number',
        'Date_réception_DPE': 'dpe_date',
        'Etiquette_DPE': 'dpe_energy_class',
        'Etiquette_GES': 'dpe_ges_class',
        'Année_construction': 'construction_year'
    }
    
    def __init__(self, input_path: str = "data/processing/geocoded.csv", 
                 output_path: str = "data/processing/dpe_enriched.csv",
                 dpe_cache_dir: str = "data/cache/dpe"):
        super().__init__(input_path, output_path)
        self.dpe_cache_dir = dpe_cache_dir
        
        # Créer le répertoire de cache si nécessaire
        os.makedirs(self.dpe_cache_dir, exist_ok=True)
    
    def process(self, **kwargs) -> bool:
        """
        Enrichit les propriétés avec des données DPE.
        
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        # Charger les données
        df = self.load_csv()
        if df is None:
            return False
        
        # Statistiques initiales
        initial_count = len(df)
        self.logger.info(f"Début de l'enrichissement DPE avec {initial_count} propriétés")
        
        try:
            # Préparer les colonnes DPE
            for field in self.DPE_FIELDS.values():
                df[field] = None
            
            # Ajouter des colonnes pour le score et le niveau de matching
            df['dpe_match_level'] = None
            df['dpe_match_score'] = None
            
            # Normaliser les adresses pour le matching
            df['address_matching'] = df['address_normalized'].apply(self.normalize_address_for_matching)
            
            # Regrouper par code INSEE
            insee_groups = df.groupby('insee_code')
            
            # Statistiques de matching
            total_matched = 0
            match_by_level = {1: 0, 2: 0, 3: 0, 4: 0}
            
            # Traiter chaque groupe INSEE
            for insee_code, group in tqdm(insee_groups, desc="Traitement des communes"):
                # Vérifier le cache des DPEs
                cache_file = os.path.join(self.dpe_cache_dir, f"dpe_{insee_code}.csv")
                
                if os.path.exists(cache_file):
                    # Charger depuis le cache
                    dpe_data = pd.read_csv(cache_file)
                    self.logger.info(f"Chargé {len(dpe_data)} DPEs depuis le cache pour INSEE {insee_code}")
                else:
                    # Récupérer les données DPE pour cette commune
                    dpe_data = self.fetch_dpe_data(insee_code)
                    
                    if dpe_data is not None and not dpe_data.empty:
                        # Sauvegarder dans le cache
                        dpe_data.to_csv(cache_file, index=False)
                
                if dpe_data is None or dpe_data.empty:
                    self.logger.warning(f"Aucun DPE trouvé pour INSEE {insee_code}")
                    continue
                
                # Préparer les données DPE pour le matching
                dpe_data['address_matching'] = dpe_data['Adresse_brute'].apply(self.normalize_address_for_matching)
                
                # Pour chaque propriété du groupe, chercher un DPE correspondant
                for idx, row in group.iterrows():
                    property_address = row['address_matching']
                    property_year = self.extract_year(row['sale_date'])
                    
                    # Utiliser différentes stratégies de matching
                    match_result = self.find_best_dpe_match(
                        property_address, 
                        property_year,
                        dpe_data,
                        row['latitude'],
                        row['longitude']
                    )
                    
                    if match_result:
                        dpe_match, match_level, match_score = match_result
                        
                        # Mettre à jour les données DPE
                        for api_field, df_field in self.DPE_FIELDS.items():
                            if api_field in dpe_match and not pd.isna(dpe_match[api_field]):
                                value = dpe_match[api_field]
                                # Conversion pour année de construction
                                if df_field == 'construction_year' and value:
                                    try:
                                        value = int(value)
                                    except (ValueError, TypeError):
                                        value = None
                                df.loc[idx, df_field] = value
                        
                        # Mettre à jour les informations de matching
                        df.loc[idx, 'dpe_match_level'] = match_level
                        df.loc[idx, 'dpe_match_score'] = match_score
                        
                        total_matched += 1
                        match_by_level[match_level] += 1
            
            # Supprimer la colonne temporaire
            df = df.drop(columns=['address_matching'])
            
            # Convertir construction_year en entier
            df['construction_year'] = pd.to_numeric(df['construction_year'], errors='coerce')
            
            # Statistiques finales
            match_percentage = (total_matched / initial_count) * 100 if initial_count > 0 else 0
            self.logger.info(f"Enrichissement DPE terminé: {total_matched}/{initial_count} propriétés enrichies ({match_percentage:.1f}%)")
            self.logger.info(f"Répartition par niveau: Exact: {match_by_level[1]}, Partiel: {match_by_level[2]}, Phonétique: {match_by_level[3]}, Géo: {match_by_level[4]}")
            
            # Sauvegarder le résultat
            return self.save_csv(df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enrichissement DPE: {str(e)}")
            return False
    
    def fetch_dpe_data(self, insee_code: str) -> Optional[pd.DataFrame]:
        """
        Récupère les données DPE pour un code INSEE.
        
        Args:
            insee_code: Code INSEE de la commune
            
        Returns:
            Optional[pd.DataFrame]: DataFrame avec les données DPE ou None si échec
        """
        # D'abord essayer les bâtiments existants
        existing_data = self.query_dpe_api(insee_code, self.EXISTING_BUILDINGS_API)
        
        # Ensuite les bâtiments neufs
        new_data = self.query_dpe_api(insee_code, self.NEW_BUILDINGS_API)
        
        if existing_data is None and new_data is None:
            return None
            
        # Combiner les résultats
        all_data = []
        if existing_data:
            all_data.extend(existing_data)
        if new_data:
            all_data.extend(new_data)
            
        self.logger.info(f"Récupéré {len(all_data)} DPEs pour INSEE {insee_code} (existants: {len(existing_data or [])}, neufs: {len(new_data or [])})")
        
        # Convertir en DataFrame
        if all_data:
            return pd.DataFrame(all_data)
        else:
            return None
    
    def query_dpe_api(self, insee_code: str, api_url: str, retry_count: int = 0) -> Optional[List[Dict[str, Any]]]:
        """
        Interroge l'API DPE pour récupérer les données d'une commune.
        
        Args:
            insee_code: Code INSEE de la commune
            api_url: URL de l'API à interroger
            retry_count: Nombre de tentatives déjà effectuées
            
        Returns:
            Optional[List[Dict[str, Any]]]: Liste des DPEs ou None si échec
        """
        if retry_count >= self.MAX_RETRIES:
            self.logger.warning(f"Nombre maximum de tentatives atteint pour INSEE {insee_code}")
            return None
        
        try:
            # Champs à récupérer
            select_fields = (
                "N°DPE,Date_réception_DPE,Etiquette_GES,Etiquette_DPE,Année_construction,"
                "Adresse_brute,Nom__commune_(BAN),Code_INSEE_(BAN),N°_voie_(BAN),"
                "Nom__rue_(BAN),Code_postal_(BAN),"
                "Coordonnée_cartographique_X_(BAN),Coordonnée_cartographique_Y_(BAN)"
            )
            
            params = {
                "size": 9999,
                "select": select_fields,
                "q": insee_code,
                "q_mode": "simple",
                "q_fields": "Code_INSEE_(BAN)"
            }
            
            self.logger.info(f"Interrogation de l'API pour INSEE {insee_code}")
            response = requests.get(api_url, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if "results" in data:
                    return data["results"]
                else:
                    self.logger.warning(f"Pas de résultats pour INSEE {insee_code}")
            else:
                self.logger.warning(f"Erreur API ({response.status_code}) pour INSEE {insee_code}")
            
            # Attendre avant de réessayer
            time.sleep(self.RETRY_DELAY * (retry_count + 1))
            return self.query_dpe_api(insee_code, api_url, retry_count + 1)
            
        except Exception as e:
            self.logger.warning(f"Erreur lors de l'interrogation de l'API DPE: {str(e)}")
            time.sleep(self.RETRY_DELAY * (retry_count + 1))
            return self.query_dpe_api(insee_code, api_url, retry_count + 1)
    
    def normalize_address_for_matching(self, address: str) -> str:
        """
        Normalise une adresse pour le matching DPE.
        
        Args:
            address: Adresse à normaliser
            
        Returns:
            str: Adresse normalisée
        """
        if not isinstance(address, str) or not address:
            return ""
        
        # Convertir en majuscules
        address = address.upper()
        
        # Supprimer les accents
        address = unicodedata.normalize('NFKD', address).encode('ASCII', 'ignore').decode('utf-8')
        
        # Supprimer la ponctuation
        address = re.sub(r'[^\w\s]', ' ', address)
        
        # Normaliser les mots couramment utilisés dans les adresses
        address = address.replace("AVENUE", "AV")
        address = address.replace("BOULEVARD", "BD")
        address = address.replace("PLACE", "PL")
        address = address.replace("ALLEE", "AL")
        address = address.replace("IMPASSE", "IMP")
        
        # Supprimer les mots non significatifs
        non_significant = ["RUE", "DE", "DES", "LA", "LE", "LES", "DU"]
        words = address.split()
        words = [word for word in words if word not in non_significant]
        
        # Recombiner
        address = " ".join(words)
        
        # Supprimer les espaces multiples
        address = re.sub(r'\s+', ' ', address).strip()
        
        return address
    
    def extract_year(self, date_str: str) -> Optional[int]:
        """
        Extrait l'année d'une date.
        
        Args:
            date_str: Date au format YYYY-MM-DD
            
        Returns:
            Optional[int]: Année ou None si invalide
        """
        if not isinstance(date_str, str):
            return None
            
        try:
            return int(date_str.split('-')[0])
        except (ValueError, IndexError):
            return None
    
    def find_best_dpe_match(self, property_address: str, property_year: Optional[int], 
                           dpe_data: pd.DataFrame, latitude: float, longitude: float) -> Optional[Tuple[Dict[str, Any], int, float]]:
        """
        Trouve le meilleur DPE correspondant à une adresse.
        
        Args:
            property_address: Adresse normalisée de la propriété
            property_year: Année de vente de la propriété
            dpe_data: DataFrame des DPEs
            latitude: Latitude de la propriété
            longitude: Longitude de la propriété
            
        Returns:
            Optional[Tuple[Dict[str, Any], int, float]]: 
                (DPE, niveau de matching, score de confiance) ou None si pas de correspondance
        """
        if property_address == "" or dpe_data.empty:
            return None
        
        best_match = None
        best_level = 0
        best_score = 0
        
        # Niveau 1: Recherche exacte
        exact_matches = dpe_data[dpe_data['address_matching'] == property_address]
        if not exact_matches.empty:
            # Trier par date de DPE (le plus récent d'abord)
            sorted_matches = exact_matches.sort_values('Date_réception_DPE', ascending=False)
            best_match = sorted_matches.iloc[0].to_dict()
            best_level = 1
            best_score = 1.0
            return (best_match, best_level, best_score)
        
        # Extraire le numéro et la rue
        match = re.match(r'^(\d+)\s+(.+)$', property_address)
        if match:
            num, street = match.groups()
            
            # Niveau 2: Recherche par numéro + rue
            num_street_matches = dpe_data[
                (dpe_data['address_matching'].str.startswith(num)) & 
                (dpe_data['address_matching'].str.contains(street))
            ]
            
            if not num_street_matches.empty:
                for _, dpe_row in num_street_matches.iterrows():
                    dpe_address = dpe_row['address_matching']
                    similarity = difflib.SequenceMatcher(None, property_address, dpe_address).ratio()
                    if similarity > best_score:
                        best_match = dpe_row.to_dict()
                        best_level = 2
                        best_score = similarity
            
            # Niveau 3: Recherche phonétique
            if best_score < self.SIMILARITY_THRESHOLD:
                for _, dpe_row in dpe_data.iterrows():
                    dpe_address = dpe_row['address_matching']
                    
                    # Comparer phonétiquement (Soundex) pour les noms de rue
                    dpe_match = re.match(r'^(\d+)\s+(.+)$', dpe_address)
                    if dpe_match:
                        dpe_num, dpe_street = dpe_match.groups()
                        
                        if num == dpe_num:
                            # Comparer les noms de rue phonétiquement
                            street_soundex = jellyfish.soundex(street)
                            dpe_street_soundex = jellyfish.soundex(dpe_street)
                            
                            if street_soundex == dpe_street_soundex:
                                # Calculer la distance de Levenshtein pour départager
                                lev_distance = Levenshtein.distance(street, dpe_street)
                                similarity = 1.0 - (lev_distance / max(len(street), len(dpe_street)))
                                
                                if similarity > best_score:
                                    best_match = dpe_row.to_dict()
                                    best_level = 3
                                    best_score = similarity
        
        # Niveau 4: Recherche par proximité géographique
        if best_score < self.SIMILARITY_THRESHOLD and pd.notna(latitude) and pd.notna(longitude):
            # Extraire et convertir les coordonnées DPE
            dpe_data['x'] = pd.to_numeric(dpe_data['Coordonnée_cartographique_X_(BAN)'], errors='coerce')
            dpe_data['y'] = pd.to_numeric(dpe_data['Coordonnée_cartographique_Y_(BAN)'], errors='coerce')
            
            # Filtrer les DPEs avec coordonnées valides
            geo_dpe = dpe_data.dropna(subset=['x', 'y'])
            
            if not geo_dpe.empty:
                # Calculer les distances (approximation simplifiée)
                geo_dpe['distance'] = ((geo_dpe['x'] - longitude) ** 2 + (geo_dpe['y'] - latitude) ** 2) ** 0.5
                
                # Sélectionner le plus proche
                nearest = geo_dpe.nsmallest(1, 'distance')
                
                # Si la distance est raisonnable (< 50m)
                if nearest['distance'].iloc[0] < 0.001:  # approximativement 50-100m
                    spatial_score = 1.0 - (nearest['distance'].iloc[0] / 0.001)
                    
                    if spatial_score > best_score:
                        best_match = nearest.iloc[0].to_dict()
                        best_level = 4
                        best_score = spatial_score
        
        if best_score >= self.SIMILARITY_THRESHOLD:
            return (best_match, best_level, best_score)
        else:
            return None
```

## 5. Estimation des prix (05_price_estimator.py)

Ce processeur est responsable de l'estimation des prix actuels des propriétés.

### Entrée
CSV avec DPE:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department,latitude,longitude,address_normalized,geocoding_score,dpe_number,dpe_date,dpe_energy_class,dpe_ges_class,construction_year,dpe_match_level,dpe_match_score
```

### Sortie
CSV avec prix estimés:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department,latitude,longitude,address_normalized,geocoding_score,dpe_number,dpe_date,dpe_energy_class,dpe_ges_class,construction_year,dpe_match_level,dpe_match_score,estimated_price,price_evolution_rate,estimation_confidence
```

### Implémentation

```python
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import create_engine, text

from .processor_base import ProcessorBase

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
    
    def __init__(self, input_path: str = "data/processing/dpe_enriched.csv", 
                 output_path: str = "data/processing/price_estimated.csv",
                 db_url: str = "postgresql://user:password@localhost/trackimmo"):
        super().__init__(input_path, output_path)
        self.db_url = db_url
        self.db_engine = None
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
        
        # Initialiser le moteur de base de données
        try:
            self.db_engine = create_engine(self.db_url)
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
            city_growth_rates = self.get_city_growth_rates(df['city_id'].unique().tolist())
            
            # Convertir sale_date en datetime
            df['sale_date_dt'] = pd.to_datetime(df['sale_date'])
            
            # Calculer l'âge de la vente en années
            df['sale_age_years'] = (self.current_date - df['sale_date_dt'].dt.date).dt.days / 365.25
            
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
            return False
    
    def get_city_growth_rates(self, city_ids: List[str]) -> Dict[str, float]:
        """
        Récupère les taux d'évolution annuels par ville et type de bien.
        
        Args:
            city_ids: Liste des IDs de villes
            
        Returns:
            Dict[str, float]: Dictionnaire {city_id_property_type: taux_annuel}
        """
        if not city_ids:
            return {}
            
        result = {}
        
        try:
            # Requête SQL pour obtenir l'évolution des prix
            query = text("""
                WITH yearly_averages AS (
                    SELECT 
                        city_id,
                        property_type,
                        EXTRACT(YEAR FROM sale_date::date) AS year,
                        AVG(price / NULLIF(surface, 0)) AS avg_price_per_m2
                    FROM 
                        addresses
                    WHERE 
                        city_id IN :city_ids
                        AND surface > 0
                    GROUP BY 
                        city_id, property_type, year
                    ORDER BY 
                        city_id, property_type, year
                ),
                
                growth_rates AS (
                    SELECT 
                        a.city_id,
                        a.property_type,
                        a.year,
                        a.avg_price_per_m2,
                        b.avg_price_per_m2 AS next_year_avg,
                        (b.avg_price_per_m2 / a.avg_price_per_m2) - 1 AS annual_growth
                    FROM 
                        yearly_averages a
                    JOIN 
                        yearly_averages b 
                    ON 
                        a.city_id = b.city_id
                        AND a.property_type = b.property_type
                        AND b.year = a.year + 1
                    WHERE 
                        a.avg_price_per_m2 > 0
                        AND b.avg_price_per_m2 > 0
                )
                
                SELECT 
                    city_id,
                    property_type,
                    AVG(annual_growth) AS avg_annual_growth
                FROM 
                    growth_rates
                GROUP BY 
                    city_id, property_type
            """)
            
            with self.db_engine.connect() as conn:
                result_proxy = conn.execute(query, {"city_ids": tuple(city_ids)})
                
                for row in result_proxy:
                    city_id = row[0]
                    property_type = row[1]
                    growth_rate = row[2]
                    
                    # Vérifier que le taux est valide et le plafonner
                    if growth_rate is not None:
                        growth_rate = min(max(growth_rate, self.MIN_ANNUAL_GROWTH), self.MAX_ANNUAL_GROWTH)
                        result[f"{city_id}_{property_type}"] = growth_rate
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des taux d'évolution: {str(e)}")
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
        elif geocoding_score < 0.6:
            score -= 0.05
        
        # Bonus surface/pièces
        if property_data.get('surface', 0) > 0 and property_data.get('rooms', 0) > 0:
            score += 0.05
        
        # Assurer que le score est entre 0 et 1
        return max(min(score, 1.0), 0.0)
```

## 6. Intégration à la base de données (06_db_integrator.py)

Ce processeur est responsable de l'intégration des propriétés enrichies dans la base de données.

### Entrée
CSV avec prix estimés:
```
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url,city_id,postal_code,insee_code,department,latitude,longitude,address_normalized,geocoding_score,dpe_number,dpe_date,dpe_energy_class,dpe_ges_class,construction_year,dpe_match_level,dpe_match_score,estimated_price,price_evolution_rate,estimation_confidence
```

### Sortie
Rapport d'intégration:
```
address_id,address_raw,city_id,success,error
```

### Implémentation

```python
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import UUID, insert
import uuid

from .processor_base import ProcessorBase

class DBIntegrationService(ProcessorBase):
    """Processeur pour intégrer les propriétés enrichies dans la base de données."""
    
    def __init__(self, input_path: str = "data/processing/price_estimated.csv", 
                 output_path: str = "data/processing/integration_report.csv",
                 db_url: str = "postgresql://user:password@localhost/trackimmo"):
        super().__init__(input_path, output_path)
        self.db_url = db_url
        self.db_engine = None
    
    def process(self, **kwargs) -> bool:
        """
        Intègre les propriétés enrichies dans la base de données.
        
        Args:
            **kwargs: Arguments additionnels
                - batch_size: Taille des lots pour l'insertion (défaut: 100)
                
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        # Récupérer les paramètres
        batch_size = kwargs.get('batch_size', 100)
        
        # Charger les données
        df = self.load_csv()
        if df is None:
            return False
        
        # Initialiser le moteur de base de données
        try:
            self.db_engine = create_engine(self.db_url)
            self.logger.info("Connexion à la base de données établie")
        except Exception as e:
            self.logger.error(f"Erreur de connexion à la base de données: {str(e)}")
            return False
        
        # Statistiques initiales
        initial_count = len(df)
        self.logger.info(f"Début de l'intégration de {initial_count} propriétés")
        
        try:
            # Créer un DataFrame pour le rapport d'intégration
            report_df = pd.DataFrame(columns=['address_id', 'address_raw', 'city_id', 'success', 'error'])
            
            # Traiter par lots
            batches = [df[i:i+batch_size] for i in range(0, len(df), batch_size)]
            
            for i, batch_df in enumerate(batches):
                self.logger.info(f"Traitement du lot {i+1}/{len(batches)} ({len(batch_df)} propriétés)")
                
                # Insérer les propriétés
                batch_report = self.insert_properties_batch(batch_df)
                
                # Ajouter au rapport
                report_df = pd.concat([report_df, pd.DataFrame(batch_report)])
            
            # Statistiques finales
            success_count = report_df['success'].sum()
            success_rate = (success_count / initial_count) * 100 if initial_count > 0 else 0
            
            self.logger.info(f"Intégration terminée: {success_count}/{initial_count} propriétés intégrées ({success_rate:.1f}%)")
            
            # Sauvegarder le rapport
            return self.save_csv(report_df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'intégration: {str(e)}")
            return False
    
    def insert_properties_batch(self, batch_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Insère un lot de propriétés dans la base de données.
        
        Args:
            batch_df: DataFrame des propriétés à insérer
            
        Returns:
            List[Dict[str, Any]]: Rapport d'intégration pour chaque propriété
        """
        batch_report = []
        
        with self.db_engine.connect() as conn:
            # Début de la transaction
            transaction = conn.begin()
            
            try:
                for _, row in batch_df.iterrows():
                    report_entry = {
                        'address_raw': row['address_raw'],
                        'city_id': row['city_id'],
                        'success': False,
                        'error': None
                    }
                    
                    try:
                        # Insérer dans la table addresses
                        address_id = self.insert_address(conn, row)
                        report_entry['address_id'] = address_id
                        
                        # Si DPE présent, insérer dans la table dpe
                        if pd.notna(row['dpe_number']):
                            self.insert_dpe(conn, row, address_id)
                        
                        report_entry['success'] = True
                        
                    except Exception as e:
                        report_entry['error'] = str(e)
                    
                    batch_report.append(report_entry)
                
                # Valider la transaction
                transaction.commit()
                
            except Exception as e:
                # Annuler la transaction en cas d'erreur
                transaction.rollback()
                self.logger.error(f"Erreur lors de l'insertion par lot: {str(e)}")
                
                # Marquer toutes les entrées restantes comme échouées
                for entry in batch_report:
                    if not entry['success']:
                        entry['error'] = f"Échec de la transaction: {str(e)}"
        
        return batch_report
    
    def insert_address(self, conn, property_data: pd.Series) -> str:
        """
        Insère une propriété dans la table addresses.
        
        Args:
            conn: Connexion à la base de données
            property_data: Données de la propriété
            
        Returns:
            str: ID de l'adresse insérée
        """
        # Générer un UUID
        address_id = str(uuid.uuid4())
        
        # Convertir les coordonnées en point PostGIS
        geoposition = f"POINT({property_data['longitude']} {property_data['latitude']})"
        
        # Préparer l'insertion
        query = text("""
            INSERT INTO addresses (
                address_id, department, city_id, address_raw, sale_date, property_type,
                surface, rooms, price, source_url, estimated_price, geoposition,
                created_at, updated_at
            )
            VALUES (
                :address_id, :department, :city_id, :address_raw, :sale_date::date, :property_type,
                :surface, :rooms, :price, :source_url, :estimated_price, ST_GeomFromText(:geoposition),
                NOW(), NOW()
            )
            ON CONFLICT (address_id) DO UPDATE
            SET
                department = EXCLUDED.department,
                city_id = EXCLUDED.city_id,
                address_raw = EXCLUDED.address_raw,
                sale_date = EXCLUDED.sale_date,
                property_type = EXCLUDED.property_type,
                surface = EXCLUDED.surface,
                rooms = EXCLUDED.rooms,
                price = EXCLUDED.price,
                source_url = EXCLUDED.source_url,
                estimated_price = EXCLUDED.estimated_price,
                geoposition = EXCLUDED.geoposition,
                updated_at = NOW()
            RETURNING address_id
        """)
        
        # Exécuter la requête
        result = conn.execute(query, {
            'address_id': address_id,
            'department': property_data['department'],
            'city_id': property_data['city_id'],
            'address_raw': property_data['address_raw'],
            'sale_date': property_data['sale_date'],
            'property_type': property_data['property_type'],
            'surface': property_data['surface'],
            'rooms': property_data['rooms'],
            'price': property_data['price'],
            'source_url': property_data['source_url'],
            'estimated_price': property_data['estimated_price'],
            'geoposition': geoposition
        })
        
        return result.scalar()
    
    def insert_dpe(self, conn, property_data: pd.Series, address_id: str) -> None:
        """
        Insère un DPE dans la table dpe.
        
        Args:
            conn: Connexion à la base de données
            property_data: Données de la propriété
            address_id: ID de l'adresse associée
        """
        # Générer un UUID
        dpe_id = str(uuid.uuid4())
        
        # Préparer l'insertion
        query = text("""
            INSERT INTO dpe (
                dpe_id, address_id, department, construction_year, dpe_date,
                dpe_energy_class, dpe_ges_class, dpe_number, created_at, updated_at
            )
            VALUES (
                :dpe_id, :address_id, :department, :construction_year, :dpe_date::date,
                :dpe_energy_class, :dpe_ges_class, :dpe_number, NOW(), NOW()
            )
            ON CONFLICT (dpe_id) DO UPDATE
            SET
                construction_year = EXCLUDED.construction_year,
                dpe_date = EXCLUDED.dpe_date,
                dpe_energy_class = EXCLUDED.dpe_energy_class,
                dpe_ges_class = EXCLUDED.dpe_ges_class,
                dpe_number = EXCLUDED.dpe_number,
                updated_at = NOW()
        """)
        
        # Convertir la date DPE
        dpe_date = property_data['dpe_date']
        if pd.notna(dpe_date):
            try:
                dpe_date = pd.to_datetime(dpe_date).strftime('%Y-%m-%d')
            except:
                dpe_date = None
        
        # Exécuter la requête
        conn.execute(query, {
            'dpe_id': dpe_id,
            'address_id': address_id,
            'department': property_data['department'],
            'construction_year': property_data['construction_year'],
            'dpe_date': dpe_date,
            'dpe_energy_class': property_data['dpe_energy_class'],
            'dpe_ges_class': property_data['dpe_ges_class'],
            'dpe_number': property_data['dpe_number']
        })
```

## 7. Orchestration (enrichment_orchestrator.py)

Ce module coordonne l'exécution de toutes les étapes du processus d'enrichissement.

### Implémentation

```python
import os
import logging
import argparse
from typing import Dict, Any, Optional, List

# Importer les processeurs
from .processor_base import ProcessorBase
from .01_data_normalizer import DataNormalizer
from .02_city_resolver import CityResolver
from .03_geocoding_service import GeocodingService
from .04_dpe_enrichment import DPEEnrichmentService
from .05_price_estimator import PriceEstimationService
from .06_db_integrator import DBIntegrationService

class EnrichmentOrchestrator:
    """Orchestrateur du processus complet d'enrichissement des données immobilières."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialise l'orchestrateur avec une configuration.
        
        Args:
            config: Configuration pour les processeurs
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Configurer les répertoires
        self.data_dir = self.config.get('data_dir', 'data')
        self.raw_dir = os.path.join(self.data_dir, 'raw')
        self.processing_dir = os.path.join(self.data_dir, 'processing')
        self.output_dir = os.path.join(self.data_dir, 'output')
        
        # Créer les répertoires si nécessaires
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.processing_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Configurer les chemins des fichiers intermédiaires
        self.file_paths = {
            'raw': os.path.join(self.raw_dir, 'properties.csv'),
            'normalized': os.path.join(self.processing_dir, 'normalized.csv'),
            'cities_resolved': os.path.join(self.processing_dir, 'cities_resolved.csv'),
            'geocoded': os.path.join(self.processing_dir, 'geocoded.csv'),
            'dpe_enriched': os.path.join(self.processing_dir, 'dpe_enriched.csv'),
            'price_estimated': os.path.join(self.processing_dir, 'price_estimated.csv'),
            'integration_report': os.path.join(self.output_dir, 'integration_report.csv')
        }
        
        # Charger la configuration de la base de données
        self.db_url = self.config.get('db_url', 'postgresql://user:password@localhost/trackimmo')
    
    def run(self, input_file: str = None, start_stage: int = 1, end_stage: int = 6, debug: bool = False) -> bool:
        """
        Exécute le processus complet d'enrichissement.
        
        Args:
            input_file: Chemin du fichier d'entrée (CSV brut)
            start_stage: Étape de départ (1-6)
            end_stage: Étape finale (1-6)
            debug: Si True, sauvegarde les fichiers intermédiaires
            
        Returns:
            bool: True si l'exécution a réussi, False sinon
        """
        # Valider les étapes
        if start_stage < 1 or start_stage > 6:
            self.logger.error(f"Étape de départ invalide: {start_stage}")
            return False
            
        if end_stage < start_stage or end_stage > 6:
            self.logger.error(f"Étape finale invalide: {end_stage}")
            return False
        
        # Si un fichier d'entrée est spécifié, le copier dans le répertoire raw
        if input_file:
            self.file_paths['raw'] = input_file
        
        # Créer les processeurs
        normalizer = DataNormalizer(
            input_path=self.file_paths['raw'],
            output_path=self.file_paths['normalized']
        )
        
        city_resolver = CityResolver(
            input_path=self.file_paths['normalized'],
            output_path=self.file_paths['cities_resolved'],
            db_url=self.db_url
        )
        
        geocoding_service = GeocodingService(
            input_path=self.file_paths['cities_resolved'],
            output_path=self.file_paths['geocoded'],
            original_bbox=self.config.get('original_bbox')
        )
        
        dpe_enrichment = DPEEnrichmentService(
            input_path=self.file_paths['geocoded'],
            output_path=self.file_paths['dpe_enriched'],
            dpe_cache_dir=os.path.join(self.data_dir, 'cache', 'dpe')
        )
        
        price_estimator = PriceEstimationService(
            input_path=self.file_paths['dpe_enriched'],
            output_path=self.file_paths['price_estimated'],
            db_url=self.db_url
        )
        
        db_integrator = DBIntegrationService(
            input_path=self.file_paths['price_estimated'],
            output_path=self.file_paths['integration_report'],
            db_url=self.db_url
        )
        
        # Exécuter les étapes selon la configuration
        stage_processors = [
            (1, "Normalisation des données", normalizer),
            (2, "Résolution des villes", city_resolver),
            (3, "Géocodage des adresses", geocoding_service),
            (4, "Enrichissement DPE", dpe_enrichment),
            (5, "Estimation des prix", price_estimator),
            (6, "Intégration en base de données", db_integrator)
        ]
        
        success = True
        
        for stage, name, processor in stage_processors:
            if start_stage <= stage <= end_stage:
                self.logger.info(f"Exécution de l'étape {stage}: {name}")
                
                stage_success = processor.process()
                
                if stage_success:
                    self.logger.info(f"Étape {stage} terminée avec succès")
                else:
                    self.logger.error(f"Échec de l'étape {stage}")
                    success = False
                    break
        
        if success:
            self.logger.info("Processus d'enrichissement terminé avec succès")
        else:
            self.logger.error("Processus d'enrichissement terminé avec des erreurs")
        
        # Nettoyer les fichiers intermédiaires si mode debug désactivé
        if not debug and success:
            self.cleanup_intermediate_files(start_stage, end_stage)
        
        return success
    
    def cleanup_intermediate_files(self, start_stage: int, end_stage: int) -> None:
        """
        Supprime les fichiers intermédiaires.
        
        Args:
            start_stage: Étape de départ
            end_stage: Étape finale
        """
        stages_files = {
            1: ['normalized'],
            2: ['cities_resolved'],
            3: ['geocoded'],
            4: ['dpe_enriched'],
            5: ['price_estimated']
        }
        
        for stage in range(start_stage, end_stage):
            if stage in stages_files:
                for file_key in stages_files[stage]:
                    file_path = self.file_paths[file_key]
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            self.logger.info(f"Suppression du fichier intermédiaire: {file_path}")
                        except Exception as e:
                            self.logger.warning(f"Impossible de supprimer {file_path}: {str(e)}")


def main():
    """Point d'entrée en ligne de commande pour l'orchestrateur."""
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Analyser les arguments de ligne de commande
    parser = argparse.ArgumentParser(description="Enrichissement des données immobilières")
    parser.add_argument("--input", help="Fichier CSV d'entrée", required=True)
    parser.add_argument("--start", type=int, default=1, help="Étape de départ (1-6)")
    parser.add_argument("--end", type=int, default=6, help="Étape finale (1-6)")
    parser.add_argument("--debug", action="store_true", help="Mode debug (conserver les fichiers intermédiaires)")
    parser.add_argument("--db", help="URL de connexion à la base de données")
    
    args = parser.parse_args()
    
    # Configurer l'orchestrateur
    config = {
        'data_dir': 'data',
        'db_url': args.db if args.db else 'postgresql://user:password@localhost/trackimmo'
    }
    
    orchestrator = EnrichmentOrchestrator(config)
    
    # Exécuter le processus
    success = orchestrator.run(
        input_file=args.input,
        start_stage=args.start,
        end_stage=args.end,
        debug=args.debug
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
```

## Flux de données complet

Le flux de données à travers tout le processus d'enrichissement est le suivant:

1. **CSV brut** → Normalisation → **CSV normalisé**
2. **CSV normalisé** → Résolution des villes → **CSV avec villes résolues**
3. **CSV avec villes résolues** → Géocodage → **CSV avec coordonnées**
4. **CSV avec coordonnées** → Enrichissement DPE → **CSV avec DPE**
5. **CSV avec DPE** → Estimation des prix → **CSV avec prix estimés**
6. **CSV avec prix estimés** → Intégration DB → **Entrées en base de données** + **Rapport d'intégration**

## Utilisation depuis la ligne de commande

```bash
python -m trackimmo.modules.enrichment.enrichment_orchestrator --input data/raw/properties.csv --debug
```

Options:
- `--input`: Fichier CSV d'entrée (obligatoire)
- `--start`: Étape de départ (1-6, défaut: 1)
- `--end`: Étape finale (1-6, défaut: 6)
- `--debug`: Mode debug (conserver les fichiers intermédiaires)
- `--db`: URL de connexion à la base de données

## Dépendances

Pour exécuter ce module, vous aurez besoin des packages Python suivants:

```
pandas
numpy
sqlalchemy
psycopg2-binary
requests
jellyfish
python-Levenshtein
tqdm
```

Installez-les avec pip:

```bash
pip install pandas numpy sqlalchemy psycopg2-binary requests jellyfish python-Levenshtein tqdm
```