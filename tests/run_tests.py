#!/usr/bin/env python
"""
Run all TrackImmo API tests.
"""
import sys
import pytest
import os
from pathlib import Path

def main():
    """
    Main function to run the tests.
    Returns the exit code from pytest.
    """
    # Get the path to the tests directory
    tests_dir = Path(__file__).parent
    api_tests_dir = tests_dir / "test_api"
    
    # Print test environment info
    print(f"Running TrackImmo API Tests")
    print(f"Python version: {sys.version}")
    print(f"Pytest version: {pytest.__version__}")
    print(f"Test directory: {api_tests_dir}")
    print("-" * 50)
    
    # Define arguments for pytest
    args = [
        # Verbose output
        "-v",
        # Show all output (don't capture)
        "-s",
        # Show extra test summary info
        "-ra",
        # Directory with the tests
        str(api_tests_dir),
    ]
    
    # List all implemented test categories
    print("Test categories implemented:")
    print("✓ API Authentication Tests")
    print("✓ API Input Validation Tests")
    print("✓ API Response Format Tests")
    print("✓ Client Processor Tests")
    print("✓ Email Notification Tests")
    print("✓ Retry Queue Tests")
    print("✓ Integration Tests")
    print("✓ Cron Job Tests")
    print("-" * 50)
    
    # Run the tests
    return pytest.main(args)

if __name__ == "__main__":
    sys.exit(main()) 