"""
Tests for the TrackImmo client processor module using real data.
These tests perform actual data processing and database operations.
"""
import os
import pytest
import pandas as pd
from datetime import datetime, timedelta
import uuid

from trackimmo.utils.validators import validate_client, validate_property
from trackimmo.modules.client_processor import (
    filter_properties_by_preferences,
    limit_and_sort_properties,
    deduplicate_properties,
    prepare_client_notification_data
)

# Test project ID for Supabase
TEST_PROJECT_ID = "winabqdzcqyuaoaqmfmn"

@pytest.fixture
def test_environment():
    """Set up test environment for client processor tests."""
    # Create necessary directories
    data_dir = "test_output/data"
    os.makedirs(os.path.join(data_dir, "output"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "processing"), exist_ok=True)
    
    return {
        'data_dir': data_dir,
        'output_dir': os.path.join(data_dir, "output"),
        'processing_dir': os.path.join(data_dir, "processing")
    }

@pytest.fixture
def test_cities_data():
    """Test cities data to be inserted and cleaned up."""
    return []

@pytest.fixture
def test_clients_data():
    """Test clients data to be inserted and cleaned up."""
    return []

@pytest.fixture
def test_addresses_data():
    """Test addresses data to be inserted and cleaned up."""
    return []

@pytest.fixture(autouse=True)
def cleanup_test_data(test_cities_data, test_clients_data, test_addresses_data):
    """Automatically cleanup test data after each test."""
    yield
    
    # Cleanup test data in reverse order (addresses -> clients -> cities)
    try:
        from trackimmo.modules.db_manager import DBManager
        with DBManager() as db:
            # Cleanup addresses
            for address_data in test_addresses_data:
                if 'address_id' in address_data:
                    db.get_client().table("addresses").delete().eq("address_id", address_data['address_id']).execute()
            
            # Cleanup clients
            for client_data in test_clients_data:
                if 'client_id' in client_data:
                    db.get_client().table("clients").delete().eq("client_id", client_data['client_id']).execute()
            
            # Cleanup cities
            for city_data in test_cities_data:
                if 'city_id' in city_data:
                    db.get_client().table("cities").delete().eq("city_id", city_data['city_id']).execute()
    except Exception as e:
        print(f"Warning: Could not cleanup test data: {e}")

@pytest.fixture
def sample_client_data():
    """Sample client data for testing."""
    return {
        'client_id': str(uuid.uuid4()),
        'first_name': 'Jean',
        'last_name': 'Dupont',
        'email': 'jean.dupont@example.com',
        'telephone': '0123456789',
        'subscription_type': 'decouverte',  # Updated to valid enum value
        'status': 'active',
        'send_day': 15,
        'addresses_per_report': 10,
        'property_type_preferences': ['house', 'apartment'],
        'chosen_cities': ['59350', '59512'],  # Lille, Roubaix INSEE codes
        'created_at': '2023-01-01T00:00:00Z',
        'updated_at': '2023-01-01T00:00:00Z'
    }

@pytest.fixture
def sample_property_data():
    """Sample property data for testing."""
    return [
        {
            'address_id': str(uuid.uuid4()),
            'department': '59',
            'address_raw': '123 Rue de la République, Lille',
            'sale_date': '15/01/2023',
            'property_type': 'house',
            'surface': 120,
            'rooms': 4,
            'price': 300000,
            'estimated_price': 295000,
            'city_name': 'Lille',
            'postal_code': '59000',
            'insee_code': '59350'
        },
        {
            'address_id': str(uuid.uuid4()),
            'department': '59',
            'address_raw': '456 Avenue du Général de Gaulle, Roubaix',
            'sale_date': '20/02/2023',
            'property_type': 'apartment',
            'surface': 80,
            'rooms': 3,
            'price': 250000,
            'estimated_price': 245000,
            'city_name': 'Roubaix',
            'postal_code': '59100',
            'insee_code': '59512'
        },
        {
            'address_id': str(uuid.uuid4()),
            'department': '59',
            'address_raw': '789 Boulevard Victor Hugo, Tourcoing',
            'sale_date': '10/03/2023',
            'property_type': 'apartment',
            'surface': 65,
            'rooms': 2,
            'price': 180000,
            'estimated_price': 175000,
            'city_name': 'Tourcoing',
            'postal_code': '59200',
            'insee_code': '59599'
        }
    ]

