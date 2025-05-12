"""
Database manager module for TrackImmo backend using Supabase.

This module provides database connection and CRUD operations through Supabase.
"""
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Generic
from uuid import UUID
import os
import dotenv
from supabase import create_client, Client as SupabaseClient

from trackimmo.models.db_models import Base, Client, City, Address, ClientAddress, DPE
from trackimmo.utils.logger import get_logger

# Load environment variables
dotenv.load_dotenv()

logger = get_logger(__name__)

# Type variable for model types
ModelType = TypeVar("ModelType", bound=Base)


class DBManager:
    """Database manager class for Supabase operations."""
    
    def __init__(self):
        """Initialize the database manager."""
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        self.client = None
        
        if not self.supabase_url or not self.supabase_key:
            logger.error("Missing Supabase credentials in environment variables")
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
    
    def __enter__(self) -> "DBManager":
        """Enter the context manager."""
        self.client = create_client(self.supabase_url, self.supabase_key)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        if exc_type:
            logger.error(f"Error in Supabase transaction: {exc_val}")
        # Supabase client doesn't need explicit closing
        self.client = None
    
    def get_client(self) -> SupabaseClient:
        """Get the Supabase client."""
        if not self.client:
            self.client = create_client(self.supabase_url, self.supabase_key)
        return self.client


class CRUDBase(Generic[ModelType]):
    """Base class for CRUD operations with Supabase."""
    
    def __init__(self, table_name: str):
        """
        Initialize with the table name.
        
        Args:
            table_name: The name of the table in Supabase
        """
        self.table_name = table_name
    
    def get(self, db: DBManager, id_name: str, id_value: Union[UUID, str]) -> Optional[Dict]:
        """
        Get a record by ID.
        
        Args:
            db: Database manager
            id_name: Name of the ID field
            id_value: ID value to search for
            
        Returns:
            Record if found, None otherwise
        """
        response = db.get_client().table(self.table_name).select("*").eq(id_name, str(id_value)).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    
    def get_multi(
        self, db: DBManager, *, skip: int = 0, limit: int = 100
    ) -> List[Dict]:
        """
        Get multiple records.
        
        Args:
            db: Database manager
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of records
        """
        response = db.get_client().table(self.table_name).select("*").range(skip, skip + limit - 1).execute()
        return response.data
    
    def create(self, db: DBManager, *, obj_in: Dict[str, Any]) -> Dict:
        """
        Create a new record.
        
        Args:
            db: Database manager
            obj_in: Data to create the record
            
        Returns:
            Created record
        """
        response = db.get_client().table(self.table_name).insert(obj_in).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return {}
    
    def update(
        self, db: DBManager, *, id_name: str, id_value: Union[UUID, str], obj_in: Dict[str, Any]
    ) -> Dict:
        """
        Update a record.
        
        Args:
            db: Database manager
            id_name: Name of the ID field
            id_value: ID value to update
            obj_in: Data to update the record
            
        Returns:
            Updated record
        """
        response = db.get_client().table(self.table_name).update(obj_in).eq(id_name, str(id_value)).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return {}
    
    def remove(self, db: DBManager, *, id_name: str, id_value: Union[UUID, str]) -> Dict:
        """
        Remove a record.
        
        Args:
            db: Database manager
            id_name: Name of the ID field
            id_value: ID value to remove
            
        Returns:
            Removed record
        """
        response = db.get_client().table(self.table_name).delete().eq(id_name, str(id_value)).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return {}


class CRUDClient(CRUDBase):
    """CRUD operations for clients."""
    
    def __init__(self):
        super().__init__("clients")
    
    def get_by_email(self, db: DBManager, *, email: str) -> Optional[Dict]:
        """Get a client by email."""
        response = db.get_client().table(self.table_name).select("*").eq("email", email).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    
    def get_with_cities(self, db: DBManager, *, client_id: Union[UUID, str]) -> Optional[Dict]:
        """Get a client with chosen cities."""
        client = self.get(db, "client_id", client_id)
        
        if client and client.get("chosen_cities"):
            cities_response = db.get_client().table("cities").select("*").in_("city_id", client["chosen_cities"]).execute()
            if cities_response.data:
                client["cities"] = cities_response.data
        
        return client


class CRUDCity(CRUDBase):
    """CRUD operations for cities."""
    
    def __init__(self):
        super().__init__("cities")
    
    def get_by_postal_code(self, db: DBManager, *, postal_code: str) -> List[Dict]:
        """Get cities by postal code."""
        response = db.get_client().table(self.table_name).select("*").eq("postal_code", postal_code).execute()
        return response.data
    
    def get_by_name(self, db: DBManager, *, name: str) -> List[Dict]:
        """Get cities by name."""
        response = db.get_client().table(self.table_name).select("*").ilike("name", f"%{name}%").execute()
        return response.data
    
    def get_by_names(self, db: DBManager, *, names: List[str]) -> List[Dict]:
        """Get cities by a list of names (case insensitive)."""
        # Convert names to uppercase for comparison
        upper_names = [name.upper() for name in names]
        
        # Supabase doesn't have direct equivalent to SQL's IN for arrays of text with case-insensitivity
        # So we'll fetch all and filter in Python
        response = db.get_client().table(self.table_name).select("*").execute()
        
        if response.data:
            return [city for city in response.data if city.get("name", "").upper() in upper_names]
        return []


class CRUDAddress(CRUDBase):
    """CRUD operations for addresses."""
    
    def __init__(self):
        super().__init__("addresses")
    
    def get_by_city(self, db: DBManager, *, city_id: Union[UUID, str]) -> List[Dict]:
        """Get addresses by city."""
        response = db.get_client().table(self.table_name).select("*").eq("city_id", str(city_id)).execute()
        return response.data
    
    def get_with_dpe(self, db: DBManager, *, address_id: Union[UUID, str]) -> Optional[Dict]:
        """Get an address with its DPE."""
        address = self.get(db, "address_id", address_id)
        
        if address:
            dpe_response = db.get_client().table("dpe").select("*").eq("address_id", str(address_id)).execute()
            if dpe_response.data and len(dpe_response.data) > 0:
                address["dpe"] = dpe_response.data[0]
        
        return address


class CRUDClientAddress(CRUDBase):
    """CRUD operations for client-address associations."""
    
    def __init__(self):
        super().__init__("client_addresses")
    
    def get_by_client(
        self, db: DBManager, *, client_id: Union[UUID, str], status: Optional[str] = None
    ) -> List[Dict]:
        """Get client-address associations by client."""
        query = db.get_client().table(self.table_name).select("*").eq("client_id", str(client_id))
        
        if status:
            query = query.eq("status", status)
            
        response = query.execute()
        return response.data
    
    def get_by_address(
        self, db: DBManager, *, address_id: Union[UUID, str]
    ) -> List[Dict]:
        """Get client-address associations by address."""
        response = db.get_client().table(self.table_name).select("*").eq("address_id", str(address_id)).execute()
        return response.data


# Create instances for each CRUD class
client = CRUDClient()
city = CRUDCity()
address = CRUDAddress()
client_address = CRUDClientAddress() 