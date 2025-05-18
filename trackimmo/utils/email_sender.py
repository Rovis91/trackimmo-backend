"""
Email sender utility for TrackImmo.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional

from trackimmo.config import settings
from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

def send_client_notification(client: Dict[str, Any], new_addresses: List[Dict[str, Any]]):
    """
    Send notification email to client.
    
    Args:
        client: Client data
        new_addresses: List of newly assigned properties
    """
    recipient = client.get("email")
    if not recipient:
        logger.error(f"No email address found for client {client.get('client_id')}")
        return
    
    subject = f"TrackImmo: {len(new_addresses)} New Properties Available"
    
    # Create a simple text email
    body = f"""
Hello {client.get('first_name', 'there')},

We've found {len(new_addresses)} new properties matching your criteria.

You can now log in to your TrackImmo dashboard to view them:
- {len(new_addresses)} new properties in your selected cities
- Property types: {', '.join(client.get('property_type_preferences', []))}

Best regards,
The TrackImmo Team
    """
    
    send_email(recipient, subject, body)

def send_error_notification(client_id: str, error_message: Optional[str] = None):
    """
    Send error notification to CTO.
    
    Args:
        client_id: The client ID that caused the error
        error_message: Error message details
    """
    subject = f"TrackImmo ERROR: Processing failed for client {client_id}"
    
    body = f"""
ALERT: Client Processing Failed

Client ID: {client_id}

This client has failed processing 3 times and requires manual intervention.

Error details:
{error_message or "No specific error message provided"}

Please check the processing_jobs table for more information.
    """
    
    send_email(settings.CTO_EMAIL, subject, body)

def send_email(recipient: str, subject: str, body: str, is_html: bool = False):
    """
    Send an email using SMTP.
    
    Args:
        recipient: Email recipient
        subject: Email subject
        body: Email body
        is_html: Whether the body is HTML (default: False)
    """
    msg = MIMEMultipart()
    msg['From'] = settings.EMAIL_SENDER
    msg['To'] = recipient
    msg['Subject'] = subject
    
    # Attach body with appropriate content type
    content_type = 'html' if is_html else 'plain'
    msg.attach(MIMEText(body, content_type))
    
    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"Email sent to {recipient}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {recipient}: {str(e)}")