def test_validate_client_data_valid(sample_client_data):
    """Test client data validation with valid data."""
    is_valid, error = validate_client(sample_client_data)
    
    assert is_valid is True
    assert error is None

def test_validate_client_data_invalid():
    """Test client data validation with invalid data."""
    # Missing required fields
    invalid_client = {
        'first_name': 'Jean',
        # Missing last_name, email, etc.
    }
    
    is_valid, error = validate_client(invalid_client)
    
    assert is_valid is False
    assert error is not None
    assert 'last_name' in error

def test_validate_property_data_valid(sample_property_data):
    """Test property data validation with valid data."""
    for property_data in sample_property_data:
        is_valid, error = validate_property(property_data)
        
        assert is_valid is True
        assert error is None

def test_validate_property_data_invalid():
    """Test property data validation with invalid data."""
    # Missing required fields
    invalid_property = {
        'address_raw': '123 Test Street',
        # Missing city_name, postal_code, etc.
    }
    
    is_valid, error = validate_property(invalid_property)
    
    assert is_valid is False
    assert error is not None

def test_filter_properties_by_preferences(sample_client_data, sample_property_data):
    """Test filtering properties by client preferences."""
    # Client prefers houses and apartments in Lille and Roubaix
    client_preferences = {
        'property_type_preferences': ['house', 'apartment'],
        'chosen_cities': ['59350', '59512']  # Lille, Roubaix INSEE codes
    }
    
    filtered_properties = filter_properties_by_preferences(
        properties=sample_property_data,
        client_preferences=client_preferences
    )
    
    # Should filter out Tourcoing property (INSEE code 59599)
    assert len(filtered_properties) == 2
    
    # Verify filtered properties match preferences
    for prop in filtered_properties:
        assert prop['property_type'] in client_preferences['property_type_preferences']
        assert prop['insee_code'] in client_preferences['chosen_cities']

def test_filter_properties_by_type_only(sample_property_data):
    """Test filtering properties by type only."""
    client_preferences = {
        'property_type_preferences': ['house'],
        'chosen_cities': []  # No city filter
    }
    
    filtered_properties = filter_properties_by_preferences(
        properties=sample_property_data,
        client_preferences=client_preferences
    )
    
    # Should only return house properties
    assert len(filtered_properties) == 1
    assert filtered_properties[0]['property_type'] == 'house'
    assert filtered_properties[0]['city_name'] == 'Lille'

def test_limit_and_sort_properties(sample_property_data):
    """Test limiting and sorting properties."""
    # Sort by price descending, limit to 2
    limited_properties = limit_and_sort_properties(
        properties=sample_property_data,
        limit=2,
        sort_by='price',
        sort_order='desc'
    )
    
    assert len(limited_properties) == 2
    
    # Should be sorted by price descending
    assert limited_properties[0]['price'] >= limited_properties[1]['price']
    assert limited_properties[0]['price'] == 300000  # Lille house (highest price)

def test_limit_and_sort_properties_by_date(sample_property_data):
    """Test sorting properties by sale date."""
    # Sort by sale date ascending
    sorted_properties = limit_and_sort_properties(
        properties=sample_property_data,
        limit=10,
        sort_by='sale_date',
        sort_order='asc'
    )
    
    assert len(sorted_properties) == 3
    
    # Should be sorted by date ascending
    dates = [prop['sale_date'] for prop in sorted_properties]
    assert dates == sorted(dates)

def test_deduplicate_properties():
    """Test property deduplication."""
    # Create properties with duplicates
    properties_with_duplicates = [
        {
            'address_id': str(uuid.uuid4()),
            'address_raw': '123 Rue de la République, Lille',
            'city_name': 'Lille',
            'price': 300000,
            'sale_date': '2023-01-15'
        },
        {
            'address_id': str(uuid.uuid4()),
            'address_raw': '123 Rue de la République, Lille',  # Duplicate address
            'city_name': 'Lille',
            'price': 305000,  # Different price
            'sale_date': '2023-01-20'  # Different date
        },
        {
            'address_id': str(uuid.uuid4()),
            'address_raw': '456 Avenue du Test, Roubaix',
            'city_name': 'Roubaix',
            'price': 250000,
            'sale_date': '2023-02-01'
        }
    ]
    
    deduplicated = deduplicate_properties(properties_with_duplicates)
    
    # Should remove one duplicate
    assert len(deduplicated) == 2
    
    # Should keep the more recent sale (higher price in this case)
    lille_property = next(p for p in deduplicated if p['city_name'] == 'Lille')
    assert lille_property['price'] == 305000  # Should keep the more recent/higher priced one

