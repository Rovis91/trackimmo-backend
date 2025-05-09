"""
Data models module for TrackImmo backend.

This module defines Pydantic models for data validation and exchange.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from pydantic import BaseModel, Field, validator
from enum import Enum


class PropertyType(str, Enum):
    """Enum for property types."""
    HOUSE = "house"
    APARTMENT = "apartment"
    LAND = "land"
    COMMERCIAL = "commercial"
    OTHER = "other"


class DPEClass(str, Enum):
    """Enum for DPE energy and GES classes."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    N = "N"  # Not defined


class AddressStatus(str, Enum):
    """Enum for property status in client-address relationship."""
    NEW = "new"
    CONTACTED = "contacted"
    MEETING = "meeting"
    NEGOTIATION = "negotiation"
    SOLD = "sold"
    MANDATE = "mandate"


class ScrapedProperty(BaseModel):
    """
    Represents a property as scraped from ImmoData.
    Raw data without enrichment.
    """
    url: str
    address_raw: str
    city_name: str
    postal_code: str
    property_type: PropertyType
    surface: Optional[float] = None
    rooms: Optional[int] = None
    price: int
    sale_date: str  # Format: DD/MM/YYYY
    department: Optional[str] = None
    immodata_url: Optional[str] = None
    
    @validator('postal_code')
    def validate_postal_code(cls, v):
        """Validate postal code format."""
        if not v or not isinstance(v, str) or not v.isdigit() or len(v) != 5:
            raise ValueError('Postal code must be a 5-digit string')
        return v
    
    @validator('sale_date')
    def validate_sale_date(cls, v):
        """Validate sale date format."""
        try:
            datetime.strptime(v, "%d/%m/%Y")
            return v
        except ValueError:
            raise ValueError('Sale date must be in format DD/MM/YYYY')
    
    @validator('department', always=True)
    def set_department_from_postal_code(cls, v, values):
        """Set department from postal code if not provided."""
        if not v and 'postal_code' in values:
            return values['postal_code'][:2]
        return v


class GeoCoordinates(BaseModel):
    """Geographical coordinates."""
    latitude: float
    longitude: float


class ProcessedProperty(BaseModel):
    """
    Represents a property after enrichment with additional data.
    Used for database insertion and API responses.
    """
    # Base data from scraping
    address_raw: str
    city_name: str
    postal_code: str
    property_type: PropertyType
    surface: Optional[float] = None
    rooms: Optional[int] = None
    price: int
    sale_date: str  # Format: DD/MM/YYYY
    department: str
    immodata_url: Optional[str] = None
    
    # Enriched data
    city_id: Optional[str] = None
    insee_code: Optional[str] = None
    region: Optional[str] = None
    coordinates: Optional[GeoCoordinates] = None
    dpe_number: Optional[str] = None
    dpe_date: Optional[str] = None
    dpe_energy_class: Optional[DPEClass] = None
    dpe_ges_class: Optional[DPEClass] = None
    construction_year: Optional[int] = None
    estimated_price: Optional[int] = None
    price_per_m2: Optional[float] = None
    
    # Calculated fields
    confidence_score: Optional[int] = Field(None, ge=0, le=100)  # 0-100
    
    class Config:
        """Config for the ProcessedProperty model."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }


class PropertyMatch(BaseModel):
    """
    Represents a property match for a client.
    Used for client-address association.
    """
    client_id: str
    address_id: str
    status: AddressStatus = AddressStatus.NEW
    send_date: Optional[datetime] = None
    notes: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    

class PropertyFilter(BaseModel):
    """Model for property filtering in requests."""
    city_name: Optional[str] = None
    postal_code: Optional[str] = None
    property_types: Optional[List[PropertyType]] = None
    start_date: Optional[str] = None  # Format: MM/YYYY
    end_date: Optional[str] = None  # Format: MM/YYYY
    
    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate date format."""
        if not v:
            return v
        try:
            datetime.strptime(v, "%m/%Y")
            return v
        except ValueError:
            raise ValueError('Date must be in format MM/YYYY')


class BatchProcessingJob(BaseModel):
    """Model for batch processing job status."""
    job_id: str
    status: str  # queued, running, completed, failed
    progress: Optional[int] = 0
    created_at: datetime
    updated_at: datetime
    current_stage: Optional[str] = None
    stages_completed: List[str] = []
    stages_pending: List[str] = []
    errors: List[str] = []
    estimated_time: Optional[int] = None  # in seconds 