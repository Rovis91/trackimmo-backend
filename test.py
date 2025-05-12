import asyncio
from trackimmo.modules.scraper.scraper import run_scraper

async def test_scraper():
    properties = await run_scraper(
        city_name="Paris",
        postal_code="75001",
        property_types=["apartment", "house"],
        start_date="01/2023",
        end_date="12/2023"
    )
    
    print(f"Scraped {len(properties)} properties")
    for prop in properties[:3]:  # Print first 3 properties
        print(f"{prop.address_raw} - {prop.price}€ - {prop.surface}m²")

if __name__ == "__main__":
    asyncio.run(test_scraper())