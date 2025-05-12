import os
import re
import unicodedata
import pandas as pd
import requests
import time
import logging
import difflib
import json
import io
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import math

from .processor_base import ProcessorBase

class DPEEnrichmentService(ProcessorBase):
    """Processeur pour enrichir les propriétés avec les données DPE."""
    
    # APIs ADEME avec les champs de recherche corrects
    DPE_APIS = {
        # DPE Logements existants (depuis juillet 2021)
        "EXISTING_BUILDINGS_NEW": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines",
            "field": "code_insee_ban",
            "zipcode_field": "code_postal_ban",
            "city_field": "nom_commune_ban"
        },
        # DPE Logements neufs (depuis juillet 2021)
        "NEW_BUILDINGS_NEW": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe02neuf/lines",
            "field": "code_insee_ban",
            "zipcode_field": "code_postal_ban",
            "city_field": "nom_commune_ban"
        },
        # DPE Tertiaire (depuis juillet 2021)
        "TERTIARY_NEW": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe01tertiaire/lines",
            "field": "code_insee_ban",
            "zipcode_field": "code_postal_ban",
            "city_field": "nom_commune_ban"
        },
        # DPE Logements (avant juillet 2021)
        "EXISTING_BUILDINGS_OLD": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines",
            "field": "code_insee_commune_actualise",
            "zipcode_field": "code_postal",
            "city_field": "commune"
        },
        # DPE tertiaire (avant juillet 2021)
        "TERTIARY_OLD": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-tertiaire/lines",
            "field": "code_insee_commune",
            "zipcode_field": "code_postal",
            "city_field": "commune"
        }
    }
    
    # Configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # secondes
    SIMILARITY_THRESHOLD = 0.7  # seuil pour le matching d'adresses
    API_BATCH_SIZE = 200  # taille des lots pour l'API
    DEBUG_SAMPLE_SIZE = 5  # nombre d'échantillons DPE à sauvegarder pour débogage
    GEOCODING_API_URL = "https://api-adresse.data.gouv.fr/search/csv/"  # API de géocodage
    
    # Mapping des champs DPE
    DPE_FIELDS = {
        'N°DPE': 'dpe_number',
        'numero_dpe': 'dpe_number',
        'Date_réception_DPE': 'dpe_date',
        'date_reception_dpe': 'dpe_date',
        'Etiquette_DPE': 'dpe_energy_class',
        'etiquette_dpe': 'dpe_energy_class',
        'classe_consommation_energie': 'dpe_energy_class',
        'Etiquette_GES': 'dpe_ges_class',
        'etiquette_ges': 'dpe_ges_class',
        'classe_estimation_ges': 'dpe_ges_class',
        'Année_construction': 'construction_year',
        'annee_construction': 'construction_year'
    }
    
    # Mapping des champs d'adresse
    ADDRESS_FIELDS = {
        'Adresse_brute': 'address_raw',
        'adresse_brut': 'address_raw',
        'adresse_ban': 'address_raw',
        'geo_adresse': 'address_raw'
    }
    
    def __init__(self, input_path: str = None, output_path: str = None,
                 dpe_cache_dir: str = "data/cache/dpe"):
        super().__init__(input_path, output_path)
        self.dpe_cache_dir = dpe_cache_dir
        self.debug_dir = os.path.join(self.dpe_cache_dir, "debug")
        
        # Créer les répertoires de cache et débogage si nécessaires
        os.makedirs(self.dpe_cache_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)
        
        # Configurer le logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # Éviter les doubles logs en vérifiant si un handler existe déjà
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
        # Désactiver la propagation des logs pour éviter les doublons
        self.logger.propagate = False
            
        self.logger.info("DPE Enrichment Service initialized")
    
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
            # Réinitialisation de l'index pour éviter les problèmes avec les duplications
            df = df.reset_index(drop=True)
            
            # Préparer les colonnes DPE
            standard_fields = set(self.DPE_FIELDS.values())
            for field in standard_fields:
                df[field] = None
            
            # Vérifier et préparer la colonne d'adresse
            if 'address_normalized' not in df.columns:
                self.logger.info("Colonne 'address_normalized' non trouvée, utilisation de 'address' à la place")
                if 'address' in df.columns:
                    df['address_normalized'] = df['address']
                else:
                    self.logger.error("Aucune colonne d'adresse trouvée. Enrichissement impossible.")
                    return False
            
            # Normaliser les adresses pour le matching
            df['address_matching'] = df['address_normalized'].apply(self.normalize_address_for_matching)
            
            # Vérifier si nous avons un code INSEE, sinon extraire du code postal
            if 'insee_code' not in df.columns:
                self.logger.info("Colonne 'insee_code' non trouvée, extraction depuis 'postal_code'")
                if 'postal_code' in df.columns:
                    # On utilise les 2 premiers chiffres du code postal + les 3 premiers du code postal
                    # C'est une approximation, pas idéale mais fonctionnelle pour le test
                    df['insee_code'] = df['postal_code'].astype(str).str[:5]
                elif 'city' in df.columns and df['city'].str.contains(r'\d{5}', regex=True).any():
                    # Essayer d'extraire le code postal du nom de la ville
                    df['insee_code'] = df['city'].str.extract(r'(\d{5})')[0]
                else:
                    self.logger.error("Impossible de déterminer le code INSEE. Enrichissement impossible.")
                    return False
            
            # Regrouper par code INSEE
            insee_groups = df.groupby('insee_code')
            
            # Statistiques de matching
            total_matched = 0
            
            # Liste pour collecter tous les candidats potentiels après matching textuel
            all_potential_matches = []
            property_info_by_candidate = {}
            
            # ÉTAPE 1: Identifier tous les candidats potentiels par matching textuel
            self.logger.info("ÉTAPE 1: Matching textuel des adresses")
            
            # Limiter le nombre total de candidats pour éviter des problèmes de mémoire
            max_total_candidates = 5000
            
            for insee_code, group in insee_groups:
                if pd.isna(insee_code):
                    self.logger.warning(f"Groupe avec code INSEE manquant ignoré ({len(group)} propriétés)")
                    continue
                    
                self.logger.info(f"Traitement du groupe INSEE {insee_code} avec {len(group)} propriétés")
                    
                # Récupérer également le code postal et le nom de la commune pour le premier élément du groupe
                zipcode = None
                city_name = None
                
                for _, row in group.head(1).iterrows():
                    if 'postal_code' in row and not pd.isna(row['postal_code']):
                        zipcode = row['postal_code']
                    elif 'city' in row and re.search(r'\d{5}', row['city']):
                        # Extraire le code postal du nom de la ville
                        match = re.search(r'(\d{5})', row['city'])
                        zipcode = match.group(1) if match else None
                    
                    if 'city' in row and not pd.isna(row['city']):
                        # Nettoyer le nom de la ville (enlever le code postal)
                        city_name = re.sub(r'\d{5}', '', row['city']).strip()
                
                # Vérifier le cache des DPEs
                cache_file = os.path.join(self.dpe_cache_dir, f"dpe_{insee_code}.csv")
                
                if os.path.exists(cache_file):
                    # Vérifier l'âge du fichier
                    file_age = time.time() - os.path.getmtime(cache_file)
                    # Si le fichier a plus de 30 jours (2592000 secondes)
                    if file_age > 2592000:
                        self.logger.info(f"Cache DPE pour INSEE {insee_code} obsolète, mise à jour...")
                        dpe_data = self.fetch_dpe_data(insee_code, zipcode, city_name)
                        if dpe_data is not None and not dpe_data.empty:
                            dpe_data.to_csv(cache_file, index=False)
                    else:
                        # Charger depuis le cache
                        dpe_data = pd.read_csv(cache_file, low_memory=False)
                        # Nettoyer les données avant utilisation
                        dpe_data = self.sanitize_cache_data(dpe_data)
                        self.logger.info(f"Chargé {len(dpe_data)} DPEs depuis le cache pour INSEE {insee_code}")
                else:
                    # Récupérer les données DPE pour cette commune
                    dpe_data = self.fetch_dpe_data(insee_code, zipcode, city_name)
                    
                    if dpe_data is not None and not dpe_data.empty:
                        # Sauvegarder dans le cache
                        dpe_data.to_csv(cache_file, index=False)
                
                if dpe_data is None or dpe_data.empty:
                    self.logger.warning(f"Aucun DPE trouvé pour INSEE {insee_code}")
                    continue
                
                # Sauvegarder quelques échantillons pour débogage
                self.save_sample_dpe(insee_code, dpe_data)
                
                # Préparer les données DPE pour le matching
                self.logger.info(f"Préparation des données DPE pour le matching: INSEE {insee_code}")
                if 'Adresse_brute' in dpe_data.columns:
                    # Assurer que l'index est unique pour éviter les erreurs de reindex
                    dpe_data = dpe_data.reset_index(drop=True)
                    
                    # Traiter les valeurs NaN ou NaT
                    dpe_data['Adresse_brute'] = dpe_data['Adresse_brute'].fillna('').astype(str)
                    
                    # Vérifier les colonnes dupliquées à nouveau pour être sûr
                    if dpe_data.columns.duplicated().any():
                        self.logger.warning("Suppression de colonnes dupliquées avant le matching d'adresse")
                        dpe_data = dpe_data.loc[:, ~dpe_data.columns.duplicated()]
                    
                    # Appliquer la normalisation - méthode sécurisée
                    self.logger.info(f"Normalisation des adresses DPE pour INSEE {insee_code}")
                    address_matching = []
                    for adr in dpe_data['Adresse_brute']:
                        address_matching.append(self.normalize_address_for_matching(adr))
                    dpe_data['address_matching'] = address_matching
                else:
                    self.logger.warning(f"Colonne Adresse_brute manquante dans les données DPE pour INSEE {insee_code}")
                    # Essayer de trouver une autre colonne d'adresse
                    address_cols = [col for col in dpe_data.columns if 'adresse' in col.lower() or 'address' in col.lower()]
                    if address_cols:
                        self.logger.info(f"Utilisation de la colonne {address_cols[0]} pour le matching d'adresse")
                        dpe_data = dpe_data.reset_index(drop=True)
                        dpe_data['Adresse_brute'] = dpe_data[address_cols[0]].fillna('').astype(str)
                        
                        # Appliquer la normalisation - méthode sécurisée
                        self.logger.info(f"Normalisation des adresses DPE pour INSEE {insee_code}")
                        address_matching = []
                        for adr in dpe_data['Adresse_brute']:
                            address_matching.append(self.normalize_address_for_matching(adr))
                        dpe_data['address_matching'] = address_matching
                    else:
                        self.logger.warning(f"Aucune colonne d'adresse trouvée, matching impossible pour INSEE {insee_code}")
                        continue
                
                # Pour chaque propriété du groupe, chercher des DPE potentiels par matching textuel
                properties_count = len(group)
                self.logger.info(f"Recherche de candidats DPE pour {properties_count} propriétés (INSEE {insee_code})")
                
                processed_properties = 0
                properties_with_candidates = 0
                
                for idx, row in group.iterrows():
                    processed_properties += 1
                    if processed_properties % 50 == 0:
                        self.logger.info(f"Traité {processed_properties}/{properties_count} propriétés pour INSEE {insee_code}")
                    
                    property_address = row['address_matching']
                    
                    # Vérifier les coordonnées
                    lat = row.get('latitude', None)
                    lon = row.get('longitude', None)
                    
                    if pd.isna(lat) or pd.isna(lon):
                        # Ignorer les propriétés sans coordonnées
                        continue
                    
                    # Trouver les candidats DPE potentiels par similarité de texte
                    candidates = self.find_text_match_candidates(property_address, dpe_data)
                    
                    # Si on a des candidats, les ajouter à la liste à géocoder
                    if candidates:
                        properties_with_candidates += 1
                        
                        for candidate in candidates:
                            # Créer un identifiant unique pour ce candidat
                            candidate_id = f"{idx}_{len(all_potential_matches)}"
                            
                            # Ajouter les coordonnées de la propriété et l'ID pour retrouver la propriété plus tard
                            candidate['property_idx'] = idx
                            candidate['property_lat'] = lat
                            candidate['property_lon'] = lon
                            candidate['candidate_id'] = candidate_id
                            
                            # Ajouter le candidat à la liste
                            all_potential_matches.append(candidate)
                            property_info_by_candidate[candidate_id] = {
                                'property_idx': idx,
                                'property_address': property_address
                            }
                    
                    # Si on a déjà trop de candidats, arrêter la recherche
                    if len(all_potential_matches) >= max_total_candidates:
                        self.logger.warning(f"Limite de {max_total_candidates} candidats atteinte, arrêt de la recherche")
                        break
                
                self.logger.info(f"Trouvé des candidats pour {properties_with_candidates}/{properties_count} propriétés pour INSEE {insee_code}")
                
                # Si on a déjà trop de candidats, arrêter la recherche
                if len(all_potential_matches) >= max_total_candidates:
                    break
            
            self.logger.info(f"Trouvé {len(all_potential_matches)} candidats potentiels au total après matching textuel")
            
            if not all_potential_matches:
                self.logger.warning("Aucun candidat DPE trouvé par matching textuel")
                return self.save_csv(df)
            
            # ÉTAPE 2: Géocoder tous les candidats DPE en une seule requête
            self.logger.info("ÉTAPE 2: Géocodage des candidats DPE")
            geocoded_dpe_matches = []
            
            # Taille des lots pour l'API de géocodage
            geocoding_batch_size = 1000
            
            # Diviser les candidats en lots pour le géocodage
            candidate_batches = [all_potential_matches[i:i+geocoding_batch_size] 
                                for i in range(0, len(all_potential_matches), geocoding_batch_size)]
            
            self.logger.info(f"Traitement en {len(candidate_batches)} lots de géocodage")
            
            for batch_idx, candidate_batch in enumerate(candidate_batches):
                self.logger.info(f"Géocodage du lot {batch_idx+1}/{len(candidate_batches)} ({len(candidate_batch)} candidats)")
                
                # Géocoder ce lot de candidats
                batch_results = self.geocode_dpe_candidates(candidate_batch)
                
                if batch_results:
                    geocoded_dpe_matches.extend(batch_results)
                    self.logger.info(f"Lot {batch_idx+1}: {len(batch_results)} candidats géocodés avec succès")
                else:
                    self.logger.warning(f"Lot {batch_idx+1}: Échec du géocodage")
                    
                # Faire une pause entre les lots pour éviter de surcharger l'API
                if batch_idx < len(candidate_batches) - 1:
                    time.sleep(1)
                
            self.logger.info(f"Géocodage terminé: {len(geocoded_dpe_matches)}/{len(all_potential_matches)} candidats géocodés avec succès")
            
            if not geocoded_dpe_matches:
                self.logger.warning("Aucun candidat DPE géocodé avec succès")
                return self.save_csv(df)
            
            # ÉTAPE 3: Valider les matches par proximité géographique et appliquer aux propriétés
            self.logger.info(f"ÉTAPE 3: Validation et application des matches ({len(geocoded_dpe_matches)} candidats géocodés)")
            
            validated_count = 0
            
            for dpe_match in geocoded_dpe_matches:
                candidate_id = dpe_match.get('candidate_id')
                
                if not candidate_id or candidate_id not in property_info_by_candidate:
                    continue
                    
                property_idx = dpe_match.get('property_idx')
                property_lat = dpe_match.get('property_lat')
                property_lon = dpe_match.get('property_lon')
                property_address = property_info_by_candidate[candidate_id]['property_address']
                
                # Valider la distance entre la propriété et l'adresse DPE
                dpe_lat = dpe_match.get('geocoded_latitude')
                dpe_lon = dpe_match.get('geocoded_longitude')
                
                if pd.isna(dpe_lat) or pd.isna(dpe_lon) or pd.isna(property_lat) or pd.isna(property_lon):
                    continue
                
                distance = self.calculate_geo_distance(property_lat, property_lon, dpe_lat, dpe_lon)
                
                # Valider si la distance est inférieure à 100m
                if distance <= 0.1:  # 100m en km
                    # Match validé, mettre à jour les données DPE pour cette propriété
                    for std_field in standard_fields:
                        if std_field in dpe_match and not pd.isna(dpe_match[std_field]):
                            value = dpe_match[std_field]
                            # Conversion pour année de construction
                            if std_field == 'construction_year' and value:
                                try:
                                    value = int(value)
                                except (ValueError, TypeError):
                                    value = None
                            df.loc[property_idx, std_field] = value
                    
                    total_matched += 1
                    validated_count += 1
                    
                    # Afficher des informations sur les matches trouvés
                    if total_matched % 10 == 0 or total_matched < 10:
                        self.logger.info(f"Match trouvé: '{property_address}' -> '{dpe_match.get('Adresse_brute', '')}' (distance: {distance*1000:.1f}m)")
            
            self.logger.info(f"Validé {validated_count}/{len(geocoded_dpe_matches)} matches par proximité géographique")
            
            # Supprimer les colonnes temporaires
            if 'address_matching' in df.columns:
                df = df.drop(columns=['address_matching'])
            
            # Convertir construction_year en entier
            df['construction_year'] = pd.to_numeric(df['construction_year'], errors='coerce')
            
            # Statistiques finales
            match_percentage = (total_matched / initial_count) * 100 if initial_count > 0 else 0
            self.logger.info(f"Enrichissement DPE terminé: {total_matched}/{initial_count} propriétés enrichies ({match_percentage:.1f}%)")
            
            # Sauvegarder le résultat
            return self.save_csv(df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enrichissement DPE: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def fetch_dpe_data(self, insee_code: str, zipcode: Optional[str] = None, city_name: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Récupère les données DPE pour un code INSEE, code postal et nom de ville.
        
        Args:
            insee_code: Code INSEE de la commune
            zipcode: Code postal de la commune
            city_name: Nom de la commune
            
        Returns:
            Optional[pd.DataFrame]: DataFrame avec les données DPE ou None si échec
        """
        all_data = []
        
        # Parcourir les APIs par priorité (les plus récentes d'abord)
        api_priority = [
            "EXISTING_BUILDINGS_NEW",  # Logements existants (depuis juillet 2021)
            "NEW_BUILDINGS_NEW",       # Logements neufs (depuis juillet 2021)
            "EXISTING_BUILDINGS_OLD",  # Logements (avant juillet 2021)
            "TERTIARY_NEW",            # Tertiaire (depuis juillet 2021)
            "TERTIARY_OLD"             # Tertiaire (avant juillet 2021)
        ]
        
        # Nombre minimum de DPE que nous voulons obtenir avant d'arrêter
        min_dpe_threshold = 200
        
        # Requêtes pour les API par ordre de priorité
        for api_name in api_priority:
            # Vérifier si nous avons déjà suffisamment de données
            if len(all_data) > min_dpe_threshold:
                self.logger.info(f"Déjà {len(all_data)} DPEs, suffisant pour l'enrichissement. Arrêt des requêtes.")
                break
                
            api_info = self.DPE_APIS[api_name]
            
            # Récupérer avec code INSEE uniquement (pas besoin de q_fields car les codes INSEE sont uniques)
            insee_data = self.query_dpe_api_with_pagination(
                insee_code, 
                api_info["url"], 
                api_info["field"], 
                "Code INSEE"
            )
            if insee_data:
                all_data.extend(insee_data)
                self.logger.info(f"Récupéré {len(insee_data)} DPEs via {api_name} avec INSEE {insee_code}")
                
                # Si nous avons suffisamment de données, on peut s'arrêter là
                if len(all_data) > min_dpe_threshold:
                    break
        
        # Dédupliquer les DPEs
        if all_data:
            # Convertir en DataFrame
            df = pd.DataFrame(all_data)
            
            # Reset de l'index pour éviter les problèmes de duplications
            df = df.reset_index(drop=True)
            
            # Vérifier et traiter les colonnes dupliquées
            if df.columns.duplicated().any():
                self.logger.warning("Détection de colonnes dupliquées dans les données DPE")
                # Garder uniquement la première occurrence de chaque colonne dupliquée
                df = df.loc[:, ~df.columns.duplicated()]
            
            # Standardiser les noms de colonnes pour l'adresse
            for api_field, std_field in self.ADDRESS_FIELDS.items():
                if api_field in df.columns:
                    df.rename(columns={api_field: std_field}, inplace=True)
            
            # Standardiser les noms de colonnes pour les données DPE
            for api_field, std_field in self.DPE_FIELDS.items():
                if api_field in df.columns:
                    df.rename(columns={api_field: std_field}, inplace=True)
            
            # Dédupliquer sur le numéro DPE
            if 'dpe_number' in df.columns:
                df = df.drop_duplicates(subset=['dpe_number'])
                self.logger.info(f"Total après déduplication: {len(df)} DPEs pour INSEE {insee_code}")
                
                # Renommer la colonne d'adresse brute pour la cohérence
                if 'address_raw' in df.columns:
                    df.rename(columns={'address_raw': 'Adresse_brute'}, inplace=True)
                    
                # Assurer que nous avons une colonne pour l'adresse brute
                if 'Adresse_brute' not in df.columns:
                    # Chercher une colonne alternative d'adresse
                    address_cols = [col for col in df.columns if 'adresse' in col.lower() or 'address' in col.lower()]
                    if address_cols:
                        df['Adresse_brute'] = df[address_cols[0]]
                    else:
                        # Créer une adresse brute à partir de ce qu'on a
                        components = []
                        for field in ['numero_voie_ban', 'nom_rue_ban', 'code_postal_ban', 'nom_commune_ban']:
                            if field in df.columns:
                                components.append(field)
                        
                        if components:
                            df['Adresse_brute'] = df[components].astype(str).apply(lambda x: ' '.join(x.dropna()), axis=1)
                        else:
                            df['Adresse_brute'] = 'Adresse non disponible'
                            
                # Limiter à 10000 résultats max pour éviter des problèmes de mémoire et de performance
                if len(df) > 10000:
                    self.logger.warning(f"Trop de résultats pour INSEE {insee_code}, limitation à 10000 résultats")
                    df = df.head(10000)
                
                # Reset de l'index à nouveau après toutes les transformations
                return df.reset_index(drop=True)
            else:
                self.logger.warning(f"Aucune colonne dpe_number dans les données récupérées")
                # Renommer la colonne d'adresse brute pour la cohérence
                if 'address_raw' in df.columns:
                    df.rename(columns={'address_raw': 'Adresse_brute'}, inplace=True)
                    
                # Limiter à 10000 résultats max pour éviter des problèmes de mémoire et de performance
                if len(df) > 10000:
                    self.logger.warning(f"Trop de résultats pour INSEE {insee_code}, limitation à 10000 résultats")
                    df = df.head(10000)
                
                # Reset de l'index à nouveau après toutes les transformations
                return df.reset_index(drop=True)
        else:
            self.logger.warning(f"Aucun DPE trouvé pour INSEE {insee_code}, zipcode {zipcode}, ville {city_name}")
            return None
    
    def normalize_city_name(self, city_name: str) -> str:
        """Normalise le nom d'une ville pour la comparaison."""
        if not isinstance(city_name, str):
            return ""
        city = city_name.upper()
        city = unicodedata.normalize('NFKD', city).encode('ASCII', 'ignore').decode('utf-8')
        city = re.sub(r'[^\w\s]', '', city)
        city = re.sub(r'\s+', ' ', city).strip()
        return city
    
    def query_dpe_api_with_pagination(self, search_value: str, api_url: str, 
                                     search_field: str, search_label: str) -> Optional[List[Dict[str, Any]]]:
        """
        Interroge l'API DPE avec pagination pour gérer les limites de 9999 résultats.
        
        Args:
            search_value: Valeur à rechercher
            api_url: URL de l'API à interroger
            search_field: Champ dans lequel rechercher
            search_label: Libellé du champ pour les logs
            
        Returns:
            Optional[List[Dict[str, Any]]]: Liste des DPEs ou None si échec
        """
        all_results = []
        page = 1  # Commencer à 1 pour compatibilité avec l'API
        has_more = True
        
        # L'API a une limitation: size * page <= 10000
        # Pour les premières pages, on peut utiliser une taille de lot plus grande
        # Ensuite, on doit réduire la taille pour les pages suivantes
        max_page_size = self.API_BATCH_SIZE
        
        while has_more:
            try:
                # Ajuster la taille du lot pour respecter la limite size*page <= 10000
                if page * max_page_size > 10000:
                    # Calculer la taille maximale possible pour cette page
                    current_page_size = min(max_page_size, 10000 // page)
                    if current_page_size <= 0:
                        self.logger.warning(f"Limite de pagination atteinte (10000) pour {search_label} {search_value}")
                        break
                else:
                    current_page_size = max_page_size
                
                # Utiliser uniquement le code INSEE comme paramètre de recherche sans q_fields
                # car les codes INSEE sont uniques
                params = {
                    "size": current_page_size,
                    "page": page,
                    "q": search_value
                }
                
                self.logger.info(f"Interrogation de l'API pour {search_label} {search_value} (page {page}, taille {current_page_size})")
                
                # Essayer plusieurs fois en cas d'erreur temporaire
                for retry in range(self.MAX_RETRIES):
                    try:
                        response = requests.get(api_url, params=params, timeout=60)
                        break
                    except requests.exceptions.RequestException as e:
                        if retry < self.MAX_RETRIES - 1:
                            self.logger.warning(f"Erreur temporaire lors de la requête API: {str(e)}. Réessai {retry+1}/{self.MAX_RETRIES}")
                            time.sleep(self.RETRY_DELAY * (retry + 1))
                        else:
                            raise
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "results" in data:
                        results = data["results"]
                        all_results.extend(results)
                        
                        # Vérifier le nombre total et s'il y a plus de données
                        total_results = data.get("total", 0)
                        
                        self.logger.info(f"Reçu {len(results)} résultats. Total annoncé: {total_results}")
                        
                        if total_results >= 9999:
                            # Si le total est de 9999 ou plus, il y a probablement plus de données (limitation API)
                            has_more = len(results) == current_page_size
                            self.logger.warning(f"Limite de 9999 résultats atteinte pour {search_label} {search_value}, "
                                              f"page {page} avec {len(results)} résultats. Continuant pagination...")
                        else:
                            # Sinon, il reste des pages si le nombre total de résultats n'a pas été atteint
                            received_so_far = sum(1 for _ in all_results)
                            has_more = received_so_far < total_results
                            if has_more:
                                self.logger.info(f"Total: {total_results}, reçus: {received_so_far}, reste: {has_more}")
                    else:
                        has_more = False
                else:
                    self.logger.warning(f"Erreur API ({response.status_code}) pour {search_label} {search_value}")
                    self.logger.warning(f"Réponse: {response.text}")
                    has_more = False
                
                # Passer à la page suivante
                page += 1
                
                # Pause pour éviter de surcharger l'API
                time.sleep(0.5)
                
                # Limite de sécurité: pas plus de 10 pages ou 20000 résultats
                if page > 20 or len(all_results) >= 20000:
                    self.logger.warning(f"Limite de pagination atteinte pour {search_label} {search_value}, arrêt.")
                    has_more = False
                
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
        if not isinstance(address, str) or not address or address.lower() == 'nan':
            return ""
        
        # Convertir en majuscules
        address = address.upper()
        
        # Supprimer les accents
        address = unicodedata.normalize('NFKD', address).encode('ASCII', 'ignore').decode('utf-8')
        
        # Supprimer les parenthèses et leur contenu
        address = re.sub(r'\([^)]*\)', '', address)
        
        # Supprimer la ponctuation
        address = re.sub(r'[^\w\s]', ' ', address)
        
        # Normaliser les mots couramment utilisés dans les adresses
        address = address.replace(" AVENUE ", " AV ")
        address = address.replace(" BOULEVARD ", " BD ")
        address = address.replace(" PLACE ", " PL ")
        address = address.replace(" ALLEE ", " AL ")
        address = address.replace(" IMPASSE ", " IMP ")
        
        # Supprimer les codes postaux pour éviter les confusions
        address = re.sub(r'\d{5}', '', address)
        
        # Supprimer les mots non significatifs
        non_significant = ["RUE", "DE", "DES", "LA", "LE", "LES", "DU", "ET", "EN", "SUR", "SOUS", "A", "AU", "AUX"]
        words = address.split()
        if len(words) > 2:  # Garder au moins le numéro et un mot significatif
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
                          dpe_data: pd.DataFrame, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Cette méthode est obsolète et sera supprimée. Utiliser le nouveau processus de matching à deux étapes.
        """
        self.logger.warning("Méthode obsolète: find_best_dpe_match. Utiliser le nouveau processus de matching à deux étapes.")
        return None

    def validate_with_geocoding(self, best_match: Dict[str, Any], candidates: pd.DataFrame, 
                             latitude: float, longitude: float, current_score: float) -> Dict[str, Any]:
        """
        Cette méthode est obsolète et sera supprimée. Utiliser le nouveau processus de matching à deux étapes.
        """
        self.logger.warning("Méthode obsolète: validate_with_geocoding. Utiliser le nouveau processus de matching à deux étapes.")
        return {'is_valid': False, 'distance': float('inf'), 'geo_score': 0.0}

    def geocode_dpe_addresses(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Géocode un lot d'adresses DPE en utilisant l'API de géocodage.
        
        Args:
            df: DataFrame avec colonne 'q' contenant les adresses complètes
            
        Returns:
            Optional[pd.DataFrame]: DataFrame avec les résultats du géocodage ou None si échec
        """
        if df.empty:
            return None
        
        # Vérifier que la colonne q existe
        if 'q' not in df.columns:
            self.logger.error("La colonne 'q' est requise pour le géocodage")
            return None
        
        # Vérifier que la colonne candidate_index existe pour tracer les résultats
        if 'candidate_index' not in df.columns:
            self.logger.warning("La colonne 'candidate_index' est manquante, l'ajout")
            df['candidate_index'] = range(len(df))
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Convertir le DataFrame en CSV
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_content = csv_buffer.getvalue()
                
                # Pour le débogage
                self.logger.info(f"Envoi du CSV pour géocodage avec {len(df)} adresses DPE")
                
                # Appeler l'API de géocodage
                files = {'data': ('addresses.csv', csv_content.encode('utf-8'), 'text/csv')}
                response = requests.post(
                    self.GEOCODING_API_URL,
                    files=files,
                    timeout=120  # Augmentation du timeout pour les grands lots
                )
                
                if response.status_code == 200:
                    # Parser la réponse CSV
                    result_df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
                    
                    # Vérifier que toutes les colonnes attendues sont présentes
                    expected_columns = ['latitude', 'longitude', 'result_score']
                    missing_columns = [col for col in expected_columns if col not in result_df.columns]
                    
                    if missing_columns:
                        self.logger.warning(f"Colonnes manquantes dans la réponse du géocodage: {missing_columns}")
                        # Continuer quand même si possible
                    
                    # Vérifier que l'index du candidat est préservé
                    if 'candidate_index' not in result_df.columns:
                        self.logger.warning("La colonne 'candidate_index' est absente de la réponse de géocodage")
                        
                        # Essayer de récupérer l'index depuis une autre colonne ou ajouter l'index
                        if len(result_df) == len(df):
                            self.logger.info("Ajout de l'index des candidats à la réponse de géocodage")
                            result_df['candidate_index'] = df['candidate_index'].values
                        else:
                            self.logger.warning(f"Impossible de récupérer l'index des candidats: {len(result_df)} résultats pour {len(df)} requêtes")
                    
                    self.logger.info(f"Géocodage DPE réussi: {len(result_df)} résultats")
                    
                    return result_df
                else:
                    self.logger.warning(f"Erreur API géocodage ({response.status_code}) - Tentative {attempt}/{self.MAX_RETRIES}")
                    self.logger.warning(f"Détail de l'erreur: {response.text}")
                    
            except Exception as e:
                self.logger.warning(f"Erreur de requête géocodage - Tentative {attempt}/{self.MAX_RETRIES}: {str(e)}")
            
            # Attendre avant de réessayer
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY * attempt)  # Délai exponentiel
        
        self.logger.error("Échec du géocodage DPE après plusieurs tentatives")
        return None
    
    def calculate_geo_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calcule la distance géographique entre deux points en kilomètres.
        Utilise la formule de Haversine pour calculer la distance sur une sphère.
        
        Args:
            lat1: Latitude du point 1
            lon1: Longitude du point 1
            lat2: Latitude du point 2
            lon2: Longitude du point 2
            
        Returns:
            float: Distance en kilomètres
        """
        # Convertir les degrés en radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Rayon de la Terre en km
        earth_radius = 6371.0
        
        # Différences de coordonnées
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        # Formule de Haversine
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = earth_radius * c
        
        return distance
    
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
            # S'assurer que l'index est unique avant de manipuler les données
            dpe_data_copy = dpe_data.copy().reset_index(drop=True)
            
            # Vérifier et traiter les colonnes dupliquées
            if dpe_data_copy.columns.duplicated().any():
                # Garder uniquement la première occurrence de chaque colonne dupliquée
                self.logger.warning("Suppression des colonnes dupliquées avant de créer l'échantillon")
                dpe_data_copy = dpe_data_copy.loc[:, ~dpe_data_copy.columns.duplicated()]
            
            # Sélectionner quelques échantillons
            sample_size = min(self.DEBUG_SAMPLE_SIZE, len(dpe_data_copy))
            samples = dpe_data_copy.sample(sample_size)
            
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

    def sanitize_cache_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Nettoie et prépare les données issues du cache.
        
        Args:
            df: DataFrame à nettoyer
            
        Returns:
            pd.DataFrame: DataFrame nettoyé et prêt à l'emploi
        """
        # Vérifier si le DataFrame est vide
        if df.empty:
            return df
            
        # Réinitialiser l'index pour éviter les problèmes de duplication
        df = df.reset_index(drop=True)
        
        # Normaliser les noms de colonnes pour éviter les duplications
        if df.columns.duplicated().any():
            # Garder uniquement la première occurrence de chaque colonne dupliquée
            df = df.loc[:, ~df.columns.duplicated()]
            self.logger.warning("Colonnes dupliquées supprimées des données du cache")
        
        # S'assurer que nous avons une colonne Adresse_brute
        if 'Adresse_brute' not in df.columns:
            address_cols = [col for col in df.columns if 'adresse' in col.lower() or 'address' in col.lower()]
            if address_cols:
                self.logger.info(f"Utilisation de la colonne {address_cols[0]} comme Adresse_brute")
                df['Adresse_brute'] = df[address_cols[0]]
            else:
                self.logger.warning("Aucune colonne d'adresse trouvée dans les données du cache")
                # Créer une colonne factice
                df['Adresse_brute'] = "Adresse non disponible"
        
        # Nettoyer la colonne d'adresse
        df['Adresse_brute'] = df['Adresse_brute'].fillna('').astype(str)
        
        # Limiter à 10000 résultats max pour éviter des problèmes de mémoire et de performance
        if len(df) > 10000:
            self.logger.warning(f"Trop de résultats dans le cache, limitation à 10000 résultats")
            df = df.head(10000)
        
        return df

    def find_text_match_candidates(self, property_address: str, dpe_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Trouve les candidats DPE par matching textuel.
        
        Args:
            property_address: Adresse normalisée de la propriété
            dpe_data: DataFrame des DPEs
            
        Returns:
            List[Dict[str, Any]]: Liste des candidats DPE
        """
        if property_address == "" or dpe_data.empty:
            return []
        
        candidates = []
        
        # Debug log to track progress
        self.logger.debug(f"Matching address: '{property_address}' against {len(dpe_data)} DPE entries")
        
        # Safety limit to avoid processing too many DPE entries
        max_dpe_to_process = min(10000, len(dpe_data))
        processed_dpe = 0
        matched_dpe = 0
        
        # Matching de similarité pour chaque DPE dans les données
        for _, dpe_row in dpe_data.head(max_dpe_to_process).iterrows():
            processed_dpe += 1
            dpe_address = dpe_row['address_matching']
            if not isinstance(dpe_address, str) or dpe_address == "":
                continue
            
            # Calculer la similarité entre l'adresse de la propriété et l'adresse DPE
            similarity = difflib.SequenceMatcher(None, property_address, dpe_address).ratio()
            
            # Si la similarité dépasse le seuil, ajouter aux candidats
            if similarity >= self.SIMILARITY_THRESHOLD:
                candidate = dpe_row.to_dict()
                candidate['similarity'] = similarity
                candidates.append(candidate)
                matched_dpe += 1
        
        # Performance logging
        if processed_dpe > 0:
            self.logger.debug(f"Processed {processed_dpe}/{len(dpe_data)} DPE entries, found {matched_dpe} matches above threshold")
        
        return candidates

    def geocode_dpe_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Géocode les candidats DPE en batch et valide les matches par proximité.
        
        Args:
            candidates: Liste des candidats DPE
            
        Returns:
            List[Dict[str, Any]]: Liste des DPE géocodés
        """
        if not candidates:
            return []
        
        # Préparer les données pour le géocodage
        geocoding_data = []
        
        self.logger.info(f"Préparation de {len(candidates)} candidats pour le géocodage")
        
        for i, candidate in enumerate(candidates):
            # Récupérer l'adresse brute + code postal + ville
            address = candidate.get('Adresse_brute', '')
            postal_code = ''
            city = ''
            
            # Chercher le code postal et la ville dans les champs disponibles
            for field in ['code_postal_ban', 'code_postal']:
                if field in candidate and candidate[field]:
                    postal_code = str(candidate[field])
                    break
                
            for field in ['nom_commune_ban', 'commune']:
                if field in candidate and candidate[field]:
                    city = str(candidate[field])
                    break
            
            # Construire l'adresse complète pour le géocodage
            if address:
                full_address = address
                if postal_code:
                    full_address += f", {postal_code}"
                if city:
                    full_address += f", {city}"
            
                geocoding_data.append({
                    'q': full_address,
                    'candidate_index': i  # Pour retrouver le candidat original
                })
        
        if not geocoding_data:
            self.logger.warning("Aucune adresse valide parmi les candidats DPE")
            return []
        
        self.logger.info(f"Envoi de {len(geocoding_data)} adresses DPE au géocodage")
        
        # Convertir en DataFrame pour l'API de géocodage
        geocoding_df = pd.DataFrame(geocoding_data)
        
        # Appeler l'API de géocodage
        result_df = self.geocode_dpe_addresses(geocoding_df)
        
        if result_df is None or result_df.empty:
            self.logger.warning("Échec du géocodage des adresses DPE")
            return []
        
        # Traiter les résultats et mettre à jour les candidats
        validated_candidates = []
        
        # Vérifier la correspondance entre les résultats et les candidats originaux
        if 'candidate_index' not in result_df.columns:
            self.logger.warning("La colonne 'candidate_index' est manquante dans les résultats du géocodage")
            return []
        
        successful_geocodes = 0
        
        for _, geocoded_row in result_df.iterrows():
            if pd.isna(geocoded_row['latitude']) or pd.isna(geocoded_row['longitude']):
                continue
            
            # Récupérer l'index du candidat
            candidate_index = geocoded_row.get('candidate_index')
            if pd.isna(candidate_index):
                continue
            
            try:
                candidate_index = int(candidate_index)
            except (ValueError, TypeError):
                continue
            
            if 0 <= candidate_index < len(candidates):
                # Récupérer le candidat original
                candidate = candidates[candidate_index].copy()
                
                # Ajouter les coordonnées géocodées
                candidate['geocoded_latitude'] = float(geocoded_row['latitude'])
                candidate['geocoded_longitude'] = float(geocoded_row['longitude'])
                
                # Ajouter aux candidats validés
                validated_candidates.append(candidate)
                successful_geocodes += 1
            else:
                self.logger.warning(f"Index de candidat invalide: {candidate_index} (max: {len(candidates)-1})")
        
        self.logger.info(f"Géocodage réussi pour {successful_geocodes}/{len(geocoding_data)} adresses DPE ({len(validated_candidates)} candidats validés)")
        
        return validated_candidates

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