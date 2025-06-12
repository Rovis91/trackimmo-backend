"""
City data scraper for TrackImmo.
Extracts city information and average property prices from ImmoData.
"""

import sys
import os
import asyncio
import re
import logging
import requests
import unicodedata
from typing import Dict, Any, Optional, Tuple
from urllib.parse import quote
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from trackimmo.utils.logger import get_logger

# Fix Windows event loop policy for Playwright compatibility
if sys.platform.startswith("win"):
    # Force WindowsSelectorEventLoop for Playwright compatibility in FastAPI context
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        # Fallback for older Python versions
        pass

logger = get_logger(__name__)

class CityDataScraper:
    """
    Scraper for city data including INSEE codes and average property prices.
    """
    
    def __init__(self, max_retries: int = 3, sleep_time: float = 1.0):
        """
        Initialize the city data scraper.
        
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
        
    async def scrape_city(self, city_name: str, postal_code: str, insee_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Scrape city data including INSEE code and average property prices.
        
        Args:
            city_name: Name of the city
            postal_code: Postal code
            insee_code: INSEE code (optional, will be fetched if not provided)
        
        Returns:
            Dict containing city data
        """
        logger.info(f"Scraping data for {city_name} ({postal_code})")
        
        # Initialize city data
        city_data = {
            "name": city_name,
            "postal_code": postal_code,
            "insee_code": insee_code,
            "house_price_avg": None,
            "apartment_price_avg": None,
            "last_scraped": "now()",
            "status": "success",
            "error_message": None
        }
        
        try:
            # 1. Get INSEE code, department and region if not provided
            if not insee_code:
                logger.info(f"Fetching INSEE code for {city_name}")
                geo_data = self._get_geocoding_data(city_name, postal_code)
                
                if not geo_data:
                    city_data["status"] = "error"
                    city_data["error_message"] = "Failed to fetch geocoding data"
                    return city_data
                
                city_data.update(geo_data)
                insee_code = geo_data.get("insee_code")
            else:
                # Even with INSEE code, we need to get department and region
                geo_data = self._get_geocoding_data(city_name, postal_code)
                if geo_data:
                    # Keep the provided INSEE code but get other data
                    geo_data["insee_code"] = insee_code
                    city_data.update(geo_data)
            
            # 2. Generate market URL
            if insee_code:
                department = city_data.get("department")
                logger.info(f"Debug: city_name={city_name}, department={department}, insee_code={insee_code}")
                market_url = self._generate_market_url(city_name, department, insee_code)
                logger.info(f"Generated market URL: {market_url}")
                
                # 3. Scrape average prices
                prices = await self._scrape_prices(market_url)
                if prices:
                    city_data.update(prices)
            else:
                city_data["status"] = "error"
                city_data["error_message"] = "Could not obtain INSEE code"
            
        except Exception as e:
            logger.error(f"Error scraping city data: {str(e)}")
            city_data["status"] = "error"
            city_data["error_message"] = str(e)
        
        return city_data
    
    def _get_geocoding_data(self, city_name: str, postal_code: str) -> Optional[Dict[str, str]]:
        """
        Get INSEE code, department and region using the geocoding API.
        
        Args:
            city_name: Name of the city
            postal_code: Postal code
        
        Returns:
            Dict with insee_code, department, and region or None if failed
        """
        try:
            # Use address API to get coordinates
            api_url = "https://api-adresse.data.gouv.fr/search/"
            
            params = {
                "q": f"{city_name} {postal_code}",
                "limit": 1,
                "type": "municipality"
            }
            
            response = requests.get(api_url, params=params)
            data = response.json()
            
            if not data.get("features"):
                logger.warning(f"No geocoding data found for {city_name} ({postal_code})")
                return None
            
            feature = data["features"][0]
            properties = feature["properties"]
            
            # Extract INSEE code, department and context
            insee_code = properties.get("citycode")
            api_postal_code = properties.get("postcode", postal_code)
            
            # Clean postal code to ensure it's only 5 digits
            # Sometimes the API returns multiple postal codes like "91190-91650"
            if api_postal_code:
                # Take only the first 5 digits, removing any non-digit characters
                clean_postal = ''.join(filter(str.isdigit, api_postal_code))[:5]
                postal_code = clean_postal if len(clean_postal) == 5 else postal_code
            
            # Extract department (first 2/3 digits of INSEE code)
            department = insee_code[:2]
            # Handle Corsica special case
            if department == "20":
                department = insee_code[:3]
            
            # Extract region from context (format is typically: region, department, ...)
            context = properties.get("context", "")
            region = context.split(",")[0].strip() if context else ""
            
            return {
                "insee_code": insee_code,
                "postal_code": postal_code,
                "department": department,
                "region": region
            }
            
        except Exception as e:
            logger.error(f"Error fetching geocoding data: {str(e)}")
            return None
    
    def _generate_market_url(self, city_name: str, department: str, insee_code: str) -> str:
        """
        Generate ImmoData market URL.
        
        Args:
            city_name: Name of the city
            department: Department code
            insee_code: INSEE code
        
        Returns:
            ImmoData market URL
        """
        # Convert to lowercase and remove accents
        city_slug = self._slugify(city_name)
        
        # Get department name and code
        department_name = self._get_department_name(department)
        department_slug = self._slugify(department_name) if department_name else department
        
        # Get region name and code
        region_name = self._get_region_from_department(department)
        region_code = self._get_region_code_from_department(department)
        region_slug = self._slugify(region_name) if region_name else "france"
        
        # Build URL with correct format: region-code/department-code/city-insee
        return f"https://www.immo-data.fr/marche-immobilier/{region_slug}-{region_code}/{department_slug}-{department}/{city_slug}-{insee_code}/"
    
    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-friendly slug format.
        
        Args:
            text: Text to slugify
        
        Returns:
            Slugified text
        """
        if not text:
            return ""
        
        # Remove accents
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace spaces with hyphens
        text = re.sub(r'[^a-z0-9]+', '-', text)
        
        # Remove leading/trailing hyphens
        text = text.strip('-')
        
        return text
    
    def _get_department_name(self, department_code: str) -> Optional[str]:
        """
        Get department name from code.
        
        Args:
            department_code: Department code
        
        Returns:
            Department name or None if not found
        """
        # Simple mapping for common departments
        department_mapping = {
            "01": "ain", "02": "aisne", "03": "allier", "04": "alpes-de-haute-provence",
            "05": "hautes-alpes", "06": "alpes-maritimes", "07": "ardeche", "08": "ardennes",
            "09": "ariege", "10": "aube", "11": "aude", "12": "aveyron",
            "13": "bouches-du-rhone", "14": "calvados", "15": "cantal", "16": "charente",
            "17": "charente-maritime", "18": "cher", "19": "correze", "21": "cote-d-or",
            "22": "cotes-d-armor", "23": "creuse", "24": "dordogne", "25": "doubs",
            "26": "drome", "27": "eure", "28": "eure-et-loir", "29": "finistere",
            "2A": "corse-du-sud", "2B": "haute-corse", "30": "gard", "31": "haute-garonne",
            "32": "gers", "33": "gironde", "34": "herault", "35": "ille-et-vilaine",
            "36": "indre", "37": "indre-et-loire", "38": "isere", "39": "jura",
            "40": "landes", "41": "loir-et-cher", "42": "loire", "43": "haute-loire",
            "44": "loire-atlantique", "45": "loiret", "46": "lot", "47": "lot-et-garonne",
            "48": "lozere", "49": "maine-et-loire", "50": "manche", "51": "marne",
            "52": "haute-marne", "53": "mayenne", "54": "meurthe-et-moselle", "55": "meuse",
            "56": "morbihan", "57": "moselle", "58": "nievre", "59": "nord",
            "60": "oise", "61": "orne", "62": "pas-de-calais", "63": "puy-de-dome",
            "64": "pyrenees-atlantiques", "65": "hautes-pyrenees", "66": "pyrenees-orientales",
            "67": "bas-rhin", "68": "haut-rhin", "69": "rhone", "70": "haute-saone",
            "71": "saone-et-loire", "72": "sarthe", "73": "savoie", "74": "haute-savoie",
            "75": "paris", "76": "seine-maritime", "77": "seine-et-marne", "78": "yvelines",
            "79": "deux-sevres", "80": "somme", "81": "tarn", "82": "tarn-et-garonne",
            "83": "var", "84": "vaucluse", "85": "vendee", "86": "vienne",
            "87": "haute-vienne", "88": "vosges", "89": "yonne", "90": "territoire-de-belfort",
            "91": "essonne", "92": "hauts-de-seine", "93": "seine-saint-denis", "94": "val-de-marne",
            "95": "val-d-oise", "971": "guadeloupe", "972": "martinique", "973": "guyane",
            "974": "la-reunion", "976": "mayotte"
        }
        
        return department_mapping.get(department_code.upper())
    
    def _get_region_from_department(self, department_code: str) -> Optional[str]:
        """
        Get region name from department code.
        
        Args:
            department_code: Department code
        
        Returns:
            Region name or None if not found
        """
        # Simplified mapping for 2022 French regions
        region_mapping = {
            "01": "auvergne-rhone-alpes", "03": "auvergne-rhone-alpes", "07": "auvergne-rhone-alpes", 
            "15": "auvergne-rhone-alpes", "26": "auvergne-rhone-alpes", "38": "auvergne-rhone-alpes", 
            "42": "auvergne-rhone-alpes", "43": "auvergne-rhone-alpes", "63": "auvergne-rhone-alpes", 
            "69": "auvergne-rhone-alpes", "73": "auvergne-rhone-alpes", "74": "auvergne-rhone-alpes",
            
            "21": "bourgogne-franche-comte", "25": "bourgogne-franche-comte", "39": "bourgogne-franche-comte", 
            "58": "bourgogne-franche-comte", "70": "bourgogne-franche-comte", "71": "bourgogne-franche-comte", 
            "89": "bourgogne-franche-comte", "90": "bourgogne-franche-comte",
            
            "22": "bretagne", "29": "bretagne", "35": "bretagne", "56": "bretagne",
            
            "18": "centre-val-de-loire", "28": "centre-val-de-loire", "36": "centre-val-de-loire", 
            "37": "centre-val-de-loire", "41": "centre-val-de-loire", "45": "centre-val-de-loire",
            
            "2A": "corse", "2B": "corse",
            
            "08": "grand-est", "10": "grand-est", "51": "grand-est", "52": "grand-est", 
            "54": "grand-est", "55": "grand-est", "57": "grand-est", "67": "grand-est", 
            "68": "grand-est", "88": "grand-est",
            
            "02": "hauts-de-france", "59": "hauts-de-france", "60": "hauts-de-france", 
            "62": "hauts-de-france", "80": "hauts-de-france",
            
            "75": "ile-de-france", "77": "ile-de-france", "78": "ile-de-france", "91": "ile-de-france", 
            "92": "ile-de-france", "93": "ile-de-france", "94": "ile-de-france", "95": "ile-de-france",
            
            "14": "normandie", "27": "normandie", "50": "normandie", "61": "normandie", "76": "normandie",
            
            "16": "nouvelle-aquitaine", "17": "nouvelle-aquitaine", "19": "nouvelle-aquitaine", 
            "23": "nouvelle-aquitaine", "24": "nouvelle-aquitaine", "33": "nouvelle-aquitaine", 
            "40": "nouvelle-aquitaine", "47": "nouvelle-aquitaine", "64": "nouvelle-aquitaine", 
            "79": "nouvelle-aquitaine", "86": "nouvelle-aquitaine", "87": "nouvelle-aquitaine",
            
            "09": "occitanie", "11": "occitanie", "12": "occitanie", "30": "occitanie", 
            "31": "occitanie", "32": "occitanie", "34": "occitanie", "46": "occitanie", 
            "48": "occitanie", "65": "occitanie", "66": "occitanie", "81": "occitanie", 
            "82": "occitanie",
            
            "44": "pays-de-la-loire", "49": "pays-de-la-loire", "53": "pays-de-la-loire", 
            "72": "pays-de-la-loire", "85": "pays-de-la-loire",
            
            "04": "provence-alpes-cote-d-azur", "05": "provence-alpes-cote-d-azur", 
            "06": "provence-alpes-cote-d-azur", "13": "provence-alpes-cote-d-azur", 
            "83": "provence-alpes-cote-d-azur", "84": "provence-alpes-cote-d-azur",
            
            "971": "guadeloupe", "972": "martinique", "973": "guyane", 
            "974": "la-reunion", "976": "mayotte"
        }
        
        return region_mapping.get(department_code.upper())
    
    def _get_region_code_from_department(self, department_code: str) -> str:
        """
        Get region code from department code.
        
        Args:
            department_code: Department code
        
        Returns:
            Region code (number) or "00" if not found
        """
        # Mapping from department to region code (2022 regions)
        region_code_mapping = {
            # Auvergne-Rhône-Alpes (84)
            "01": "84", "03": "84", "07": "84", "15": "84", "26": "84", "38": "84", 
            "42": "84", "43": "84", "63": "84", "69": "84", "73": "84", "74": "84",
            
            # Bourgogne-Franche-Comté (27)
            "21": "27", "25": "27", "39": "27", "58": "27", "70": "27", "71": "27", 
            "89": "27", "90": "27",
            
            # Bretagne (53)
            "22": "53", "29": "53", "35": "53", "56": "53",
            
            # Centre-Val de Loire (24)
            "18": "24", "28": "24", "36": "24", "37": "24", "41": "24", "45": "24",
            
            # Corse (94)
            "2A": "94", "2B": "94",
            
            # Grand Est (44)
            "08": "44", "10": "44", "51": "44", "52": "44", "54": "44", "55": "44", 
            "57": "44", "67": "44", "68": "44", "88": "44",
            
            # Hauts-de-France (32)
            "02": "32", "59": "32", "60": "32", "62": "32", "80": "32",
            
            # Île-de-France (11)
            "75": "11", "77": "11", "78": "11", "91": "11", "92": "11", "93": "11", 
            "94": "11", "95": "11",
            
            # Normandie (28)
            "14": "28", "27": "28", "50": "28", "61": "28", "76": "28",
            
            # Nouvelle-Aquitaine (75)
            "16": "75", "17": "75", "19": "75", "23": "75", "24": "75", "33": "75", 
            "40": "75", "47": "75", "64": "75", "79": "75", "86": "75", "87": "75",
            
            # Occitanie (76)
            "09": "76", "11": "76", "12": "76", "30": "76", "31": "76", "32": "76", 
            "34": "76", "46": "76", "48": "76", "65": "76", "66": "76", "81": "76", 
            "82": "76",
            
            # Pays de la Loire (52)
            "44": "52", "49": "52", "53": "52", "72": "52", "85": "52",
            
            # Provence-Alpes-Côte d'Azur (93)
            "04": "93", "05": "93", "06": "93", "13": "93", "83": "93", "84": "93",
            
            # Overseas territories
            "971": "01", "972": "02", "973": "03", "974": "04", "976": "06"
        }
        
        return region_code_mapping.get(department_code.upper(), "00")
    
    async def _scrape_prices(self, url: str) -> Dict[str, Optional[int]]:
        """
        Scrape average property prices from ImmoData.
        
        Args:
            url: ImmoData market URL
        
        Returns:
            Dict with house_price_avg and apartment_price_avg
        """
        result = {
            "house_price_avg": None,
            "apartment_price_avg": None
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent
            )
            
            try:
                page = await context.new_page()
                
                # Navigate to URL
                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
                # Extract apartment price with JavaScript evaluation
                apartment_price = await page.evaluate('''
                    () => {
                        // Find the paragraph with the text "Appartements - Prix"
                        const apartmentHeading = Array.from(document.querySelectorAll('p')).find(
                            p => p.textContent.includes('Appartements - Prix')
                        );
                        
                        if (!apartmentHeading) return null;
                        
                        // Get the closest parent div
                        const card = apartmentHeading.closest('div.flex.flex-col.gap-3');
                        if (!card) return null;
                        
                        // Find the price span
                        const priceElement = card.querySelector('p.text-3xl.font-bold > span');
                        return priceElement ? priceElement.textContent : null;
                    }
                ''')
                
                if apartment_price:
                    # Parse the price (remove currency symbol and non-digits)
                    numeric_price = re.sub(r'[^\d]', '', apartment_price)
                    if numeric_price:
                        result["apartment_price_avg"] = int(numeric_price)
                        logger.info(f"Extracted apartment price: {result['apartment_price_avg']}")
                
                # Extract house price with JavaScript evaluation
                house_price = await page.evaluate('''
                    () => {
                        // Find the paragraph with the text "Maisons - Prix"
                        const houseHeading = Array.from(document.querySelectorAll('p')).find(
                            p => p.textContent.includes('Maisons - Prix')
                        );
                        
                        if (!houseHeading) return null;
                        
                        // Get the closest parent div
                        const card = houseHeading.closest('div.flex.flex-col.gap-3');
                        if (!card) return null;
                        
                        // Find the price span
                        const priceElement = card.querySelector('p.text-3xl.font-bold > span');
                        return priceElement ? priceElement.textContent : null;
                    }
                ''')
                
                if house_price:
                    # Parse the price (remove currency symbol and non-digits)
                    numeric_price = re.sub(r'[^\d]', '', house_price)
                    if numeric_price:
                        result["house_price_avg"] = int(numeric_price)
                        logger.info(f"Extracted house price: {result['house_price_avg']}")
                
            except Exception as e:
                logger.error(f"Error scraping prices: {str(e)}")
            
            finally:
                await context.close()
                await browser.close()
        
        return result

async def scrape_cities(cities_data, max_retries=3, sleep_time=1.0):
    """
    Scrape data for multiple cities.
    
    Args:
        cities_data: List of dicts with city_name and postal_code
        max_retries: Maximum number of retry attempts
        sleep_time: Wait time between requests
    
    Returns:
        List of city data dicts
    """
    scraper = CityDataScraper(max_retries=max_retries, sleep_time=sleep_time)
    results = []
    
    for city_data in cities_data:
        city_name = city_data.get("city_name")
        postal_code = city_data.get("postal_code")
        insee_code = city_data.get("insee_code")
        
        if not city_name or not postal_code:
            logger.warning(f"Skipping city with missing data: {city_data}")
            continue
        
        result = await scraper.scrape_city(city_name, postal_code, insee_code)
        results.append(result)
        
        # Sleep between requests
        await asyncio.sleep(sleep_time)
    
    return results