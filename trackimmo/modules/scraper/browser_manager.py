"""
Browser manager for web scraping.
Uses Playwright to extract data from ImmoData pages.
"""

import sys
import os
import asyncio
import re
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

# Fix Windows event loop policy for Playwright compatibility
if sys.platform.startswith("win"):
    # Force WindowsSelectorEventLoop for Playwright compatibility in FastAPI context
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        # Fallback for older Python versions
        pass

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
        "details_url": "a.whitespace-nowrap.border.bg-primary-500"
    }
    
    # Property type mapping from French to English
    PROPERTY_TYPE_MAPPING = {
        'maison': 'house',
        'maisons': 'house',
        'appartement': 'apartment',
        'appartements': 'apartment',
        'terrain': 'land',
        'terrains': 'land',
        'local commercial': 'commercial',
        'locaux commerciaux': 'commercial',
        'autre': 'other',
        'autres': 'other'
    }
    
    def __init__(self, max_retries: int = 3, sleep_time: float = 0.1):
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
        # Shared browser context for reuse
        self._browser = None
        self._context = None
        self._initialized = False
    
    async def _ensure_browser_initialized(self):
        """Ensure browser is initialized for concurrent processing"""
        if not self._initialized:
            try:
                from playwright.async_api import async_playwright
                
                # Force event loop policy for Windows compatibility
                if sys.platform.startswith("win"):
                    try:
                        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                    except AttributeError:
                        pass
                
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    # Additional args for Windows compatibility
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding'
                    ] if sys.platform.startswith("win") else []
                )
                self._context = await self._browser.new_context(
                    viewport={"width": 1920, "height": 1080},  # Large viewport to ensure content is visible
                    user_agent=self.user_agent,
                    # Additional settings to ensure proper loading
                    ignore_https_errors=True,
                    java_script_enabled=True
                )
                self._initialized = True
                logger.info("Browser initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize browser: {str(e)}")
                # Clean up partial initialization
                await self._cleanup_partial_init()
                # Re-raise the exception so calling code can handle it
                raise
    
    async def _cleanup_partial_init(self):
        """Clean up partially initialized browser resources"""
        try:
            if hasattr(self, '_context') and self._context:
                await self._context.close()
        except:
            pass
        
        try:
            if hasattr(self, '_browser') and self._browser:
                await self._browser.close()
        except:
            pass
        
        try:
            if hasattr(self, '_playwright') and self._playwright:
                await self._playwright.stop()
        except:
            pass
        
        self._initialized = False
    
    async def cleanup(self):
        """Cleanup browser resources"""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if hasattr(self, '_playwright'):
            await self._playwright.stop()
        self._initialized = False
    
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
        
        try:
            # Force event loop policy for Windows compatibility
            if sys.platform.startswith("win"):
                try:
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) 
                except AttributeError:
                    pass
            
            async with async_playwright() as p:
                # Launch browser with improved settings for Windows
                browser_args = []
                if sys.platform.startswith("win"):
                    browser_args = [
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding'
                    ]
                
                browser = await p.chromium.launch(
                    headless=True,
                    args=browser_args
                )
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},  # Large viewport
                    user_agent=self.user_agent,
                    ignore_https_errors=True,
                    java_script_enabled=True
                )
                
                try:
                    page = await context.new_page()
                    
                    # Process each URL
                    for index, url_data in enumerate(urls):
                        url = url_data["url"]
                        logger.debug(f"Processing URL {index+1}/{len(urls)}: {url[:100]}...")
                        
                        # Extract properties with retry
                        properties = await self._extract_from_url(
                            page, url, url_data, retries=self.max_retries
                        )
                        
                        if properties:
                            all_properties.extend(properties)
                            #logger.info(f"Extracted {len(properties)} properties from URL")
                        else:
                            logger.warning(f"No properties extracted from URL")
                        
                        # Pause between requests
                        await asyncio.sleep(self.sleep_time)
                
                finally:
                    # Close browser
                    try:
                        await context.close()
                        await browser.close()
                    except Exception as e:
                        logger.warning(f"Error closing browser resources: {str(e)}")
        
        except Exception as e:
            logger.error(f"Critical error in extract_properties: {str(e)}")
            logger.error(f"This might be due to Windows/Playwright compatibility issues")
            
            # Return empty list instead of crashing
            # The calling code should handle this gracefully
            if "NotImplementedError" in str(e) or "subprocess" in str(e).lower():
                logger.error("This appears to be a Windows event loop compatibility issue")
                logger.error("Consider running the script directly instead of through the API")
            
            return []
        
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
            # Navigate to URL with proper waiting
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Wait for main container to load
            await page.wait_for_selector(self.SELECTORS["container"], timeout=60000)
            
            # Additional wait to ensure dynamic content loads and skeleton elements are replaced
            # Wait for actual property elements (not skeleton ones)
            try:
                # Wait for non-skeleton property elements to appear
                await page.wait_for_function(
                    """() => {
                        const properties = document.querySelectorAll('div.border-b.border-b-gray-100');
                        // Check if we have real properties (not skeleton loading elements)
                        for (let prop of properties) {
                            if (!prop.querySelector('.skeleton') && prop.textContent.trim().length > 50) {
                                return true;
                            }
                        }
                        return false;
                    }""",
                    timeout=20000
                )
            except:
                # If no non-skeleton elements found, wait a bit more for page to finish loading
                await asyncio.sleep(3)
            
            # Additional wait for any remaining JavaScript
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Get HTML content
            content = await page.content()
            
            # Parse with BeautifulSoup
            return self._parse_properties(content, url_data)
            
        except Exception as e:
            logger.error(f"Error extracting from URL: {str(e)}")
            
            if retries > 0:
                logger.info(f"Retrying... ({retries} attempts left)")
                await asyncio.sleep(3)  # Longer delay before retry
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
            
            # Filter out skeleton/loading elements
            real_property_elements = []
            for element in property_elements:
                # Skip if element contains skeleton loading indicators
                if element.select_one('.skeleton'):
                    logger.debug("Skipping skeleton element")
                    continue
                    
                # Skip if element appears to be empty or just whitespace
                text_content = element.get_text(strip=True)
                if len(text_content) < 20:  # Too short to be a real property
                    logger.debug("Skipping element with insufficient content")
                    continue
                    
                # Skip if element contains only hidden content
                if 'hidden' in element.get('class', []):
                    logger.debug("Skipping hidden element")
                    continue
                    
                real_property_elements.append(element)
            
            logger.debug(f"Found {len(property_elements)} total elements, {len(real_property_elements)} real property elements")
            
            for element in real_property_elements:
                try:
                    # Extract essential information
                    address_elem = element.select_one(self.SELECTORS["address"])
                    price_elem = element.select_one(self.SELECTORS["price"])
                    rooms_elem = element.select_one(self.SELECTORS["rooms"])
                    surface_elem = element.select_one(self.SELECTORS["surface"])
                    date_elem = element.select_one(self.SELECTORS["date"])
                    details_url_elem = element.select_one(self.SELECTORS["details_url"])

                    # Extract property type from HTML with improved parsing
                    property_type = ""
                    raw_property_type = ""
                    
                    # Method 1: Look for the specific class with span (most common)
                    type_tag = element.find('p', class_='flex items-center text-sm text-gray-400')
                    if type_tag:
                        # First try to find the span element inside
                        span_elem = type_tag.find('span')
                        if span_elem and span_elem.text and span_elem.text.strip():
                            raw_property_type = span_elem.text.strip()
                            property_type = self._normalize_property_type(raw_property_type)
                            logger.debug(f"Method 1 found property type: '{raw_property_type}' -> '{property_type}'")
                        else:
                            # Fallback: try to extract text without SVG content
                            # Remove SVG elements first
                            for svg in type_tag.find_all('svg'):
                                svg.decompose()
                            text_content = type_tag.get_text(strip=True)
                            if text_content:
                                # Split by whitespace and take the last non-empty word
                                words = [w.strip() for w in text_content.split() if w.strip()]
                                if words:
                                    raw_property_type = words[-1]
                                    property_type = self._normalize_property_type(raw_property_type)
                                    logger.debug(f"Method 1 fallback found: '{raw_property_type}' -> '{property_type}'")
                    
                    # Method 2: Look for spans with property type keywords directly
                    if not property_type:
                        spans = element.find_all('span')
                        for span in spans:
                            if span.text and span.text.strip():
                                text = span.text.strip().lower()
                                if any(keyword in text for keyword in ['appartement', 'maison', 'terrain', 'local', 'commercial']):
                                    raw_property_type = span.text.strip()
                                    property_type = self._normalize_property_type(raw_property_type)
                                    logger.debug(f"Method 2 found property type: '{raw_property_type}' -> '{property_type}'")
                                    break
                    
                    # Method 3: Search in all text content (broadest search)
                    if not property_type:
                        all_text = element.get_text().lower()
                        # More specific pattern matching
                        if 'appartement' in all_text:
                            property_type = 'apartment'
                            logger.debug(f"Method 3 found 'appartement' in text -> 'apartment'")
                        elif 'maison' in all_text:
                            property_type = 'house'
                            logger.debug(f"Method 3 found 'maison' in text -> 'house'")
                        elif 'terrain' in all_text:
                            property_type = 'land'
                            logger.debug(f"Method 3 found 'terrain' in text -> 'land'")
                        elif 'local commercial' in all_text or 'commercial' in all_text:
                            property_type = 'commercial'
                            logger.debug(f"Method 3 found 'commercial' in text -> 'commercial'")
                    
                    # Method 4: Try alternative CSS selectors (backup)
                    if not property_type:
                        # Try different class combinations that might contain property type
                        alt_selectors = [
                            'p.text-sm.text-gray-400',
                            'span.text-gray-400',
                            'div.text-sm span',
                            'p span'
                        ]
                        for selector in alt_selectors:
                            elements = element.select(selector)
                            for elem in elements:
                                if elem.text and elem.text.strip():
                                    text = elem.text.strip().lower()
                                    if any(keyword in text for keyword in ['appartement', 'maison', 'terrain', 'local', 'commercial']):
                                        raw_property_type = elem.text.strip()
                                        property_type = self._normalize_property_type(raw_property_type)
                                        logger.debug(f"Method 4 ({selector}) found: '{raw_property_type}' -> '{property_type}'")
                                        break
                            if property_type:
                                break
                    
                    # Final fallback and logging
                    if not property_type:
                        property_type = "other"
                        # Log first few times for debugging
                        if len(properties) < 3:  # Only log for first few properties to avoid spam
                            logger.warning(f"Property type not found in property {len(properties)+1}. Element HTML sample: {str(element)[:200]}...")
                            logger.warning(f"All text content: {element.get_text()[:100]}...")
                        else:
                            logger.debug("Property type not found, using 'other'")
                    else:
                        # Log successful extractions for first few properties
                        if len(properties) < 5:
                            logger.debug(f"Property {len(properties)+1}: Successfully extracted type '{property_type}' from '{raw_property_type}'")

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
    
    def _normalize_property_type(self, raw_type: str) -> str:
        """
        Normalize property type from French to English.
        
        Args:
            raw_type: Raw property type in French
            
        Returns:
            str: Normalized property type in English
        """
        if not raw_type:
            return "other"
        
        # Convert to lowercase for mapping
        normalized = raw_type.lower().strip()
        
        # Map to English equivalent
        return self.PROPERTY_TYPE_MAPPING.get(normalized, "other")
    
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
        
        # Display URL and metadata
        subdivision_level = url_data.get("subdivision_level", 0)
        price_range = url_data.get("price_range", "all prices")
        property_type = url_data.get("property_type", "all types")
        property_types_str = ",".join(url_data.get("property_types", []))

        logger.debug(f"Processing URL (depth={recursion_depth}, level={subdivision_level})")
        logger.debug(f"Type: {property_type}, Types included: {property_types_str}, Price: {price_range}")
        logger.debug(f"Complete URL: {url}")
                
        all_properties = []
        was_subdivided = False
        
        # Use shared browser context for better performance
        await self._ensure_browser_initialized()
        page = await self._context.new_page()
        
        try:
            # Extract properties with retry
            properties = await self._extract_from_url(
                page, url, url_data, retries=self.max_retries
            )
            
            property_count = len(properties)
            logger.info(f"Extracted {property_count} properties from URL")
            
            # Always start by collecting the properties from this level
            all_properties.extend(properties)
            
            # Check if we need further subdivision (when we hit the 101 property limit)
            # Using progressive subdivision approach with caching
            if adaptive_generator and property_count >= 99:
                
                # Log subdivision decision with progressive context
                subdivision_level = url_data.get("subdivision_level", 0)
                progressive_level = url_data.get("progressive_level", 1)
                
                # Pass extracted properties for appropriate subdivision
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
                            logger.debug(f"Added {len(sub_props)} properties from subdivision {sub_url_data['property_type']}")
                        
                        # Pause between requests
                        await asyncio.sleep(self.sleep_time)
        
        finally:
            await page.close()
        
        # Always return all properties collected, the count of properties at this level,
        # and whether this level was subdivided
        return all_properties, property_count, was_subdivided