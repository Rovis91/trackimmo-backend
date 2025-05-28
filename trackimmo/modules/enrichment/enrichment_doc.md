# Enrichment Module Documentation

## Overview

The Enrichment module is a comprehensive data processing pipeline that transforms raw real estate property data through six sequential stages: normalization, city resolution, geocoding, DPE (energy performance) enrichment, price estimation, and database integration. It's designed to enrich scraped property data with additional valuable information before storage.

## Architecture

The module follows a pipeline architecture with:

- **Base Class**: `ProcessorBase` - Common interface for all processors
- **6 Processing Stages**: Each stage has its own processor class
- **Orchestrator**: `EnrichmentOrchestrator` - Manages the entire pipeline

## Processing Stages

### 1. DataNormalizer

**Purpose**: Cleans and standardizes raw property data.

**Key Operations**:

- Removes accents and converts to uppercase
- Normalizes addresses and city names
- Converts dates from DD/MM/YYYY to YYYY-MM-DD
- Maps French property types to English
- Validates data integrity

### 2. CityResolver

**Purpose**: Resolves city information and obtains postal/INSEE codes.

**Key Operations**:

- Groups properties by city name
- Queries French geocoding API for missing cities
- Extracts INSEE codes and departments
- Updates database with new cities

### 3. GeocodingService

**Purpose**: Obtains geographic coordinates for property addresses.

**Key Operations**:

- Batch geocoding via French address API
- Validates coordinates quality (score > 0.5)
- Filters by geographic boundaries if provided
- Processes up to 5000 addresses per batch

### 4. DPEEnrichmentService

**Purpose**: Enriches properties with energy performance diagnostics data.

**Key Operations**:

- Queries 5 different ADEME APIs for DPE data
- Matches properties using address similarity and proximity
- Caches DPE data for 30 days
- Calculates match confidence scores

### 5. PriceEstimationService

**Purpose**: Estimates current property values based on historical data.

**Key Operations**:

- Calculates price evolution based on sale age
- Applies DPE-based adjustments
- Uses city average prices from database
- Generates confidence scores

### 6. DBIntegrationService

**Purpose**: Integrates enriched properties into Supabase database.

**Key Operations**:

- Batch inserts properties
- Creates PostGIS geometries
- Handles DPE data insertion
- Generates integration reports

## Key Functions

### ProcessorBase Class

#### `process(**kwargs) -> bool`

Abstract method implemented by each processor.

**Returns**: Success status

#### `load_csv(file_path: Optional[str] = None) -> Optional[pd.DataFrame]`

Loads input CSV file.

**Returns**: DataFrame or None

#### `save_csv(df: pd.DataFrame, file_path: Optional[str] = None) -> bool`

Saves DataFrame to CSV.

**Returns**: Success status

### EnrichmentOrchestrator Class

#### `run(input_file: str, start_stage: int = 1, end_stage: int = 6, debug: bool = False) -> bool`

Executes the enrichment pipeline.

**Parameters**:

- `input_file`: Path to raw CSV
- `start_stage`: Starting stage (1-6)
- `end_stage`: Ending stage (1-6)
- `debug`: Keep intermediate files if True

**Returns**: Success status

## Data Flow

### Stage 1: Normalization

**Input CSV**:

``` csv
address,city,price,surface,rooms,sale_date,property_type,property_url
```

**Output CSV**:

``` csv
address_raw,city_name,price,surface,rooms,sale_date,property_type,source_url
```

### Stage 2: City Resolution

**Added columns**:

``` csv
city_id,postal_code,insee_code,department
```

### Stage 3: Geocoding

**Added columns**:

``` csv
latitude,longitude,address_normalized,geocoding_score
```

### Stage 4: DPE Enrichment

**Added columns**:

``` csv
dpe_number,dpe_date,dpe_energy_class,dpe_ges_class,construction_year,dpe_match_confidence
```

### Stage 5: Price Estimation

**Added columns**:

``` csv
estimated_price,price_evolution_rate,estimation_confidence
```

### Stage 6: Database Integration

**Output**: Integration report CSV with:

``` csv
address_id,address_raw,city_id,success,error
```

## Important Variables and Configuration

### API Endpoints

- **Geocoding**: `https://api-adresse.data.gouv.fr/search/csv/`
- **ADEME DPE APIs**: 5 different endpoints for various DPE types

### Processing Limits

- **Geocoding batch size**: 5000 addresses
- **DPE API batch size**: 9000 results
- **Database batch size**: 100 properties
- **DPE cache duration**: 30 days

### DPE Price Adjustments

```python
DPE_FACTORS = {
    'A': 0.05,   # +5%
    'B': 0.03,   # +3%
    'C': 0.01,   # +1%
    'D': 0.00,   # reference
    'E': -0.02,  # -2%
    'F': -0.05,  # -5%
    'G': -0.08   # -8%
}
```

### Match Thresholds

- **Address similarity**: 0.7 (0.85 for addresses without numbers)
- **Geographic proximity**: 20 meters
- **Geocoding score**: 0.5 minimum

## Error Handling

Each processor implements comprehensive error handling:

- Invalid data is logged and skipped
- API failures trigger retries (max 3 attempts)
- Failed database operations are reported
- Processing continues despite individual failures

## Usage Example

### Command Line

```bash
# Full pipeline
python -m trackimmo.modules.enrichment.enrichment_orchestrator \
    --input data/raw/properties.csv \
    --debug

# Partial pipeline (stages 2-4)
python -m trackimmo.modules.enrichment.enrichment_orchestrator \
    --input data/raw/properties.csv \
    --start 2 \
    --end 4
```

### Programmatic

```python
from trackimmo.modules.enrichment import EnrichmentOrchestrator

# Configure orchestrator
config = {
    'data_dir': 'data',
    'original_bbox': {
        'min_lat': 48.8,
        'max_lat': 48.9,
        'min_lon': 2.3,
        'max_lon': 2.4
    }
}

orchestrator = EnrichmentOrchestrator(config)

# Run full pipeline
success = orchestrator.run(
    input_file='properties.csv',
    start_stage=1,
    end_stage=6,
    debug=True
)
```

## Dependencies

- **pandas**: Data manipulation
- **requests**: API calls
- **unicodedata**: Text normalization
- **datetime**: Date handling
- **logging**: Event logging
- **uuid**: Unique ID generation
- **difflib**: Text similarity
- **math**: Geographic calculations

## Performance Considerations

- **Caching**: DPE data cached for 30 days per location
- **Batch Processing**: All stages process data in batches
- **Rate Limiting**: Built-in delays between API calls
- **Memory Management**: 10,000 DPE limit per location

## Notes

- The pipeline is designed to be fault-tolerant - failures in individual records don't stop processing
- Intermediate files can be preserved with `--debug` flag
- Each stage can be run independently by specifying start/end stages
- All timestamps use ISO format for consistency
- Geographic operations assume WGS84 coordinate system
- The module handles French-specific data formats (addresses, dates, etc.)
