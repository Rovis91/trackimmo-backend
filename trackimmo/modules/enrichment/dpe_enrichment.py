import os
import re
import unicodedata
import pandas as pd
import requests
import time
import logging
import difflib
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime

from .processor_base import ProcessorBase

class DPEEnrichmentService(ProcessorBase):
    """Processeur pour enrichir les propriétés avec les données DPE."""
    
    # APIs ADEME
    EXISTING_BUILDINGS_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines"
    NEW_BUILDINGS_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-neufs/lines"
    
    # Configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # secondes
    SIMILARITY_THRESHOLD = 0.7  # seuil pour le matching d'adresses (réduit de 0.8 à 0.7)
    API_BATCH_SIZE = 5000  # taille des lots pour l'API
    DEBUG_SAMPLE_SIZE = 5  # nombre d'échantillons DPE à sauvegarder pour débogage
    
    # Mapping des champs DPE
    DPE_FIELDS = {
        'N°DPE': 'dpe_number',
        'Date_réception_DPE': 'dpe_date',
        'Etiquette_DPE': 'dpe_energy_class',
        'Etiquette_GES': 'dpe_ges_class',
        'Année_construction': 'construction_year'
    }
    
    def __init__(self, input_path: str = None, output_path: str = None,
                 dpe_cache_dir: str = "data/cache/dpe"):
        super().__init__(input_path, output_path)
        self.dpe_cache_dir = dpe_cache_dir
        self.debug_dir = os.path.join(self.dpe_cache_dir, "debug")
        
        # Créer les répertoires de cache et débogage si nécessaires
        os.makedirs(self.dpe_cache_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)
    
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
            for insee_code, group in insee_groups:
                if pd.isna(insee_code):
                    self.logger.warning(f"Groupe avec code INSEE manquant ignoré ({len(group)} propriétés)")
                    continue
                    
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
                
                # Sauvegarder quelques échantillons pour débogage
                self.save_sample_dpe(insee_code, dpe_data)
                
                # Préparer les données DPE pour le matching
                dpe_data['address_matching'] = dpe_data['Adresse_brute'].apply(self.normalize_address_for_matching)
                
                # Pour chaque propriété du groupe, chercher un DPE correspondant
                for idx, row in group.iterrows():
                    property_address = row['address_matching']
                    property_year = self.extract_year(row['sale_date'])
                    
                    # Afficher quelques échantillons pour débogage
                    if idx % 100 == 0:
                        self.logger.info(f"Propriété {idx}: Adresse: '{property_address}'")
                    
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
                        
                        # Afficher des informations sur les matches trouvés
                        if total_matched % 10 == 0 or total_matched < 10:
                            self.logger.info(f"Match trouvé: '{property_address}' -> '{dpe_match.get('Adresse_brute', '')}' (niveau {match_level}, score {match_score:.2f})")
            
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
        existing_data = self.query_dpe_api_with_pagination(insee_code, self.EXISTING_BUILDINGS_API)
        
        # Ensuite les bâtiments neufs
        new_data = self.query_dpe_api_with_pagination(insee_code, self.NEW_BUILDINGS_API)
        
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
    
    def query_dpe_api_with_pagination(self, insee_code: str, api_url: str) -> Optional[List[Dict[str, Any]]]:
        """
        Interroge l'API DPE avec pagination pour gérer les limites de 9999 résultats.
        
        Args:
            insee_code: Code INSEE de la commune
            api_url: URL de l'API à interroger
            
        Returns:
            Optional[List[Dict[str, Any]]]: Liste des DPEs ou None si échec
        """
        all_results = []
        page = 0
        has_more = True
        
        while has_more:
            # Calcul des offsets de pagination
            from_idx = page * self.API_BATCH_SIZE
            
            try:
                # Champs à récupérer
                select_fields = (
                    "N°DPE,Date_réception_DPE,Etiquette_GES,Etiquette_DPE,Année_construction,"
                    "Adresse_brute,Nom__commune_(BAN),Code_INSEE_(BAN),N°_voie_(BAN),"
                    "Nom__rue_(BAN),Code_postal_(BAN),"
                    "Coordonnée_cartographique_X_(BAN),Coordonnée_cartographique_Y_(BAN)"
                )
                
                params = {
                    "size": self.API_BATCH_SIZE,
                    "from": from_idx,
                    "select": select_fields,
                    "q": insee_code,
                    "q_mode": "simple",
                    "q_fields": "Code_INSEE_(BAN)"
                }
                
                self.logger.info(f"Interrogation de l'API pour INSEE {insee_code} (page {page+1}, from {from_idx})")
                response = requests.get(api_url, params=params, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "results" in data:
                        results = data["results"]
                        all_results.extend(results)
                        
                        # Vérifier s'il y a plus de données
                        has_more = len(results) == self.API_BATCH_SIZE
                    else:
                        has_more = False
                else:
                    self.logger.warning(f"Erreur API ({response.status_code}) pour INSEE {insee_code}")
                    has_more = False
                
                # Passer à la page suivante
                page += 1
                
                # Pause pour éviter de surcharger l'API
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"Erreur lors de l'interrogation de l'API DPE: {str(e)}")
                has_more = False
        
        return all_results
    
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
                # Pour simplifier, utilisons une approche basée sur la similitude difflib
                # au lieu de Soundex/phonétique (qui nécessiterait l'installation de jellyfish)
                for _, dpe_row in dpe_data.iterrows():
                    dpe_address = dpe_row['address_matching']
                    
                    # Comparer phonétiquement (simplifié par difflib)
                    dpe_match = re.match(r'^(\d+)\s+(.+)$', dpe_address)
                    if dpe_match:
                        dpe_num, dpe_street = dpe_match.groups()
                        
                        if num == dpe_num:
                            # Comparer les noms de rue
                            similarity = difflib.SequenceMatcher(None, street, dpe_street).ratio()
                            
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
    
    def save_sample_dpe(self, insee_code: str, dpe_data: pd.DataFrame):
        """
        Sauvegarde des échantillons de DPE pour débogage.
        
        Args:
            insee_code: Code INSEE
            dpe_data: DataFrame de DPEs
        """
        if dpe_data.empty or len(dpe_data) == 0:
            return
            
        try:
            # Sélectionner quelques échantillons
            sample_size = min(self.DEBUG_SAMPLE_SIZE, len(dpe_data))
            samples = dpe_data.sample(sample_size)
            
            # Créer un fichier JSON pour les échantillons
            samples_file = os.path.join(self.debug_dir, f"dpe_samples_{insee_code}.json")
            
            # Convertir et sauvegarder
            samples_dict = samples.to_dict(orient='records')
            
            with open(samples_file, 'w', encoding='utf-8') as f:
                json.dump(samples_dict, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Sauvegardé {sample_size} échantillons DPE dans {samples_file}")
            
            # Afficher les adresses des échantillons
            for i, sample in enumerate(samples_dict):
                self.logger.info(f"Échantillon DPE {i+1}: Adresse brute: '{sample.get('Adresse_brute', '')}', Match: '{sample.get('address_matching', '')}'")
                
        except Exception as e:
            self.logger.warning(f"Impossible de sauvegarder les échantillons DPE: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Analyser les arguments
    parser = argparse.ArgumentParser(description="Enrichissement des propriétés avec données DPE")
    parser.add_argument("--input", help="Fichier CSV d'entrée", required=True)
    parser.add_argument("--output", help="Fichier CSV de sortie", required=False)
    parser.add_argument("--cache", help="Répertoire de cache DPE", required=False)
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_dpe_enriched.csv")
    cache_dir = args.cache or "data/cache/dpe"
    
    # Exécuter le processeur
    enricher = DPEEnrichmentService(args.input, output, cache_dir)
    success = enricher.process()
    
    exit(0 if success else 1) 