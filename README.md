# TrackImmo Backend

Backend service for TrackImmo, a real estate data scraping and enrichment application.

## Features

- **Data Scraping**:
  - Automated extraction of real estate transaction data using Playwright
  - City data collection including INSEE codes and property market prices
- **Data Enrichment**:
  - Geocoding of addresses using the French government API
  - DPE (energy performance) data integration from official sources
  - Price estimation algorithm based on market trends
- **REST API**: Comprehensive FastAPI endpoints with JWT authentication
- **Monitoring**: Built-in metrics and logging for application performance
- **Export Utilities**: CSV export for processed data

## Installation

### Prerequisites

- Python 3.10+
- Supabase account for database operations
- Playwright browsers

### Setup

1. Clone the repository
   ```
   git clone https://github.com/yourusername/trackimmo-backend.git
   cd trackimmo-backend
   ```

2. Create and activate a virtual environment
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Install Playwright browsers
   ```
   playwright install --with-deps
   ```

5. Create a `.env` file from the example
   ```
   cp .env.example .env
   ```
   
6. Update the `.env` file with your specific settings, including Supabase credentials:
   ```
   SUPABASE_URL=https://your-project-url.supabase.co
   SUPABASE_KEY=your-supabase-api-key
   ```

## Supabase Integration

This project uses Supabase as the database backend. To setup:

1. Create a Supabase account at [supabase.com](https://supabase.com)
2. Create a new project
3. Get your project URL and API key from the project settings
4. Add these credentials to your `.env` file as described above

The database schema follows the SQLAlchemy models defined in `trackimmo/models/db_models.py`. Make sure your Supabase database has the same tables and columns as defined in these models.

## Configuration

The application uses environment variables for configuration. See [config.py](trackimmo/config.py) for all available options.

Key settings include:
- `SUPABASE_URL`: URL for your Supabase project
- `SUPABASE_KEY`: API key for Supabase authentication
- `SECRET_KEY`: Secret key for JWT token generation
- `SCRAPER_HEADLESS`: Whether to run browser in headless mode
- `METRICS_PORT`: Port for the metrics server

## Running the application

### Development mode

```
uvicorn trackimmo.app:app --reload
```

The API will be available at http://localhost:8000, with documentation at http://localhost:8000/docs.

### Production mode

```
uvicorn trackimmo.app:app --host 0.0.0.0 --port 8000
```

## Project Structure

- `trackimmo/`: Main package
  - `api/`: API routes and authentication
    - `auth.py`: JWT authentication
    - `routes.py`: API endpoints
  - `models/`: Data models
    - `data_models.py`: Pydantic models
    - `db_models.py`: SQLAlchemy models
  - `modules/`: Core functionality
    - `scraper/`: Web scraping module for property data
    - `city_scraper/`: City data collection module
      - `city_scraper.py`: City data extraction
      - `db_operations.py`: City database operations
    - `enrichment/`: Data enrichment pipeline
      - `data_normalizer.py`: Data cleaning and normalization
      - `city_resolver.py`: City code resolution
      - `geocoding_service.py`: Address geocoding
      - `dpe_enrichment.py`: Energy performance data integration
      - `price_estimator.py`: Property price estimation
      - `db_integrator.py`: Database integration
    - `db_manager.py`: Database operations (Supabase integration)
  - `utils/`: Utility functions
    - `logger.py`: Logging configuration
    - `metrics.py`: Performance metrics
    - `export.py`: CSV export utilities
  - `tests/`: Test suite
  - `app.py`: Application entry point
  - `config.py`: Configuration loader

## Documentation

- `API_DOCS.md`: API endpoints and usage
- `DB_SCHEMA.md`: Database schema
- `trackimmo/modules/enrichment/enrichment_doc.md`: Enrichment module documentation
- `trackimmo/modules/city_scraper/city_scraper_doc.md`: City scraper module documentation

## Modules

### Scraper Module

The scraper module handles the extraction of property data from ImmoData. It includes:

- `ImmoDataScraper`: Main scraper class
- `BrowserManager`: Manages browser automation using Playwright
- `URLGenerator`: Creates URLs for scraping
- `GeoDivider`: Divides geographic areas into smaller regions

### City Scraper Module

The city scraper module collects data about French cities including INSEE codes, postal codes, departments, and average property prices. It includes:

- `CityDataScraper`: Main scraper class for city data
- `CityDatabaseOperations`: Database operations for city data

This module enhances the application by providing up-to-date city information and market prices for better analysis and enrichment of property data.

### Enrichment Module

The enrichment module processes raw property data through a pipeline of steps to clean, enhance, and normalize it. The process includes:

1. **Data Normalization**: Cleans and standardizes raw data
2. **City Resolution**: Maps city names to postal and INSEE codes
3. **Geocoding**: Adds geographical coordinates to property addresses
4. **DPE Enrichment**: Adds energy performance data from official sources
5. **Price Estimation**: Calculates current market values based on historical data
6. **Database Integration**: Stores processed data in the database

Each step is handled by a dedicated processor, allowing for modular execution and easy maintenance.

### API Module

(To be implemented)

### Models

Data models for the application are defined in `trackimmo/models/data_models.py`.

## Testing

The test suite offers comprehensive coverage of the TrackImmo API:

- **Total Tests**: 50 tests (47 passing, 3 skipped)
- **Test Categories**: Authentication, input validation, client processing, integration, etc.
- **Async Support**: Full support for testing asynchronous functions
- **Database Tests**: Uses a separate test database configuration

To run tests:

```bash
# Run all tests
python -m pytest

# Run specific test categories
python -m pytest tests/test_api/test_client_processor.py
```

See [TEST_REPORT.md](TEST_REPORT.md) for detailed testing information.
