#!/usr/bin/env python3
"""
Script de test pour le scraper TrackImmo.
"""

import argparse
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au sys.path pour l'importation
sys.path.insert(0, str(Path(__file__).parent.parent))

from trackimmo.modules.scraper import ImmoDataScraper

def main():
    """
    Script principal pour tester le scraper.
    """
    parser = argparse.ArgumentParser(description="Test the TrackImmo scraper")
    parser.add_argument("--city", required=True, help="City name")
    parser.add_argument("--postal_code", required=True, help="Postal code")
    parser.add_argument("--output", default=None, help="Output CSV file")
    parser.add_argument("--start_date", default="01/2023", help="Start date (MM/YYYY)")
    parser.add_argument("--end_date", default="06/2024", help="End date (MM/YYYY)")
    parser.add_argument("--types", default="house,apartment", 
                        help="Property types (comma-separated: house,apartment,land,commercial,other)")
    
    args = parser.parse_args()
    
    # Convertir les types de propriétés en liste
    property_types = args.types.split(",")
    
    print(f"Testing scraper for {args.city} ({args.postal_code})")
    print(f"Property types: {property_types}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    
    # Créer et exécuter le scraper
    scraper = ImmoDataScraper(output_dir="test_output")
    
    try:
        result_file = scraper.scrape_city(
            city_name=args.city,
            postal_code=args.postal_code,
            property_types=property_types,
            start_date=args.start_date,
            end_date=args.end_date,
            output_file=args.output
        )
        
        print(f"\nScraping completed successfully!")
        print(f"Results saved to: {result_file}")
        
    except Exception as e:
        print(f"\nError during scraping: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())