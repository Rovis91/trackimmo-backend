import os
import logging
import argparse
from typing import Dict, Any, Optional, List
import asyncio
import pandas as pd

# Importer les processeurs
from .processor_base import ProcessorBase
from .data_normalizer import DataNormalizer
from .city_resolver import CityResolver
from .geocoding_service import GeocodingService
from .dpe_enrichment import DPEEnrichmentService
from .price_estimator import PriceEstimationService
from .db_integrator import DBIntegrationService
from ..city_scraper.city_scraper import CityDataScraper
from trackimmo.modules.db_manager import DBManager

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
        
        # Initialize DBManager
        self.db_manager = DBManager()
    
    def run(self, input_file: str = None, start_stage: int = 1, end_stage: int = 7, debug: bool = False) -> bool:
        """
        Exécute le processus complet d'enrichissement.
        
        Args:
            input_file: Chemin du fichier d'entrée (CSV brut)
            start_stage: Étape de départ (1-7)
            end_stage: Étape finale (1-7)
            debug: Si True, sauvegarde les fichiers intermédiaires
            
        Returns:
            bool: True si l'exécution a réussi, False sinon
        """
        # Check if we're running in an async context
        try:
            import asyncio
            current_loop = asyncio.get_running_loop()
            is_async_context = True
        except RuntimeError:
            is_async_context = False
        
        if is_async_context:
            # We're in an async context, run async version
            return asyncio.create_task(self.run_async(input_file, start_stage, end_stage, debug))
        else:
            # We're not in an async context, use asyncio.run
            return asyncio.run(self.run_async(input_file, start_stage, end_stage, debug))
    
    async def run_async(self, input_file: str = None, start_stage: int = 1, end_stage: int = 7, debug: bool = False) -> bool:
        """
        Async version of the enrichment process.
        
        Args:
            input_file: Chemin du fichier d'entrée (CSV brut)
            start_stage: Étape de départ (1-7)
            end_stage: Étape finale (1-7)
            debug: Si True, sauvegarde les fichiers intermédiaires
            
        Returns:
            bool: True si l'exécution a réussi, False sinon
        """
        # Valider les étapes
        if start_stage < 1 or start_stage > 7:
            self.logger.error(f"Étape de départ invalide: {start_stage}")
            return False
            
        if end_stage < start_stage or end_stage > 7:
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
            output_path=self.file_paths['cities_resolved']
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
            output_path=self.file_paths['price_estimated']
        )
        
        db_integrator = DBIntegrationService(
            input_path=self.file_paths['price_estimated'],
            output_path=self.file_paths['integration_report']
        )
        
        # Exécuter les étapes selon la configuration
        stage_processors = [
            (1, "Normalisation des données", normalizer),
            (2, "Résolution des villes", city_resolver),
            (3, "Géocodage des adresses", geocoding_service),
            (4, "Enrichissement DPE", dpe_enrichment),
            (5, "Scraping des données de villes", self._scrape_city_data),
            (6, "Estimation des prix", price_estimator),
            (7, "Intégration en base de données", db_integrator)
        ]
        
        success = True
        
        for stage, name, processor in stage_processors:
            if start_stage <= stage <= end_stage:
                self.logger.info(f"Exécution de l'étape {stage}: {name}")
                
                # Handle async stages
                if stage == 5:  # City scraping stage (async)
                    stage_success = await processor()
                else:
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
            5: [],  # City scraping doesn't create intermediate files
            6: ['price_estimated']
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

    async def _scrape_city_data(self) -> bool:
        """
        Scrape city data (average prices) for all unique cities in the dataset.
        This step is necessary before price estimation.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import pandas as pd
            import asyncio
            
            # Load the geocoded data to get unique cities
            df = pd.read_csv(self.file_paths['dpe_enriched'])
            self.logger.info(f"Loading {len(df)} properties for city data extraction")
            
            # Get unique cities that have city_id
            unique_cities = df[df['city_id'].notna()][['city_name', 'postal_code', 'city_id']].drop_duplicates()
            self.logger.info(f"Found {len(unique_cities)} unique cities to scrape")
            
            if len(unique_cities) == 0:
                self.logger.warning("No cities with city_id found - skipping city scraping")
                return True
            
            # Initialize database connection
            db_manager = DBManager()
            city_scraper = CityDataScraper()
            
            scraped_count = 0
            skipped_count = 0
            
            with db_manager as db:
                supabase_client = db.get_client()
                
                for _, city_row in unique_cities.iterrows():
                    city_name = city_row['city_name']
                    postal_code = city_row['postal_code']
                    city_id = city_row['city_id']
                    
                    try:
                        # Check if city data already exists in database
                        existing_city = supabase_client.table("cities").select("*").eq("city_id", city_id).execute()
                        
                        if existing_city.data and len(existing_city.data) > 0:
                            city_data_existing = existing_city.data[0]
                            
                            # Check if city was scraped in the last year (365 days)
                            last_scraped = city_data_existing.get('last_scraped')
                            if last_scraped:
                                try:
                                    from datetime import datetime, timedelta
                                    # Handle different date formats
                                    if 'T' in last_scraped:
                                        last_scraped_date = datetime.fromisoformat(last_scraped.replace('Z', '+00:00'))
                                    else:
                                        last_scraped_date = datetime.fromisoformat(last_scraped)
                                    
                                    # Skip if scraped within the last year (365 days)
                                    days_since_scraped = (datetime.now() - last_scraped_date.replace(tzinfo=None)).days
                                    if days_since_scraped <= 365:
                                        self.logger.info(f"City {city_name} was scraped {days_since_scraped} days ago - skipping (less than 365 days)")
                                        skipped_count += 1
                                        continue
                                    else:
                                        self.logger.info(f"City {city_name} was scraped {days_since_scraped} days ago - needs update")
                                except (ValueError, TypeError) as e:
                                    self.logger.warning(f"Could not parse last_scraped date for {city_name}: {last_scraped} - {str(e)}")
                            
                            # Also check if we have price data (secondary check)
                            if (city_data_existing.get('house_price_avg') is not None or 
                                city_data_existing.get('apartment_price_avg') is not None) and not last_scraped:
                                self.logger.debug(f"City {city_name} already has price data but no last_scraped timestamp")
                        
                        # Scrape city data
                        self.logger.info(f"Scraping city data for {city_name} ({postal_code})")
                        city_data = await city_scraper.scrape_city(city_name, postal_code)  # Don't pass city_id as insee_code
                        
                        if city_data.get('status') == 'success':
                            # Update or insert city data
                            # Ensure data fits database constraints
                            postal_code_clean = postal_code[:5] if postal_code else None
                            department_clean = city_data.get('department', '')[:5] if city_data.get('department') else None
                            
                            self.logger.info(f"Debug database insert: postal_code='{postal_code_clean}' (len={len(postal_code_clean) if postal_code_clean else 0}), department='{department_clean}' (len={len(department_clean) if department_clean else 0})")
                            
                            city_record = {
                                'city_id': city_id,
                                'name': city_name,
                                'postal_code': postal_code_clean,
                                'insee_code': city_data.get('insee_code'),
                                'department': department_clean,
                                'region': city_data.get('region'),
                                'house_price_avg': city_data.get('house_price_avg'),
                                'apartment_price_avg': city_data.get('apartment_price_avg'),
                                'last_scraped': 'now()'
                            }
                            
                            # Upsert city data
                            result = supabase_client.table("cities").upsert(city_record).execute()
                            
                            if result.data:
                                scraped_count += 1
                                self.logger.info(f"Successfully scraped and saved data for {city_name}")
                            else:
                                self.logger.error(f"Failed to save city data for {city_name}")
                        else:
                            self.logger.warning(f"Failed to scrape city data for {city_name}: {city_data.get('error_message')}")
                        
                        # Add delay between requests
                        await asyncio.sleep(1.0)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing city {city_name}: {str(e)}")
                        continue
            
            self.logger.info(f"City scraping completed: {scraped_count} scraped, {skipped_count} skipped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during city data scraping: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def process(self, **kwargs) -> bool:
        """
        Process enrichment pipeline
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            bool: True if successful
        """
        batch_size = kwargs.get("batch_size", 1000)
        
        try:
            # Read the CSV
            self.logger.info("Reading CSV data...")
            df = pd.read_csv(self.file_paths['raw'])
            self.logger.info(f"Read {len(df)} rows from CSV")
            
            # Pre-filter out URLs that already exist in database to avoid duplicates
            df = await self._filter_existing_urls(df)
            if len(df) == 0:
                self.logger.info("All properties already exist in database, skipping enrichment")
                return True
            
            # Data normalization
            self.logger.info("Starting data normalization...")
            normalizer = DataNormalizer(self.file_paths['raw'], self.file_paths['normalized'])
            success = normalizer.process()
            if not success:
                self.logger.error("Data normalization failed")
                return False
            
            # City resolution
            self.logger.info("Starting city resolution...")
            city_resolver = CityResolver(normalizer.output_path, self.file_paths['cities_resolved'])
            success = await city_resolver.process()
            if not success:
                self.logger.error("City resolution failed")
                return False
            
            # Geocoding
            self.logger.info("Starting geocoding...")
            geocoding_service = GeocodingService(city_resolver.output_path, self.file_paths['geocoded'])
            success = geocoding_service.process(batch_size=batch_size)
            if not success:
                self.logger.error("Geocoding failed")
                return False
            
            # DPE enrichment
            self.logger.info("Starting DPE enrichment...")
            dpe_enrichment = DPEEnrichmentService(geocoding_service.output_path, self.file_paths['dpe_enriched'])
            success = await dpe_enrichment.process()
            if not success:
                self.logger.error("DPE enrichment failed")
                return False
            
            # Price estimation
            self.logger.info("Starting price estimation...")
            price_estimator = PriceEstimationService(self.file_paths['dpe_enriched'], self.file_paths['price_estimated'])
            success = price_estimator.process()
            if not success:
                self.logger.error("Price estimation failed")
                return False
            
            # Database integration
            self.logger.info("Starting database integration...")
            db_integrator = DBIntegrationService(self.file_paths['price_estimated'], self.file_paths['integration_report'])
            success = db_integrator.process(batch_size=batch_size)
            if not success:
                self.logger.error("Database integration failed")
                return False
            
            self.logger.info("Enrichment pipeline completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in enrichment pipeline: {str(e)}")
            return False
    
    async def _filter_existing_urls(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter out properties with URLs that already exist in the database.
        
        Args:
            df: DataFrame with properties
            
        Returns:
            pd.DataFrame: Filtered DataFrame without existing URLs
        """
        if 'source_url' not in df.columns or df['source_url'].isna().all():
            self.logger.warning("No source_url column found or all URLs are null, cannot filter existing URLs")
            return df
        
        # Get non-null URLs
        urls_to_check = df[df['source_url'].notna()]['source_url'].unique().tolist()
        if not urls_to_check:
            self.logger.warning("No valid URLs found for duplicate checking")
            return df
        
        self.logger.info(f"Checking for {len(urls_to_check)} existing URLs in database...")
        
        try:
            with self.db_manager as db:
                # Check URLs in batches to avoid query limits
                existing_urls = set()
                batch_size = 100
                
                for i in range(0, len(urls_to_check), batch_size):
                    batch_urls = urls_to_check[i:i+batch_size]
                    
                    # Query for existing URLs
                    response = db.get_client().table('addresses').select('immodata_url').in_('immodata_url', batch_urls).execute()
                    
                    if response.data:
                        batch_existing = {row['immodata_url'] for row in response.data if row['immodata_url']}
                        existing_urls.update(batch_existing)
                
                if existing_urls:
                    self.logger.info(f"Found {len(existing_urls)} URLs already in database, filtering them out")
                    # Filter out rows with existing URLs
                    df_filtered = df[~df['source_url'].isin(existing_urls)]
                    self.logger.info(f"Filtered from {len(df)} to {len(df_filtered)} properties ({len(df) - len(df_filtered)} duplicates removed)")
                    return df_filtered
                else:
                    self.logger.info("No existing URLs found, proceeding with all properties")
                    return df
                    
        except Exception as e:
            self.logger.warning(f"Could not check for existing URLs: {str(e)}, proceeding with all properties")
            return df


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
    parser.add_argument("--start", type=int, default=1, help="Étape de départ (1-7)")
    parser.add_argument("--end", type=int, default=7, help="Étape finale (1-7)")
    parser.add_argument("--debug", action="store_true", help="Mode debug (conserver les fichiers intermédiaires)")
    
    args = parser.parse_args()
    
    # Configurer l'orchestrateur
    config = {
        'data_dir': 'data'
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