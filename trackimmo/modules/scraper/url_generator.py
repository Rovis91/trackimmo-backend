"""
URL generator for ImmoData scraping with dynamic subdivision.
"""

import logging
import statistics
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import urllib.parse
from typing import List, Dict, Optional, Tuple, Set

from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

class UrlGenerator:
    """
    Generates search URLs for ImmoData.
    """
    
    def __init__(self):
        """
        Initialize the URL generator with default parameters.
        """
        self.base_url = "https://www.immo-data.fr/explorateur/transaction/recherche"
        
        # Property type mapping
        self.property_type_mapping = {
            "house": "1",
            "apartment": "2",
            "land": "4",
            "commercial": "0",
            "other": "5"
        }
        
        # French month names
        self.month_names_fr = {
            1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai',
            6: 'Juin', 7: 'Juillet', 8: 'Août', 9: 'Septembre',
            10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
        }
        
        # Parameters for price subdivision
        self.max_price = 25000000  # Maximum price (25 million €)
    
    def generate_urls(
        self,
        rectangles: List[Dict],
        property_types: List[str],
        start_date: str = "01/2014",
        end_date: str = "12/2024"
    ) -> List[Dict]:
        """
        Generates URLs for each rectangle and month, initially combining all types.
        """
        logger.info(f"Generating URLs for {len(rectangles)} rectangles, {len(property_types)} property types")
        logger.info(f"Date range: {start_date} to {end_date}")
        
        # Validate property types
        valid_property_types = [pt for pt in property_types if pt in self.property_type_mapping]
        if not valid_property_types:
            logger.error(f"No valid property types among {property_types}")
            return []
        
        # Parse dates and generate periods
        try:
            start = datetime.strptime(start_date, "%m/%Y")
            end = datetime.strptime(end_date, "%m/%Y")
        except ValueError as e:
            logger.error(f"Invalid date format: {str(e)}")
            return []
        
        if start > end:
            logger.error("Start date must be earlier than end date")
            return []
        
        # Generate monthly periods
        periods = []
        current = start
        while current <= end:
            month_fr = self.month_names_fr[current.month]
            date_fr = f"{month_fr} {current.year}"
            periods.append(date_fr)
            current += relativedelta(months=1)
        
        logger.info(f"Generated {len(periods)} monthly periods")
        
        # Generate URLs by rectangle and month, combining all types
        urls = []
        
        for rect in rectangles:
            for period in periods:
                # Combine all property types in a single initial URL
                type_codes = [self.property_type_mapping[t] for t in valid_property_types]
                
                # Create initial URL with all types combined
                url_params = {
                    "center": f"{rect['center_lon']};{rect['center_lat']}",
                    "zoom": str(rect['zoom']),
                    "propertytypes": ",".join(type_codes),
                    "minmonthyear": period,
                    "maxmonthyear": period
                }
                
                query = urllib.parse.urlencode(url_params)
                url = f"{self.base_url}?{query}"
                
                # Add to list with metadata
                urls.append({
                    "url": url,
                    "rectangle": rect,
                    "property_type": "all",  # Mark as combining all types
                    "period": period,
                    "property_types": valid_property_types.copy(),
                    "subdivision_level": 0  # Level 0 = not yet subdivided
                })
        
        logger.info(f"Generated {len(urls)} URLs (1 URL per rectangle and month, all property types)")
        return urls

