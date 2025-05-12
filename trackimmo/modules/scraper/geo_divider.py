"""
Geographic division module for web scraping.
Divides a city into rectangles to ensure complete coverage.
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
    Divides a city into geographic rectangles for scraping.
    """
    
    def __init__(self):
        """
        Initialize the geographic divider with default parameters.
        """
        # Scraping rectangle dimension parameters (at zoom level 12)
        self.rectangle_width_km = 17  # Width in km
        self.rectangle_height_km = 14  # Height in km
        self.zoom_level = 12
        self.overlap_percent = 10  # Overlap between rectangles (%)
        
        # Conversion constants
        self.km_per_degree_lat = 110.574  # Constant
    
    def divide_city_area(
        self,
        city_name: str,
        postal_code: str,
        overlap_percent: Optional[float] = None
    ) -> List[Dict]:
        """
        Divides a city into geographic rectangles with overlap.
        
        Args:
            city_name: Name of the city
            postal_code: Postal code
            overlap_percent: Overlap percentage
        
        Returns:
            List[Dict]: List of rectangles with their coordinates
        """
        if overlap_percent is not None:
            self.overlap_percent = overlap_percent
        
        logger.info(f"Dividing city area for {city_name} ({postal_code})")
        
        # 1. Get city coordinates
        coordinates = self._get_city_coordinates(city_name, postal_code)
        if not coordinates:
            logger.error(f"Unable to get coordinates for {city_name} ({postal_code})")
            return []
        
        # 2. Calculate bounding rectangle
        bounds = self._calculate_bounding_rectangle(coordinates)
        logger.info(f"Calculated bounding rectangle: {bounds}")
        
        # 3. Calculate scraping rectangle dimensions
        rect_dimensions = self._calculate_rectangle_dimensions(
            (bounds[0] + bounds[2]) / 2  # Average latitude
        )
        
        # 4. Divide into sub-rectangles
        rectangles = self._divide_into_subrectangles(bounds, rect_dimensions)
        logger.info(f"City divided into {len(rectangles)} rectangles")
        
        return rectangles
    
    def _get_city_coordinates(
        self,
        city_name: str,
        postal_code: str
    ) -> List[Tuple[float, float]]:
        """
        Gets city coordinates via the address API.
        
        Returns:
            List[Tuple[float, float]]: List of coordinates (lat, lon)
        """
        # Use address API to get coordinates
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
                logger.warning(f"No data found for {city_name} ({postal_code})")
                return []
            
            # Get centroid and bounding box to build coordinates
            feature = data["features"][0]
            center = feature["geometry"]["coordinates"]  # [lon, lat]
            
            # Check if bounding box exists in properties
            if "bbox" in feature["properties"]:
                bbox = feature["properties"]["bbox"]  # [min_lon, min_lat, max_lon, max_lat]
                # Generate some points along the bounding box
                coordinates = [
                    (bbox[1], bbox[0]),  # min_lat, min_lon
                    (bbox[1], bbox[2]),  # min_lat, max_lon
                    (bbox[3], bbox[0]),  # max_lat, min_lon
                    (bbox[3], bbox[2]),  # max_lat, max_lon
                    (center[1], center[0])  # center_lat, center_lon
                ]
            else:
                # If no bounding box, create a square around the center
                # With a size of 1km in each direction
                lat = center[1]
                lon = center[0]
                km_per_degree_lon = 111.320 * math.cos(math.radians(lat))
                
                # Calculate delta (about 1km in each direction)
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
            logger.error(f"Error retrieving coordinates: {str(e)}")
            return []
    
    def _calculate_bounding_rectangle(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> Tuple[float, float, float, float]:
        """
        Calculates the bounding rectangle for a set of coordinates.
        
        Args:
            coordinates: List of coordinates (lat, lon)
        
        Returns:
            Tuple[float, float, float, float]: (min_lat, min_lon, max_lat, max_lon)
        """
        if not coordinates:
            logger.error("No coordinates provided to calculate bounding rectangle")
            # Default values centered on Paris
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
        Calculates rectangle dimensions in degrees at a given latitude.
        
        Args:
            latitude: Latitude at which to calculate dimensions
        
        Returns:
            Tuple[float, float]: (width_degrees, height_degrees)
        """
        # Calculate km per degree of longitude at this latitude
        km_per_degree_lon = 111.320 * math.cos(math.radians(latitude))
        
        # Convert dimensions km -> degrees
        width_degrees = self.rectangle_width_km / km_per_degree_lon
        height_degrees = self.rectangle_height_km / self.km_per_degree_lat
        
        return (width_degrees, height_degrees)
    
    def _divide_into_subrectangles(
        self,
        bounds: Tuple[float, float, float, float],
        rect_dimensions: Tuple[float, float]
    ) -> List[Dict]:
        """
        Divides a bounding rectangle into sub-rectangles with overlap.
        
        Args:
            bounds: (min_lat, min_lon, max_lat, max_lon)
            rect_dimensions: (width_degrees, height_degrees)
        
        Returns:
            List[Dict]: List of resulting rectangles
        """
        min_lat, min_lon, max_lat, max_lon = bounds
        rect_width, rect_height = rect_dimensions
        
        # Total dimensions
        total_width = max_lon - min_lon
        total_height = max_lat - min_lat
        
        # Calculate step with overlap
        overlap_factor = self.overlap_percent / 100
        step_width = rect_width * (1 - overlap_factor)
        step_height = rect_height * (1 - overlap_factor)
        
        # Calculate number of steps
        lon_steps = max(1, math.ceil(total_width / step_width))
        lat_steps = max(1, math.ceil(total_height / step_height))
        
        logger.info(f"Grid size: {lon_steps}×{lat_steps} = {lon_steps * lat_steps} rectangles")
        
        # Special case: single rectangle
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
        
        # Generate rectangles
        rectangles = []
        
        for i in range(lat_steps):
            for j in range(lon_steps):
                # For uniform distribution
                if lon_steps > 1:
                    sub_min_lon = min_lon + (j * (total_width - rect_width) / (lon_steps - 1))
                else:
                    sub_min_lon = min_lon
                    
                if lat_steps > 1:
                    sub_min_lat = min_lat + (i * (total_height - rect_height) / (lat_steps - 1))
                else:
                    sub_min_lat = min_lat
                
                # Calculate limits
                sub_max_lon = sub_min_lon + rect_width
                sub_max_lat = sub_min_lat + rect_height
                
                # Add rectangle
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