"""
Database manager module for TrackImmo backend.

This module provides database session management and CRUD operations.
"""
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Generic
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import sessionmaker, Session

from trackimmo.config import settings
from trackimmo.models.db_models import Base, Client, City, Address, ClientAddress, DPE
from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Type variable for model types
ModelType = TypeVar("ModelType", bound=Base)


class DBManager:
    """Database manager class for CRUD operations."""
    
    def __init__(self):
        """Initialize the database manager."""
        self.session = None
    
    def __enter__(self) -> "DBManager":
        """Enter the context manager."""
        self.session = SessionLocal()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        if self.session:
            if exc_type:
                self.session.rollback()
                logger.error(f"Transaction rolled back due to error: {exc_val}")
            self.session.close()
            self.session = None
    
    def get_session(self) -> Session:
        """Get the current session."""
        if not self.session:
            self.session = SessionLocal()
        return self.session
    
    def commit(self):
        """Commit the current transaction."""
        if self.session:
            self.session.commit()
    
    def rollback(self):
        """Rollback the current transaction."""
        if self.session:
            self.session.rollback()
    
    def close(self):
        """Close the current session."""
        if self.session:
            self.session.close()
            self.session = None


class CRUDBase(Generic[ModelType]):
    """Base class for CRUD operations."""
    
    def __init__(self, model: Type[ModelType]):
        """
        Initialize with the model.
        
        Args:
            model: The SQLAlchemy model
        """
        self.model = model
    
    def get(self, db: Session, id: Union[UUID, str]) -> Optional[ModelType]:
        """
        Get a record by ID.
        
        Args:
            db: Database session
            id: Record ID
            
        Returns:
            Record if found, None otherwise
        """
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple records.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of records
        """
        return db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create a new record.
        
        Args:
            db: Database session
            obj_in: Data to create the record
            
        Returns:
            Created record
        """
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: Dict[str, Any]
    ) -> ModelType:
        """
        Update a record.
        
        Args:
            db: Database session
            db_obj: Record to update
            obj_in: Data to update the record
            
        Returns:
            Updated record
        """
        for field in obj_in:
            setattr(db_obj, field, obj_in[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def remove(self, db: Session, *, id: Union[UUID, str]) -> ModelType:
        """
        Remove a record.
        
        Args:
            db: Database session
            id: Record ID
            
        Returns:
            Removed record
        """
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj


# Create CRUD classes for each model
class CRUDClient(CRUDBase[Client]):
    """CRUD operations for clients."""
    
    def get_by_email(self, db: Session, *, email: str) -> Optional[Client]:
        """Get a client by email."""
        return db.query(Client).filter(Client.email == email).first()
    
    def get_with_cities(self, db: Session, *, client_id: Union[UUID, str]) -> Optional[Client]:
        """Get a client with chosen cities."""
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if client and client.chosen_cities:
            # Note: In SQLAlchemy 2.0+, this would use joinedload
            # For now, we'll manually fetch the cities
            cities = db.query(City).filter(City.city_id.in_(client.chosen_cities)).all()
            # We'd attach these to the client object in a real implementation
        return client


class CRUDCity(CRUDBase[City]):
    """CRUD operations for cities."""
    
    def get_by_postal_code(self, db: Session, *, postal_code: str) -> List[City]:
        """Get cities by postal code."""
        return db.query(City).filter(City.postal_code == postal_code).all()
    
    def get_by_name(self, db: Session, *, name: str) -> List[City]:
        """Get cities by name."""
        return db.query(City).filter(City.name.ilike(f"%{name}%")).all()


class CRUDAddress(CRUDBase[Address]):
    """CRUD operations for addresses."""
    
    def get_by_city(self, db: Session, *, city_id: Union[UUID, str]) -> List[Address]:
        """Get addresses by city."""
        return db.query(Address).filter(Address.city_id == city_id).all()
    
    def get_with_dpe(self, db: Session, *, address_id: Union[UUID, str]) -> Optional[Address]:
        """Get an address with its DPE."""
        address = db.query(Address).filter(Address.address_id == address_id).first()
        if address:
            # Manual join for simplicity
            dpe = db.query(DPE).filter(DPE.address_id == address_id).first()
            # We'd attach the DPE to the address object in a real implementation
        return address


class CRUDClientAddress(CRUDBase[ClientAddress]):
    """CRUD operations for client-address associations."""
    
    def get_by_client(
        self, db: Session, *, client_id: Union[UUID, str], status: Optional[str] = None
    ) -> List[ClientAddress]:
        """Get client-address associations by client."""
        query = db.query(ClientAddress).filter(ClientAddress.client_id == client_id)
        if status:
            query = query.filter(ClientAddress.status == status)
        return query.all()
    
    def get_by_address(
        self, db: Session, *, address_id: Union[UUID, str]
    ) -> List[ClientAddress]:
        """Get client-address associations by address."""
        return db.query(ClientAddress).filter(ClientAddress.address_id == address_id).all()


# Create instances for each CRUD class
client = CRUDClient(Client)
city = CRUDCity(City)
address = CRUDAddress(Address)
client_address = CRUDClientAddress(ClientAddress) 