def test_prepare_client_notification_data(sample_client_data, sample_property_data):
    """Test preparing client notification data."""
    notification_data = prepare_client_notification_data(
        client=sample_client_data,
        properties=sample_property_data,
        report_date=datetime.now()
    )
    
    # Verify notification data structure
    assert 'client' in notification_data
    assert 'properties' in notification_data
    assert 'report_date' in notification_data
    assert 'summary' in notification_data
    
    # Verify client data
    assert notification_data['client']['first_name'] == sample_client_data['first_name']
    assert notification_data['client']['last_name'] == sample_client_data['last_name']
    assert notification_data['client']['email'] == sample_client_data['email']
    
    # Verify properties data
    assert len(notification_data['properties']) == len(sample_property_data)
    
    # Verify summary data
    summary = notification_data['summary']
    assert 'total_properties' in summary
    assert 'property_types' in summary
    assert 'price_range' in summary
    assert summary['total_properties'] == len(sample_property_data)

def test_prepare_notification_with_empty_properties(sample_client_data):
    """Test preparing notification data with no properties."""
    notification_data = prepare_client_notification_data(
        client=sample_client_data,
        properties=[],
        report_date=datetime.now()
    )
    
    assert notification_data['summary']['total_properties'] == 0
    assert len(notification_data['properties']) == 0

@pytest.mark.database
def test_client_processor_database_integration(test_cities_data):
    """Test client processor integration with database."""
    from trackimmo.modules.db_manager import DBManager
    
    # Create test client
    test_client = {
        "client_id": str(uuid.uuid4()),  # Added required client_id
        "first_name": "Test",
        "last_name": "Client",
        "email": "test.client@example.com",
        "telephone": "0123456789",
        "subscription_type": "decouverte",  # Changed to valid enum value
        "status": "active",
        "property_type_preferences": ["house", "apartment"]
    }
    
    test_clients = []
    
    try:
        with DBManager() as db:
            # Insert test client
            result = db.get_client().table("clients").insert(test_client).execute()
            created_client = result.data[0]
            test_clients.append(created_client)
            
            client_id = created_client['client_id']
            
            # Verify client can be retrieved
            retrieved = db.get_client().table("clients").select("*").eq("client_id", client_id).execute()
            assert len(retrieved.data) == 1
            assert retrieved.data[0]['email'] == test_client['email']
            
            # Test client preferences validation
            is_valid, error = validate_client(retrieved.data[0])
            assert is_valid is True
            
            # Cleanup
            db.get_client().table("clients").delete().eq("client_id", client_id).execute()
            
    except Exception as e:
        # Cleanup clients if test fails
        try:
            with DBManager() as db:
                for client in test_clients:
                    db.get_client().table("clients").delete().eq("client_id", client['client_id']).execute()
        except:
            pass
        pytest.fail(f"Database integration test failed: {e}")

