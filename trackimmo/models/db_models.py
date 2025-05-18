"""
Database models module for TrackImmo backend.

This module defines SQLAlchemy models matching the database schema.
"""
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, Table, DateTime, Date, Text, ARRAY, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableList
from enum import Enum as PyEnum
import datetime

Base = declarative_base()


class PropertyTypeEnum(PyEnum):
    """Enum for property types in database."""
    HOUSE = "house"
    APARTMENT = "apartment"
    LAND = "land"
    COMMERCIAL = "commercial"
    OTHER = "other"


class SubscriptionTypeEnum(PyEnum):
    """Enum for subscription types in database."""
    DECOUVERTE = "decouverte"
    PRO = "pro"
    ENTREPRISE = "entreprise"


class UserRoleEnum(PyEnum):
    """Enum for user roles in database."""
    ADMIN = "admin"
    USER = "user"


class AddressStatusEnum(PyEnum):
    """Enum for address status in client relationship."""
    NEW = "new"
    CONTACTED = "contacted"
    MEETING = "meeting"
    NEGOTIATION = "negotiation"
    SOLD = "sold"
    MANDATE = "mandate"


class DPEClassEnum(PyEnum):
    """Enum for DPE energy and GES classes."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    N = "N"


class ClientStatusEnum(PyEnum):
    """Enum for client status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TEST = "test"
    PENDING = "pending"


class SaleHorizonEnum(PyEnum):
    """Enum for sale horizon options."""
    THREE_MONTHS = "3 mois"
    SIX_MONTHS = "6 mois"
    NINE_MONTHS = "9 mois"
    ONE_YEAR = "1 an"


class FollowUpEnum(PyEnum):
    """Enum for follow-up options."""
    ONE_MONTH = "1m"
    THREE_MONTHS = "3m"
    SIX_MONTHS = "6m"
    ONE_YEAR = "1y"


class HeatingTypeEnum(PyEnum):
    """Enum for heating type options."""
    ELECTRIC = "electric"
    GAS = "gas"
    OIL = "oil"
    WOOD = "wood"
    DISTRICT = "district"


class City(Base):
    """City model."""
    __tablename__ = "cities"
    
    city_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    insee_code = Column(String, nullable=False, unique=True)
    region = Column(String)
    department = Column(String, nullable=False)
    last_scraped = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<City {self.name} ({self.postal_code})>"


class Client(Base):
    """Client model."""
    __tablename__ = "clients"
    
    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    telephone = Column(String)
    company_name = Column(String)
    subscription_type = Column(Enum(SubscriptionTypeEnum))
    status = Column(Enum(ClientStatusEnum), nullable=False)
    subscription_start_date = Column(Date)
    send_day = Column(Integer)
    addresses_per_report = Column(Integer, default=0)
    template_name = Column(String)
    info = Column(Text)
    chosen_cities = Column(MutableList.as_mutable(ARRAY(UUID(as_uuid=True))), default=[])
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    stripe_customer_id = Column(String)
    stripe_subscription_id = Column(String)
    stripe_subscription_status = Column(String)
    stripe_subscription_end_date = Column(DateTime)
    property_type_preferences = Column(MutableList.as_mutable(ARRAY(String)), default=[])
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.ADMIN)
    additional_users = Column(MutableList.as_mutable(ARRAY(UUID(as_uuid=True))), default=[])
    company_address = Column(String)
    first_report_date = Column(Date)
    
    def __repr__(self):
        return f"<Client {self.first_name} {self.last_name}>"


class SecondaryUser(Base):
    """Secondary user model for enterprise accounts."""
    __tablename__ = "secondary_users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id"), nullable=False)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.USER)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SecondaryUser {self.first_name} {self.last_name}>"


class Address(Base):
    """Address model."""
    __tablename__ = "addresses"
    
    address_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department = Column(String, nullable=False)
    city_id = Column(UUID(as_uuid=True), ForeignKey("cities.city_id"), nullable=False)
    address_raw = Column(String, nullable=False)
    sale_date = Column(Date, nullable=False)
    property_type = Column(Enum(PropertyTypeEnum), nullable=False)
    surface = Column(Integer)
    rooms = Column(Integer)
    price = Column(Integer)
    immodata_url = Column(Text)
    dpe_number = Column(String)
    estimated_price = Column(Integer)
    # In production, these would be geometry columns from PostGIS
    # For simplicity, we'll use JSONB here
    geoposition = Column(JSONB)  # {type: "Point", coordinates: [lon, lat]}
    boundary = Column(JSONB)     # GeoJSON polygon
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Address {self.address_raw}>"


class ClientAddress(Base):
    """Junction table between clients and addresses."""
    __tablename__ = "client_addresses"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id"), primary_key=True)
    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.address_id"), primary_key=True)
    client_address_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True)
    send_date = Column(DateTime, default=func.now())
    validation = Column(Boolean, default=False)
    status = Column(Enum(AddressStatusEnum), default=AddressStatusEnum.NEW)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    owner_name = Column(String(255))
    owner_phone = Column(String(20))
    owner_email = Column(String(255))
    is_owner_occupant = Column(Boolean)
    contact_date = Column(Date)
    potential_interest_in_selling = Column(Boolean)
    sale_horizon = Column(Enum(SaleHorizonEnum))
    desired_price = Column(Float)
    travaux_effectue = Column(Boolean)
    travaux_necessaire = Column(Boolean)
    required_renovations = Column(Text)
    estimation_travaux = Column(Float)
    dpe_energy_class = Column(Enum(DPEClassEnum))
    dpe_ges_class = Column(Enum(DPEClassEnum))
    is_archived = Column(Boolean, default=False)
    is_rented = Column(Boolean)
    accord_estimation = Column(Boolean)
    follow_up = Column(Enum(FollowUpEnum))
    rental_yield = Column(Float)
    heating_type = Column(Enum(HeatingTypeEnum))
    floor = Column(Integer)
    has_elevator = Column(Boolean)
    has_parking = Column(Boolean)
    construction_year = Column(Integer)
    last_renovation_year = Column(Integer)
    contact_established = Column(Boolean)
    
    def __repr__(self):
        return f"<ClientAddress {self.client_id} - {self.address_id}>"


class DPE(Base):
    """DPE (Diagnostic de Performance Énergétique) model."""
    __tablename__ = "dpe"
    
    dpe_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=False)
    department = Column(String, nullable=False)
    construction_year = Column(Integer)
    dpe_date = Column(Date, nullable=False)
    dpe_energy_class = Column(Enum(DPEClassEnum), nullable=False)
    dpe_ges_class = Column(Enum(DPEClassEnum), nullable=False)
    dpe_number = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<DPE {self.dpe_number}>"


class ProcessingJob(Base):
    """Processing job model for tracking batch operations."""
    __tablename__ = "processing_jobs"
    
    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id"))
    status = Column(String, nullable=False)  # queued, running, completed, failed
    job_type = Column(String, nullable=False)  # city_processing, enrichment, etc.
    parameters = Column(JSONB)  # Job parameters
    progress = Column(Integer, default=0)
    result = Column(JSONB)  # Job results
    error_message = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ProcessingJob {self.job_id} ({self.status})>" 