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
    """Processor for enriching properties with DPE data."""
    
    # ADEME APIs with correct search fields
    DPE_APIS = {
        # DPE Existing buildings (since July 2021)
        "EXISTING_BUILDINGS_NEW": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines",
            "insee_field": "code_insee_ban",
            "zipcode_field": "code_postal_ban",
            "city_field": "nom_commune_ban"
        },
        # DPE New buildings (since July 2021)
        "NEW_BUILDINGS_NEW": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe02neuf/lines",
            "insee_field": "code_insee_ban",
            "zipcode_field": "code_postal_ban",
            "city_field": "nom_commune_ban"
        },
        # DPE Tertiary buildings (since July 2021)
        "TERTIARY_NEW": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe01tertiaire/lines",
            "insee_field": "code_insee_ban",
            "zipcode_field": "code_postal_ban",
            "city_field": "nom_commune_ban"
        },
        # DPE Existing buildings (before July 2021)
        "EXISTING_BUILDINGS_OLD": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines",
            "insee_field": "code_insee_commune_actualise",
            "zipcode_field": "code_postal",
            "city_field": "commune"
        },
        # DPE Tertiary buildings (before July 2021)
        "TERTIARY_OLD": {
            "url": "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-tertiaire/lines",
            "insee_field": "code_insee_commune",
            "zipcode_field": "code_postal",
            "city_field": "commune"
        }
    }
    
    # Configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    SIMILARITY_THRESHOLD = 0.7  # threshold for text matching
    HIGH_SIMILARITY_THRESHOLD = 0.85  # threshold for addresses without numbers
    API_BATCH_SIZE = 9000  # batch size for API
    DEBUG_SAMPLE_SIZE = 5  # number of DPE samples to save for debugging
    PROXIMITY_THRESHOLD = 0.02  # 20 meters in km
    STRICT_NUMBER_VALIDATION = True  # enable strict street number validation
    
    # DPE field mapping
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
    
    # Address field mapping
    ADDRESS_FIELDS = {
        'Adresse_brute': 'address_raw',
        'adresse_brut': 'address_raw',
        'adresse_ban': 'address_raw',
        'geo_adresse': 'address_raw'
    }
    
    # Geopoint field mapping
    GEOPOINT_FIELDS = [
        '_geopoint', 'geo_point', 'geopoint', 
        'coordinates_ban', 'coordonnees_ban'
    ]
    
    def __init__(self, input_path: str = None, output_path: str = None,
                 dpe_cache_dir: str = "data/cache/dpe"):
        super().__init__(input_path, output_path)
        self.dpe_cache_dir = dpe_cache_dir
        self.debug_dir = os.path.join(self.dpe_cache_dir, "debug")
        
        # Create cache and debug directories if needed
        os.makedirs(self.dpe_cache_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)
        
        # Configure logging with proper level
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Use configured log level instead of hardcoded INFO
        try:
            from trackimmo.config import settings
            log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.ERROR)
        except ImportError:
            log_level = logging.ERROR
            
        self.logger.setLevel(log_level)
        
        # Avoid duplicate logs by checking if a handler already exists
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Disable log propagation to avoid duplicates
        self.logger.propagate = False
            
        self.logger.info("DPE Enrichment Service initialized")
    
    def process(self, **kwargs) -> bool:
        """
        Enrich properties with DPE data.
        
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        # Load data
        df = self.load_csv()
        if df is None:
            return False
        
        # Initial statistics
        initial_count = len(df)
        self.logger.info(f"Starting DPE enrichment for {initial_count} properties")
        
        try:
            # Reset index to avoid problems with duplicates
            df = df.reset_index(drop=True)
            
            # Prepare DPE columns
            standard_fields = set(self.DPE_FIELDS.values())
            for field in standard_fields:
                df[field] = None
            
            # Check and prepare address column
            if 'address_normalized' not in df.columns:
                self.logger.info("Column 'address_normalized' not found, using 'address' instead")
                if 'address' in df.columns:
                    df['address_normalized'] = df['address']
                else:
                    self.logger.error("No address column found. Enrichment impossible.")
                    return False
            
            # Normalize addresses for matching
            df['address_matching'] = df['address_normalized'].apply(self.normalize_address_for_matching)
            
            # Extract address components with focus on street numbers
            df['address_components'] = df['address_normalized'].apply(self.parse_address)
            
            # Check if we have INSEE code, otherwise extract from postal code
            if 'insee_code' not in df.columns:
                self.logger.info("Column 'insee_code' not found, extracting from 'postal_code'")
                if 'postal_code' in df.columns:
                    # Use first 2 digits of postal code + 3 first of postal code
                    # This is an approximation, not ideal but functional for testing
                    df['insee_code'] = df['postal_code'].astype(str).str[:5]
                elif 'city' in df.columns and df['city'].str.contains(r'\d{5}', regex=True).any():
                    # Try to extract postal code from city name
                    df['insee_code'] = df['city'].str.extract(r'(\d{5})')[0]
                else:
                    self.logger.error("Cannot determine INSEE code. Enrichment impossible.")
                    return False
            
            # Group by INSEE code and postal code for more complete matching
            location_groups = self.group_properties_by_location(df)
            
            # Matching statistics
            total_matched = 0
            
            # Process each location group
            for location_id, group_info in location_groups.items():
                if pd.isna(location_id):
                    self.logger.warning(f"Group with missing location ID ignored ({len(group_info['dataframe'])} properties)")
                    continue
                    
                group = group_info['dataframe']
                location_type = group_info['type']
                
                self.logger.info(f"Processing {location_type} group {location_id} with {len(group)} properties")
                
                # Get all relevant information for the location
                location_info = {
                    "insee_code": None,
                    "postal_code": None,
                    "city_name": None,
                    "type": location_type
                }
                
                # Extract location details from the first property in group
                for _, row in group.head(1).iterrows():
                    if location_type == 'insee':
                        location_info["insee_code"] = location_id
                        if 'postal_code' in row and not pd.isna(row['postal_code']):
                            location_info["postal_code"] = row['postal_code']
                    else:  # postal_code
                        location_info["postal_code"] = location_id
                        if 'insee_code' in row and not pd.isna(row['insee_code']):
                            location_info["insee_code"] = row['insee_code']
                    
                    if 'city' in row and not pd.isna(row['city']):
                        # Clean city name (remove postal code)
                        location_info["city_name"] = re.sub(r'\d{5}', '', row['city']).strip()
                
                # Get DPE data for this location (using cache if available)
                dpe_data = self.get_cached_or_fetch_dpe_data(location_id, location_info)
                
                if dpe_data is None or dpe_data.empty:
                    self.logger.warning(f"No DPE data found for {location_type}: {location_id}")
                    continue
                
                # Save sample DPEs for debugging
                self.save_sample_dpe(location_id, dpe_data)
                
                # Prepare DPE data for matching
                self.logger.debug(f"Preparing DPE data for matching: {location_type} {location_id}")
                dpe_data = self.prepare_dpe_data_for_matching(dpe_data)
                
                if dpe_data is None or dpe_data.empty:
                    self.logger.warning(f"Failed to prepare DPE data for {location_type}: {location_id}")
                    continue
                
                # Find matches for each property
                properties_count = len(group)
                self.logger.info(f"Looking for DPE matches for {properties_count} properties ({location_type}: {location_id})")
                
                processed_properties = 0
                properties_with_matches = 0
                
                for idx, row in group.iterrows():
                    processed_properties += 1
                    if processed_properties % 50 == 0:
                        self.logger.info(f"Processed {processed_properties}/{properties_count} properties for {location_type}: {location_id}")
                    
                    # Check coordinates
                    lat = row.get('latitude', None)
                    lon = row.get('longitude', None)
                    
                    if pd.isna(lat) or pd.isna(lon):
                        # Skip properties without coordinates
                        continue
                    
                    # Get address components
                    property_address = row['address_matching']
                    property_components = row['address_components']
                    
                    # Find potential DPE matches by text similarity
                    candidates = self.find_text_match_candidates(property_address, property_components, dpe_data)
                    
                    if not candidates:
                        continue
                    
                    properties_with_matches += 1
                    self.logger.debug(f"Found {len(candidates)} potential matches for property: {property_address}")
                    
                    # Validate matches by geographic proximity
                    validated_match = self.find_best_geo_match(lat, lon, candidates)
                    
                    if validated_match:
                        # Calculate match confidence
                        match_data = {
                            "property_address": property_address,
                            "property_components": property_components,
                            "dpe_address": validated_match.get('Adresse_brute', ''),
                            "dpe_components": self.parse_address(validated_match.get('Adresse_brute', '')),
                            "distance_m": validated_match['distance_m'],
                            "similarity": validated_match['similarity']
                        }
                        confidence = self.calculate_match_confidence(match_data)
                        
                        # Update property with DPE data
                        for std_field in standard_fields:
                            if std_field in validated_match and not pd.isna(validated_match[std_field]):
                                value = validated_match[std_field]
                                # Convert construction year
                                if std_field == 'construction_year' and value:
                                    try:
                                        value = int(value)
                                    except (ValueError, TypeError):
                                        value = None
                                df.loc[idx, std_field] = value
                        
                        # Add confidence score
                        df.loc[idx, 'dpe_match_confidence'] = confidence
                        
                        total_matched += 1
                        
                        # Log information about match
                        if total_matched % 10 == 0 or total_matched < 10:
                            self.logger.info(
                                f"Match found: '{property_address}' -> '{validated_match.get('Adresse_brute', '')}' "
                                f"(distance: {validated_match['distance_m']:.1f}m, confidence: {confidence})"
                            )
                
                self.logger.info(f"Found matches for {properties_with_matches}/{properties_count} properties for {location_type}: {location_id}")
            
            # Remove temporary columns
            if 'address_matching' in df.columns:
                df = df.drop(columns=['address_matching'])
            if 'address_components' in df.columns:
                df = df.drop(columns=['address_components'])
            
            # Convert construction_year to integer
            df['construction_year'] = pd.to_numeric(df['construction_year'], errors='coerce')
            
            # Final statistics
            match_percentage = (total_matched / initial_count) * 100 if initial_count > 0 else 0
            self.logger.info(f"DPE enrichment completed: {total_matched}/{initial_count} properties enriched ({match_percentage:.1f}%)")
            
            # Save result
            return self.save_csv(df)
            
        except Exception as e:
            self.logger.error(f"Error during DPE enrichment: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def group_properties_by_location(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        Group properties by INSEE code and postal code for more complete matching.
        
        Args:
            df: DataFrame with properties
            
        Returns:
            Dict mapping location IDs to groups
        """
        location_groups = {}
        
        # First try to group by INSEE code (preferred)
        if 'insee_code' in df.columns:
            insee_groups = df.groupby('insee_code')
            for insee_code, group in insee_groups:
                if pd.isna(insee_code) or not insee_code:
                    continue
                location_groups[str(insee_code)] = {
                    'dataframe': group,
                    'type': 'insee'
                }
        
        # Then try to group by postal code for properties without INSEE code
        if 'postal_code' in df.columns:
            # Get properties not already grouped by INSEE
            if 'insee_code' in df.columns:
                ungrouped = df[df['insee_code'].isna() | (df['insee_code'] == '')]
            else:
                ungrouped = df
                
            postal_groups = ungrouped.groupby('postal_code')
            for postal_code, group in postal_groups:
                if pd.isna(postal_code) or not postal_code:
                    continue
                # Only add if not already grouped by INSEE
                if str(postal_code) not in location_groups:
                    location_groups[str(postal_code)] = {
                        'dataframe': group,
                        'type': 'postal'
                    }
        
        return location_groups
    
    def get_cached_or_fetch_dpe_data(self, location_id: str, location_info: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Get DPE data from cache or fetch from API.
        
        Args:
            location_id: Location ID (INSEE code or postal code)
            location_info: Dict with location information
            
        Returns:
            DataFrame with DPE data or None if not found
        """
        # Check cache
        cache_file = os.path.join(self.dpe_cache_dir, f"dpe_{location_id}.csv")
        
        if os.path.exists(cache_file):
            # Check file age
            file_age = time.time() - os.path.getmtime(cache_file)
            # If file is older than 30 days (2592000 seconds)
            if file_age > 2592000:
                self.logger.info(f"DPE cache for {location_id} is outdated, updating...")
                dpe_data = self.fetch_dpe_data(location_info)
                if dpe_data is not None and not dpe_data.empty:
                    dpe_data.to_csv(cache_file, index=False)
            else:
                # Load from cache
                dpe_data = pd.read_csv(cache_file, low_memory=False)
                # Clean data before use
                dpe_data = self.sanitize_cache_data(dpe_data)
                self.logger.info(f"Loaded {len(dpe_data)} DPEs from cache for {location_id}")
        else:
            # Fetch DPE data for this location
            dpe_data = self.fetch_dpe_data(location_info)
            
            if dpe_data is not None and not dpe_data.empty:
                # Save to cache
                dpe_data.to_csv(cache_file, index=False)
        
        return dpe_data
    
    def fetch_dpe_data(self, location_info: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Fetch DPE data from all APIs using multiple lookup methods.
        
        Args:
            location_info: Dict with location details
            
        Returns:
            DataFrame with DPE data or None if not found
        """
        all_data = []
        
        # API priority (newest first)
        api_priority = [
            "EXISTING_BUILDINGS_NEW",  # Existing buildings (since July 2021)
            "NEW_BUILDINGS_NEW",       # New buildings (since July 2021)
            "EXISTING_BUILDINGS_OLD",  # Existing buildings (before July 2021)
            "TERTIARY_NEW",            # Tertiary buildings (since July 2021)
            "TERTIARY_OLD"             # Tertiary buildings (before July 2021)
        ]
        
        # Minimum DPEs we want before stopping
        min_dpe_threshold = 200
        
        # Query strategies in order of priority
        query_strategies = []
        
        # Strategy 1: INSEE code (if available)
        if location_info.get('insee_code'):
            query_strategies.append({
                'field_type': 'insee',
                'value': location_info['insee_code'],
                'description': 'INSEE Code'
            })
        
        # Strategy 2: Postal code (if available)
        if location_info.get('postal_code'):
            query_strategies.append({
                'field_type': 'zipcode',
                'value': location_info['postal_code'],
                'description': 'Postal Code'
            })
        
        # Strategy 3: City name + postal code (if both available)
        if location_info.get('city_name') and location_info.get('postal_code'):
            query_strategies.append({
                'field_type': 'city',
                'value': location_info['city_name'],
                'postal_code': location_info['postal_code'],
                'description': 'City Name'
            })
        
        # Try each API with each strategy
        for api_name in api_priority:
            # Check if we have enough data already
            if len(all_data) > min_dpe_threshold:
                self.logger.info(f"Already have {len(all_data)} DPEs, sufficient for enrichment. Stopping queries.")
                break
                
            api_info = self.DPE_APIS[api_name]
            
            for strategy in query_strategies:
                # Skip if we already have enough data
                if len(all_data) > min_dpe_threshold:
                    break
                
                field_type = strategy['field_type']
                search_value = strategy['value']
                
                # Determine the right field to search in
                if field_type == 'insee':
                    search_field = api_info['insee_field']
                elif field_type == 'zipcode':
                    search_field = api_info['zipcode_field']
                elif field_type == 'city':
                    search_field = api_info['city_field']
                    # For city search, we also filter by postal code
                    postal_filter = strategy.get('postal_code')
                else:
                    continue  # Skip unknown field types
                
                # Query the API
                results = self.query_dpe_api_with_pagination(
                    search_value, 
                    api_info["url"], 
                    search_field,
                    strategy["description"],
                    extra_filters={api_info['zipcode_field']: postal_filter} if field_type == 'city' and 'postal_code' in strategy else None
                )
                
                if results:
                    self.logger.info(f"Found {len(results)} DPEs via {api_name} with {strategy['description']}: {search_value}")
                    all_data.extend(results)
        
        # Process the collected data
        if all_data:
            # Convert to DataFrame
            df = pd.DataFrame(all_data)
            
            # Reset index to avoid duplication problems
            df = df.reset_index(drop=True)
            
            # Check for and handle duplicate columns
            if df.columns.duplicated().any():
                self.logger.warning("Detected duplicate columns in DPE data")
                # Keep only the first occurrence of each duplicate column
                df = df.loc[:, ~df.columns.duplicated()]
            
            # Standardize field names
            for api_field, std_field in self.ADDRESS_FIELDS.items():
                if api_field in df.columns:
                    df.rename(columns={api_field: std_field}, inplace=True)
            
            for api_field, std_field in self.DPE_FIELDS.items():
                if api_field in df.columns:
                    df.rename(columns={api_field: std_field}, inplace=True)
            
            # Rename or create a standard address column
            if 'address_raw' in df.columns:
                df.rename(columns={'address_raw': 'Adresse_brute'}, inplace=True)
            elif not 'Adresse_brute' in df.columns:
                # Find an alternative address column
                address_cols = [col for col in df.columns if 'adresse' in col.lower() or 'address' in col.lower()]
                if address_cols:
                    df.rename(columns={address_cols[0]: 'Adresse_brute'}, inplace=True)
                else:
                    # Create an address from components
                    components = []
                    for field in ['numero_voie_ban', 'nom_rue_ban', 'code_postal_ban', 'nom_commune_ban']:
                        if field in df.columns:
                            components.append(field)
                    
                    if components:
                        df['Adresse_brute'] = df[components].astype(str).apply(lambda x: ' '.join(x.dropna()), axis=1)
                    else:
                        df['Adresse_brute'] = 'Address not available'
            
            # Find geopoint column if available
            for geopoint_field in self.GEOPOINT_FIELDS:
                if geopoint_field in df.columns:
                    df.rename(columns={geopoint_field: '_geopoint'}, inplace=True)
                    break
            
            # Deduplicate on DPE number if available
            if 'dpe_number' in df.columns:
                df = df.drop_duplicates(subset=['dpe_number'])
                self.logger.info(f"Total after deduplication: {len(df)} DPEs")
            
            # Limit to 10000 results max to avoid memory issues
            if len(df) > 10000:
                self.logger.warning(f"Too many results, limiting to 10000")
                df = df.head(10000)
            
            # Reset index again after all transformations
            return df.reset_index(drop=True)
        else:
            self.logger.warning(f"No DPE data found")
            return None
    
    def query_dpe_api_with_pagination(self, search_value: str, api_url: str, 
                                     search_field: str, search_label: str,
                                     extra_filters: Dict[str, str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Query DPE API with pagination to handle 9999 result limit.
        
        Args:
            search_value: Value to search for
            api_url: API URL
            search_field: Field to search in
            search_label: Label for the field (for logging)
            extra_filters: Additional filters to apply
            
        Returns:
            List of DPEs or None if failed
        """
        all_results = []
        page = 1
        has_more = True
        
        # API limitation: size * page <= 10000
        # For first pages, we can use larger batch size
        # For later pages, we need to reduce the size
        max_page_size = self.API_BATCH_SIZE
        
        while has_more:
            try:
                # Adjust batch size to respect the limit
                if page * max_page_size > 10000:
                    # Calculate maximum possible size for this page
                    if max_page_size <= 0:
                        self.logger.warning(f"Pagination limit reached (10000) for {search_label} {search_value}")
                        break
                else:
                    current_page_size = max_page_size
                
                # Build query parameters
                params = {
                    "size": current_page_size,
                    "page": page,
                    "q": search_value,
                    "q_fields": search_field
                }
                
                # Add any extra filters
                if extra_filters:
                    for field, value in extra_filters.items():
                        if value:
                            # This is a hack but it works for the ADEME API - add an additional search filter
                            params["q"] = f"{params['q']} {value}"
                            params["q_fields"] = f"{params['q_fields']},{field}"
                
                self.logger.info(f"Querying API for {search_label} {search_value} (page {page}, size {current_page_size})")
                
                # Try multiple times in case of temporary error
                for retry in range(self.MAX_RETRIES):
                    try:
                        response = requests.get(api_url, params=params, timeout=60)
                        break
                    except requests.exceptions.RequestException as e:
                        if retry < self.MAX_RETRIES - 1:
                            self.logger.warning(f"Temporary error during API request: {str(e)}. Retry {retry+1}/{self.MAX_RETRIES}")
                            time.sleep(self.RETRY_DELAY * (retry + 1))
                        else:
                            raise
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "results" in data:
                        results = data["results"]
                        all_results.extend(results)
                        
                        # Check total and if there's more data
                        total_results = data.get("total", 0)
                        
                        self.logger.info(f"Received {len(results)} results. Total reported: {total_results}")
                        
                        if total_results >= 9999:
                            # If total is 9999 or more, there's probably more data (API limitation)
                            has_more = len(results) == current_page_size
                            self.logger.warning(f"9999 result limit reached for {search_label} {search_value}, "
                                              f"page {page} with {len(results)} results. Continuing pagination...")
                        else:
                            # Otherwise, continue until we've fetched all results
                            received_so_far = len(all_results)
                            has_more = received_so_far < total_results
                            if has_more:
                                self.logger.info(f"Total: {total_results}, received: {received_so_far}, more: {has_more}")
                    else:
                        has_more = False
                else:
                    self.logger.warning(f"API error ({response.status_code}) for {search_label} {search_value}")
                    self.logger.warning(f"Response: {response.text}")
                    has_more = False
                
                # Next page
                page += 1
                
                # Pause to avoid overloading the API
                time.sleep(0.5)
                
                # Safety limit: no more than 15 pages or 20000 results
                if page > 15 or len(all_results) >= 20000:
                    self.logger.warning(f"Pagination limit reached for {search_label} {search_value}, stopping.")
                    has_more = False
                
            except Exception as e:
                self.logger.warning(f"Error querying DPE API: {str(e)}")
                has_more = False
        
        return all_results
    
    def parse_address(self, address: str) -> Dict[str, Any]:
        """
        Parse an address into components with focus on street number.
        
        Args:
            address: Raw address string
            
        Returns:
            Dict with parsed components
        """
        if not isinstance(address, str) or not address or address.lower() == 'nan':
            return {"number": None, "street": "", "city": ""}
        
        # Basic normalization
        address = address.upper()
        address = unicodedata.normalize('NFKD', address).encode('ASCII', 'ignore').decode('utf-8')
        
        # Extract street number - multiple patterns
        number_match = re.search(r'^(\d+\s*[A-Z]?)[\s,]', address)
        number = number_match.group(1).strip() if number_match else None
        
        # Remove the number from the address for further processing
        if number_match:
            address = address[len(number_match.group(0)):].strip()
        
        # Try to separate street from city
        parts = address.split(',')
        if len(parts) > 1:
            street = parts[0].strip()
            city = parts[1].strip()
        else:
            # Alternative splitting logic - look for postal code
            postal_match = re.search(r'\b\d{5}\b', address)
            if postal_match:
                split_point = postal_match.start()
                street = address[:split_point].strip()
                city = address[split_point:].strip()
            else:
                street = address
                city = ""
        
        return {
            "number": number,
            "street": street,
            "city": city
        }
    
    def validate_street_number_match(self, property_number: Optional[str], dpe_number: Optional[str]) -> bool:
        """
        Validate if two street numbers can be considered a match.
        
        Args:
            property_number: Number from property address
            dpe_number: Number from DPE address
            
        Returns:
            bool: True if numbers match, False otherwise
        """
        # If either number is missing, no strict validation possible
        if not property_number or not dpe_number:
            return False
        
        # Clean the numbers (remove non-digit parts)
        property_digits = re.sub(r'[^0-9]', '', property_number)
        dpe_digits = re.sub(r'[^0-9]', '', dpe_number)
        
        # Exact match
        if property_digits == dpe_digits:
            return True
        
        # Allow adjacent numbers (±2) for possible data entry errors
        try:
            p_num = int(property_digits)
            d_num = int(dpe_digits)
            if abs(p_num - d_num) <= 2:
                return True
        except ValueError:
            pass
        
        return False
    
    def normalize_address_for_matching(self, address: str) -> str:
        """
        Normalize address for matching.
        
        Args:
            address: Address to normalize
            
        Returns:
            Normalized address
        """
        if not isinstance(address, str) or not address or address.lower() == 'nan':
            return ""
        
        # Convert to uppercase
        address = address.upper()
        
        # Remove accents
        address = unicodedata.normalize('NFKD', address).encode('ASCII', 'ignore').decode('utf-8')
        
        # Remove parentheses and their content
        address = re.sub(r'\([^)]*\)', '', address)
        
        # Remove punctuation
        address = re.sub(r'[^\w\s]', ' ', address)
        
        # Normalize common words
        address = address.replace(" AVENUE ", " AV ")
        address = address.replace(" BOULEVARD ", " BD ")
        address = address.replace(" PLACE ", " PL ")
        address = address.replace(" ALLEE ", " AL ")
        address = address.replace(" IMPASSE ", " IMP ")
        
        # Remove postal codes to avoid confusion
        address = re.sub(r'\d{5}', '', address)
        
        # Remove multiple spaces
        address = re.sub(r'\s+', ' ', address).strip()
        
        return address
    
    def prepare_dpe_data_for_matching(self, dpe_data: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Prepare DPE data for matching by normalizing addresses and extracting components.
        
        Args:
            dpe_data: DataFrame with DPE data
            
        Returns:
            Prepared DataFrame or None if failed
        """
        if dpe_data is None or dpe_data.empty:
            return None
        
        try:
            # Reset index to avoid duplication problems
            dpe_data = dpe_data.reset_index(drop=True)
            
            # Check for Adresse_brute column
            if 'Adresse_brute' not in dpe_data.columns:
                self.logger.warning(f"Adresse_brute column missing in DPE data")
                # Try to find another address column
                address_cols = [col for col in dpe_data.columns if 'adresse' in col.lower() or 'address' in col.lower()]
                if address_cols:
                    self.logger.info(f"Using {address_cols[0]} column for address matching")
                    dpe_data = dpe_data.reset_index(drop=True)
                    dpe_data['Adresse_brute'] = dpe_data[address_cols[0]].fillna('').astype(str)
                else:
                    self.logger.warning(f"No address column found, matching impossible")
                    return None
            
            # Handle NaN/NaT values
            dpe_data['Adresse_brute'] = dpe_data['Adresse_brute'].fillna('').astype(str)
            
            # Check for duplicate columns again
            if dpe_data.columns.duplicated().any():
                self.logger.warning("Removing duplicate columns before address matching")
                dpe_data = dpe_data.loc[:, ~dpe_data.columns.duplicated()]
            
            # Normalize addresses for matching
            self.logger.info(f"Normalizing DPE addresses")
            address_matching = []
            address_components = []
            
            for adr in dpe_data['Adresse_brute']:
                address_matching.append(self.normalize_address_for_matching(adr))
                address_components.append(self.parse_address(adr))
                
            dpe_data['address_matching'] = address_matching
            dpe_data['address_components'] = address_components
            
            return dpe_data
            
        except Exception as e:
            self.logger.error(f"Error preparing DPE data: {str(e)}")
            return None
        
    def find_text_match_candidates(self, property_address: str, property_components: Dict[str, Any], 
                             dpe_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Find potential DPE matches by text similarity with strict number validation.
        
        Args:
            property_address: Normalized property address
            property_components: Parsed property address components
            dpe_data: DataFrame with DPE data
            
        Returns:
            List of candidate matches
        """
        if property_address == "" or dpe_data.empty:
            return []
        
        candidates = []
        property_number = property_components.get('number')
        
        # Skip properties without street numbers if strict validation enabled
        if self.STRICT_NUMBER_VALIDATION and not property_number:
            self.logger.debug(f"Skipping property without street number: {property_address}")
            return []
        
        # Matching for each DPE
        for _, dpe_row in dpe_data.iterrows():
            dpe_address = dpe_row['address_matching']
            if not isinstance(dpe_address, str) or dpe_address == "":
                continue
            
            # Get DPE address components
            dpe_components = dpe_row['address_components']
            dpe_number = dpe_components.get('number')
            
            # Check for number match if strict validation is enabled
            if self.STRICT_NUMBER_VALIDATION:
                if not self.validate_street_number_match(property_number, dpe_number):
                    continue
            
            # Calculate text similarity
            similarity = difflib.SequenceMatcher(None, property_address, dpe_address).ratio()
            
            # Apply appropriate threshold
            threshold = self.SIMILARITY_THRESHOLD
            if not property_number or not dpe_number:
                threshold = self.HIGH_SIMILARITY_THRESHOLD
                
            if similarity >= threshold:
                # Create a copy of all DPE data for this match
                candidate = dpe_row.to_dict()
                
                # Extract/transform specific fields for database compatibility
                
                # 1. DPE Number
                if 'dpe_number' not in candidate and 'numero_dpe' in candidate:
                    candidate['dpe_number'] = candidate['numero_dpe']
                
                # 2. DPE Date (try multiple possible fields)
                if 'dpe_date' not in candidate:
                    for date_field in ['date_etablissement_dpe', 'date_visite_diagnostiqueur', 'date_derniere_modification_dpe']:
                        if date_field in candidate and pd.notna(candidate[date_field]):
                            candidate['dpe_date'] = candidate[date_field]
                            break
                
                # 3. Energy class
                if 'dpe_energy_class' not in candidate:
                    for class_field in ['classe_consommation_energie', 'etiquette_dpe']:
                        if class_field in candidate and pd.notna(candidate[class_field]):
                            candidate['dpe_energy_class'] = candidate[class_field]
                            break
                
                # 4. GES class
                if 'dpe_ges_class' not in candidate:
                    for class_field in ['classe_estimation_ges', 'etiquette_ges']:
                        if class_field in candidate and pd.notna(candidate[class_field]):
                            candidate['dpe_ges_class'] = candidate[class_field]
                            break
                
                # 5. Construction year
                if 'construction_year' not in candidate:
                    for year_field in ['annee_construction', 'periode_construction']:
                        if year_field in candidate and pd.notna(candidate[year_field]):
                            # Try to convert string period to year if needed
                            try:
                                candidate['construction_year'] = int(candidate[year_field])
                            except (ValueError, TypeError):
                                # Handle period descriptions by taking the midpoint or earliest year
                                if isinstance(candidate[year_field], str):
                                    year_match = re.search(r'(\d{4})', candidate[year_field])
                                    if year_match:
                                        candidate['construction_year'] = int(year_match.group(1))
                
                # Add similarity score to candidate
                candidate['similarity'] = similarity
                candidates.append(candidate)
        
        return candidates

    def extract_geopoint(self, candidate: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract latitude and longitude from _geopoint field.
        
        Args:
            candidate: DPE candidate with potential _geopoint field
            
        Returns:
            Tuple of (latitude, longitude) or (None, None) if not available
        """
        if '_geopoint' in candidate and candidate['_geopoint']:
            try:
                # _geopoint format is typically "lat,lon"
                coords = candidate['_geopoint'].split(',')
                if len(coords) == 2:
                    return float(coords[0]), float(coords[1])
            except (ValueError, IndexError):
                pass
        return None, None
    
    def calculate_geo_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate geographic distance between two points in kilometers.
        Uses Haversine formula to calculate distance on a sphere.
        
        Args:
            lat1: Latitude of point 1
            lon1: Longitude of point 1
            lat2: Latitude of point 2
            lon2: Longitude of point 2
            
        Returns:
            Distance in kilometers
        """
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Earth radius in km
        earth_radius = 6371.0
        
        # Coordinate differences
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = earth_radius * c
        
        return distance
    
    def find_best_geo_match(self, property_lat: float, property_lon: float, 
                           candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find the best match among candidates using 20m proximity threshold.
        
        Args:
            property_lat: Property latitude
            property_lon: Property longitude
            candidates: List of DPE candidates
            
        Returns:
            Best match or None if no valid match found
        """
        if not candidates:
            return None
            
        best_match = None
        best_distance = float('inf')
        
        for candidate in candidates:
            # Try to get coordinates from _geopoint first
            dpe_lat, dpe_lon = self.extract_geopoint(candidate)
            
            # Skip if no coordinates
            if dpe_lat is None or dpe_lon is None:
                continue
            
            # Calculate distance
            distance = self.calculate_geo_distance(property_lat, property_lon, dpe_lat, dpe_lon)
            
            # Check if within threshold (20m = 0.02km)
            if distance <= self.PROXIMITY_THRESHOLD and distance < best_distance:
                candidate['distance'] = distance
                candidate['distance_m'] = distance * 1000  # Convert to meters for logging
                best_distance = distance
                best_match = candidate
        
        return best_match
    
    def calculate_match_confidence(self, match_data: Dict[str, Any]) -> int:
        """
        Calculate confidence score for a DPE match.
        
        Args:
            match_data: Dict with match information
            
        Returns:
            Confidence score (0-100)
        """
        base_score = 70
        
        # Text similarity factor (0-25 points)
        similarity = match_data.get('similarity', 0)
        text_score = min(int(similarity * 25), 25)
        
        # Geographic proximity factor (0-40 points)
        distance_m = match_data.get('distance_m', 1000)
        if distance_m < 5:
            geo_score = 40
        elif distance_m < 10:
            geo_score = 35
        elif distance_m < 15:
            geo_score = 25
        elif distance_m < 20:
            geo_score = 15
        else:
            geo_score = 0
        
        # Street number match factor (0-25 points)
        property_number = match_data['property_components'].get('number')
        dpe_number = match_data['dpe_components'].get('number')
        
        if property_number and dpe_number:
            if property_number == dpe_number:
                number_score = 25  # Exact match
            elif self.validate_street_number_match(property_number, dpe_number):
                number_score = 15  # Similar number
            else:
                number_score = 0
        else:
            number_score = 0  # No numbers to compare
        
        # Calculate total score
        total_score = base_score + text_score + geo_score + number_score
        
        # Cap at 100
        return min(total_score, 100)
    
    def save_sample_dpe(self, location_id: str, dpe_data: pd.DataFrame):
        """
        Save sample DPEs for debugging.
        
        Args:
            location_id: Location ID
            dpe_data: DataFrame with DPE data
        """
        if dpe_data.empty or len(dpe_data) == 0:
            return
            
        try:
            # Ensure index is unique
            dpe_data_copy = dpe_data.copy().reset_index(drop=True)
            
            # Check for duplicate columns
            if dpe_data_copy.columns.duplicated().any():
                self.logger.warning("Removing duplicate columns before creating sample")
                dpe_data_copy = dpe_data_copy.loc[:, ~dpe_data_copy.columns.duplicated()]
            
            # Select samples
            sample_size = min(self.DEBUG_SAMPLE_SIZE, len(dpe_data_copy))
            samples = dpe_data_copy.sample(sample_size)
            
            # Create JSON file for samples
            samples_file = os.path.join(self.debug_dir, f"dpe_samples_{location_id}.json")
            
            # Convert and save
            samples_dict = samples.to_dict(orient='records')
            
            with open(samples_file, 'w', encoding='utf-8') as f:
                json.dump(samples_dict, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Saved {sample_size} DPE samples to {samples_file}")
            
            # Log sample addresses
            for i, sample in enumerate(samples_dict):
                self.logger.info(f"DPE Sample {i+1}: Adresse brute: '{sample.get('Adresse_brute', '')}'")
                
        except Exception as e:
            self.logger.warning(f"Failed to save DPE samples: {str(e)}")

    def sanitize_cache_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and prepare data from cache.
        
        Args:
            df: DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        # Check if DataFrame is empty
        if df.empty:
            return df
            
        # Reset index to avoid duplication problems
        df = df.reset_index(drop=True)
        
        # Normalize column names to avoid duplicates
        if df.columns.duplicated().any():
            # Keep only the first occurrence of each duplicate column
            df = df.loc[:, ~df.columns.duplicated()]
            self.logger.warning("Duplicate columns removed from cache data")
        
        # Ensure we have an Adresse_brute column
        if 'Adresse_brute' not in df.columns:
            address_cols = [col for col in df.columns if 'adresse' in col.lower() or 'address' in col.lower()]
            if address_cols:
                self.logger.info(f"Using {address_cols[0]} as Adresse_brute")
                df['Adresse_brute'] = df[address_cols[0]]
            else:
                self.logger.warning("No address column found in cache data")
                # Create dummy column
                df['Adresse_brute'] = "Address not available"
        
        # Clean address column
        df['Adresse_brute'] = df['Adresse_brute'].fillna('').astype(str)
        
        # Limit to 10000 results max to avoid memory issues
        if len(df) > 10000:
            self.logger.warning(f"Too many results in cache, limiting to 10000")
            df = df.head(10000)
        
        return df

if __name__ == "__main__":
    import argparse
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Property enrichment with DPE data")
    parser.add_argument("--input", help="Input CSV file", required=True)
    parser.add_argument("--output", help="Output CSV file", required=False)
    parser.add_argument("--cache", help="DPE cache directory", required=False)
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_dpe_enriched.csv")
    cache_dir = args.cache or "data/cache/dpe"
    
    # Run processor
    enricher = DPEEnrichmentService(args.input, output, cache_dir)
    success = enricher.process()
    
    exit(0 if success else 1)