@pytest.mark.database
def test_property_filtering_with_database(test_cities_data):
    """Test property filtering with real database data."""
    from trackimmo.modules.db_manager import DBManager
    
    # Create test city
    test_city = {
        "name": "Client Processor Test City",
        "postal_code": "77777",
        "insee_code": "77777",
        "department": "77",
        "region": "Test Region"
    }
    
    test_properties = []
    
    try:
        with DBManager() as db:
            # Insert test city
            city_result = db.get_client().table("cities").insert(test_city).execute()
            created_city = city_result.data[0]
            test_cities_data.append(created_city)
            
            city_id = created_city['city_id']
            
            # Create test properties
            properties_to_insert = [
                {
                    "department": "77",
                    "city_id": city_id,
                    "address_raw": "123 Test Street",
                    "sale_date": "2023-01-15",
                    "property_type": "house",
                    "surface": 120,
                    "rooms": 4,
                    "price": 300000
                },
                {
                    "department": "77",
                    "city_id": city_id,
                    "address_raw": "456 Test Avenue",
                    "sale_date": "2023-02-20",
                    "property_type": "apartment",
                    "surface": 80,
                    "rooms": 3,
                    "price": 250000
                }
            ]
            
            # Insert test properties
            prop_result = db.get_client().table("addresses").insert(properties_to_insert).execute()
            test_properties.extend(prop_result.data)
            
            # Test property filtering
            client_preferences = {
                'property_type_preferences': ['house'],
                'chosen_cities': ['77777']
            }
            
            # Convert database properties to expected format
            db_properties = []
            for prop in prop_result.data:
                db_properties.append({
                    'address_id': prop['address_id'],
                    'address_raw': prop['address_raw'],
                    'property_type': prop['property_type'],
                    'price': prop['price'],
                    'sale_date': prop['sale_date'],
                    'insee_code': '77777'  # From our test city
                })
            
            filtered = filter_properties_by_preferences(
                properties=db_properties,
                client_preferences=client_preferences
            )
            
            # Should only return house properties
            assert len(filtered) == 1
            assert filtered[0]['property_type'] == 'house'
            
            # Cleanup properties
            for prop in test_properties:
                db.get_client().table("addresses").delete().eq("address_id", prop['address_id']).execute()
            
    except Exception as e:
        # Cleanup properties if test fails
        try:
            with DBManager() as db:
                for prop in test_properties:
                    db.get_client().table("addresses").delete().eq("address_id", prop['address_id']).execute()
        except:
            pass
        pytest.fail(f"Property filtering database test failed: {e}")

@pytest.mark.performance
def test_client_processor_performance():
    """Test client processor performance with large datasets."""
    import time
    
    # Create large dataset for performance testing
    large_property_dataset = []
    for i in range(1000):  # 1000 properties
        large_property_dataset.append({
            'address_id': str(uuid.uuid4()),
            'address_raw': f'{100 + i} Rue de Test',
            'city_name': 'TestCity',
            'property_type': 'apartment' if i % 2 == 0 else 'house',
            'price': 200000 + (i * 100),
            'sale_date': f'2023-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            'insee_code': '59350'
        })
    
    client_preferences = {
        'property_type_preferences': ['apartment', 'house'],
        'chosen_cities': ['59350']
    }
    
    start_time = time.time()
    
    # Test filtering performance
    filtered = filter_properties_by_preferences(
        properties=large_property_dataset,
        client_preferences=client_preferences
    )
    
    # Test sorting performance
    sorted_properties = limit_and_sort_properties(
        properties=filtered,
        limit=100,
        sort_by='price',
        sort_order='desc'
    )
    
    # Test deduplication performance
    deduplicated = deduplicate_properties(sorted_properties)
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    # Performance assertions
    assert execution_time < 5  # Should complete within 5 seconds for 1000 properties
    assert len(filtered) == 1000  # All should match preferences
    assert len(sorted_properties) == 100  # Limited to 100
    assert len(deduplicated) <= 100  # Should be <= sorted properties
    
    print(f"Client processor performance: {execution_time:.2f}s for 1000 properties")

# TODO: Add integration test with notification system
@pytest.mark.integration
def test_client_processor_to_notification_integration():
    """
    Integration test from client processing to notification system.
    
    INTEGRATION TEST REQUIREMENTS:
    1. Process client preferences and property data
    2. Generate notification data
    3. Test email template rendering
    4. Verify notification delivery tracking
    5. Test error handling for notification failures
    """
    pass

# TODO: Add client preference optimization test
@pytest.mark.optimization
def test_client_preference_optimization():
    """
    Test client preference optimization and learning.
    
    OPTIMIZATION TEST REQUIREMENTS:
    1. Track client interaction with properties
    2. Analyze preference patterns
    3. Suggest preference improvements
    4. Test machine learning integration
    5. Verify recommendation accuracy
    """
    pass

# TODO: Add bulk processing test
@pytest.mark.bulk_processing
def test_bulk_client_processing():
    """
    Test bulk processing of multiple clients.
    
    BULK PROCESSING TEST REQUIREMENTS:
    1. Process multiple clients simultaneously
    2. Test resource management and memory usage
    3. Verify processing queue management
    4. Test error isolation between clients
    5. Measure throughput and scalability
    """
    pass 