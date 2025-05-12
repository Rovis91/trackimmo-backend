"""
Module de découpage géographique pour le scraping.
Divise une ville en rectangles pour assurer une couverture complète.
"""

import os
import math
import logging
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

class GeoDivider:
    """
    Divise une ville en rectangles géographiques pour le scraping.
    """
    
    def __init__(self):
        """
        Initialise le diviseur géographique avec les paramètres par défaut.
        """
        # Paramètres de dimension du rectangle de scraping (à zoom 12)
        self.rectangle_width_km = 17  # Largeur en km
        self.rectangle_height_km = 14  # Hauteur en km
        self.zoom_level = 12
        self.overlap_percent = 10  # Chevauchement entre rectangles (%)
        
        # Constantes de conversion
        self.km_per_degree_lat = 110.574  # Constante
    
    def divide_city_area(
        self,
        city_name: str,
        postal_code: str,
        overlap_percent: Optional[float] = None
    ) -> List[Dict]:
        """
        Divise une ville en rectangles géographiques avec chevauchement.
        
        Args:
            city_name: Nom de la ville
            postal_code: Code postal
            overlap_percent: Pourcentage de chevauchement
        
        Returns:
            List[Dict]: Liste des rectangles avec leurs coordonnées
        """
        if overlap_percent is not None:
            self.overlap_percent = overlap_percent
        
        logger.info(f"Dividing city area for {city_name} ({postal_code})")
        
        # 1. Obtenir les coordonnées de la ville
        coordinates = self._get_city_coordinates(city_name, postal_code)
        if not coordinates:
            logger.error(f"Impossible d'obtenir les coordonnées pour {city_name} ({postal_code})")
            return []
        
        # 2. Calculer le rectangle englobant
        bounds = self._calculate_bounding_rectangle(coordinates)
        logger.info(f"Bounding rectangle calculé: {bounds}")
        
        # 3. Calculer les dimensions du rectangle de scraping
        rect_dimensions = self._calculate_rectangle_dimensions(
            (bounds[0] + bounds[2]) / 2  # Latitude moyenne
        )
        
        # 4. Diviser en sous-rectangles
        rectangles = self._divide_into_subrectangles(bounds, rect_dimensions)
        logger.info(f"Ville divisée en {len(rectangles)} rectangles")
        
        return rectangles
    
    def _get_city_coordinates(
        self,
        city_name: str,
        postal_code: str
    ) -> List[Tuple[float, float]]:
        """
        Obtient les coordonnées d'une ville via l'API d'adresses.
        
        Returns:
            List[Tuple[float, float]]: Liste de coordonnées (lat, lon)
        """
        # Utiliser l'API adresse pour obtenir les coordonnées
        api_url = "https://api-adresse.data.gouv.fr/search/"
        
        try:
            params = {
                "q": f"{city_name} {postal_code}",
                "limit": 1,
                "type": "municipality"
            }
            
            response = requests.get(api_url, params=params)
            data = response.json()
            
            if not data.get("features"):
                logger.warning(f"Aucune donnée trouvée pour {city_name} ({postal_code})")
                return []
            
            # Récupérer le centroïde et le bounding box pour construire les coordonnées
            feature = data["features"][0]
            center = feature["geometry"]["coordinates"]  # [lon, lat]
            
            # Vérifier si le bounding box existe dans les propriétés
            if "bbox" in feature["properties"]:
                bbox = feature["properties"]["bbox"]  # [min_lon, min_lat, max_lon, max_lat]
                # Générer quelques points le long du bounding box
                coordinates = [
                    (bbox[1], bbox[0]),  # min_lat, min_lon
                    (bbox[1], bbox[2]),  # min_lat, max_lon
                    (bbox[3], bbox[0]),  # max_lat, min_lon
                    (bbox[3], bbox[2]),  # max_lat, max_lon
                    (center[1], center[0])  # center_lat, center_lon
                ]
            else:
                # Si pas de bounding box, créer un carré autour du centre
                # Avec une taille de 1km dans chaque direction
                lat = center[1]
                lon = center[0]
                km_per_degree_lon = 111.320 * math.cos(math.radians(lat))
                
                # Calcul du delta (environ 1km dans chaque direction)
                delta_lat = 1.0 / self.km_per_degree_lat
                delta_lon = 1.0 / km_per_degree_lon
                
                coordinates = [
                    (lat - delta_lat, lon - delta_lon),
                    (lat - delta_lat, lon + delta_lon),
                    (lat + delta_lat, lon - delta_lon),
                    (lat + delta_lat, lon + delta_lon),
                    (lat, lon)
                ]
            
            return coordinates
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des coordonnées: {str(e)}")
            return []
    
    def _calculate_bounding_rectangle(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> Tuple[float, float, float, float]:
        """
        Calcule le rectangle englobant un ensemble de coordonnées.
        
        Args:
            coordinates: Liste de coordonnées (lat, lon)
        
        Returns:
            Tuple[float, float, float, float]: (min_lat, min_lon, max_lat, max_lon)
        """
        if not coordinates:
            logger.error("Aucune coordonnée fournie pour calculer le rectangle englobant")
            # Valeurs par défaut centrées sur Paris
            return (48.8566, 2.3522 - 0.1, 48.8566 + 0.1, 2.3522 + 0.1)
        
        lats = [coord[0] for coord in coordinates]
        lons = [coord[1] for coord in coordinates]
        
        min_lat = min(lats)
        min_lon = min(lons)
        max_lat = max(lats)
        max_lon = max(lons)
        
        return (min_lat, min_lon, max_lat, max_lon)
    
    def _calculate_rectangle_dimensions(
        self,
        latitude: float
    ) -> Tuple[float, float]:
        """
        Calcule les dimensions d'un rectangle en degrés à une latitude donnée.
        
        Args:
            latitude: Latitude à laquelle calculer les dimensions
        
        Returns:
            Tuple[float, float]: (width_degrees, height_degrees)
        """
        # Calcul des km par degré de longitude à cette latitude
        km_per_degree_lon = 111.320 * math.cos(math.radians(latitude))
        
        # Conversion des dimensions km -> degrés
        width_degrees = self.rectangle_width_km / km_per_degree_lon
        height_degrees = self.rectangle_height_km / self.km_per_degree_lat
        
        return (width_degrees, height_degrees)
    
    def _divide_into_subrectangles(
        self,
        bounds: Tuple[float, float, float, float],
        rect_dimensions: Tuple[float, float]
    ) -> List[Dict]:
        """
        Divise un rectangle englobant en sous-rectangles avec chevauchement.
        
        Args:
            bounds: (min_lat, min_lon, max_lat, max_lon)
            rect_dimensions: (width_degrees, height_degrees)
        
        Returns:
            List[Dict]: Liste des rectangles résultants
        """
        min_lat, min_lon, max_lat, max_lon = bounds
        rect_width, rect_height = rect_dimensions
        
        # Dimensions totales
        total_width = max_lon - min_lon
        total_height = max_lat - min_lat
        
        # Calcul du pas avec chevauchement
        overlap_factor = self.overlap_percent / 100
        step_width = rect_width * (1 - overlap_factor)
        step_height = rect_height * (1 - overlap_factor)
        
        # Calcul du nombre de pas
        lon_steps = max(1, math.ceil(total_width / step_width))
        lat_steps = max(1, math.ceil(total_height / step_height))
        
        logger.info(f"Grid size: {lon_steps}×{lat_steps} = {lon_steps * lat_steps} rectangles")
        
        # Cas spécial: un seul rectangle
        if lon_steps == 1 and lat_steps == 1:
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            
            return [{
                "center_lat": center_lat,
                "center_lon": center_lon,
                "min_lat": center_lat - rect_height/2,
                "min_lon": center_lon - rect_width/2,
                "max_lat": center_lat + rect_height/2,
                "max_lon": center_lon + rect_width/2,
                "zoom": self.zoom_level
            }]
        
        # Génération des rectangles
        rectangles = []
        
        for i in range(lat_steps):
            for j in range(lon_steps):
                # Pour distribuer uniformément
                if lon_steps > 1:
                    sub_min_lon = min_lon + (j * (total_width - rect_width) / (lon_steps - 1))
                else:
                    sub_min_lon = min_lon
                    
                if lat_steps > 1:
                    sub_min_lat = min_lat + (i * (total_height - rect_height) / (lat_steps - 1))
                else:
                    sub_min_lat = min_lat
                
                # Calculer les limites
                sub_max_lon = sub_min_lon + rect_width
                sub_max_lat = sub_min_lat + rect_height
                
                # Ajouter le rectangle
                center_lat = (sub_min_lat + sub_max_lat) / 2
                center_lon = (sub_min_lon + sub_max_lon) / 2
                
                rectangles.append({
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "min_lat": sub_min_lat,
                    "min_lon": sub_min_lon,
                    "max_lat": sub_max_lat,
                    "max_lon": sub_max_lon,
                    "zoom": self.zoom_level
                })
        
        return rectangles