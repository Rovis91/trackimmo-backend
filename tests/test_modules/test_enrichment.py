"""
Tests for the TrackImmo enrichment module using real data.
These tests perform actual API calls and database operations.
"""
import os
import csv
import pytest
import pandas as pd
from pathlib import Path

from trackimmo.modules.enrichment import EnrichmentOrchestrator
from trackimmo.modules.enrichment.data_normalizer import DataNormalizer
from trackimmo.modules.enrichment.city_resolver import CityResolver
from trackimmo.modules.enrichment.geocoding_service import GeocodingService
from trackimmo.modules.enrichment.dpe_enrichment import DPEEnrichmentService
from trackimmo.modules.enrichment.price_estimator import PriceEstimationService

# Test project ID for Supabase
TEST_PROJECT_ID = "winabqdzcqyuaoaqmfmn"

@pytest.fixture
def test_environment():
    """Set up test environment for enrichment tests."""
    # Create necessary directories
    data_dir = "test_output/data"
    os.makedirs(os.path.join(data_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "processing"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "output"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "cache", "dpe"), exist_ok=True)
    
    return {
        'data_dir': data_dir,
        'raw_dir': os.path.join(data_dir, "raw"),
        'processing_dir': os.path.join(data_dir, "processing"),
        'output_dir': os.path.join(data_dir, "output"),
        'cache_dir': os.path.join(data_dir, "cache")
    }

