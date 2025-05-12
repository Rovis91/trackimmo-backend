#!/usr/bin/env python3
"""
Script de test pour le module d'enrichissement TrackImmo.
"""

import argparse
import os
import sys
import logging
import shutil
from pathlib import Path

# Ajouter le répertoire parent au sys.path pour l'importation
sys.path.insert(0, str(Path(__file__).parent.parent))

from trackimmo.modules.enrichment import EnrichmentOrchestrator

def setup_test_environment():
    """
    Prépare l'environnement de test.
    """
    # Créer les répertoires nécessaires
    data_dir = "data"
    os.makedirs(os.path.join(data_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "processing"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "output"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "cache", "dpe"), exist_ok=True)
    
    return data_dir

def main():
    """
    Script principal pour tester le module d'enrichissement.
    """
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Test the TrackImmo enrichment module")
    parser.add_argument("--input", default="test_output/Lille_59000_20250512_142519.csv", 
                        help="Input CSV file (default: test_output/Lille_59000_20250512_142519.csv)")
    parser.add_argument("--start_stage", type=int, default=1, help="Starting stage (1-6)")
    parser.add_argument("--end_stage", type=int, default=6, help="Ending stage (1-6)")
    parser.add_argument("--debug", action="store_true", help="Debug mode (keep intermediate files)")
    parser.add_argument("--db_url", default="postgresql://user:password@localhost/trackimmo", 
                        help="Database connection URL")
    
    args = parser.parse_args()
    
    # Vérifier si le fichier d'entrée existe
    if not os.path.exists(args.input):
        print(f"Erreur: Le fichier d'entrée '{args.input}' n'existe pas.")
        return 1
    
    print(f"Testing enrichment module with data from {args.input}")
    print(f"Running stages {args.start_stage} to {args.end_stage}")
    
    # Préparer l'environnement de test
    data_dir = setup_test_environment()
    
    # Configurer l'orchestrateur
    config = {
        "data_dir": data_dir,
        "db_url": args.db_url
    }
    
    # Exécuter le processus d'enrichissement
    orchestrator = EnrichmentOrchestrator(config)
    
    try:
        success = orchestrator.run(
            input_file=args.input,
            start_stage=args.start_stage,
            end_stage=args.end_stage,
            debug=args.debug
        )
        
        if success:
            print("\nEnrichissement terminé avec succès!")
            if args.end_stage >= 6:
                print(f"Rapport d'intégration sauvegardé dans: {orchestrator.file_paths['integration_report']}")
        else:
            print("\nErreur lors de l'enrichissement.")
            return 1
        
    except Exception as e:
        print(f"\nException lors de l'exécution: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 