"""
Gestionnaire de navigateur pour le scraping.
Utilise Playwright pour extraire les données depuis les pages ImmoData.
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
    Gère l'interaction avec le navigateur et l'extraction des données.
    """
    
    # Sélecteurs CSS pour ImmoData
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
        Initialise le gestionnaire de navigateur.
        
        Args:
            max_retries: Nombre maximal de tentatives en cas d'erreur
            sleep_time: Temps d'attente entre les requêtes (secondes)
        """
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    
    async def extract_properties(self, urls: List[Dict]) -> List[Dict[str, Any]]:
        """
        Extrait les propriétés à partir d'une liste d'URLs.
        
        Args:
            urls: Liste de dictionnaires contenant les URLs et métadonnées
        
        Returns:
            List[Dict]: Liste des propriétés extraites
        """
        logger.info(f"Extracting properties from {len(urls)} URLs")
        
        all_properties = []
        
        async with async_playwright() as p:
            # Lancer le navigateur
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent
            )
            
            try:
                page = await context.new_page()
                
                # Traiter chaque URL
                for index, url_data in enumerate(urls):
                    url = url_data["url"]
                    logger.info(f"Processing URL {index+1}/{len(urls)}: {url[:100]}...")
                    
                    # Extraire les propriétés avec retry
                    properties = await self._extract_from_url(
                        page, url, url_data, retries=self.max_retries
                    )
                    
                    if properties:
                        all_properties.extend(properties)
                        logger.info(f"Extracted {len(properties)} properties from URL")
                    else:
                        logger.warning(f"No properties extracted from URL")
                    
                    # Pause entre les requêtes
                    await asyncio.sleep(self.sleep_time)
            
            finally:
                # Fermer le navigateur
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
        Extrait les propriétés d'une page ImmoData avec retry.
        
        Args:
            page: Page Playwright
            url: URL à extraire
            url_data: Données associées à l'URL
            retries: Nombre de tentatives restantes
        
        Returns:
            List[Dict]: Liste des propriétés extraites
        """
        try:
            # Naviguer vers l'URL
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Attendre que le contenu soit chargé
            await page.wait_for_selector(self.SELECTORS["container"], timeout=10000)
            
            # Récupérer le contenu HTML
            content = await page.content()
            
            # Parser avec BeautifulSoup
            return self._parse_properties(content, url_data)
            
        except Exception as e:
            logger.error(f"Error extracting from URL: {str(e)}")
            
            if retries > 0:
                logger.info(f"Retrying... ({retries} attempts left)")
                await asyncio.sleep(2)  # Délai avant retry
                return await self._extract_from_url(page, url, url_data, retries - 1)
            
            return []
    
    def _parse_properties(self, html: str, url_data: Dict) -> List[Dict[str, Any]]:
        """
        Parse le HTML pour extraire les propriétés.
        
        Args:
            html: Contenu HTML de la page
            url_data: Données associées à l'URL
        
        Returns:
            List[Dict]: Liste des propriétés extraites
        """
        properties = []
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Trouver le conteneur principal
            container = soup.select_one(self.SELECTORS["container"])
            if not container:
                logger.warning("Container not found in HTML")
                return []
            
            # Trouver toutes les propriétés
            property_elements = container.select(self.SELECTORS["property"])
            
            logger.info(f"Found {len(property_elements)} property elements")
            
            for element in property_elements:
                try:
                    # Extraire les informations essentielles
                    address_elem = element.select_one(self.SELECTORS["address"])
                    price_elem = element.select_one(self.SELECTORS["price"])
                    rooms_elem = element.select_one(self.SELECTORS["rooms"])
                    surface_elem = element.select_one(self.SELECTORS["surface"])
                    date_elem = element.select_one(self.SELECTORS["date"])
                    details_url_elem = element.select_one(self.SELECTORS["details_url"])
                    
                    # Informations de base de l'URL
                    property_type = url_data["property_type"]
                    period = url_data["period"]
                    
                    # Extraire l'adresse et la ville
                    address, city, postal_code = self._parse_address(
                        address_elem.text if address_elem else ""
                    )
                    
                    # Créer l'objet propriété
                    property_data = {
                        "address": address,
                        "city": city,
                        "postal_code": postal_code,
                        "price": self._parse_price(price_elem.text if price_elem else ""),
                        "rooms": self._parse_rooms(rooms_elem.text if rooms_elem else ""),
                        "surface": self._parse_surface(surface_elem.text if surface_elem else ""),
                        "sale_date": self._parse_date(date_elem.get("datetime") if date_elem else ""),
                        "property_type": property_type,
                        "property_url": self._parse_url(details_url_elem.get("href") if details_url_elem else ""),
                        "source_url": url_data["url"]
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
        Parse l'adresse pour extraire l'adresse, la ville et le code postal.
        
        Args:
            text: Texte contenant l'adresse
        
        Returns:
            Tuple[str, str, str]: (adresse, ville, code_postal)
        """
        if not text:
            return "", "", ""
        
        # Format attendu: "Adresse - Ville CP"
        match = re.search(r'(.+)\s-\s(.+)\s(\d{5})', text)
        if match:
            address = match.group(1).strip()
            city = match.group(2).strip()
            postal_code = match.group(3).strip()
            return address, city, postal_code
        
        # Alternative: "Adresse - Ville"
        match = re.search(r'(.+)\s-\s(.+)', text)
        if match:
            address = match.group(1).strip()
            city = match.group(2).strip()
            # Essayer d'extraire le code postal de la ville
            cp_match = re.search(r'(\d{5})', city)
            postal_code = cp_match.group(1) if cp_match else ""
            city = re.sub(r'\d{5}', '', city).strip()
            return address, city, postal_code
        
        return text, "", ""
    
    def _parse_price(self, text: str) -> int:
        """
        Parse le prix pour extraire une valeur numérique.
        
        Args:
            text: Texte contenant le prix
        
        Returns:
            int: Prix en euros
        """
        if not text:
            return 0
        
        # Extraire les chiffres
        numbers = re.sub(r'[^\d]', '', text)
        try:
            return int(numbers)
        except ValueError:
            return 0
    
    def _parse_rooms(self, text: str) -> int:
        """
        Parse le nombre de pièces.
        
        Args:
            text: Texte contenant le nombre de pièces
        
        Returns:
            int: Nombre de pièces
        """
        if not text:
            return 0
        
        try:
            # Nettoyer et convertir
            clean_text = text.strip()
            return int(clean_text) if clean_text.isdigit() else 0
        except ValueError:
            return 0
    
    def _parse_surface(self, text: str) -> float:
        """
        Parse la surface en m².
        
        Args:
            text: Texte contenant la surface
        
        Returns:
            float: Surface en m²
        """
        if not text:
            return 0.0
        
        try:
            # Format attendu: "XX m²"
            clean_text = text.replace('m²', '').strip().replace(',', '.')
            return float(clean_text)
        except ValueError:
            return 0.0
    
    def _parse_date(self, timestamp: str) -> str:
        """
        Parse la date de vente depuis un timestamp.
        
        Args:
            timestamp: Timestamp Unix en millisecondes
        
        Returns:
            str: Date au format DD/MM/YYYY
        """
        if not timestamp:
            return ""
        
        try:
            # Format attendu: timestamp en millisecondes
            ts = int(timestamp) // 1000  # Convertir en secondes
            date = datetime.fromtimestamp(ts)
            return date.strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            return ""
    
    def _parse_url(self, url: str) -> str:
        """
        Formate l'URL de détails de la propriété.
        
        Args:
            url: URL relative
            
        Returns:
            str: URL complète
        """
        if not url:
            return ""
        
        # Ajouter le préfixe si c'est une URL relative
        if url.startswith('/'):
            return f"https://www.immo-data.fr{url}"
        return url