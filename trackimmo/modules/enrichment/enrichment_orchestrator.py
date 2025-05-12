import os
import logging
import argparse
from typing import Dict, Any, Optional, List

# Importer les processeurs
from .processor_base import ProcessorBase
from .data_normalizer import DataNormalizer
from .city_resolver import CityResolver
from .geocoding_service import GeocodingService
from .dpe_enrichment import DPEEnrichmentService
from .price_estimator import PriceEstimationService
from .db_integrator import DBIntegrationService

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