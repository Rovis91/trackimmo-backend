# Scraper Module Documentation

## Overview

The Scraper module extracts real estate property data from ImmoData by dividing cities into geographic rectangles and implementing adaptive subdivision strategies to handle API limitations. It uses browser automation to navigate and extract property listings while managing the 101-property limit per search.

## Architecture

The module consists of four main components working together:

### 1. ImmoDataScraper

**Purpose**: Main orchestrator for the scraping process.

### 2. GeoDivider

**Purpose**: Divides cities into geographic rectangles for systematic coverage.

### 3. UrlGenerator & AdaptiveUrlGenerator

**Purpose**: Generates search URLs and implements adaptive subdivision when hitting limits.

### 4. BrowserManager

**Purpose**: Handles browser automation and HTML parsing.

## Key Functions

### ImmoDataScraper Class

#### `scrape_city(city_name: str, postal_code: str, property_types: List[str], start_date: str, end_date: str) -> str`

Main entry point for scraping a city (synchronous version).

**Input**:

- `city_name`: Name of the city
- `postal_code`: 5-digit postal code
- `property_types`: List of types ["house", "apartment", "land", "commercial"]
- `start_date`: Start date (MM/YYYY format)
- `end_date`: End date (MM/YYYY format)

**Output**: Path to generated CSV file

#### `scrape_city_async(...)`

Async version for use in async contexts (e.g., FastAPI).

### GeoDivider Class

#### `divide_city_area(city_name: str, postal_code: str, overlap_percent: float = 10) -> List[Dict]`

Divides a city into overlapping rectangles.

**Output per rectangle**:

```python
{
    "center_lat": float,
    "center_lon": float,
    "min_lat": float,
    "min_lon": float,
    "max_lat": float,
    "max_lon": float,
    "zoom": 12
}
```

### UrlGenerator Class

#### `generate_urls(rectangles: List[Dict], property_types: List[str], start_date: str, end_date: str) -> List[Dict]`

Generates initial search URLs for each rectangle and month.

**URL metadata structure**:

```python
{
    "url": str,
    "rectangle": Dict,
    "property_type": str,  # "all" initially
    "period": str,  # e.g., "Janvier 2024"
    "property_types": List[str],
    "subdivision_level": 0
}
```

### AdaptiveUrlGenerator Class

#### `subdivide_if_needed(url_data: Dict, property_count: int, properties: List[Dict]) -> List[Dict]`

Implements adaptive subdivision strategy when approaching API limits.

**Subdivision levels**:

- Level 0: All property types combined
- Level 1: Separated by type (apartments, houses, others)
- Level 2: Split by dynamic price ranges
- Level 3: Refined price ranges
- Level 4+: Binary price subdivision

### BrowserManager Class

#### `extract_properties_with_count(url_data: Dict, adaptive_generator, recursion_depth: int) -> Tuple[List[Dict], int, bool]`

Extracts properties with adaptive subdivision support.

**Returns**:

- List of extracted properties
- Property count at this level
- Whether subdivision occurred

## Scraping Strategy

### 1. Geographic Division

``` txt
City → Rectangles (17km × 14km with 10% overlap) → Monthly searches
```

### 2. Adaptive Subdivision

When a search returns ≥95 properties (near the 101 limit):

1. Type subdivision: all → [apartments, houses, others]
2. Price subdivision: full range → optimal ranges based on distribution
3. Further refinement: binary splits until under limit

### 3. Property Extraction

Each property contains:

```python
{
    "address": str,
    "city": str,
    "price": int,
    "surface": float,
    "rooms": int,
    "sale_date": str,  # DD/MM/YYYY format
    "property_type": str,  # Extracted from HTML
    "property_url": str
}
```

## Important Variables and Configuration

### Geographic Parameters

```python
rectangle_width_km = 17
rectangle_height_km = 14
zoom_level = 12
overlap_percent = 10
```

### Property Type Mapping

```python
{
    "house": "1",
    "apartment": "2",
    "land": "4",
    "commercial": "0",
    "other": "5"
}
```

### French Month Names

```python
{
    1: 'Janvier', 2: 'Février', 3: 'Mars', ...
}
```

### Subdivision Thresholds

- **Trigger threshold**: 95 properties (raised from 90)
- **Max price**: 25,000,000€
- **API batch limit**: 101 properties

## Data Flow

### 1. City Division

``` csv
City coordinates → API lookup → Bounding box → Rectangle grid
```

### 2. URL Generation

``` csv
Rectangle + Month + Property Types → Search URL
```

### 3. Extraction Process

``` csv
URL → Browser automation → HTML parsing → Property data
```

### 4. Adaptive Subdivision

``` csv
If count ≥ 95:
  → Subdivide by type/price
  → Extract from subdivisions
  → Merge all results
```

### 5. Post-processing

``` csv
All properties → Deduplication → CSV export
```

## CSV Export Format

The final CSV excludes `postal_code` and `source_url`, containing only:

``` csv
address,city,price,surface,rooms,sale_date,property_type,property_url
```

## Error Handling

- **Browser failures**: Retry up to 3 times with delays
- **Network timeouts**: 60-second timeout for page loads
- **Invalid data**: Logged and skipped
- **Subdivision limits**: No hard limit on subdivision depth

## Usage Example

### Simple Usage

```python
from trackimmo.modules.scraper import ImmoDataScraper

scraper = ImmoDataScraper(output_dir="data/scraped")
result_file = scraper.scrape_city(
    city_name="Lyon",
    postal_code="69001",
    property_types=["house", "apartment"],
    start_date="01/2023",
    end_date="12/2023"
)
```

### Async Usage (in FastAPI)

```python
result_file = await scraper.scrape_city_async(
    city_name="Lyon",
    postal_code="69001",
    property_types=["house", "apartment"],
    start_date="01/2023",
    end_date="12/2023"
)
```

## Performance Characteristics

### Time Estimates

- **Per URL**: ~5-10 seconds (depends on property count)
- **Per rectangle**: ~30-60 seconds (12 months)
- **Medium city**: 15-30 minutes
- **Large city (Paris)**: 1-2 hours

### Resource Usage

- **Browser instances**: 1 at a time
- **Memory**: ~500MB-1GB during execution
- **Network**: Moderate (HTML pages only)

## Key Implementation Details

### Property Type Extraction

The `property_type` is extracted directly from HTML, not from search parameters:

```python
type_tag = element.find('p', class_='flex items-center text-sm text-gray-400')
if type_tag and type_tag.span:
    property_type = type_tag.span.text.strip()
```

### Deduplication Strategy

Properties are deduplicated based on:

- address
- city
- price
- surface
- rooms
- sale_date

### Price Range Optimization

The module analyzes actual price distributions to create optimal ranges:

- Uses 5th and 95th percentiles for central range
- Creates more divisions when at API limit
- Implements binary subdivision for deep recursion

## Dependencies

- **playwright**: Browser automation
- **beautifulsoup4**: HTML parsing
- **pandas**: Data manipulation
- **asyncio**: Asynchronous operations
- **requests**: HTTP requests for geocoding

## Notes

- The scraper respects rate limits with configurable delays
- All properties are collected, including from subdivided searches
- The module handles French-specific formats (dates, addresses)
- Playwright runs in headless mode by default
- Geographic coverage ensures no properties are missed with 10% overlap
- The adaptive strategy ensures complete data extraction despite API limits
