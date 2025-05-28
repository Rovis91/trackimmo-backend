"""
Email sender utility for TrackImmo.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime

from trackimmo.config import settings
from trackimmo.utils.logger import get_logger
from trackimmo.utils.email_templates import (
    get_client_notification_template,
    get_error_notification_template,
    get_welcome_template
)

logger = get_logger(__name__)

async def send_client_notification(client: Dict[str, Any], new_addresses: List[Dict[str, Any]]):
    """
    Send notification email to client about new properties.
    
    Args:
        client: Client data
        new_addresses: List of newly assigned properties
    """
    recipient = client.get("email")
    if not recipient:
        logger.error(f"No email address found for client {client.get('client_id')}")
        return False
    
    try:
        # Generate HTML content
        html_content = get_client_notification_template(client, new_addresses)
        
        # Subject
        count = len(new_addresses)
        subject = f"TrackImmo: {count} nouvelle{'s' if count > 1 else ''} propriété{'s' if count > 1 else ''} pour vous !"
        
        # Send HTML email
        success = await send_email_async(
            recipient=recipient,
            subject=subject,
            html_body=html_content,
            priority="high"
        )
        
        if success:
            logger.info(f"Client notification sent successfully to {recipient} ({count} properties)")
        else:
            logger.error(f"Failed to send client notification to {recipient}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error sending client notification to {recipient}: {str(e)}")
        return False

def send_error_notification(client_id: str, error_message: Optional[str] = None):
    """
    Send error notification to CTO (synchronous for compatibility).
    
    Args:
        client_id: The client ID that caused the error
        error_message: Error message details
    """
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            send_error_notification_async(client_id, error_message)
        )
        loop.close()
        return success
    except Exception as e:
        logger.error(f"Error in sync error notification: {str(e)}")
        return False

async def send_error_notification_async(client_id: str, error_message: Optional[str] = None):
    """
    Send error notification to CTO (async version).
    
    Args:
        client_id: The client ID that caused the error
        error_message: Error message details
    """
    if not settings.CTO_EMAIL:
        logger.warning("No CTO email configured for error notifications")
        return False
    
    try:
        # Generate HTML content
        html_content = get_error_notification_template(client_id, error_message or "Unknown error")
        
        subject = f"🚨 TrackImmo Alert: Client Processing Failed ({client_id[:8]}...)"
        
        success = await send_email_async(
            recipient=settings.CTO_EMAIL,
            subject=subject,
            html_body=html_content,
            priority="urgent"
        )
        
        if success:
            logger.info(f"Error notification sent to CTO for client {client_id}")
        else:
            logger.error(f"Failed to send error notification to CTO for client {client_id}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error sending error notification: {str(e)}")
        return False

async def send_welcome_email(client: Dict[str, Any]):
    """
    Send welcome email to new client.
    
    Args:
        client: New client data
    """
    recipient = client.get("email")
    if not recipient:
        logger.error(f"No email address found for client {client.get('client_id')}")
        return False
    
    try:
        # Generate HTML content
        html_content = get_welcome_template(client)
        
        first_name = client.get('first_name', '')
        subject = f"Bienvenue chez TrackImmo{', ' + first_name if first_name else ''} ! 🏠"
        
        success = await send_email_async(
            recipient=recipient,
            subject=subject,
            html_body=html_content,
            priority="normal"
        )
        
        if success:
            logger.info(f"Welcome email sent successfully to {recipient}")
        else:
            logger.error(f"Failed to send welcome email to {recipient}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error sending welcome email to {recipient}: {str(e)}")
        return False

async def send_email_async(
    recipient: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    priority: str = "normal",
    max_retries: int = 3
) -> bool:
    """
    Send an HTML email asynchronously with retry logic.
    
    Args:
        recipient: Email recipient
        subject: Email subject
        html_body: HTML email body
        text_body: Plain text fallback (optional)
        priority: Email priority (normal, high, urgent)
        max_retries: Number of retry attempts
        
    Returns:
        True if sent successfully, False otherwise
    """
    
    # Validate configuration
    if not all([settings.EMAIL_SENDER, settings.SMTP_SERVER, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
        logger.error("Email configuration incomplete")
        return False
    
    for attempt in range(max_retries):
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = settings.EMAIL_SENDER
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Set priority headers
            if priority == "urgent":
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
                msg['Importance'] = 'high'
            elif priority == "high":
                msg['X-Priority'] = '2'
                msg['X-MSMail-Priority'] = 'High'
                msg['Importance'] = 'high'
            
            # Add text version if provided or create simple fallback
            if text_body:
                text_part = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(text_part)
            else:
                # Simple text fallback
                simple_text = f"""
