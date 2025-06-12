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
from trackimmo.config import settings

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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Generates URLs for each rectangle and month, initially combining all types.
        """
        if start_date is None:
            start_date = settings.SCRAPER_DEFAULT_START_DATE
        if end_date is None:
            end_date = settings.SCRAPER_DEFAULT_END_DATE
        
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
    and generates optimal subdivisions with progressive approach.
    """
    
    def __init__(self, base_generator: UrlGenerator):
        """
        Initialize the adaptive generator.
        
        Args:
            base_generator: Base URL generator
        """
        self.base_generator = base_generator
        self.threshold_min = 99  # Minimum threshold for subdivision (raised to be closer to 100 limit)
        self.threshold_optimal_min = 50  # Minimum for optimal subdivision (avoid too small chunks)
        self.max_price = 25000000  # Maximum price (25 million €)
        self.num_price_ranges = 8  # Reduced from 10 to 8 (less aggressive subdivision)
        self.max_subdivision_level = 999  # Effectively unlimited subdivision levels
        
        # Cache for optimal subdivision levels
        # Key: (rectangle_center, period, property_type)
        # Value: {"subdivision_level": int, "success_count": int}
        self.subdivision_cache = {}
    
    def subdivide_if_needed(
        self, 
        url_data: Dict, 
        property_count: int,
        properties: List[Dict] = None
    ) -> List[Dict]:
        """
        Decides whether to subdivide using progressive approach and caching.
        Only subdivides when truly necessary and tries to maintain 50-99 properties per chunk.
        """
        # Only subdivide if we're very close to the 100 property limit
        if property_count >= self.threshold_min:
            subdivision_level = url_data.get("subdivision_level", 0)
            
            # Generate cache key for this context
            cache_key = self._generate_cache_key(url_data)
            
            # Check if we have cached optimal subdivision for similar context
            cached_info = self.subdivision_cache.get(cache_key)
            if cached_info and cached_info["success_count"] >= 2:
                # Use cached subdivision level if it has been successful multiple times
                target_level = cached_info["subdivision_level"]
                logger.info(f"Using cached subdivision level {target_level} for similar context")
                
                # Jump directly to the known successful level
                if target_level == 1 and subdivision_level == 0:
                    logger.warning(f"URL has {property_count} properties, applying cached subdivision by type...")
                    return self._subdivide_by_property_type(url_data)
                elif target_level == 2 and subdivision_level <= 1:
                    logger.warning(f"URL has {property_count} properties, applying cached price subdivision...")
                    return self._progressive_price_subdivision(url_data, properties, progressive_level=1)
            
            # Log the subdivision decision with more context
            # logger.warning(f"URL has {property_count} properties (>={self.threshold_min} threshold), progressive subdivision needed.")
            
            if subdivision_level == 0:
                # First step: subdivision by property type (only if multiple types)
                property_types = url_data.get("property_types", [])
                if len(property_types) > 1:
                    logger.warning(f"Level 0 -> Level 1: Subdividing by property type...")
                    result = self._subdivide_by_property_type(url_data)
                    self._update_cache(cache_key, 1, True)
                    return result
                else:
                    # Skip type subdivision if only one type, go to price
                    logger.warning(f"Level 0 -> Level 2: Single type, subdividing by price...")
                    result = self._progressive_price_subdivision(url_data, properties, progressive_level=1)
                    self._update_cache(cache_key, 2, True)
                    return result
            
            elif subdivision_level == 1:
                # Second step: progressive price subdivision
                logger.warning(f"Level 1 -> Level 2: Progressive price subdivision...")
                result = self._progressive_price_subdivision(url_data, properties, progressive_level=1)
                self._update_cache(cache_key, 2, True)
                return result
            
            else:
                # Deep progressive subdivision: increase progressive level
                current_progressive = url_data.get("progressive_level", 1)
                new_progressive = current_progressive + 1
                logger.warning(f"Level {subdivision_level} -> Progressive level {new_progressive}: Deep progressive subdivision...")
                result = self._progressive_price_subdivision(url_data, properties, progressive_level=new_progressive)
                self._update_cache(cache_key, subdivision_level + 1, True)
                return result
        else:
            # Log when we don't subdivide and update cache for successful non-subdivision
            logger.info(f"URL has {property_count} properties (< {self.threshold_min} threshold), no subdivision needed.")
            cache_key = self._generate_cache_key(url_data)
            self._update_cache(cache_key, 0, True)  # Level 0 = no subdivision needed
        
        return []

    def _generate_cache_key(self, url_data: Dict) -> str:
        """Generate a cache key for similar contexts."""
        rect = url_data["rectangle"]
        period = url_data["period"]
        property_type = url_data.get("property_type", "all")
        
        # Use rectangle center and zoom as identifier
        rect_id = f"{rect['center_lon']:.3f},{rect['center_lat']:.3f},{rect['zoom']}"
        
        return f"{rect_id}|{period}|{property_type}"
    
    def _update_cache(self, cache_key: str, subdivision_level: int, success: bool):
        """Update cache with subdivision result."""
        if cache_key not in self.subdivision_cache:
            self.subdivision_cache[cache_key] = {"subdivision_level": subdivision_level, "success_count": 0}
        
        if success:
            self.subdivision_cache[cache_key]["subdivision_level"] = subdivision_level
            self.subdivision_cache[cache_key]["success_count"] += 1
        
        # Limit cache size to prevent memory issues
        if len(self.subdivision_cache) > 1000:
            # Remove oldest entries (simple approach)
            keys_to_remove = list(self.subdivision_cache.keys())[:100]
            for key in keys_to_remove:
                del self.subdivision_cache[key]

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
        
        # Check if we're at the API limit (101 properties)
        use_aggressive_division = len(properties) >= 101
        num_central_divisions = 10 if use_aggressive_division else 6  # Reduced from 16/12 to 10/6
        
        # Generate price ranges based on property analysis
        price_ranges = self._generate_optimal_price_ranges(
            properties, 
            num_central_divisions=num_central_divisions
        )
        
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
                "min_price": min_price,
                "max_price": max_price,
                "subdivision_level": 2,  # Second level of subdivision
                "is_price_subdivision": True
            })
        
        # Detailed log of generated price ranges
        ranges_str = [f"{int(min_p)}-{int(max_p)}" for min_p, max_p in price_ranges]
        strategy = "aggressive" if use_aggressive_division else "standard"
        logger.info(f"Level 2 subdivision: {len(result)} URLs by price ranges ({strategy} strategy)")
        logger.info(f"Generated price ranges: {', '.join(ranges_str)}")
        
        return result
    
    def _refine_price_subdivision(
        self, 
        url_data: Dict, 
        properties: List[Dict]
    ) -> List[Dict]:
        """
        Third level subdivision: splits an existing price range into smaller segments.
        
        Args:
            url_data: URL data with existing price range
            properties: Properties found with current range
            
        Returns:
            List[Dict]: New subdivided URLs with refined price ranges
        """
        # Get basic information
        rect = url_data["rectangle"]
        period = url_data["period"]
        property_type = url_data["property_type"]
        property_types = url_data.get("property_types", [])
        
        # Get original price range
        min_price = url_data.get("min_price", 0)
        max_price = url_data.get("max_price", self.max_price)
        
        # Get type codes for URL
        type_codes = [self.base_generator.property_type_mapping[t] for t in property_types 
                     if t in self.base_generator.property_type_mapping]
        
        # Extract prices from the current subset of properties
        prices = [p.get("price", 0) for p in properties if p.get("price", 0) > 0]
        
        # Determine number of subdivisions based on context
        use_aggressive_division = len(properties) >= 101
        num_divisions = 8 if use_aggressive_division else 4  # Reduced from 12/8 to 8/4
        
        # If we don't have enough prices to analyze, simply split into equal parts
        if len(prices) < 20:
            price_step = (max_price - min_price) / num_divisions
            price_ranges = []
            for i in range(num_divisions):
                price_min = min_price + i * price_step
                price_max = min_price + (i + 1) * price_step
                price_ranges.append((price_min, price_max))
        else:
            # Sort prices for percentile calculation
            prices.sort()
            
            if use_aggressive_division:
                # Use 6 divisions (more granular) when we're at the API limit
                # Calculate percentiles at 16.7%, 33.3%, 50%, 66.7%, and 83.3%
                p1 = prices[int(0.167 * len(prices))]
                p2 = prices[int(0.333 * len(prices))]
                p3 = prices[int(0.500 * len(prices))]
                p4 = prices[int(0.667 * len(prices))]
                p5 = prices[int(0.833 * len(prices))]
                
                # Create 6 price ranges based on percentiles
                price_ranges = [
                    (min_price, p1),
                    (p1, p2),
                    (p2, p3),
                    (p3, p4),
                    (p4, p5),
                    (p5, max_price)
                ]
            else:
                # Standard case: quartiles (25%, 50%, 75%)
                q1 = prices[int(0.25 * len(prices))]
                q2 = prices[int(0.50 * len(prices))]
                q3 = prices[int(0.75 * len(prices))]
                
                # Create 4 price ranges based on quartiles
                price_ranges = [
                    (min_price, q1),
                    (q1, q2),
                    (q2, q3),
                    (q3, max_price)
                ]
                
        # Create a URL for each price range
        result = []
        base_type = property_type.split('_price_')[0] if '_price_' in property_type else property_type
        
        for i, (min_p, max_p) in enumerate(price_ranges):
            # Make sure prices are at least 1 euro apart to avoid duplicates
            if max_p - min_p < 1:
                max_p = min_p + 1
                
            # Format prices for URL (avoid commas)
            min_price_str = str(int(min_p))
            max_price_str = str(int(max_p))
            
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
            range_label = f"{base_type}_price_{min_price_str}_{max_price_str}"
            
            # Add to list
            result.append({
                "url": url,
                "rectangle": rect,
                "property_type": range_label,
                "period": period,
                "property_types": property_types,
                "price_range": f"{min_price_str}-{max_price_str}",
                "min_price": min_p,
                "max_price": max_p,
                "subdivision_level": 3,  # Third level of subdivision
                "is_price_subdivision": True
            })
        
        # Detailed log of generated price ranges
        ranges_str = [f"{int(min_p)}-{int(max_p)}" for min_p, max_p in price_ranges]
        logger.info(f"Level 3 subdivision: {len(result)} URLs by refined price ranges")
        strategy = "aggressive" if use_aggressive_division else "standard"
        logger.info(f"Using {strategy} subdivision strategy with {num_divisions} divisions")
        logger.info(f"Refined price ranges: {', '.join(ranges_str)}")
        
        return result
        
    def _deep_price_subdivision(
        self, 
        url_data: Dict, 
        properties: List[Dict]
    ) -> List[Dict]:
        """
        Deep subdivision beyond level 3: uses binary splitting strategy.
        This method is called recursively for very dense property areas.
        
        Args:
            url_data: URL data with existing price range
            properties: Properties found with current range
            
        Returns:
            List[Dict]: New subdivided URLs with binary price ranges
        """
        # Get basic information
        rect = url_data["rectangle"]
        period = url_data["period"]
        property_type = url_data["property_type"]
        property_types = url_data.get("property_types", [])
        subdivision_level = url_data.get("subdivision_level", 3)
        
        # Get original price range
        min_price = url_data.get("min_price", 0)
        max_price = url_data.get("max_price", self.max_price)
        
        # Get type codes for URL
        type_codes = [self.base_generator.property_type_mapping[t] for t in property_types 
                     if t in self.base_generator.property_type_mapping]
        
        # For deep subdivision, always split in half (binary splitting)
        # This is the most reliable strategy when we keep hitting API limits
        median_price = (min_price + max_price) / 2
        
        # If the price range is too small, use a minimum difference
        if max_price - min_price < 5000:
            # If we're already at a very small range, use an even smaller step
            step = 1000 if max_price - min_price < 1000 else 2500
            median_price = min_price + step
        
        # Create exactly 2 price ranges for binary subdivision
        price_ranges = [
            (min_price, median_price),
            (median_price, max_price)
        ]
        
        # Create a URL for each price range
        result = []
        base_type = property_type.split('_price_')[0] if '_price_' in property_type else property_type
        
        for i, (min_p, max_p) in enumerate(price_ranges):
            # Make sure prices are at least 1 euro apart
            if max_p - min_p < 1:
                max_p = min_p + 1
                
            # Format prices for URL (avoid commas)
            min_price_str = str(int(min_p))
            max_price_str = str(int(max_p))
            
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
            range_label = f"{base_type}_price_{min_price_str}_{max_price_str}"
            
            # Add to list with incremented subdivision level
            result.append({
                "url": url,
                "rectangle": rect,
                "property_type": range_label,
                "period": period,
                "property_types": property_types,
                "price_range": f"{min_price_str}-{max_price_str}",
                "min_price": min_p,
                "max_price": max_p,
                "subdivision_level": subdivision_level + 1,  # Increment subdivision level
                "is_price_subdivision": True
            })
        
        # Detailed log of generated price ranges
        ranges_str = [f"{int(min_p)}-{int(max_p)}" for min_p, max_p in price_ranges]
        logger.info(f"Level {subdivision_level+1} deep subdivision: {len(result)} URLs by binary price ranges")
        logger.info(f"Deep price ranges: {', '.join(ranges_str)}")
        
        return result
    
    def _generate_optimal_price_ranges(
        self, 
        properties: List[Dict],
        num_central_divisions: int = 6  # Reduced from 8 to 6 (less aggressive default)
    ) -> List[Tuple[float, float]]:
        """
        Generates optimal price ranges based on analysis of
        actual data according to the specified logic.
        
        Args:
            properties: List of properties with their prices
            num_central_divisions: Number of divisions for the central price range
        
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
        
        # Divide central range (p05 to p95) into specified number of intervals
        central_step = (p95 - p05) / num_central_divisions
        for i in range(num_central_divisions):
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
            (0, 80000),            # 0-80K
            (80000, 120000),       # 80K-120K
            (120000, 150000),      # 120K-150K
            (150000, 180000),      # 150K-180K
            (180000, 220000),      # 180K-220K
            (220000, 260000),      # 220K-260K
            (260000, 300000),      # 260K-300K
            (300000, 350000),      # 300K-350K
            (350000, 400000),      # 350K-400K
            (400000, 500000),      # 400K-500K
            (500000, 600000),      # 500K-600K
            (600000, 750000),      # 600K-750K
            (750000, 1000000),     # 750K-1M
            (1000000, 25000000)    # 1M+
        ]

    def _progressive_price_subdivision(
        self, 
        url_data: Dict, 
        properties: List[Dict],
        progressive_level: int = 1
    ) -> List[Dict]:
        """
        Progressive price subdivision that starts with binary splits and progresses as needed.
        Aims to keep 50-99 properties per subdivision to optimize extraction.
        
        Args:
            url_data: URL data
            properties: Extracted properties to analyze
            progressive_level: Level of progression (1=binary, 2=quad, 3=octal)
        
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
        
        # Extract prices for analysis
        prices = [p.get("price", 0) for p in properties if p.get("price", 0) > 0]
        
        if len(prices) < 10:
            logger.warning("Not enough price data for analysis, using binary split")
            # Default to binary price split
            num_divisions = 2
        else:
            # Calculate optimal number of divisions based on progressive level
            # Level 1: 2 divisions, Level 2: 4 divisions, Level 3: 8 divisions
            base_divisions = 2 ** progressive_level
            
            # Estimate properties per division
            estimated_per_division = len(properties) / base_divisions
            
            # Adjust divisions to target 50-99 properties per division
            if estimated_per_division < self.threshold_optimal_min:
                # Too few per division, reduce divisions
                num_divisions = max(2, len(properties) // self.threshold_optimal_min)
                # logger.info(f"Adjusted divisions from {base_divisions} to {num_divisions} to maintain >= {self.threshold_optimal_min} properties per division")
            elif estimated_per_division > self.threshold_min:
                # Too many per division, increase divisions
                num_divisions = min(8, (len(properties) // self.threshold_optimal_min) + 1)
                # logger.info(f"Adjusted divisions from {base_divisions} to {num_divisions} to avoid > {self.threshold_min} properties per division")
            else:
                num_divisions = base_divisions
        
        # Get price range
        min_price = url_data.get("min_price", 0)
        max_price = url_data.get("max_price", self.max_price)
        
        # Generate price ranges
        if len(prices) >= 20 and num_divisions <= 4:
            # Use data-driven percentiles for fewer divisions
            prices.sort()
            price_ranges = self._generate_percentile_ranges(prices, min_price, max_price, num_divisions)
        else:
            # Use equal splits for simplicity with many divisions or little data
            price_ranges = self._generate_equal_price_ranges(min_price, max_price, num_divisions)
        
        # Create URLs
        result = []
        base_type = property_type.split('_price_')[0] if '_price_' in property_type else property_type
        
        for i, (min_p, max_p) in enumerate(price_ranges):
            # Format prices for URL
            min_price_str = str(int(min_p))
            max_price_str = str(int(max_p)) if i < len(price_ranges) - 1 else str(self.max_price)
            
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
            
            # Create descriptive label
            range_label = f"{base_type}_price_{min_price_str}_{max_price_str}"
            
            # Add to list
            result.append({
                "url": url,
                "rectangle": rect,
                "property_type": range_label,
                "period": period,
                "property_types": property_types,
                "price_range": f"{min_price_str}-{max_price_str}",
                "min_price": min_p,
                "max_price": max_p,
                "subdivision_level": 2,  # Always level 2 for price subdivision
                "progressive_level": progressive_level,
                "is_price_subdivision": True
            })
        
        # Log results
        ranges_str = [f"{int(min_p)}-{int(max_p)}" for min_p, max_p in price_ranges]
        estimated_per_div = len(properties) // len(price_ranges)
        # logger.info(f"Progressive subdivision (level {progressive_level}): {len(result)} URLs")
        # logger.info(f"Target: ~{estimated_per_div} properties per URL (from {len(properties)} total)")
        # logger.info(f"Price ranges: {', '.join(ranges_str)}")
        
        return result

    def _generate_percentile_ranges(self, sorted_prices: List[float], min_price: float, max_price: float, num_divisions: int) -> List[Tuple[float, float]]:
        """Generate price ranges based on data percentiles."""
        ranges = []
        
        if num_divisions == 2:
            # Binary split at median
            median = sorted_prices[len(sorted_prices) // 2]
            ranges = [(min_price, median), (median, max_price)]
        elif num_divisions == 4:
            # Quartile split
            q1 = sorted_prices[len(sorted_prices) // 4]
            q2 = sorted_prices[len(sorted_prices) // 2]
            q3 = sorted_prices[3 * len(sorted_prices) // 4]
            ranges = [(min_price, q1), (q1, q2), (q2, q3), (q3, max_price)]
        else:
            # Fall back to equal ranges
            ranges = self._generate_equal_price_ranges(min_price, max_price, num_divisions)
        
        return ranges

    def _generate_equal_price_ranges(self, min_price: float, max_price: float, num_divisions: int) -> List[Tuple[float, float]]:
        """Generate equal price ranges."""
        step = (max_price - min_price) / num_divisions
        ranges = []
        
        for i in range(num_divisions):
            range_min = min_price + i * step
            range_max = min_price + (i + 1) * step
            ranges.append((range_min, range_max))
        
        return ranges