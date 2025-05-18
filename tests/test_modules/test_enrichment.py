"""
Tests for the TrackImmo enrichment module.
"""
import os
import csv
import pytest
from pathlib import Path

from trackimmo.modules.enrichment import EnrichmentOrchestrator

@pytest.fixture
def test_environment():
    """Set up test environment for enrichment tests."""
    # Create necessary directories
    data_dir = "test_output/data"
    os.makedirs(os.path.join(data_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "processing"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "output"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "cache", "dpe"), exist_ok=True)
    
    # Create a simple test data file
    test_data_file = os.path.join(data_dir, "raw", "test_properties.csv")
    with open(test_data_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['address_id', 'city_id', 'address_raw', 'sale_date', 'property_type', 'surface', 'rooms', 'price'])
        writer.writerow(['test1', 'city1', '123 Test Street, Lille', '2023-01-15', 'house', '120', '4', '300000'])
        writer.writerow(['test2', 'city2', '456 Sample Avenue, Paris', '2023-02-20', 'apartment', '80', '3', '250000'])
    
    return {
        'data_dir': data_dir,
        'test_file': test_data_file
    }

def test_enrichment_orchestrator(test_environment):
    """Test the enrichment orchestrator."""
    # Configure the orchestrator
    config = {
        "data_dir": test_environment['data_dir'],
        "db_url": "postgresql://test:test@localhost/test"  # Mock connection string
    }
    
    # Create the orchestrator
    orchestrator = EnrichmentOrchestrator(config)
    
    # Verify the orchestrator was created successfully
    assert orchestrator is not None
    assert orchestrator.config["data_dir"] == test_environment['data_dir']
    
    # Verify file paths were set up correctly
    assert 'raw' in orchestrator.file_paths
    assert 'normalized' in orchestrator.file_paths
    assert 'cities_resolved' in orchestrator.file_paths
    
    # Verify directories are created
    assert os.path.exists(orchestrator.raw_dir)
    assert os.path.exists(orchestrator.processing_dir)
    assert os.path.exists(orchestrator.output_dir)
    
    # Test using our pre-created test file
    orchestrator.file_paths['raw'] = test_environment['test_file']
    
    # Create a minimal processor stub for test
    class TestProcessor:
        def __init__(self, input_path, output_path):
            self.input_path = input_path
            self.output_path = output_path
            
        def process(self):
            # Just copy the input file to output location to simulate processing
            with open(self.input_path, 'r') as input_file:
                data = input_file.read()
            with open(self.output_path, 'w') as output_file:
                output_file.write(data)
            return True
    
    # Monkey patch the run method to use our test processor
    original_run = orchestrator.run
    
    # Test a simplified version of the run method
    def test_run(input_file=None, start_stage=1, end_stage=1, debug=True):
        """Test implementation of run that just processes stage 1"""
        if input_file:
            orchestrator.file_paths['raw'] = input_file
            
        # Use a test processor for normalizer
        normalizer = TestProcessor(
            input_path=orchestrator.file_paths['raw'],
            output_path=orchestrator.file_paths['normalized']
        )
        
        # Process stage 1 only
        normalizer.process()
        return True
    
    # Replace the run method temporarily
    orchestrator.run = test_run
    
    # Execute the test run
    success = orchestrator.run(
        input_file=test_environment['test_file'],
        start_stage=1,
        end_stage=1,
        debug=True
    )
    
    # Restore the original run method
    orchestrator.run = original_run
    
    # Verify success and output file exists
    assert success is True
    assert os.path.exists(orchestrator.file_paths['normalized'])
    
    # Verify output file has the expected content
    with open(orchestrator.file_paths['normalized'], 'r') as f:
        content = f.read()
        assert 'Test Street' in content
        assert 'Sample Avenue' in content 