"""
Générateur d'URLs pour le scraping ImmoData.
Crée les URLs paramétrées pour chaque zone géographique.
"""

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
import urllib.parse
from typing import List, Dict, Optional, Tuple

from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

class UrlGenerator:
    """
    Génère les URLs de recherche pour ImmoData.
    """
    
    def __init__(self):
        """
        Initialise le générateur d'URLs avec les paramètres par défaut.
        """
        self.base_url = "https://www.immo-data.fr/explorateur/transaction/recherche"
        
        # Mapping des types de propriétés
        self.property_type_mapping = {
            "house": "1",
            "apartment": "2",
            "land": "4",
            "commercial": "0",
            "other": "5"
        }
        
        # Noms des mois en français
        self.month_names_fr = {
            1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai',
            6: 'Juin', 7: 'Juillet', 8: 'Août', 9: 'Septembre',
            10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
        }
    
    def generate_urls(
        self,
        rectangles: List[Dict],
        property_types: List[str],
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Génère les URLs pour chaque rectangle et type de propriété.
        
        Args:
            rectangles: Liste des rectangles géographiques
            property_types: Liste des types de propriétés
            start_date: Date de début (MM/YYYY)
            end_date: Date de fin (MM/YYYY)
        
        Returns:
            List[Dict]: Liste de dictionnaires contenant les URLs et paramètres
        """
        logger.info(f"Generating URLs for {len(rectangles)} rectangles, {len(property_types)} property types")
        
        # Valider les types de propriétés
        valid_property_types = [pt for pt in property_types if pt in self.property_type_mapping]
        if not valid_property_types:
            logger.error(f"Aucun type de propriété valide parmi {property_types}")
            return []
        
        # Analyser les dates et générer les périodes
        try:
            start = datetime.strptime(start_date, "%m/%Y")
            end = datetime.strptime(end_date, "%m/%Y")
        except ValueError as e:
            logger.error(f"Format de date invalide: {str(e)}")
            return []
        
        if start > end:
            logger.error("La date de début doit être antérieure à la date de fin")
            return []
        
        # Générer les périodes mensuelles
        periods = []
        current = start
        while current <= end:
            month_fr = self.month_names_fr[current.month]
            date_fr = f"{month_fr} {current.year}"
            periods.append(date_fr)
            current += relativedelta(months=1)
        
        # Générer toutes les combinaisons d'URLs
        urls = []
        
        for rect in rectangles:
            for prop_type in valid_property_types:
                for period in periods:
                    # Créer l'URL avec ses paramètres
                    url_params = {
                        "center": f"{rect['center_lon']};{rect['center_lat']}",
                        "zoom": str(rect['zoom']),
                        "propertytypes": self.property_type_mapping[prop_type],
                        "minmonthyear": period,
                        "maxmonthyear": period
                    }
                    
                    # Construire l'URL
                    query = urllib.parse.urlencode(url_params)
                    url = f"{self.base_url}?{query}"
                    
                    # Ajouter à la liste avec les métadonnées
                    urls.append({
                        "url": url,
                        "rectangle": rect,
                        "property_type": prop_type,
                        "period": period
                    })
        
        logger.info(f"Generated {len(urls)} URLs")
        return urls