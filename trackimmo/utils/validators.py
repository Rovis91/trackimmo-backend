"""
Validators module for TrackImmo backend.

This module provides validation utilities for data processing.
"""
import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple


def validate_postal_code(postal_code: str) -> bool:
    """
    Validate a French postal code.
    
    Args:
        postal_code: The postal code to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not postal_code:
        return False
    
    # French postal codes are 5 digits
    pattern = r"^\d{5}$"
    return bool(re.match(pattern, postal_code))


def validate_insee_code(insee_code: str) -> bool:
    """
    Validate a French INSEE code.
    
    Args:
        insee_code: The INSEE code to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not insee_code:
        return False
    
    # INSEE codes are 5 characters (digits or letters for Corsica)
    pattern = r"^[0-9A-Z]{5}$"
    return bool(re.match(pattern, insee_code))


def validate_date_format(date_str: str, format_str: str = "%d/%m/%Y") -> bool:
    """
    Validate a date string against a specified format.
    
    Args:
        date_str: The date string to validate
        format_str: The expected date format
        
    Returns:
        True if valid, False otherwise
    """
    if not date_str:
        return False
    
    try:
        datetime.strptime(date_str, format_str)
        return True
    except ValueError:
        return False


def validate_email(email: str) -> bool:
    """
    Validate an email address.
    
    Args:
        email: The email to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone_number(phone: str) -> bool:
    """
    Validate a French phone number.
    
    Args:
        phone: The phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not phone:
        return False
    
    # Remove spaces and other characters
    phone = re.sub(r'[^0-9+]', '', phone)
    
    # French phone number patterns
    patterns = [
        r"^(?:\+33|0)[1-9](?:[\s.-]?[0-9]{2}){4}$",  # Standard format
        r"^\+33[1-9][0-9]{8}$",                      # International without spaces
        r"^0[1-9][0-9]{8}$"                          # National without spaces
    ]
    
    return any(bool(re.match(pattern, phone)) for pattern in patterns)


def normalize_address(address: str) -> str:
    """
    Normalize an address for comparison.
    
    Args:
        address: The address to normalize
        
    Returns:
        Normalized address
    """
    if not address:
        return ""
    
    # Convert to uppercase
    address = address.upper()
    
    # Remove accents (would need unidecode in a real implementation)
    # address = unidecode.unidecode(address)
    
    # Remove punctuation and special characters
    address = re.sub(r'[^\w\s]', '', address)
    
    # Remove common words
    common_words = ['RUE', 'AVENUE', 'AV', 'BOULEVARD', 'BD', 'PLACE', 'PL', 'ALLEE', 'IMPASSE', 'IMP']
    words = address.split()
    words = [word for word in words if word not in common_words]
    
    # Rebuild address
    return ' '.join(words)


def validate_client(client_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate client data.
    
    Args:
        client_data: The client data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['first_name', 'last_name', 'email']
    
    # Check required fields
    for field in required_fields:
        if field not in client_data or not client_data[field]:
            return False, f"Missing required field: {field}"
    
    # Validate email
    if not validate_email(client_data['email']):
        return False, "Invalid email format"
    
    # Validate phone number if provided
    if 'telephone' in client_data and client_data['telephone']:
        if not validate_phone_number(client_data['telephone']):
            return False, "Invalid phone number format"
    
    # Validate subscription type if provided
    if 'subscription_type' in client_data and client_data['subscription_type']:
        valid_subscription_types = ['decouverte', 'pro', 'entreprise']
        if client_data['subscription_type'] not in valid_subscription_types:
            return False, f"Invalid subscription type, expected one of: {', '.join(valid_subscription_types)}"
    
    # Validate status if provided
    if 'status' in client_data and client_data['status']:
        valid_statuses = ['active', 'inactive', 'suspended', 'pending']
        if client_data['status'] not in valid_statuses:
            return False, f"Invalid status, expected one of: {', '.join(valid_statuses)}"
    
    # Validate send_day if provided
    if 'send_day' in client_data and client_data['send_day'] is not None:
        try:
            send_day = int(client_data['send_day'])
            if send_day < 1 or send_day > 31:
                return False, "Send day must be between 1 and 31"
        except (ValueError, TypeError):
            return False, "Send day must be a number"
    
    # Validate addresses_per_report if provided
    if 'addresses_per_report' in client_data and client_data['addresses_per_report'] is not None:
        try:
            addresses_per_report = int(client_data['addresses_per_report'])
            if addresses_per_report < 0:
                return False, "Addresses per report cannot be negative"
        except (ValueError, TypeError):
            return False, "Addresses per report must be a number"
    
    return True, None


def validate_property(property_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate property data.
    
    Args:
        property_data: The property data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['address_raw', 'city_name', 'postal_code', 'property_type', 'sale_date', 'price']
    
    # Check required fields
    for field in required_fields:
        if field not in property_data or not property_data[field]:
            return False, f"Missing required field: {field}"
    
    # Validate postal code
    if not validate_postal_code(property_data['postal_code']):
        return False, "Invalid postal code format"
    
    # Validate sale date
    if not validate_date_format(property_data['sale_date']):
        return False, "Invalid sale date format, expected DD/MM/YYYY"
    
    # Validate property type
    valid_property_types = ['house', 'apartment', 'land', 'commercial', 'other']
    if property_data['property_type'] not in valid_property_types:
        return False, f"Invalid property type, expected one of: {', '.join(valid_property_types)}"
    
    # Validate numeric values
    numeric_fields = ['price', 'surface', 'rooms']
    for field in numeric_fields:
        if field in property_data and property_data[field] is not None:
            try:
                float_value = float(property_data[field])
                if float_value < 0:
                    return False, f"Field {field} cannot be negative"
            except (ValueError, TypeError):
                return False, f"Field {field} must be a number"
    
    return True, None 