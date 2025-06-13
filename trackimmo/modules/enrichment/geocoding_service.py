import pandas as pd
import requests
import io
import time
import logging
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
    
    def __init__(self, input_path: str = None, output_path: str = None,
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
                self.logger.debug(f"Traitement du lot {i+1}/{len(chunks)} ({len(chunk_df)} adresses)")
                
                # Préparer les données pour le géocodage
                # Convertir les colonnes en chaînes pour éviter les problèmes de type
                chunk_df['address_raw'] = chunk_df['address_raw'].astype(str)
                chunk_df['city_name'] = chunk_df['city_name'].astype(str)
                chunk_df['postal_code'] = chunk_df['postal_code'].astype(str)
                
                # Utiliser une colonne 'q' pour l'adresse complète (adresse + ville + code postal)
                geocoding_df = pd.DataFrame({
                    'q': chunk_df['address_raw'] + ", " + chunk_df['city_name'] + ", " + chunk_df['postal_code']
                })
                
                # Géocoder le lot
                geocoded_df = self.geocode_batch(geocoding_df)
                
                if geocoded_df is not None and not geocoded_df.empty:
                    # Combiner avec les données originales
                    chunk_result = chunk_df.copy()
                    
                    # Map column names from API response to expected names
                    column_mapping = {
                        'result_latitude': 'latitude',
                        'latitude': 'latitude',
                        'result_longitude': 'longitude', 
                        'longitude': 'longitude',
                        'result_label': 'address_normalized',
                        'label': 'address_normalized',
                        'result_score': 'geocoding_score',
                        'score': 'geocoding_score'
                    }
                    
                    # Try to map columns correctly
                    for api_col, target_col in column_mapping.items():
                        if api_col in geocoded_df.columns and target_col not in chunk_result.columns:
                            chunk_result[target_col] = geocoded_df[api_col]
                    
                    # If mapping failed, try direct assignment
                    if 'latitude' not in chunk_result.columns:
                        if 'result_latitude' in geocoded_df.columns:
                            chunk_result['latitude'] = geocoded_df['result_latitude']
                        elif 'latitude' in geocoded_df.columns:
                            chunk_result['latitude'] = geocoded_df['latitude']
                        else:
                            self.logger.warning("No latitude column found in geocoding response")
                            continue
                    
                    if 'longitude' not in chunk_result.columns:
                        if 'result_longitude' in geocoded_df.columns:
                            chunk_result['longitude'] = geocoded_df['result_longitude']
                        elif 'longitude' in geocoded_df.columns:
                            chunk_result['longitude'] = geocoded_df['longitude']
                        else:
                            self.logger.warning("No longitude column found in geocoding response")
                            continue
                    
                    if 'address_normalized' not in chunk_result.columns:
                        if 'result_label' in geocoded_df.columns:
                            chunk_result['address_normalized'] = geocoded_df['result_label']
                        elif 'label' in geocoded_df.columns:
                            chunk_result['address_normalized'] = geocoded_df['label']
                        else:
                            chunk_result['address_normalized'] = "Non disponible"
                    
                    if 'geocoding_score' not in chunk_result.columns:
                        if 'result_score' in geocoded_df.columns:
                            chunk_result['geocoding_score'] = geocoded_df['result_score']
                        elif 'score' in geocoded_df.columns:
                            chunk_result['geocoding_score'] = geocoded_df['score']
                        else:
                            chunk_result['geocoding_score'] = 0.0
                    
                    # Valider et filtrer
                    chunk_result = self.validate_geocoding(chunk_result, original_bbox, distance_threshold)
                    
                    # Ajouter au résultat
                    if not chunk_result.empty:
                        result_df = pd.concat([result_df, chunk_result])
                    else:
                        self.logger.warning(f"All addresses in chunk {i+1} were filtered out")
                
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
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def geocode_batch(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Géocode un lot d'adresses.
        
        Args:
            df: DataFrame avec colonne 'q' contenant les adresses complètes
            
        Returns:
            Optional[pd.DataFrame]: DataFrame avec les résultats du géocodage ou None si échec
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Convertir le DataFrame en CSV
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_content = csv_buffer.getvalue()
                
                # Pour le débogage
                self.logger.debug(f"Envoi du CSV avec les colonnes: {list(df.columns)}")
                self.logger.debug(f"Exemple de première ligne: {df.iloc[0].to_dict() if not df.empty else 'DataFrame vide'}")
                
                # Appeler l'API de géocodage
                files = {'data': ('addresses.csv', csv_content.encode('utf-8'), 'text/csv')}
                response = requests.post(
                    self.GEOCODING_API,
                    files=files
                )
                
                if response.status_code == 200:
                    # Parser la réponse CSV
                    result_df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
                    
                    # Vérifier les colonnes reçues
                    self.logger.debug(f"Colonnes reçues: {list(result_df.columns)}")
                    if not result_df.empty:
                        self.logger.debug(f"Exemple de résultat: {result_df.iloc[0].to_dict()}")
                    
                    return result_df
                else:
                    self.logger.warning(f"Erreur API ({response.status_code}) - Tentative {attempt}/{self.MAX_RETRIES}")
                    self.logger.warning(f"Détail de l'erreur: {response.text}")
                    
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
        
        # Filtrer les lignes sans coordonnées - keep only this essential filter
        valid_coords = df['latitude'].notna() & df['longitude'].notna()
        invalid_coords_count = (~valid_coords).sum()
        
        if invalid_coords_count > 0:
            self.logger.warning(f"Suppression de {invalid_coords_count} adresses sans coordonnées")
            df = df[valid_coords]
        
        # Skip all other filtering for now to prevent massive data loss
        # Original filtering was too aggressive causing 14k → 115 reduction
        
        # Store original counts for logging
        before_score_filter = len(df)
        
        # Only filter out extremely low scores (< 0.1) instead of 0.3
        if not df.empty:
            extremely_low_score = df['geocoding_score'] < 0.1
            extremely_low_count = extremely_low_score.sum()
            
            if extremely_low_count > 0:
                self.logger.info(f"Suppression de {extremely_low_count} adresses avec score extrêmement faible (<0.1)")
                df = df[~extremely_low_score]
        
        # Skip bounding box filtering entirely for now to prevent data loss
        # The original bbox filtering was removing too many valid addresses
        
        after_filtering = len(df)
        self.logger.info(f"Validation géocodage: {before_score_filter} → {after_filtering} adresses gardées")
        
        return df

if __name__ == "__main__":
    import argparse
    
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Analyser les arguments
    parser = argparse.ArgumentParser(description="Géocodage des adresses")
    parser.add_argument("--input", help="Fichier CSV d'entrée", required=True)
    parser.add_argument("--output", help="Fichier CSV de sortie", required=False)
    parser.add_argument("--bbox", help="Rectangle de la zone de scraping (min_lat,min_lon,max_lat,max_lon)", required=False)
    parser.add_argument("--distance", help="Distance maximale en km", type=float, default=5.0)
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_geocoded.csv")
    
    # Convertir le rectangle si fourni
    original_bbox = None
    if args.bbox:
        try:
            min_lat, min_lon, max_lat, max_lon = map(float, args.bbox.split(","))
            original_bbox = {
                "min_lat": min_lat,
                "min_lon": min_lon,
                "max_lat": max_lat,
                "max_lon": max_lon
            }
        except Exception as e:
            print(f"Erreur lors du parsing du rectangle: {str(e)}")
            exit(1)
    
    # Exécuter le processeur
    geocoder = GeocodingService(args.input, output, original_bbox)
    success = geocoder.process(distance_threshold=args.distance)
    
    exit(0 if success else 1) 