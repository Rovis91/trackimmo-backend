"""
Browser manager for web scraping.
Uses Playwright to extract data from ImmoData pages.
"""

import asyncio
import re
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

class BrowserManager:
    """
    Manages browser interaction and data extraction.
    """
    
    # CSS selectors for ImmoData
    SELECTORS = {
        "container": "div.md\\:h-full.flex.flex-col.md\\:w-112.w-full.order-1.md\\:order-2",
        "property": "div.border-b.border-b-gray-100",
        "address": "p.text-gray-700.font-bold.truncate",
        "price": "p.text-primary-500.font-bold.whitespace-nowrap span",
        "rooms": "svg.fa-objects-column + span.font-semibold",
        "surface": "svg.fa-ruler-combined + span.font-semibold",
        "date": "time",
        "details_url": "a.whitespace-nowrap.border.bg-primary-500",
    }
    
    def __init__(self, max_retries: int = 3, sleep_time: float = 1.0):
        """
        Initialize the browser manager.
        
        Args:
            max_retries: Maximum number of retry attempts in case of error
            sleep_time: Wait time between requests (seconds)
        """
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    
    async def extract_properties(self, urls: List[Dict]) -> List[Dict[str, Any]]:
        """
        Extract properties from a list of URLs.
        
        Args:
            urls: List of dictionaries containing URLs and metadata
        
        Returns:
            List[Dict]: List of extracted properties
        """
        logger.info(f"Extracting properties from {len(urls)} URLs")
        
        all_properties = []
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent
            )
            
            try:
                page = await context.new_page()
                
                # Process each URL
                for index, url_data in enumerate(urls):
                    url = url_data["url"]
                    logger.info(f"Processing URL {index+1}/{len(urls)}: {url[:100]}...")
                    
                    # Extract properties with retry
                    properties = await self._extract_from_url(
                        page, url, url_data, retries=self.max_retries
                    )
                    
                    if properties:
                        all_properties.extend(properties)
                        logger.info(f"Extracted {len(properties)} properties from URL")
                    else:
                        logger.warning(f"No properties extracted from URL")
                    
                    # Pause between requests
                    await asyncio.sleep(self.sleep_time)
            
            finally:
                # Close browser
                await context.close()
                await browser.close()
        
        logger.info(f"Total properties extracted: {len(all_properties)}")
        return all_properties
    
    async def _extract_from_url(
        self,
        page: Page,
        url: str,
        url_data: Dict,
        retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Extract properties from an ImmoData page with retry mechanism.
        
        Args:
            page: Playwright Page
            url: URL to extract data from
            url_data: Metadata associated with the URL
            retries: Number of remaining attempts
        
        Returns:
            List[Dict]: List of extracted properties
        """
        try:
            # Navigate to URL
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Wait for content to load
            await page.wait_for_selector(self.SELECTORS["container"], timeout=10000)
            
            # Get HTML content
            content = await page.content()
            
            # Parse with BeautifulSoup
            return self._parse_properties(content, url_data)
            
        except Exception as e:
            logger.error(f"Error extracting from URL: {str(e)}")
            
            if retries > 0:
                logger.info(f"Retrying... ({retries} attempts left)")
                await asyncio.sleep(2)  # Delay before retry
                return await self._extract_from_url(page, url, url_data, retries - 1)
            
            return []
    
    def _parse_properties(self, html: str, url_data: Dict) -> List[Dict[str, Any]]:
        """
        Parse HTML to extract properties.
        
        Args:
            html: HTML content of the page
            url_data: Metadata associated with the URL
        
        Returns:
            List[Dict]: List of extracted properties
        """
        properties = []
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Find main container
            container = soup.select_one(self.SELECTORS["container"])
            if not container:
                logger.warning("Container not found in HTML")
                return []
            
            # Find all properties
            property_elements = container.select(self.SELECTORS["property"])
            
            logger.info(f"Found {len(property_elements)} property elements")
            
            for element in property_elements:
                try:
                    # Extract essential information
                    address_elem = element.select_one(self.SELECTORS["address"])
                    price_elem = element.select_one(self.SELECTORS["price"])
                    rooms_elem = element.select_one(self.SELECTORS["rooms"])
                    surface_elem = element.select_one(self.SELECTORS["surface"])
                    date_elem = element.select_one(self.SELECTORS["date"])
                    details_url_elem = element.select_one(self.SELECTORS["details_url"])

                    # Extract property type from HTML, not from URL data
                    type_tag = element.find('p', class_='flex items-center text-sm text-gray-400')
                    if type_tag and type_tag.span:
                        property_type = type_tag.span.text.strip()
                    else:
                        property_type = ""
                        logger.warning("Property type not found for a property element")

                    # Extract address and city
                    address, city, postal_code = self._parse_address(
                        address_elem.text if address_elem else ""
                    )
                    
                    # Create property object (exclude 'source_url' and 'postal_code')
                    property_data = {
                        "address": address,
                        "city": city,
                        "price": self._parse_price(price_elem.text if price_elem else ""),
                        "rooms": self._parse_rooms(rooms_elem.text if rooms_elem else ""),
                        "surface": self._parse_surface(surface_elem.text if surface_elem else ""),
                        "sale_date": self._parse_date(date_elem.get("datetime") if date_elem else ""),
                        "property_type": property_type,
                        "property_url": self._parse_url(details_url_elem.get("href") if details_url_elem else "")
                    }
                    
                    properties.append(property_data)
                
                except Exception as e:
                    logger.error(f"Error parsing property element: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {str(e)}")
        
        return properties
    
    def _parse_address(self, text: str) -> Tuple[str, str, str]:
        """
        Parse address to extract address, city and postal code.
        
        Args:
            text: Text containing the address
        
        Returns:
            Tuple[str, str, str]: (address, city, postal_code)
        """
        if not text:
            return "", "", ""
        
        # Expected format: "Address - City ZIP"
        match = re.search(r'(.+)\s-\s(.+)\s(\d{5})', text)
        if match:
            address = match.group(1).strip()
            city = match.group(2).strip()
            postal_code = match.group(3).strip()
            return address, city, postal_code
        
        # Alternative: "Address - City"
        match = re.search(r'(.+)\s-\s(.+)', text)
        if match:
            address = match.group(1).strip()
            city = match.group(2).strip()
            # Try to extract postal code from city
            cp_match = re.search(r'(\d{5})', city)
            postal_code = cp_match.group(1) if cp_match else ""
            city = re.sub(r'\d{5}', '', city).strip()
            return address, city, postal_code
        
        return text, "", ""
    
    def _parse_price(self, text: str) -> int:
        """
        Parse price to extract a numeric value.
        
        Args:
            text: Text containing the price
        
        Returns:
            int: Price in euros
        """
        if not text:
            return 0
        
        # Extract numbers
        numbers = re.sub(r'[^\d]', '', text)
        try:
            return int(numbers)
        except ValueError:
            return 0
    
    def _parse_rooms(self, text: str) -> int:
        """
        Parse number of rooms.
        
        Args:
            text: Text containing the number of rooms
        
        Returns:
            int: Number of rooms
        """
        if not text:
            return 0
        
        try:
            # Clean and convert
            clean_text = text.strip()
            return int(clean_text) if clean_text.isdigit() else 0
        except ValueError:
            return 0
    
    def _parse_surface(self, text: str) -> float:
        """
        Parse surface area in square meters.
        
        Args:
            text: Text containing the surface area
        
        Returns:
            float: Surface area in m²
        """
        if not text:
            return 0.0
        
        try:
            # Expected format: "XX m²"
            clean_text = text.replace('m²', '').strip().replace(',', '.')
            return float(clean_text)
        except ValueError:
            return 0.0
    
    def _parse_date(self, timestamp: str) -> str:
        """
        Parse sale date from timestamp.
        
        Args:
            timestamp: Unix timestamp in milliseconds
        
        Returns:
            str: Date in DD/MM/YYYY format
        """
        if not timestamp:
            return ""
        
        try:
            # Expected format: timestamp in milliseconds
            ts = int(timestamp) // 1000  # Convert to seconds
            date = datetime.fromtimestamp(ts)
            return date.strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            return ""
    
    def _parse_url(self, url: str) -> str:
        """
        Format property details URL.
        
        Args:
            url: Relative URL
            
        Returns:
            str: Complete URL
        """
        if not url:
            return ""
        
        # Add prefix if it's a relative URL
        if url.startswith('/'):
            return f"https://www.immo-data.fr{url}"
        return url
        
    async def extract_properties_with_count(
        self, 
        url_data: Dict, 
        adaptive_generator=None,
        recursion_depth: int = 0
    ) -> Tuple[List[Dict[str, Any]], int, bool]:
        """
        Extract properties from a URL with counting and adaptive recursion.
        Always returns all properties regardless of subdivision status.
        
        Args:
            url_data: URL data
            adaptive_generator: Adaptive generator for subdivision
            recursion_depth: Current recursion depth
        
        Returns:
            Tuple[List[Dict], int, bool]: 
                - Extracted properties
                - Number of properties
                - Indicator if subdivisions were performed
        """
        url = url_data["url"]
        max_recursion = 2  # Limit to 2 levels of subdivision
        
        # Display URL and metadata
        subdivision_level = url_data.get("subdivision_level", 0)
        price_range = url_data.get("price_range", "all prices")
        property_type = url_data.get("property_type", "all types")
        property_types_str = ",".join(url_data.get("property_types", []))

        logger.info(f"Processing URL (depth={recursion_depth}, level={subdivision_level})")
        logger.info(f"Type: {property_type}, Types included: {property_types_str}, Price: {price_range}")
        logger.info(f"Complete URL: {url}")
                
        all_properties = []
        was_subdivided = False
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent
            )
            
            try:
                page = await context.new_page()
                
                # Extract properties with retry
                properties = await self._extract_from_url(
                    page, url, url_data, retries=self.max_retries
                )
                
                property_count = len(properties)
                logger.info(f"Extracted {property_count} properties from URL")
                
                # Always start by collecting the properties from this level
                all_properties.extend(properties)
                
                # If adaptive generator provided, sufficient number of properties, and max level not reached
                if adaptive_generator and property_count >= 90 and recursion_depth < max_recursion:
                    # Log subdivision decision
                    if subdivision_level == 0:
                        logger.warning(f"URL has {property_count} properties, subdividing by TYPE...")
                    elif subdivision_level == 1:
                        logger.warning(f"URL has {property_count} properties, subdividing by PRICE...")
                    else:
                        logger.warning(f"URL has {property_count} properties, additional subdivision...")
                        
                    # Pass extracted properties for price analysis
                    subdivided_urls = adaptive_generator.subdivide_if_needed(
                        url_data, property_count, properties
                    )
                    
                    if subdivided_urls:
                        logger.info(f"URL subdivided into {len(subdivided_urls)} new URLs")
                        was_subdivided = True
                        
                        # Process each subdivision
                        for sub_url_data in subdivided_urls:
                            sub_props, sub_count, _ = await self.extract_properties_with_count(
                                sub_url_data, 
                                adaptive_generator, 
                                recursion_depth + 1
                            )
                            
                            # Always collect properties from subdivisions
                            if sub_props:
                                all_properties.extend(sub_props)
                                logger.info(f"Added {len(sub_props)} properties from subdivision {sub_url_data['property_type']}")
                            
                            # Pause between requests
                            await asyncio.sleep(self.sleep_time)
            
            finally:
                await context.close()
                await browser.close()
        
        # Always return all properties collected, the count of properties at this level,
        # and whether this level was subdivided
        return all_properties, property_count, was_subdivided