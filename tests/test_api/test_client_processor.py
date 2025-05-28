"""
Unit tests for client processor module.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import uuid

from trackimmo.modules.client_processor import (
    weighted_random_selection,
    filter_properties_by_preferences,
    deduplicate_properties,
    get_client_by_id,
    assign_properties_to_client
)

class TestWeightedRandomSelection:
    """Test weighted random selection algorithm."""
    
    def test_weighted_selection_empty_list(self):
        """Test with empty property list."""
        result = weighted_random_selection([], 5)
        assert result == []
    
    def test_weighted_selection_fewer_than_requested(self):
        """Test when there are fewer properties than requested."""
        properties = [
            {"address_id": "1", "sale_date": "2017-01-01"},
            {"address_id": "2", "sale_date": "2017-06-01"}
        ]
        
        result = weighted_random_selection(properties, 5)
        assert len(result) == 2
        assert result == properties
    
    def test_weighted_selection_exact_count(self):
        """Test when property count equals requested count."""
        properties = [
            {"address_id": "1", "sale_date": "2017-01-01"},
            {"address_id": "2", "sale_date": "2017-06-01"},
            {"address_id": "3", "sale_date": "2018-01-01"}
        ]
        
        result = weighted_random_selection(properties, 3)
        assert len(result) == 3
        # All properties should be selected
        selected_ids = [p["address_id"] for p in result]
        assert set(selected_ids) == {"1", "2", "3"}
    
    def test_weighted_selection_ordering(self):
        """Test that older properties are favored."""
        properties = [
            {"address_id": "newest", "sale_date": "2018-12-01"},
            {"address_id": "oldest", "sale_date": "2017-01-01"},
            {"address_id": "middle", "sale_date": "2018-01-01"}
        ]
        
        # Run selection many times to test probability distribution
        selections = []
        for _ in range(100):
            result = weighted_random_selection(properties, 1)
            if result:
                selections.append(result[0]["address_id"])
        
        # Count selections
        oldest_count = selections.count("oldest")
        newest_count = selections.count("newest")
        
        # Oldest should be selected more frequently than newest
        assert oldest_count > newest_count, f"Oldest: {oldest_count}, Newest: {newest_count}"
    
    def test_weighted_selection_deterministic_with_seed(self):
        """Test that selection is deterministic with same random seed."""
        import random
        
        properties = [
            {"address_id": "1", "sale_date": "2017-01-01"},
            {"address_id": "2", "sale_date": "2017-06-01"},
            {"address_id": "3", "sale_date": "2018-01-01"}
        ]
        
        # Set seed and run selection
        random.seed(42)
        result1 = weighted_random_selection(properties, 2)
        
        # Reset seed and run again
        random.seed(42)
        result2 = weighted_random_selection(properties, 2)
        
        # Results should be identical
        assert result1 == result2

class TestFilterPropertiesByPreferences:
    """Test property filtering by client preferences."""
    
    def test_filter_by_property_type(self):
        """Test filtering by property type."""
        properties = [
            {"property_type": "house", "city_id": "city1"},
            {"property_type": "apartment", "city_id": "city1"},
            {"property_type": "land", "city_id": "city1"}
        ]
        
        preferences = {
            "property_type_preferences": ["house", "apartment"],
            "chosen_cities": ["city1"]
        }
        
        result = filter_properties_by_preferences(properties, preferences)
        assert len(result) == 2
        assert all(p["property_type"] in ["house", "apartment"] for p in result)
    
    def test_filter_by_city(self):
        """Test filtering by chosen cities."""
        properties = [
            {"property_type": "house", "city_id": "city1"},
            {"property_type": "house", "city_id": "city2"},
            {"property_type": "house", "city_id": "city3"}
        ]
        
        preferences = {
            "property_type_preferences": ["house"],
            "chosen_cities": ["city1", "city2"]
        }
        
        result = filter_properties_by_preferences(properties, preferences)
        assert len(result) == 2
        assert all(p["city_id"] in ["city1", "city2"] for p in result)
    
    def test_filter_empty_preferences(self):
        """Test filtering with empty preferences."""
        properties = [
            {"property_type": "house", "city_id": "city1"},
            {"property_type": "apartment", "city_id": "city2"}
        ]
        
        preferences = {
            "property_type_preferences": [],
            "chosen_cities": []
        }
        
        result = filter_properties_by_preferences(properties, preferences)
        assert len(result) == 2  # No filtering applied
    
    def test_filter_no_matches(self):
        """Test filtering with no matching properties."""
        properties = [
            {"property_type": "house", "city_id": "city1"},
            {"property_type": "apartment", "city_id": "city2"}
        ]
        
        preferences = {
            "property_type_preferences": ["land"],
            "chosen_cities": ["city3"]
        }
        
        result = filter_properties_by_preferences(properties, preferences)
        assert len(result) == 0

class TestDeduplicateProperties:
    """Test property deduplication logic."""
    
    def test_deduplicate_identical_addresses(self):
        """Test deduplication of identical addresses."""
        properties = [
            {"address_raw": "123 Rue de la Paix", "city_id": "city1", "price": 300000, "sale_date": "2017-01-01"},
            {"address_raw": "123 rue de la paix", "city_id": "city1", "price": 350000, "sale_date": "2017-02-01"},  # Same address, different case
            {"address_raw": "456 Avenue Test", "city_id": "city1", "price": 400000, "sale_date": "2017-01-01"}
        ]
        
        result = deduplicate_properties(properties)
        assert len(result) == 2  # One duplicate removed
        
        # Should keep the one with more recent date
        kept_property = next(p for p in result if "123" in p["address_raw"])
        assert kept_property["sale_date"] == "2017-02-01"
        assert kept_property["price"] == 350000
    
    def test_deduplicate_same_date_different_price(self):
        """Test deduplication with same date but different prices."""
        properties = [
            {"address_raw": "123 Rue Test", "city_id": "city1", "price": 300000, "sale_date": "2017-01-01"},
            {"address_raw": "123 Rue Test", "city_id": "city1", "price": 350000, "sale_date": "2017-01-01"}  # Same date, higher price
        ]
        
        result = deduplicate_properties(properties)
        assert len(result) == 1
        
        # Should keep the one with higher price
        assert result[0]["price"] == 350000
    
    def test_deduplicate_different_cities(self):
        """Test that same address in different cities is not deduplicated."""
        properties = [
            {"address_raw": "123 Rue de la Paix", "city_id": "paris", "price": 300000, "sale_date": "2017-01-01"},
            {"address_raw": "123 Rue de la Paix", "city_id": "lyon", "price": 250000, "sale_date": "2017-01-01"}
        ]
        
        result = deduplicate_properties(properties)
        assert len(result) == 2  # Different cities, so no deduplication
    
    def test_deduplicate_no_duplicates(self):
        """Test deduplication with no actual duplicates."""
        properties = [
            {"address_raw": "123 Rue A", "city_id": "city1", "price": 300000, "sale_date": "2017-01-01"},
            {"address_raw": "456 Rue B", "city_id": "city1", "price": 350000, "sale_date": "2017-01-01"},
            {"address_raw": "789 Rue C", "city_id": "city1", "price": 400000, "sale_date": "2017-01-01"}
        ]
        
        result = deduplicate_properties(properties)
        assert len(result) == 3  # No duplicates, all kept

class TestClientProcessorIntegration:
    """Test client processor integration with mocked database."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager."""
        with patch('trackimmo.modules.client_processor.DBManager') as mock:
            yield mock
    
    @pytest.fixture
    def sample_client(self):
        """Sample client data."""
        return {
            "client_id": str(uuid.uuid4()),
            "first_name": "Test",
            "last_name": "Client",
            "email": "test@example.com",
            "status": "active",
            "chosen_cities": [str(uuid.uuid4()), str(uuid.uuid4())],
            "property_type_preferences": ["house", "apartment"],
            "addresses_per_report": 10
        }
    
    @pytest.fixture
    def sample_properties(self):
        """Sample properties data."""
        base_date = datetime.now() - timedelta(days=7*365)  # 7 years ago
        return [
            {
                "address_id": str(uuid.uuid4()),
                "address_raw": "123 Test Street",
                "city_id": str(uuid.uuid4()),
                "price": 300000,
                "surface": 80,
                "rooms": 3,
                "property_type": "house",
                "sale_date": (base_date + timedelta(days=i*30)).strftime("%Y-%m-%d")
            }
            for i in range(10)
        ]
    
    @pytest.mark.asyncio
    async def test_get_client_by_id_success(self, mock_db_manager, sample_client):
        """Test successful client retrieval."""
        # Mock database response
        mock_db = MagicMock()
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_client]
        mock_db_manager.return_value.__enter__.return_value = mock_db
        
        result = await get_client_by_id(sample_client["client_id"])
        
        assert result is not None
        assert result["client_id"] == sample_client["client_id"]
        assert result["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_get_client_by_id_not_found(self, mock_db_manager):
        """Test client not found scenario."""
        # Mock empty database response
        mock_db = MagicMock()
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_db_manager.return_value.__enter__.return_value = mock_db
        
        result = await get_client_by_id("non-existent-id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_assign_properties_to_client_success(self, sample_client, sample_properties):
        """Test successful property assignment."""
        # Mock the DBManager and its database operations
        with patch('trackimmo.modules.client_processor.DBManager') as mock_db_manager:
            # Create mock database instance
            mock_db = MagicMock()
            mock_db_manager.return_value.__enter__.return_value = mock_db
            mock_db_manager.return_value.__exit__.return_value = None
            
            # Mock the client_addresses table query (existing assignments - should be empty)
            mock_client_addresses_table = MagicMock()
            mock_client_addresses_response = MagicMock()
            mock_client_addresses_response.data = []  # No existing assignments
            mock_client_addresses_table.select.return_value.eq.return_value.execute.return_value = mock_client_addresses_response
            
            # Mock the addresses table query (available properties)
            mock_addresses_table = MagicMock()
            mock_addresses_response = MagicMock()
            mock_addresses_response.data = sample_properties  # Return our sample properties
            
            # Set up the complex query chain for addresses table
            query_chain = mock_addresses_table.select.return_value
            query_chain.in_.return_value.in_.return_value.gte.return_value.lte.return_value.execute.return_value = mock_addresses_response
            
            # Mock the insert operation
            mock_insert_response = MagicMock()
            mock_client_addresses_table.insert.return_value.execute.return_value = mock_insert_response
            
            # Set up table routing
            def table_side_effect(table_name):
                if table_name == "client_addresses":
                    return mock_client_addresses_table
                elif table_name == "addresses":
                    return mock_addresses_table
                return MagicMock()
            
            mock_db.get_client.return_value.table.side_effect = table_side_effect
            
            # Import and call the function
            from trackimmo.modules.client_processor import assign_properties_to_client
            result = await assign_properties_to_client(sample_client, 3)
            
            # Verify results
            assert len(result) == 3
            assert all(prop["property_type"] in sample_client["property_type_preferences"] for prop in result)
            
            # Verify database calls were made
            mock_db.get_client.assert_called()
            mock_client_addresses_table.select.assert_called()
            mock_addresses_table.select.assert_called()
    
    @pytest.mark.asyncio
    async def test_assign_properties_no_eligible_properties(self, sample_client):
        """Test assignment when no eligible properties exist."""
        # Mock the DBManager and its database operations
        with patch('trackimmo.modules.client_processor.DBManager') as mock_db_manager:
            # Create mock database instance
            mock_db = MagicMock()
            mock_db_manager.return_value.__enter__.return_value = mock_db
            mock_db_manager.return_value.__exit__.return_value = None
            
            # Mock the client_addresses table query (existing assignments - should be empty)
            mock_client_addresses_table = MagicMock()
            mock_client_addresses_response = MagicMock()
            mock_client_addresses_response.data = []  # No existing assignments
            mock_client_addresses_table.select.return_value.eq.return_value.execute.return_value = mock_client_addresses_response
            
            # Mock the addresses table query (no available properties)
            mock_addresses_table = MagicMock()
            mock_addresses_response = MagicMock()
            mock_addresses_response.data = []  # No properties available
            
            # Set up the complex query chain for addresses table
            query_chain = mock_addresses_table.select.return_value
            query_chain.in_.return_value.in_.return_value.gte.return_value.lte.return_value.execute.return_value = mock_addresses_response
            
            # Set up table routing
            def table_side_effect(table_name):
                if table_name == "client_addresses":
                    return mock_client_addresses_table
                elif table_name == "addresses":
                    return mock_addresses_table
                return MagicMock()
            
            mock_db.get_client.return_value.table.side_effect = table_side_effect
            
            # Import and call the function
            from trackimmo.modules.client_processor import assign_properties_to_client
            result = await assign_properties_to_client(sample_client, 5)
            
            # Verify no properties were assigned
            assert len(result) == 0

class TestPropertyAgeCalculation:
    """Test property age calculation logic."""
    
    def test_age_range_calculation(self):
        """Test that age range calculation is correct."""
        from trackimmo.config import settings
        
        # Test current date ranges
        now = datetime.now()
        min_date = now - timedelta(days=settings.MAX_PROPERTY_AGE_YEARS * 365)
        max_date = now - timedelta(days=settings.MIN_PROPERTY_AGE_YEARS * 365)
        
        # Verify the range makes sense
        assert min_date < max_date
        assert (max_date - min_date).days == (settings.MAX_PROPERTY_AGE_YEARS - settings.MIN_PROPERTY_AGE_YEARS) * 365
    
    def test_property_within_age_range(self):
        """Test property age validation."""
        from trackimmo.config import settings
        
        now = datetime.now()
        
        # Property that's 7 years old (within 6-8 year range)
        seven_years_ago = now - timedelta(days=7 * 365)
        
        min_date = now - timedelta(days=settings.MAX_PROPERTY_AGE_YEARS * 365)
        max_date = now - timedelta(days=settings.MIN_PROPERTY_AGE_YEARS * 365)
        
        assert min_date <= seven_years_ago <= max_date
    
    def test_property_outside_age_range(self):
        """Test property age validation for out-of-range properties."""
        from trackimmo.config import settings
        
        now = datetime.now()
        
        # Property that's 3 years old (too new)
        three_years_ago = now - timedelta(days=3 * 365)
        
        # Property that's 10 years old (too old)
        ten_years_ago = now - timedelta(days=10 * 365)
        
        min_date = now - timedelta(days=settings.MAX_PROPERTY_AGE_YEARS * 365)
        max_date = now - timedelta(days=settings.MIN_PROPERTY_AGE_YEARS * 365)
        
        assert not (min_date <= three_years_ago <= max_date)
        assert not (min_date <= ten_years_ago <= max_date)

# Pytest configuration
def pytest_configure():
    """Configure pytest."""
    import sys
    import os
    
    # Add project root to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v", "--tb=short"])