class AdaptiveUrlGenerator:
    """
    Adaptive URL generator that analyzes price distribution
    and generates optimal subdivisions.
    """
    
    def __init__(self, base_generator: UrlGenerator):
        """
        Initialize the adaptive generator.
        
        Args:
            base_generator: Base URL generator
        """
        self.base_generator = base_generator
        self.threshold_min = 90  # Minimum threshold for subdivision
        self.max_price = 25000000  # Maximum price (25 million €)
        self.num_price_ranges = 10  # Total number of price ranges
    
    def subdivide_if_needed(
        self, 
        url_data: Dict, 
        property_count: int,
        properties: List[Dict] = None
    ) -> List[Dict]:
        """
        Decides whether to subdivide and generates subdivision URLs.
        """
        # Check if we're close to the limit
        if self.threshold_min <= property_count:
            subdivision_level = url_data.get("subdivision_level", 0)
            
            if subdivision_level == 0:
                # First step: subdivision by property type
                logger.warning(f"URL has {property_count} properties, subdividing by type...")
                return self._subdivide_by_property_type(url_data)
            
            elif subdivision_level == 1:
                # Second step: subdivision by price range
                logger.warning(f"URL has {property_count} properties, subdividing by price...")
                return self._subdivide_by_dynamic_price_ranges(url_data, properties)
        
        return []

    def _subdivide_by_property_type(self, url_data: Dict) -> List[Dict]:
        """
        First subdivision: separates into houses, apartments and others.
        """
        # Get property types
        property_types = url_data.get("property_types", [])
        
        # Define subdivision groups
        type_groups = [
            {"label": "apartments", "types": ["apartment"]},
            {"label": "houses", "types": ["house"]},
            {"label": "others", "types": ["land", "commercial", "other"]}
        ]
        
        # Create sub-URLs
        result = []
        rect = url_data["rectangle"]
        period = url_data["period"]
        
        for group in type_groups:
            # Filter valid types for this group
            valid_types = [t for t in group["types"] if t in property_types]
            
            if not valid_types:
                continue  # Skip this group if there are no valid types
            
            # Convert types to codes
            type_codes = [self.base_generator.property_type_mapping[t] for t in valid_types]
            
            # Create URL
            url_params = {
                "center": f"{rect['center_lon']};{rect['center_lat']}",
                "zoom": str(rect['zoom']),
                "propertytypes": ",".join(type_codes),
                "minmonthyear": period,
                "maxmonthyear": period
            }
            
            query = urllib.parse.urlencode(url_params)
            url = f"{self.base_generator.base_url}?{query}"
            
            # Add to list
            result.append({
                "url": url,
                "rectangle": rect,
                "property_type": group["label"],
                "period": period,
                "property_types": valid_types,
                "is_subdivision": True,
                "subdivision_level": 1  # First level of subdivision
            })
        
        logger.info(f"Level 1 subdivision: {len(result)} URLs by property type")
        return result

    def _subdivide_by_dynamic_price_ranges(
        self, 
        url_data: Dict, 
        properties: List[Dict]
    ) -> List[Dict]:
        """
        Subdivides by dynamic price ranges based on data analysis.
        
        Args:
            url_data: URL data
            properties: Extracted properties to analyze
        
        Returns:
            List[Dict]: New subdivided URLs
        """
        # Get basic information
        rect = url_data["rectangle"]
        period = url_data["period"]
        property_type = url_data["property_type"]
        property_types = url_data.get("property_types", [])
        
        # Get type codes for URL
        type_codes = [self.base_generator.property_type_mapping[t] for t in property_types 
                     if t in self.base_generator.property_type_mapping]
        
        # Generate price ranges based on property analysis
        price_ranges = self._generate_optimal_price_ranges(properties)
        
        # Create a URL for each price range
        result = []
        
        for i, (min_price, max_price) in enumerate(price_ranges):
            # Format prices for URL (avoid commas)
            min_price_str = str(int(min_price))
            
            # For the last range, use the global maximum price
            if i == len(price_ranges) - 1:
                max_price_str = str(self.max_price)
            else:
                max_price_str = str(int(max_price))
            
            # Create URL with price filter
            url_params = {
                "center": f"{rect['center_lon']};{rect['center_lat']}",
                "zoom": str(rect['zoom']),
                "propertytypes": ",".join(type_codes),
                "minmonthyear": period,
                "maxmonthyear": period,
                "minprice": min_price_str,
                "maxprice": max_price_str
            }
            
            query = urllib.parse.urlencode(url_params)
            url = f"{self.base_generator.base_url}?{query}"
            
            # Create descriptive label for this price range
            range_label = f"{property_type}_price_{min_price_str}_{max_price_str}"
            
            # Add to list
            result.append({
                "url": url,
                "rectangle": rect,
                "property_type": range_label,
                "period": period,
                "property_types": property_types,
                "price_range": f"{min_price_str}-{max_price_str}",
                "subdivision_level": 2,  # Second level of subdivision
                "is_price_subdivision": True
            })
        
        # Detailed log of generated price ranges
        ranges_str = [f"{int(min_p)}-{int(max_p)}" for min_p, max_p in price_ranges]
        logger.info(f"Level 2 subdivision: {len(result)} URLs by price ranges")
        logger.info(f"Generated price ranges: {', '.join(ranges_str)}")
        
        return result
    
    def _generate_optimal_price_ranges(self, properties: List[Dict]) -> List[Tuple[float, float]]:
        """
        Generates optimal price ranges based on analysis of
        actual data according to the specified logic.
        
        Args:
            properties: List of properties with their prices
        
        Returns:
            List[Tuple[float, float]]: List of tuples (min_price, max_price)
        """
        # Extract non-zero prices
        prices = [p.get("price", 0) for p in properties if p.get("price", 0) > 0]
        
        # If not enough data for analysis, use default ranges
        if len(prices) < 10:
            logger.warning("Not enough data for price analysis, using default ranges")
            return self._default_price_ranges()
        
        # Sort prices
        prices.sort()
        
        # Calculate percentiles to determine central range (90% of properties)
        if len(prices) >= 20:  # Enough data for reliable percentiles
            p05 = prices[int(0.05 * len(prices))]  # 5th percentile
            p95 = prices[int(0.95 * len(prices))]  # 95th percentile
        else:
            # If little data, widen the range to avoid bias
            p05 = prices[0]
            p95 = prices[-1]
        
        # Ensure values are at least 1000€ apart
        if p95 - p05 < 1000:
            center = (p05 + p95) / 2
            p05 = max(0, center - 500)
            p95 = center + 500
        
        # Create first range (0 to p05)
        ranges = [(0, p05)]
        
        # Divide central range (p05 to p95) into 8 intervals
        central_step = (p95 - p05) / 8
        for i in range(8):
            min_price = p05 + i * central_step
            max_price = p05 + (i + 1) * central_step
            ranges.append((min_price, max_price))
        
        # Add last range (p95 to max_price)
        ranges.append((p95, self.max_price))
        
        # Log statistics
        logger.info(f"Price analysis: {len(prices)} properties, 5%={p05}, 95%={p95}")
        
        return ranges
    
    def _default_price_ranges(self) -> List[Tuple[float, float]]:
        """
        Generates default price ranges (non-linear).
        
        Returns:
            List[Tuple[float, float]]: List of tuples (min_price, max_price)
        """
        return [
            (0, 100000),           # 0-100K
            (100000, 150000),      # 100K-150K
            (150000, 200000),      # 150K-200K
            (200000, 250000),      # 200K-250K
            (250000, 300000),      # 250K-300K
            (300000, 400000),      # 300K-400K
            (400000, 500000),      # 400K-500K
            (500000, 750000),      # 500K-750K
            (750000, 1000000),     # 750K-1M
            (1000000, 25000000)    # 1M+
        ]