TrackImmo

{subject}

Pour une meilleure expérience, veuillez consulter cet email dans un client supportant le HTML.

Cordialement,
L'équipe TrackImmo
https://trackimmo.app
                """.strip()
                text_part = MIMEText(simple_text, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # Add HTML version
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email using asyncio
            await send_smtp_async(msg)
            
            logger.info(f"Email sent successfully to {recipient} (attempt {attempt + 1})")
            return True
            
        except Exception as e:
            logger.warning(f"Email send attempt {attempt + 1} failed to {recipient}: {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"All email send attempts failed to {recipient}")
                return False
            
            # Wait before retry (exponential backoff)
            await asyncio.sleep(2 ** attempt)
    
    return False

async def send_smtp_async(msg: MIMEMultipart):
    """
    Send email via SMTP asynchronously.
    
    Args:
        msg: Email message to send
    """
    loop = asyncio.get_event_loop()
    
    def _send_smtp():
        # Use SMTP_SSL for port 465, regular SMTP with STARTTLS for other ports
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
    
    # Run SMTP operation in thread pool to avoid blocking
    await loop.run_in_executor(None, _send_smtp)

def send_email(recipient: str, subject: str, body: str, is_html: bool = False):
    """
    Legacy synchronous email function for backward compatibility.
    
    Args:
        recipient: Email recipient
        subject: Email subject
        body: Email body
        is_html: Whether the body is HTML (default: False)
    """
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if is_html:
            success = loop.run_until_complete(
                send_email_async(recipient, subject, body)
            )
        else:
            success = loop.run_until_complete(
                send_email_async(recipient, subject, "", text_body=body)
            )
        
        loop.close()
        return success
        
    except Exception as e:
        logger.error(f"Error in legacy send_email: {str(e)}")
        return False

# Test function for email configuration
async def test_email_configuration() -> Dict[str, Any]:
    """
    Test email configuration by sending a test email.
    
    Returns:
        Dict with test results
    """
    test_results = {
        "smtp_config": False,
        "connection": False,
        "send_test": False,
        "errors": []
    }
    
    try:
        # Check SMTP configuration
        required_settings = [
            'EMAIL_SENDER', 'SMTP_SERVER', 'SMTP_USERNAME', 'SMTP_PASSWORD'
        ]
        
        missing_settings = [
            setting for setting in required_settings 
            if not getattr(settings, setting, None)
        ]
        
        if missing_settings:
            test_results["errors"].append(f"Missing settings: {', '.join(missing_settings)}")
            return test_results
        
        test_results["smtp_config"] = True
        
        # Test connection
        loop = asyncio.get_event_loop()
        
        def _test_connection():
            # Use SMTP_SSL for port 465, regular SMTP with STARTTLS for other ports
            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    return True
            else:
                with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                    server.starttls()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    return True
        
        await loop.run_in_executor(None, _test_connection)
        test_results["connection"] = True
        
        # Send test email to sender (self-test)
        test_html = f"""
        <html>
        <body>
            <h2>TrackImmo Email Test</h2>
            <p>This is a test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>If you receive this, your email configuration is working correctly!</p>
        </body>
        </html>
        """
        
        success = await send_email_async(
            recipient=settings.EMAIL_SENDER,
            subject="TrackImmo Email Configuration Test",
            html_body=test_html
        )
        
        test_results["send_test"] = success
        
        if not success:
            test_results["errors"].append("Failed to send test email")
            
    except Exception as e:
        test_results["errors"].append(str(e))
        logger.error(f"Email configuration test failed: {str(e)}")
    
    return test_results