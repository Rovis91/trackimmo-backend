# TrackImmo Backend

A comprehensive real estate data processing system that scrapes, enriches, and analyzes French property transaction data. The system consists of three main modules that work together to provide complete property market intelligence.

## System Overview

TrackImmo Backend is designed around a modular architecture with three core processing modules:

1. **Scraper Module**: Extracts property transaction data from ImmoData
2. **City Scraper Module**: Collects city information and market prices
3. **Enrichment Module**: Processes and enhances raw data through a 6-stage pipeline

## Core Modules

### 1. Scraper Module

The scraper module extracts real estate property data by dividing cities into geographic rectangles and implementing adaptive subdivision strategies to handle API limitations.

**Key Features**:

- Geographic division of cities into 17km × 14km rectangles with 10% overlap
- Adaptive subdivision when hitting the 101-property API limit
- Browser automation using Playwright for JavaScript-heavy pages
- Automatic deduplication and CSV export

**Usage**:

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

**Output**: CSV file with property data including address, price, surface, rooms, sale date, and property type.

### 2. City Scraper Module

Collects comprehensive city information including INSEE codes, department/region data, and current market prices.

**Key Features**:

- Automatic INSEE code resolution via French geocoding API
- Market price extraction for houses and apartments
- Database integration with UPSERT operations
- Batch processing capabilities

**Usage**:

```python
from trackimmo.modules.city_scraper import scrape_cities, CityDatabaseOperations

cities = [
    {"city_name": "Paris", "postal_code": "75001"},
    {"city_name": "Lyon", "postal_code": "69001"}
]

scraped_data = await scrape_cities(cities)
db_ops = CityDatabaseOperations()
results = db_ops.update_cities(scraped_data)
```

**Output**: Enriched city data with INSEE codes, department, region, and average property prices per m².

### 3. Enrichment Module

A 6-stage data processing pipeline that transforms raw property data into enriched, analysis-ready information.

**Processing Stages**:

1. **Data Normalization**: Cleans and standardizes raw data
2. **City Resolution**: Maps city names to postal and INSEE codes
3. **Geocoding**: Adds geographical coordinates using French address API
4. **DPE Enrichment**: Integrates energy performance data from ADEME APIs
5. **Price Estimation**: Calculates current market values based on historical data
6. **Database Integration**: Stores processed data in Supabase

**Usage**:

```python
from trackimmo.modules.enrichment import EnrichmentOrchestrator

config = {
    'data_dir': 'data',
    'original_bbox': {
        'min_lat': 48.8, 'max_lat': 48.9,
        'min_lon': 2.3, 'max_lon': 2.4
    }
}

orchestrator = EnrichmentOrchestrator(config)
success = orchestrator.run(
    input_file='properties.csv',
    start_stage=1,
    end_stage=6,
    debug=True
)
```

## API

TrackImmo provides a API for managing client processing and property assignments. The API allows you to:

- **Process Clients**: Automatically assign new properties to clients based on their preferences
- **Manage Properties**: Retrieve and manage client property assignments
- **Monitor Jobs**: Track processing status and manage the job queue
- **Administration**: Access system statistics and manage clients

### Quick Start

**Base URL**: `http://147.93.94.3:8000`  
**API Key**: `cb67274b99d89ab5`

### Basic Usage Examples

```bash
# Check API health
curl http://147.93.94.3:8000/health

# Process a client (assign new properties)
curl -X POST \
  -H "X-API-Key: cb67274b99d89ab5" \
  -H "Content-Type: application/json" \
  -d '{"client_id": "your-client-id"}' \
  http://147.93.94.3:8000/api/process-client

# Get client properties
curl -H "X-API-Key: cb67274b99d89ab5" \
  http://147.93.94.3:8000/api/get-client-properties/your-client-id

# Check system stats (admin)
curl -H "X-Admin-Key: cb67274b99d89ab5" \
  http://147.93.94.3:8000/admin/stats
```

### Key Features

- **Automated Processing**: Assigns properties to clients based on age criteria (6-8 years old) and preferences
- **Weighted Selection**: Prioritizes older properties while maintaining variety
- **Email Notifications**: Sends automatic notifications when properties are assigned
- **Job Management**: Asynchronous processing with status tracking and retry capabilities
- **Admin Controls**: Comprehensive administration endpoints for system management

For complete API documentation, see `trackimmo/api/api_doc.md`.

