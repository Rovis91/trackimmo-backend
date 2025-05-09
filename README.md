# TrackImmo Backend

Backend service for TrackImmo, a real estate data scraping and enrichment application.

## Features

- Scraping of real estate transaction data
- Geocoding of addresses
- DPE (energy performance) data enrichment
- Price estimation algorithm
- REST API for data access

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Install Playwright browsers:
   ```
   playwright install
   ```

## Configuration

Create a `.env` file based on `.env.example` with your specific settings.

## Running the application

```
uvicorn trackimmo.app:app --reload
```

The API will be available at http://localhost:8000, with documentation at http://localhost:8000/docs.

## Project Structure

- `trackimmo/`: Main package
  - `api/`: API routes and authentication
  - `models/`: Data models (Pydantic and SQLAlchemy)
  - `modules/`: Core functionality modules
  - `utils/`: Utility functions
  - `tests/`: Test suite

## Documentation

- `API_DOCS.md`: API endpoints and usage
- `DB_SCHEMA.md`: Database schema
- `DPE_API.md`: DPE API integration
- `GEOCODING_API.md`: Geocoding API integration
- `PRICE_ESTIMATION.md`: Price estimation algorithm
- `SCRAPING.md`: Scraping methodology

## License

Proprietary - All Rights Reserved