@pytest.fixture
def sample_raw_data(test_environment):
    """Create sample raw data file for testing."""
    test_data_file = os.path.join(test_environment['raw_dir'], 'sample_properties.csv')
    
    sample_data = [
        ['123 Rue de la République', 'Lille', '300000', '120', '4', '15/01/2023', 'maison', 'https://example.com/1'],
        ['456 Avenue du Général de Gaulle', 'Roubaix', '250000', '80', '3', '20/02/2023', 'appartement', 'https://example.com/2'],
        ['789 Boulevard Victor Hugo', 'Tourcoing', '180000', '65', '2', '10/03/2023', 'appartement', 'https://example.com/3']
    ]
    
    with open(test_data_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address', 'city', 'price', 'surface', 'rooms', 'sale_date', 'property_type', 'property_url'])
        writer.writerows(sample_data)
    
    return test_data_file

@pytest.fixture
def test_cities_data():
    """Test cities data to be inserted and cleaned up."""
    return []

@pytest.fixture(autouse=True)
def cleanup_test_data(test_cities_data):
    """Automatically cleanup test data after each test."""
    yield
    
    # Cleanup any test cities that were created
    if test_cities_data:
        try:
            from trackimmo.modules.db_manager import DBManager
            with DBManager() as db:
                for city_data in test_cities_data:
                    if 'city_id' in city_data:
                        # Delete test city
                        db.get_client().table("cities").delete().eq("city_id", city_data['city_id']).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test city data: {e}")

def test_data_normalizer_real_addresses(test_environment, sample_raw_data):
    """Test data normalization with real French addresses."""
    normalizer = DataNormalizer(
        input_path=sample_raw_data,
        output_path=os.path.join(test_environment['processing_dir'], "normalized.csv")
    )
    
    success = normalizer.process()
    assert success is True
    
    # Verify normalized output
    df = pd.read_csv(normalizer.output_path)
    assert len(df) == 3
    
    # Check normalized columns
    assert 'address_raw' in df.columns
    assert 'city_name' in df.columns
    assert 'property_type' in df.columns
    
    # Verify normalization
    assert df.iloc[0]['address_raw'] == '123 RUE DE LA REPUBLIQUE'
    assert df.iloc[0]['city_name'] == 'LILLE'
    assert df.iloc[0]['property_type'] == 'house'  # maison -> house
    assert df.iloc[1]['property_type'] == 'apartment'  # appartement -> apartment

def test_city_resolver_real_cities(test_environment):
    """Test city resolution with real French cities."""
    # Create test data with normalized addresses
    test_file = os.path.join(test_environment['processing_dir'], 'normalized_for_city_test.csv')
    
    test_data = [
        ['123 RUE DE LA REPUBLIQUE', 'LILLE', 300000, 120, 4, '2023-01-15', 'house', ''],
        ['456 AVENUE DU GENERAL DE GAULLE', 'ROUBAIX', 250000, 80, 3, '2023-02-20', 'apartment', '']
    ]
    
    with open(test_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address_raw', 'city_name', 'price', 'surface', 'rooms', 'sale_date', 'property_type', 'source_url'])
        writer.writerows(test_data)
    
    city_resolver = CityResolver(
        input_path=test_file,
        output_path=os.path.join(test_environment['processing_dir'], "cities_resolved.csv")
    )
    
    success = city_resolver.process()
    assert success is True
    
    # Verify city resolution results
    df = pd.read_csv(city_resolver.output_path)
    assert len(df) == 2
    
    # Check that city resolution columns were added
    assert 'city_id' in df.columns
    assert 'postal_code' in df.columns
    assert 'insee_code' in df.columns
    assert 'department' in df.columns

@pytest.mark.slow
def test_geocoding_service_real_api(test_environment):
    """Test geocoding service with real French geocoding API."""
    # Create test data with city information
    test_file = os.path.join(test_environment['processing_dir'], 'cities_resolved_for_geo_test.csv')
    
    test_data = [
        ['123 RUE DE LA REPUBLIQUE', 'LILLE', 300000, 120, 4, '2023-01-15', 'house', '', 'city-id-1', '59000', '59350', '59'],
        ['456 AVENUE DU GENERAL DE GAULLE', 'ROUBAIX', 250000, 80, 3, '2023-02-20', 'apartment', '', 'city-id-2', '59100', '59512', '59']
    ]
    
    with open(test_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address_raw', 'city_name', 'price', 'surface', 'rooms', 'sale_date', 'property_type', 'source_url', 'city_id', 'postal_code', 'insee_code', 'department'])
        writer.writerows(test_data)
    
    geocoding_service = GeocodingService(
        input_path=test_file,
        output_path=os.path.join(test_environment['processing_dir'], "geocoded.csv"),
        original_bbox={
            "min_lat": 50.5,
            "max_lat": 50.8,
            "min_lon": 2.8,
            "max_lon": 3.3
        }
    )
    
    success = geocoding_service.process()
    assert success is True
    
    # Verify geocoding results
    df = pd.read_csv(geocoding_service.output_path)
    assert len(df) == 2
    
    # Check that geocoding columns were added
    assert 'latitude' in df.columns
    assert 'longitude' in df.columns
    assert 'address_normalized' in df.columns
    assert 'geocoding_score' in df.columns

@pytest.mark.slow
def test_dpe_enrichment_real_api(test_environment):
    """Test DPE enrichment with real ADEME API."""
    # Create test data with geocoded information
    test_file = os.path.join(test_environment['processing_dir'], 'geocoded_for_dpe_test.csv')
    
    test_data = [
        ['123 RUE DE LA REPUBLIQUE', 'LILLE', 300000, 120, 4, '2023-01-15', 'house', '', 'city-id-1', '59000', '59350', '59', 50.6292, 3.0573, '123 RUE DE LA REPUBLIQUE LILLE', 0.95],
        ['456 AVENUE DU GENERAL DE GAULLE', 'ROUBAIX', 250000, 80, 3, '2023-02-20', 'apartment', '', 'city-id-2', '59100', '59512', '59', 50.6942, 3.1746, '456 AVENUE DU GENERAL DE GAULLE ROUBAIX', 0.90]
    ]
    
    with open(test_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address_raw', 'city_name', 'price', 'surface', 'rooms', 'sale_date', 'property_type', 'source_url', 'city_id', 'postal_code', 'insee_code', 'department', 'latitude', 'longitude', 'address_normalized', 'geocoding_score'])
        writer.writerows(test_data)
    
    dpe_enrichment = DPEEnrichmentService(
        input_path=test_file,
        output_path=os.path.join(test_environment['processing_dir'], "dpe_enriched.csv"),
        dpe_cache_dir=os.path.join(test_environment['cache_dir'], "dpe")
    )
    
    success = dpe_enrichment.process()
    assert success is True
    
    # Verify DPE enrichment results
    df = pd.read_csv(dpe_enrichment.output_path)
    assert len(df) == 2
    
    # Check that DPE columns were added (they might be None if no matches found)
    assert 'dpe_number' in df.columns
    assert 'dpe_date' in df.columns
    assert 'dpe_energy_class' in df.columns
    assert 'dpe_ges_class' in df.columns

def test_price_estimator_real_data(test_environment):
    """Test price estimation with real data."""
    # Create test data with DPE information
    test_file = os.path.join(test_environment['processing_dir'], 'dpe_enriched_for_price_test.csv')
    
    test_data = [
        ['123 RUE DE LA REPUBLIQUE', 'LILLE', 300000, 120, 4, '2023-01-15', 'house', '', 'city-id-1', '59000', '59350', '59', 50.6292, 3.0573, '123 RUE DE LA REPUBLIQUE LILLE', 0.95, None, None, 'D', 'D'],
        ['456 AVENUE DU GENERAL DE GAULLE', 'ROUBAIX', 250000, 80, 3, '2023-02-20', 'apartment', '', 'city-id-2', '59100', '59512', '59', 50.6942, 3.1746, '456 AVENUE DU GENERAL DE GAULLE ROUBAIX', 0.90, None, None, 'C', 'C']
    ]
    
    with open(test_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address_raw', 'city_name', 'price', 'surface', 'rooms', 'sale_date', 'property_type', 'source_url', 'city_id', 'postal_code', 'insee_code', 'department', 'latitude', 'longitude', 'address_normalized', 'geocoding_score', 'dpe_number', 'dpe_date', 'dpe_energy_class', 'dpe_ges_class'])
        writer.writerows(test_data)
    
    price_estimator = PriceEstimationService(
        input_path=test_file,
        output_path=os.path.join(test_environment['processing_dir'], "price_estimated.csv")
    )
    
    success = price_estimator.process()
    assert success is True
    
    # Verify price estimation results
    df = pd.read_csv(price_estimator.output_path)
    assert len(df) == 2
    
    # Check that price estimation columns were added
    assert 'estimated_price' in df.columns
    assert 'price_evolution_rate' in df.columns
    assert 'estimation_confidence' in df.columns

def test_enrichment_orchestrator_initialization(test_environment):
    """Test enrichment orchestrator initialization."""
    config = {
        "data_dir": test_environment['data_dir'],
        "original_bbox": {
            "min_lat": 50.5,
            "max_lat": 50.8,
            "min_lon": 2.8,
            "max_lon": 3.3
        }
    }
    
    orchestrator = EnrichmentOrchestrator(config)
    
    assert orchestrator.config == config
    assert orchestrator.data_dir == test_environment['data_dir']
    assert os.path.exists(orchestrator.raw_dir)
    assert os.path.exists(orchestrator.processing_dir)
    assert os.path.exists(orchestrator.output_dir)
    
def test_enrichment_orchestrator_partial_pipeline(test_environment, sample_raw_data):
    """Test enrichment orchestrator with partial pipeline (stages 1-3)."""
    config = {
        "data_dir": test_environment['data_dir'],
        "original_bbox": {
            "min_lat": 50.5,
            "max_lat": 50.8,
            "min_lon": 2.8,
            "max_lon": 3.3
        }
    }
    
    orchestrator = EnrichmentOrchestrator(config)
    
    # Run only stages 1-3 (normalization, city resolution, geocoding)
    success = orchestrator.run(
        input_file=sample_raw_data,
        start_stage=1,
        end_stage=3,
        debug=True
    )
    
    assert success is True
    
    # Verify intermediate files were created
    assert os.path.exists(orchestrator.file_paths['normalized'])
    assert os.path.exists(orchestrator.file_paths['cities_resolved'])
    assert os.path.exists(orchestrator.file_paths['geocoded'])
    
    # Verify final output
    df = pd.read_csv(orchestrator.file_paths['geocoded'])
    assert len(df) == 3
    assert 'latitude' in df.columns
    assert 'longitude' in df.columns

@pytest.mark.database
def test_enrichment_database_integration(test_cities_data):
    """Test enrichment integration with database for city data."""
    from trackimmo.modules.db_manager import DBManager
    
    # Create test cities for enrichment
    test_cities = [
        {
            "name": "Enrichment Test City 1",
            "postal_code": "88888",
            "insee_code": "88888",
            "department": "88",
            "region": "Test Region"
        },
        {
            "name": "Enrichment Test City 2",
            "postal_code": "99999",
            "insee_code": "99999",
            "department": "99",
            "region": "Test Region"
        }
    ]
    
    try:
        with DBManager() as db:
            # Insert test cities
            result = db.get_client().table("cities").insert(test_cities).execute()
            created_cities = result.data
            test_cities_data.extend(created_cities)  # Add to cleanup list
            
            assert len(created_cities) == 2
            
            # Verify cities can be retrieved for enrichment
            for city in created_cities:
                city_id = city['city_id']
                retrieved = db.get_client().table("cities").select("*").eq("city_id", city_id).execute()
                assert len(retrieved.data) == 1
                assert retrieved.data[0]['name'] == city['name']
                assert retrieved.data[0]['postal_code'] == city['postal_code']
            
    except Exception as e:
        pytest.fail(f"Database integration test failed: {e}")

@pytest.mark.performance
def test_enrichment_performance_metrics(test_environment):
    """Test enrichment performance with sample data."""
    import time
    
    # Create larger sample dataset for performance testing
    test_file = os.path.join(test_environment['raw_dir'], 'performance_test.csv')
    
    sample_data = []
    for i in range(50):  # 50 properties for performance test
        sample_data.append([
            f'{100 + i} Rue de Test',
            'Lille',
            250000 + (i * 1000),
            80 + (i % 20),
            3 + (i % 3),
            '15/01/2023',
            'apartment' if i % 2 == 0 else 'house',
            f'https://example.com/{i}'
        ])
    
    with open(test_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address', 'city', 'price', 'surface', 'rooms', 'sale_date', 'property_type', 'property_url'])
        writer.writerows(sample_data)
    
    config = {
        "data_dir": test_environment['data_dir'],
        "original_bbox": {
            "min_lat": 50.5,
            "max_lat": 50.8,
            "min_lon": 2.8,
            "max_lon": 3.3
        }
    }
    
    orchestrator = EnrichmentOrchestrator(config)
    
    start_time = time.time()
    
    # Run only stages 1-2 for performance test (avoid slow API calls)
    success = orchestrator.run(
        input_file=test_file,
        start_stage=1,
        end_stage=2,
        debug=False
    )
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    assert success is True
    
    # Performance assertions
    assert execution_time < 30  # Should complete within 30 seconds for 50 properties
    
    # Verify output quality
    df = pd.read_csv(orchestrator.file_paths['cities_resolved'])
    assert len(df) == 50
    
    print(f"Enrichment performance: {execution_time:.2f}s for 50 properties")

# TODO: Add integration test with database insertion
@pytest.mark.integration
def test_enrichment_to_database_integration():
    """
    Integration test for enrichment pipeline to database insertion.
    
    INTEGRATION TEST REQUIREMENTS:
    1. Run complete enrichment pipeline
    2. Insert enriched properties into database
    3. Verify data integrity across all stages
    4. Test error handling for database operations
    5. Verify foreign key relationships
    """
    pass

# TODO: Add full pipeline test
@pytest.mark.full_pipeline
def test_complete_enrichment_pipeline():
    """
    Test complete enrichment pipeline with all stages.
    
    FULL PIPELINE TEST REQUIREMENTS:
    1. Run all 6 enrichment stages
    2. Use real API calls for all services
    3. Verify data quality at each stage
    4. Test with various property types and locations
    5. Measure end-to-end performance
    """
    pass

# TODO: Add API rate limiting test
@pytest.mark.api_limits
def test_enrichment_api_rate_limiting():
    """
    Test API rate limiting for enrichment services.
    
    API TESTING REQUIREMENTS:
    1. Test geocoding API rate limits
    2. Test DPE API rate limits
    3. Verify retry mechanisms
    4. Test error handling for API failures
    5. Test concurrent processing limits
    """
    pass 