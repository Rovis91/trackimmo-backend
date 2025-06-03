#!/usr/bin/env python3
"""
Simple test script to run enrichment on a scraped file.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trackimmo.modules.enrichment import EnrichmentOrchestrator

async def main():
    """Run enrichment on a scraped file."""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting enrichment test on scraped data")
    
    # Use the Lagord scraped file
    input_file = "data/scraped/Lagord_17140_20250602_231128.csv"
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return False
    
    print(f"🚀 Running enrichment on: {input_file}")
    print("This will test all our fixes:")
    print("  ✓ Improved geocoding (less aggressive filtering)")
    print("  ✓ Fixed DPE enrichment logging")
    print("  ✓ Better property type extraction")
    print("  ✓ Fixed database schema issues")
    print()
    
    try:
        # Configure enrichment
        config = {
            'data_dir': 'data',
        }
        
        # Run enrichment pipeline
        orchestrator = EnrichmentOrchestrator(config)
        success = await orchestrator.run_async(
            input_file=input_file,
            start_stage=1,  # Start from normalization
            end_stage=7,    # End at database integration
            debug=True     # Keep intermediate files for debugging
        )
        
        if success:
            print("✅ Enrichment completed successfully!")
            print("Check data/output/ for final results")
            return True
        else:
            print("❌ Enrichment failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error during enrichment: {str(e)}")
        logger.error(f"Error during enrichment: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TrackImmo - Enrichment Pipeline Test")
    print("=" * 60)
    print()
    
    # Run the async main function
    success = asyncio.run(main())
    
    print()
    print("=" * 60)
    if success:
        print("Enrichment test completed successfully! ✅")
    else:
        print("Enrichment test failed! ❌")
    print("=" * 60)
    
    sys.exit(0 if success else 1) 