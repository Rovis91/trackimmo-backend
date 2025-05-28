# City Scraper Module Documentation

## Overview

The City Scraper module is responsible for extracting city information and average property prices from French municipalities. It enriches the TrackImmo database with INSEE codes, department/region data, and current real estate market prices for houses and apartments.

## Main Components

### 1. CityDataScraper

**Purpose**: Scrapes city data including INSEE codes and average property prices from ImmoData.

### 2. CityDatabaseOperations

**Purpose**: Handles database operations for storing and updating city information in Supabase.

### 3. scrape_cities (function)

**Purpose**: Batch processing function for scraping multiple cities.

## Key Functions

### CityDataScraper Class

#### `__init__(max_retries: int = 3, sleep_time: float = 1.0)`

Initializes the scraper with retry logic and rate limiting.

**Parameters:**

- `max_retries`: Maximum retry attempts for failed requests
- `sleep_time`: Delay between requests in seconds

#### `async scrape_city(city_name: str, postal_code: str, insee_code: Optional[str] = None) -> Dict[str, Any]`

Main method that orchestrates the city data extraction process.

**Input:**

- `city_name`: Name of the city
- `postal_code`: 5-digit postal code
- `insee_code`: Optional INSEE code (will be fetched if not provided)

**Output:**

```python
{
    "name": str,
    "postal_code": str,
    "insee_code": str,
    "department": str,
    "region": str,
    "house_price_avg": int,      # Average price per m² for houses
    "apartment_price_avg": int,   # Average price per m² for apartments
    "last_scraped": str,         # Timestamp
    "status": str,               # "success" or "error"
    "error_message": str         # Error details if any
}
```

### CityDatabaseOperations Class

#### `update_cities(cities_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]`

Batch updates multiple cities in the database.

**Input:**

- `cities_data`: List of city data dictionaries

**Output:**

- List of city data with added status information and city_id

#### `update_city(city_data: Dict[str, Any]) -> Dict[str, Any]`

Updates or inserts a single city in the database using UPSERT operation.

**Input:**

- `city_data`: Single city data dictionary

**Output:**

- Updated city data with city_id and operation status

### Utility Function

#### `async scrape_cities(cities_data, max_retries=3, sleep_time=1.0) -> List[Dict[str, Any]]`

Convenience function for scraping multiple cities sequentially.

**Input:**

- `cities_data`: List of dicts containing `city_name`, `postal_code`, and optional `insee_code`
- `max_retries`: Maximum retry attempts
- `sleep_time`: Delay between cities

**Output:**

- List of scraped city data dictionaries

## How It Works

### 1. Data Collection Flow

1. Receive city name and postal code
2. Query French Geocoding API to get INSEE code, department, and region
3. Generate ImmoData market URL using slugified names
4. Scrape average prices using Playwright browser automation
5. Return enriched city data

### 2. URL Generation Process

- City names are slugified (accents removed, spaces replaced with hyphens)
- Department codes are mapped to department names
- Region is determined from department code
- Final URL format: `https://www.immo-data.fr/marche-immobilier/{region}/{department}/{city}-{insee_code}/`

### 3. Price Extraction

- Uses Playwright to render JavaScript-heavy pages
- Extracts prices via DOM queries for "Appartements - Prix" and "Maisons - Prix" sections
- Parses and cleans price strings to integers

### 4. Database Operations

- Uses UPSERT to handle both new cities and updates
- INSEE code serves as the unique identifier
- Automatically timestamps last_scraped field

## Important Variables and Mappings

### Department Mapping

- Maps 95 French department codes to URL-friendly names
- Special handling for Corsica (2A, 2B)
- Includes overseas territories

### Region Mapping

- Maps department codes to 13 metropolitan regions + 5 overseas
- Based on 2022 French administrative divisions

### API Endpoints

- Geocoding API: `https://api-adresse.data.gouv.fr/search/`
- ImmoData base URL: `https://www.immo-data.fr/marche-immobilier/`

## Error Handling

The module implements comprehensive error handling:

- Network failures trigger retries up to max_retries
- Missing INSEE codes are logged and marked as errors
- Failed price extractions don't block city data updates
- All errors are captured in the returned data structure

## Usage Example

```python
import asyncio
from trackimmo.modules.city_scraper import scrape_cities, CityDatabaseOperations

# Prepare cities to scrape
cities = [
    {"city_name": "Paris", "postal_code": "75001"},
    {"city_name": "Lyon", "postal_code": "69001"},
    {"city_name": "Marseille", "postal_code": "13001"}
]

# Scrape cities
scraped_data = asyncio.run(scrape_cities(cities))

# Update database
db_ops = CityDatabaseOperations()
results = db_ops.update_cities(scraped_data)

# Check results
for city in results:
    if city["status"] == "success":
        print(f"{city['name']}: House avg {city['house_price_avg']}€/m²")
```

## Dependencies

- **playwright**: Browser automation for scraping
- **beautifulsoup4**: HTML parsing (imported but not used in current implementation)
- **requests**: HTTP requests for geocoding API
- **asyncio**: Asynchronous operations
- **unicodedata**: Text normalization for URL generation

## Notes

- The scraper respects rate limits with configurable sleep times
- INSEE codes are immutable once set (used as unique identifiers)
- Price data may be None if not available on ImmoData
- The module handles both creating new cities and updating existing ones
- All timestamps use database server time via "now()" function
