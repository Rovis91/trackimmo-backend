"""
Configure pytest for TrackImmo API tests.
This file is automatically loaded by pytest to configure the test environment.
"""
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Callable, AsyncGenerator, Generator

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

# Add the project root directory to the Python path
# This ensures imports like 'from trackimmo.app import app' will work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Print path for debugging
print(f"Added to Python path: {project_root}")

# Load environment variables
load_dotenv()

# Test database credentials
TEST_SUPABASE_URL = os.environ.get("TEST_SUPABASE_URL", os.environ.get("SUPABASE_URL"))
TEST_SUPABASE_KEY = os.environ.get("TEST_SUPABASE_KEY", os.environ.get("SUPABASE_KEY"))

# Test data constants
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"
TEST_CITY_ID_1 = "c1d2e3f4-a1b2-c3d4-e5f6-a1b2c3d4e5f6"
TEST_CITY_ID_2 = "c1d2e3f4-a1b2-c3d4-e5f6-a1b2c3d4e5f7"
TEST_CITY_ID_3 = "c1d2e3f4-a1b2-c3d4-e5f6-a1b2c3d4e5f8"

TEST_CLIENT = {
    "client_id": TEST_CLIENT_ID,
    "first_name": "Test",
    "last_name": "User",
    "email": "test@example.com",
    "telephone": "1234567890",
    "status": "active",
    "chosen_cities": [TEST_CITY_ID_1, TEST_CITY_ID_2],
    "property_type_preferences": ["house", "apartment"],
    "room_count_min": 2,
    "price_max": 500000,
    "addresses_per_report": 3,
    "send_day": 15,
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
    "last_updated": datetime.now().isoformat()
}

TEST_CITIES = [
    {
        "city_id": TEST_CITY_ID_1,
        "name": "Paris",
        "postal_code": "75001",
        "insee_code": "75101",
        "department": "75",
        "region": "Île-de-France",
        "last_scraped": (datetime.now() - timedelta(days=100)).isoformat()  # Outdated city
    },
    {
        "city_id": TEST_CITY_ID_2,
        "name": "Lyon",
        "postal_code": "69001",
        "insee_code": None,  # Missing INSEE code
        "department": "69",
        "region": None,
        "last_scraped": None  # Never scraped
    },
    {
        "city_id": TEST_CITY_ID_3,
        "name": "Marseille",
        "postal_code": "13001",
        "insee_code": "13201",
        "department": "13",
        "region": "Provence-Alpes-Côte d'Azur",
        "last_scraped": datetime.now().isoformat()  # Up to date
    }
]

TEST_ADDRESSES = [
    {
        "address_id": str(uuid.uuid4()),
        "city_id": TEST_CITY_ID_1,
        "department": "75",
        "address_raw": "123 Rue de Paris",
        "sale_date": "2023-01-15",
        "property_type": "house",
        "surface": 120,
        "rooms": 4,
        "price": 300000
    },
    {
        "address_id": str(uuid.uuid4()),
        "city_id": TEST_CITY_ID_1,
        "department": "75",
        "address_raw": "456 Avenue de Paris",
        "sale_date": "2023-02-20",
        "property_type": "apartment",
        "surface": 80,
        "rooms": 3,
        "price": 250000
    },
    {
        "address_id": str(uuid.uuid4()),
        "city_id": TEST_CITY_ID_2,
        "department": "69",
        "address_raw": "789 Boulevard de Lyon",
        "sale_date": "2023-03-10",
        "property_type": "house",
        "surface": 150,
        "rooms": 5,
        "price": 400000
    },
    {
        "address_id": str(uuid.uuid4()),
        "city_id": TEST_CITY_ID_2,
        "department": "69",
        "address_raw": "101 Rue de Lyon",
        "sale_date": "2023-04-05",
        "property_type": "apartment",
        "surface": 60,
        "rooms": 2,
        "price": 180000
    },
    {
        "address_id": str(uuid.uuid4()),
        "city_id": TEST_CITY_ID_3,
        "department": "13",
        "address_raw": "111 Avenue de Marseille",
        "sale_date": "2023-05-15",
        "property_type": "house",
        "surface": 100,
        "rooms": 3,
        "price": 220000
    }
]

def get_test_supabase_client() -> Client:
    """Get a Supabase client for the test database."""
    return create_client(TEST_SUPABASE_URL, TEST_SUPABASE_KEY)

@pytest.fixture
def clean_test_db() -> Generator[None, None, None]:
    """
    Clean the test database before and after tests.
    
    This fixture:
    1. Deletes all data from test tables
    2. Seeds the database with test data
    3. After the test, cleans up the database again
    """
    client = get_test_supabase_client()
    
    # Clean all test tables first
    try:
        client.table("client_addresses").delete().execute()
        client.table("addresses").delete().execute()
        client.table("processing_jobs").delete().execute()
        client.table("clients").delete().execute()
        client.table("cities").delete().execute()
    except Exception as e:
        print(f"Error cleaning test database: {e}")
    
    # Seed test data
    try:
        # Insert cities
        for city in TEST_CITIES:
            client.table("cities").insert(city).execute()
        
        # Insert client
        client.table("clients").insert(TEST_CLIENT).execute()
        
        # Insert addresses
        for address in TEST_ADDRESSES:
            client.table("addresses").insert(address).execute()
    except Exception as e:
        print(f"Error seeding test database: {e}")
    
    yield
    
    # Clean up after test
    try:
        client.table("client_addresses").delete().execute()
        client.table("addresses").delete().execute()
        client.table("processing_jobs").delete().execute()
        client.table("clients").delete().execute()
        client.table("cities").delete().execute()
    except Exception as e:
        print(f"Error cleaning test database after test: {e}")

class TestDBManager:
    """
    A test database manager that uses the test database.
    This can be used to patch the real DBManager in tests.
    """
    # Use class variables instead of initializing in __init__
    supabase_url = TEST_SUPABASE_URL
    supabase_key = TEST_SUPABASE_KEY
    client = None
    
    def __enter__(self):
        """Enter the context manager."""
        self.client = create_client(self.supabase_url, self.supabase_key)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        # Supabase client doesn't need explicit closing
        self.client = None
    
    def get_client(self):
        """Get the Supabase client."""
        if not self.client:
            self.client = create_client(self.supabase_url, self.supabase_key)
        return self.client 