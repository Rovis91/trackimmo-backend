"""
Main ImmoData scraper class.
Coordinates the end-to-end scraping process.
"""

import os
import asyncio
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .url_generator import AdaptiveUrlGenerator

from trackimmo.utils.logger import get_logger
from .geo_divider import GeoDivider
from .url_generator import UrlGenerator
from .browser_manager import BrowserManager

logger = get_logger(__name__)

class ImmoDataScraper:
    """
    Scraper for ImmoData. Extracts real estate properties
    for a given city using geographic division.
    """
    
    def __init__(self, output_dir: str = "data/scraped"):
        """
        Initialize the scraper.
        
        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.geo_divider = GeoDivider()
        self.url_generator = UrlGenerator()
        
        logger.info(f"ImmoDataScraper initialized (output directory: {self.output_dir})")
    
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
        Extracts all properties for a given city.
        Note: In async contexts (e.g. FastAPI), use the async version directly.
        """
        logger.info(f"Starting scraping for {city_name} ({postal_code})")
        if not property_types:
            property_types = ["house", "apartment"]
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"{city_name}_{postal_code}_{timestamp}.csv"
        else:
            output_file = Path(output_file)

        # Helper to check if we're in an event loop
        def in_event_loop():
            try:
                asyncio.get_running_loop()
                return True
            except RuntimeError:
                return False

        if in_event_loop():
            raise RuntimeError("scrape_city() cannot be called from an async context. Use await scrape_city_async() instead.")
        else:
            all_properties = asyncio.run(self._scrape_city_async(
                city_name=city_name,
                postal_code=postal_code,
                property_types=property_types,
                start_date=start_date,
                end_date=end_date
            ))
        unique_properties = self._deduplicate_properties(all_properties)
        logger.info(f"Extraction completed: {len(unique_properties)} unique properties extracted")
        self._export_to_csv(unique_properties, output_file)
        logger.info(f"Data exported to {output_file}")
        return str(output_file)

    async def scrape_city_async(
        self,
        city_name: str,
        postal_code: str,
        property_types: Optional[List[str]] = None,
        start_date: str = "01/2014",
        end_date: str = "06/2024",
        output_file: Optional[str] = None
    ) -> str:
        """
        Async version for use in async contexts (e.g. FastAPI endpoints).
        """
        logger.info(f"Starting scraping for {city_name} ({postal_code}) [async]")
        if not property_types:
            property_types = ["house", "apartment"]
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"{city_name}_{postal_code}_{timestamp}.csv"
        else:
            output_file = Path(output_file)
        all_properties = await self._scrape_city_async(
            city_name=city_name,
            postal_code=postal_code,
            property_types=property_types,
            start_date=start_date,
            end_date=end_date
        )
        unique_properties = self._deduplicate_properties(all_properties)
        logger.info(f"Extraction completed: {len(unique_properties)} unique properties extracted [async]")
        self._export_to_csv(unique_properties, output_file)
        logger.info(f"Data exported to {output_file} [async]")
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
        Asynchronous implementation of scraping with adaptive subdivision.
        Collects properties from all levels, including subdivided URLs.
        
        Returns:
            List[Dict]: List of extracted properties
        """
        # 1. Divide the city into geographic rectangles
        rectangles = self.geo_divider.divide_city_area(city_name, postal_code)
        logger.info(f"City divided into {len(rectangles)} rectangles")
        
        # 2. Generate initial URLs (level 1) by rectangle, month and property type
        urls = self.url_generator.generate_urls(
            rectangles, property_types, start_date, end_date
        )
        logger.info(f"Generated {len(urls)} initial URLs")
        
        # 3. Create adaptive generator and browser manager
        from .url_generator import AdaptiveUrlGenerator
        adaptive_generator = AdaptiveUrlGenerator(self.url_generator)
        browser_manager = BrowserManager()
        
        # 4. Extract properties with adaptive approach
        all_properties = []
        
        for i, url_data in enumerate(urls):
            logger.info(f"Processing URL {i+1}/{len(urls)}")
            
            # Extract with adaptation if necessary - now always collect properties
            properties, count, was_subdivided = await browser_manager.extract_properties_with_count(
                url_data, adaptive_generator
            )
            
            # Always add properties, regardless of subdivision status
            if properties:
                all_properties.extend(properties)
                logger.info(f"Added {len(properties)} properties from URL {i+1}")
                
                # Log whether this URL was subdivided
                if was_subdivided:
                    logger.info(f"Properties include those from main URL and its subdivisions")
            
            logger.info(f"Total: {len(all_properties)} properties extracted so far")
            
            # Pause between URLs to avoid overloading the server
            await asyncio.sleep(1.0)
        
        logger.info(f"Extraction completed: {len(all_properties)} properties extracted in total (before deduplication)")
        return all_properties
    
    def _deduplicate_properties(self, properties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Eliminates duplicates in extracted properties.
        
        Args:
            properties: List of extracted properties
        
        Returns:
            List[Dict]: List of deduplicated properties
        """
        # Create DataFrame to facilitate deduplication
        if not properties:
            logger.warning("No properties to deduplicate")
            return []
        
        df = pd.DataFrame(properties)
        logger.info(f"Deduplicating {len(df)} properties")
        
        # Identify essential columns for deduplication (exclude postal_code)
        duplicate_keys = ["address", "city", "price", "surface", "rooms", "sale_date"]
        available_keys = [key for key in duplicate_keys if key in df.columns]
        
        if not available_keys:
            logger.warning("Unable to deduplicate: essential columns missing")
            return properties
        
        # Deduplicate on essential columns
        df_unique = df.drop_duplicates(subset=available_keys)
        logger.info(f"Deduplication: {len(df) - len(df_unique)} duplicates removed")
        
        return df_unique.to_dict("records")
    
    def _export_to_csv(self, properties: List[Dict[str, Any]], output_file: Path) -> None:
        """
        Exports properties to a CSV file.
        
        Args:
            properties: List of properties
            output_file: Output file path
        """
        if not properties:
            logger.warning("No properties to export")
            # Create empty file to indicate the process has completed
            with open(output_file, "w") as f:
                f.write("address,city,price,surface,rooms,sale_date,property_type,property_url\n")
            return
        
        # Create DataFrame and reorganize columns
        df = pd.DataFrame(properties)
        
        # Remove unwanted columns if present
        for col in ["postal_code", "source_url"]:
            if col in df.columns:
                df = df.drop(columns=[col])
        
        # Remove rows where all main columns are empty or zero (after header)
        main_cols = ["address", "city", "price", "surface", "rooms", "sale_date"]
        if all(col in df.columns for col in main_cols):
            df = df[~((df[main_cols].isnull() | (df[main_cols] == 0) | (df[main_cols] == "")).all(axis=1))]
        
        # Reorganize/rename columns if they exist
        column_mapping = {
            "address": "address",
            "city": "city",
            "price": "price",
            "surface": "surface",
            "rooms": "rooms",
            "sale_date": "sale_date",
            "property_type": "property_type",
            "property_url": "property_url"
        }
        
        # Apply mapping only for existing columns
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        if existing_columns:
            df = df.rename(columns=existing_columns)
        
        # Define main column order (use only existing columns)
        ordered_columns = [v for k, v in column_mapping.items() 
                          if k in df.columns and v in df.columns]
        
        # Add additional columns not in the mapping
        other_columns = [col for col in df.columns if col not in ordered_columns]
        final_columns = ordered_columns + other_columns
        
        # Reorganize and save
        df = df[final_columns]
        logger.info(f"Exporting {len(df)} properties to CSV")
        df.to_csv(output_file, index=False)