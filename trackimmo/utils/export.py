"""
Export utilities for saving scraped data.
"""
import os
import csv
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime

from trackimmo.models.data_models import ScrapedProperty
from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)


def save_to_csv(properties: List[Dict[str, Any]], city_name: str, postal_code: str, output_dir: str = "data/raw") -> str:
    """
    Save raw property data to a CSV file.
    
    Args:
        properties: List of raw property dictionaries
        city_name: Name of the city
        postal_code: Postal code
        output_dir: Directory to save the CSV file
        
    Returns:
        Path to the saved CSV file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename based on city and date
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{city_name}_{postal_code}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
    # Convert to DataFrame and save
    df = pd.DataFrame(properties)
    df.to_csv(filepath, index=False)
    
    logger.info(f"Saved {len(properties)} properties to {filepath}")
    return filepath


def save_processed_to_csv(properties: List[ScrapedProperty], city_name: str, output_dir: str = "data/processed") -> str:
    """
    Save processed property data to a CSV file.
    
    Args:
        properties: List of ScrapedProperty objects
        city_name: Name of the city
        output_dir: Directory to save the CSV file
        
    Returns:
        Path to the saved CSV file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename based on city and date
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{city_name}_processed_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
    # Convert to dictionaries
    data = [prop.dict() for prop in properties]
    
    # Save to CSV
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        if data:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    
    logger.info(f"Saved {len(properties)} processed properties to {filepath}")
    return filepath 