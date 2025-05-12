# TrackImmo Backend

Backend service for TrackImmo, a real estate data scraping and enrichment application.

## Features

- **Data Scraping**: Automated extraction of real estate transaction data using Playwright
- **Data Enrichment**:
  - Geocoding of addresses using the French government API
  - DPE (energy performance) data integration from official sources
  - Price estimation algorithm based on market trends
- **REST API**: Comprehensive FastAPI endpoints with JWT authentication
- **Monitoring**: Built-in metrics and logging for application performance
- **Export Utilities**: CSV export for processed data

## Project Status

The project is currently in development phase with approximately 75% completion:
- ✅ Core infrastructure and API design complete
- ✅ Data scraping and processing modules implemented
- ✅ Authentication system in place
- ⏳ Testing across various data types in progress
- ⏳ Data import functionality partially implemented
- ⏳ Performance optimizations pending

For detailed task status, see [TASKS.md](TASKS.md).

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
    - `scraper.py`: Web scraping module
    - `processor.py`: Data enrichment
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
- `DPE_API.md`: DPE API integration
- `GEOCODING_API.md`: Geocoding API integration
- `PRICE_ESTIMATION.md`: Price estimation algorithm
- `SCRAPING.md`: Scraping methodology

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create a new Pull Request

## License

MIT License - See [LICENSE](LICENSE) for details.

## Running Tests

### Scraper Tests

The scraper module can be tested in both mock mode and real scraping mode:

#### Mock Mode (Default)

This mode uses mock data instead of real web scraping, making it fast and reliable for testing:

```bash
python -m trackimmo.tests.test_scraper
```

#### Real Scraping Mode

This mode performs actual web scraping. It requires an internet connection and the Playwright browsers to be installed:

```bash
python -m trackimmo.tests.test_scraper --real
```

## Modules

### Scraper Module

The scraper module handles the extraction of property data from ImmoData. It includes:

- `ImmoDataScraper`: Main scraper class
- `BrowserManager`: Manages browser automation using Playwright
- `URLGenerator`: Creates URLs for scraping
- `GeoDivider`: Divides geographic areas into smaller regions

### API Module

(To be implemented)

### Models

Data models for the application are defined in `trackimmo/models/data_models.py`.

## Configuration

Configuration settings are defined in `trackimmo/config.py` and can be overridden using environment variables or a `.env` file.
