# Scraper Module Documentation

## Overview

This module provides the main scraping logic for extracting real estate property data from ImmoData. It coordinates the end-to-end process, including URL generation, browser automation, adaptive subdivision, and data export.

## Main Classes

### ImmoDataScraper
- **Purpose:** High-level interface for scraping all properties for a given city and exporting results to CSV.
- **Key Methods:**
  - `scrape_city(city_name, postal_code, ...)` — Orchestrates the full scraping and export process.
  - Handles deduplication and CSV export.

### BrowserManager
- **Purpose:** Manages browser automation (via Playwright) and HTML parsing (via BeautifulSoup).
- **Key Methods:**
  - `extract_properties_with_count(...)` — Extracts properties from a URL, with adaptive subdivision if needed.
  - `_parse_properties(...)` — Parses HTML to extract property data.

## Property Type Extraction
- The `property_type` field is **not** taken from the search parameters or URL.
- Instead, it is extracted directly from the HTML content of each property card, using:
  ```python
  type_tag = element.find('p', class_='flex items-center text-sm text-gray-400')
  if type_tag and type_tag.span:
      property_type = type_tag.span.text.strip()
  else:
      property_type = ""
      logger.warning("Property type not found for a property element")
  ```
- This ensures the property type reflects the actual listing, not just the search filter.

## CSV Export
- The exported CSV **excludes** the following fields:
  - `postal_code`
  - `source_url`
- The columns included are:
  - `address`, `city`, `price`, `surface`, `rooms`, `sale_date`, `property_type`, `property_url`
- Rows where all main columns are empty or zero (after the header) are removed.
- Deduplication is performed on the following columns: `address`, `city`, `price`, `surface`, `rooms`, `sale_date`.

## Usage Example
```python
from trackimmo.modules.scraper.scraper import ImmoDataScraper
scraper = ImmoDataScraper()
scraper.scrape_city(
    city_name="Paris",
    postal_code="75000",
    property_types=["house", "apartment"],
    start_date="01/2020",
    end_date="12/2020"
)
```

## Notes
- The module uses modern async browser automation and robust HTML parsing.
- Only minimal, relevant columns are exported for clarity and downstream usability.
- For more details, see the code and docstrings in each class. 