"""
Classe principale du scraper ImmoData.
Coordonne le processus de scraping de bout en bout.
"""

import os
import asyncio
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from trackimmo.utils.logger import get_logger
from .geo_divider import GeoDivider
from .url_generator import UrlGenerator
from .browser_manager import BrowserManager

logger = get_logger(__name__)

class ImmoDataScraper:
    """
    Scraper pour ImmoData. Extrait les propriétés immobilières
    pour une ville donnée en utilisant un découpage géographique.
    """
    
    def __init__(self, output_dir: str = "data/scraped"):
        """
        Initialise le scraper.
        
        Args:
            output_dir: Répertoire pour les fichiers de sortie
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.geo_divider = GeoDivider()
        self.url_generator = UrlGenerator()
        
        logger.info(f"ImmoDataScraper initialisé (dossier de sortie: {self.output_dir})")
    
    def scrape_city(
        self,
        city_name: str,
        postal_code: str,
        property_types: Optional[List[str]] = None,
        start_date: str = "01/2014",
        end_date: str = "06/2024",
        output_file: Optional[str] = None
    ) -> str:
        """
        Extrait toutes les propriétés pour une ville donnée.
        
        Args:
            city_name: Nom de la ville
            postal_code: Code postal
            property_types: Types de propriétés ["house", "apartment"]
            start_date: Date de début (MM/YYYY)
            end_date: Date de fin (MM/YYYY)
            output_file: Chemin du fichier CSV de sortie
        
        Returns:
            str: Chemin du fichier CSV généré
        """
        logger.info(f"Début du scraping pour {city_name} ({postal_code})")
        
        if not property_types:
            property_types = ["house", "apartment"]
        
        # Déterminer le nom du fichier de sortie
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"{city_name}_{postal_code}_{timestamp}.csv"
        else:
            output_file = Path(output_file)
        
        # Exécuter le scraping de manière asynchrone
        all_properties = asyncio.run(self._scrape_city_async(
            city_name=city_name,
            postal_code=postal_code,
            property_types=property_types,
            start_date=start_date,
            end_date=end_date
        ))
        
        # Dédupliquer les propriétés
        unique_properties = self._deduplicate_properties(all_properties)
        logger.info(f"Extraction terminée: {len(unique_properties)} propriétés uniques extraites")
        
        # Exporter vers CSV
        self._export_to_csv(unique_properties, output_file)
        logger.info(f"Données exportées vers {output_file}")
        
        return str(output_file)
    
    async def _scrape_city_async(
        self,
        city_name: str,
        postal_code: str,
        property_types: List[str],
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Implémentation asynchrone du scraping.
        
        Returns:
            List[Dict]: Liste des propriétés extraites
        """
        # 1. Découper la ville en rectangles géographiques
        rectangles = self.geo_divider.divide_city_area(city_name, postal_code)
        logger.info(f"Ville divisée en {len(rectangles)} rectangles")
        
        # 2. Générer les URLs pour chaque rectangle
        urls = self.url_generator.generate_urls(
            rectangles, property_types, start_date, end_date
        )
        logger.info(f"Génération de {len(urls)} URLs")
        
        # 3. Extraire les propriétés via le navigateur
        browser_manager = BrowserManager()
        properties = await browser_manager.extract_properties(urls)
        logger.info(f"Extraction terminée: {len(properties)} propriétés extraites")
        
        return properties
    
    def _deduplicate_properties(self, properties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Élimine les doublons dans les propriétés extraites.
        
        Args:
            properties: Liste des propriétés extraites
        
        Returns:
            List[Dict]: Liste des propriétés dédupliquées
        """
        # Créer un DataFrame pour faciliter la déduplication
        if not properties:
            return []
        
        df = pd.DataFrame(properties)
        
        # Identifier les colonnes essentielles pour la déduplication
        duplicate_keys = ["address", "city", "price", "surface", "rooms", "sale_date"]
        available_keys = [key for key in duplicate_keys if key in df.columns]
        
        if not available_keys:
            logger.warning("Impossible de dédupliquer: colonnes essentielles manquantes")
            return properties
        
        # Dédupliquer sur les colonnes essentielles
        df_unique = df.drop_duplicates(subset=available_keys)
        logger.info(f"Déduplication: {len(df) - len(df_unique)} doublons supprimés")
        
        return df_unique.to_dict("records")
    
    def _export_to_csv(self, properties: List[Dict[str, Any]], output_file: Path) -> None:
        """
        Exporte les propriétés vers un fichier CSV.
        
        Args:
            properties: Liste des propriétés
            output_file: Chemin du fichier de sortie
        """
        if not properties:
            logger.warning("Aucune propriété à exporter")
            # Créer un fichier vide pour indiquer que le processus s'est terminé
            with open(output_file, "w") as f:
                f.write("adresse,ville,code_postal,prix,surface,pieces,date_vente,url\n")
            return
        
        # Créer le DataFrame et réorganiser les colonnes
        df = pd.DataFrame(properties)
        
        # Réorganiser/renommer les colonnes si elles existent
        column_mapping = {
            "address": "adresse",
            "city": "ville",
            "postal_code": "code_postal",
            "price": "prix",
            "surface": "surface",
            "rooms": "pieces",
            "sale_date": "date_vente",
            "property_url": "url"
        }
        
        # Appliquer le mapping seulement pour les colonnes existantes
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        if existing_columns:
            df = df.rename(columns=existing_columns)
        
        # Définir l'ordre des colonnes principal (utilise uniquement les colonnes existantes)
        ordered_columns = [v for k, v in column_mapping.items() 
                          if k in df.columns and v in df.columns]
        
        # Ajouter les colonnes supplémentaires qui n'étaient pas dans le mapping
        other_columns = [col for col in df.columns if col not in ordered_columns]
        final_columns = ordered_columns + other_columns
        
        # Réorganiser et sauvegarder
        df = df[final_columns]
        df.to_csv(output_file, index=False)