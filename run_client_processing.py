#!/usr/bin/env python3
"""
Standalone script to run client processing without the API.
"""
import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trackimmo.modules.client_processor import process_client_data, get_client_by_id
from trackimmo.utils.logger import get_logger
from trackimmo.config import settings

logger = get_logger("client_processing")

async def main():
    """Run client processing for a specific client."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run client processing")
    parser.add_argument("--client-id", default="e86f4960-f848-4236-b45c-0759b95db5a3", 
                       help="Client ID to process")
    parser.add_argument("--skip-scraping", action="store_true", 
                       help="Skip scraping step and only run enrichment on existing data")
    args = parser.parse_args()
    
    # Client ID to process
    client_id = args.client_id
    skip_scraping = args.skip_scraping
    
    print(f"Starting client processing for client: {client_id}")
    if skip_scraping:
        print("🔄 SKIP SCRAPING MODE: Will only run enrichment on existing scraped data")
    logger.info(f"Starting client processing for client: {client_id}, skip_scraping: {skip_scraping}")
    
    try:
        # First check if client exists
        client = await get_client_by_id(client_id)
        if not client:
            print(f"❌ Client {client_id} not found")
            logger.error(f"Client {client_id} not found")
            return False
        
        if client["status"] != "active":
            print(f"❌ Client {client_id} is not active (status: {client['status']})")
            logger.error(f"Client {client_id} is not active (status: {client['status']})")
            return False
        
        print(f"✓ Found client: {client['first_name']} {client['last_name']}")
        print(f"  Email: {client['email']}")
        print(f"  Cities: {len(client.get('chosen_cities', []))} selected")
        print(f"  Property types: {client.get('property_type_preferences', [])}")
        print(f"  Addresses per report: {client.get('addresses_per_report', 10)}")
        print()
        
        # Run the full client processing
        print("🚀 Starting client processing...")
        if skip_scraping:
            print("This includes:")
            print("  1. Loading existing scraped data")
            print("  2. Running enrichment pipeline on scraped properties")
            print("  3. Assigning properties to client based on preferences")
            print("  4. Sending email notification")
        else:
            print("This includes:")
            print("  1. Updating city data if needed")
            print("  2. Scraping new properties if insufficient data")
            print("  3. Running enrichment pipeline on new properties")
            print("  4. Assigning properties to client based on preferences")
            print("  5. Sending email notification")
        print()
        
        result = await process_client_data(client_id, skip_scraping=skip_scraping)
        
        if result["success"]:
            print("✅ Client processing completed successfully!")
            print(f"   Properties assigned: {result['properties_assigned']}")
            print(f"   Message: {result['message']}")
            logger.info(f"Client processing completed: {result}")
        else:
            print("❌ Client processing failed")
            print(f"   Error: {result.get('message', 'Unknown error')}")
            logger.error(f"Client processing failed: {result}")
            
        return result["success"]
        
    except Exception as e:
        print(f"❌ Error during client processing: {str(e)}")
        logger.error(f"Error during client processing: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TrackImmo - Client Processing")
    print("=" * 60)
    print()
    
    # Run the async main function
    success = asyncio.run(main())
    
    print()
    print("=" * 60)
    if success:
        print("Processing completed successfully! ✅")
    else:
        print("Processing failed! ❌")
    print("=" * 60)
    
    sys.exit(0 if success else 1) 