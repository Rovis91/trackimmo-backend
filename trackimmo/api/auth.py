"""
Authentication module for TrackImmo API.

This module provides JWT token-based authentication.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from trackimmo.config import settings
from trackimmo.models.db_models import Client

# Define OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Create a password hash."""
    return pwd_context.hash(password)


def create_access_token(*, data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time
        
    Returns:
        JWT token as string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def authenticate_client(db: Session, email: str, password: str) -> Optional[Client]:
    """
    Authenticate a client with email and password.
    
    Args:
        db: Database session
        email: Client email
        password: Client password
        
    Returns:
        Client if authenticated, None otherwise
    """
    # This is a placeholder - in a real implementation, you would:
    # 1. Fetch the client from the database
    # 2. Verify the password hash
    
    # client = db.query(Client).filter(Client.email == email).first()
    # if not client or not verify_password(password, client.password_hash):
    #     return None
    # return client
    
    # For development purposes only:
    if email == "dev@example.com" and password == "password123":
        # Create a dummy client 
        client = Client()
        client.client_id = "11111111-1111-1111-1111-111111111111"
        client.email = email
        client.first_name = "Dev"
        client.last_name = "User"
        client.role = "admin"
        return client
    return None


async def get_current_client(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Get the current authenticated client from a JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        Client data
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        client_id: str = payload.get("sub")
        if client_id is None:
            raise credentials_exception
        
        return {
            "client_id": client_id,
            "email": payload.get("email"),
            "role": payload.get("role"),
            "exp": payload.get("exp")
        }
    
    except JWTError:
        raise credentials_exception


async def get_current_active_client(current_client: dict = Depends(get_current_client)) -> dict:
    """
    Get the current active client.
    
    Args:
        current_client: Current client data
        
    Returns:
        Current client data if active
        
    Raises:
        HTTPException: If client is inactive
    """
    # In a real implementation, you would check if the client is active in the database
    return current_client 