## Data Flow Architecture

### Complete Processing Pipeline

```
Raw Property Data → Scraper Module → CSV Export
                                        ↓
City Information ← City Scraper ← Database Integration
                                        ↓
Enriched Data ← Enrichment Pipeline ← Normalized Data
```

### Typical Workflow

1. **Data Collection**: Use scraper module to extract property transactions for target cities
2. **City Enhancement**: Run city scraper to collect market context and administrative data
3. **Data Enrichment**: Process raw data through the enrichment pipeline
4. **Analysis Ready**: Final data includes coordinates, energy ratings, price estimates, and market context

## Key Configuration

### Geographic Parameters

- Rectangle size: 17km × 14km with 10% overlap
- Zoom level: 12 for optimal coverage
- Subdivision threshold: 95 properties (near API limit)

### API Integration

- French Geocoding API for address resolution
- ADEME APIs for energy performance data
- ImmoData for property transactions and market prices

### Data Processing Limits

- Geocoding: 5000 addresses per batch
- DPE enrichment: 9000 results per API call
- Database operations: 100 properties per batch

## Performance Characteristics

### Processing Times

- **Per property search**: 5-10 seconds
- **Medium city (50k properties)**: 15-30 minutes
- **Large city (Paris)**: 1-2 hours
- **Enrichment pipeline**: 10-20 minutes per 1000 properties

### Resource Requirements

- **Memory**: 500MB-1GB during execution
- **Storage**: ~1MB per 1000 properties
- **Network**: Moderate usage for API calls

## Output Formats

### Scraper Output

```csv
address,city,price,surface,rooms,sale_date,property_type,property_url
```

### City Scraper Output

```python
{
    "name": "Lyon",
    "postal_code": "69001",
    "insee_code": "69123",
    "department": "Rhône",
    "region": "Auvergne-Rhône-Alpes",
    "house_price_avg": 4500,
    "apartment_price_avg": 3200,
    "last_scraped": "2024-01-15T10:30:00Z"
}
```

### Enrichment Output

Final enriched data includes all original fields plus:

- Geographic coordinates (latitude, longitude)
- Energy performance ratings (DPE class, GES class)
- Estimated current market value
- Administrative codes (INSEE, postal, department)

## Error Handling and Reliability

### Robust Processing

- Automatic retries for network failures (max 3 attempts)
- Graceful handling of missing data
- Comprehensive logging for debugging
- Fault-tolerant pipeline design

### Data Quality

- Address similarity matching (70% threshold)
- Geographic proximity validation (20m radius)
- Confidence scoring for all enrichments
- Duplicate detection and removal

## Project Structure

```
trackimmo/
├── modules/
│   ├── scraper/           # Property data extraction
│   ├── city_scraper/      # City information collection
│   └── enrichment/        # Data processing pipeline
├── models/                # Data models and schemas
├── utils/                 # Logging, metrics, export utilities
└── config.py             # Configuration management
```

## Dependencies

### Core Libraries

- **playwright**: Browser automation for scraping
- **pandas**: Data manipulation and analysis
- **requests**: HTTP API interactions
- **asyncio**: Asynchronous processing

### Database Integration

- **supabase**: Database operations and storage
- **postgis**: Geographic data handling

### Data Processing

- **beautifulsoup4**: HTML parsing
- **unicodedata**: Text normalization
- **difflib**: Text similarity matching

## Usage Patterns

### Single City Analysis

```python
# Extract data for one city
scraper = ImmoDataScraper()
properties = scraper.scrape_city("Lyon", "69001", ["house"], "01/2023", "12/2023")

# Enrich the data
orchestrator = EnrichmentOrchestrator(config)
orchestrator.run(properties, start_stage=1, end_stage=6)
```

### Batch Processing

```python
# Process multiple cities
cities = [{"city_name": "Lyon", "postal_code": "69001"}, ...]
for city in cities:
    properties = scraper.scrape_city(**city, property_types=["house", "apartment"])
    orchestrator.run(properties)
```

### Partial Pipeline Execution

```python
# Run only specific enrichment stages
orchestrator.run(
    input_file="raw_data.csv",
    start_stage=3,  # Start from geocoding
    end_stage=5,    # End at price estimation
    debug=True      # Keep intermediate files
)
```

This system provides a complete solution for French real estate market analysis, from raw data extraction to enriched, analysis-ready datasets.
