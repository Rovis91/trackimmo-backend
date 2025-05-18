"""
Test email notification functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
import smtplib

from trackimmo.utils.email_sender import send_email
from trackimmo.config import settings

# Test client ID
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"

def test_send_email_success():
    """Test successfully sending an email."""
    # Mock the SMTP class to avoid actual email sending
    with patch('trackimmo.utils.email_sender.smtplib.SMTP') as mock_smtp:
        # Setup the mock instance for the context manager
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        # Call the function
        recipient = "test@example.com"
        subject = "Test Subject"
        body = "Test Body"
        send_email(recipient, subject, body)
        
        # Verify that SMTP was used correctly
        mock_smtp.assert_called_once()
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once()
        mock_smtp_instance.send_message.assert_called_once()
        
        # Verify the logger was called
        with patch('trackimmo.utils.email_sender.logger.info') as mock_info:
            send_email(recipient, subject, body)
            mock_info.assert_called_once()

def test_send_email_smtp_error():
    """Test handling of SMTP errors."""
    # Mock the SMTP class to raise an exception
    with patch('trackimmo.utils.email_sender.smtplib.SMTP') as mock_smtp:
        # Make the context manager raise an exception
        mock_smtp.return_value.__enter__.side_effect = smtplib.SMTPException("Connection refused")
        
        # Mock the logger to capture errors
        with patch('trackimmo.utils.email_sender.logger.error') as mock_error:
            # Call the function (should not raise exception)
            recipient = "test@example.com"
            subject = "Test Subject"
            body = "Test Body"
            send_email(recipient, subject, body)
            
            # Verify that an error was logged
            mock_error.assert_called_once()
            assert "failed" in mock_error.call_args[0][0].lower()

def test_send_email_html_content():
    """Test sending an email with HTML content."""
    # Mock the SMTP class
    with patch('trackimmo.utils.email_sender.smtplib.SMTP') as mock_smtp:
        # Setup the mock instance for the context manager
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        # Call the function with HTML content
        recipient = "test@example.com"
        subject = "HTML Test"
        body = "<h1>Test HTML</h1><p>This is a test</p>"
        send_email(recipient, subject, body, is_html=True)
        
        # Verify that SMTP was used correctly
        mock_smtp.assert_called_once()
        mock_smtp_instance.send_message.assert_called_once()
        
        # The content type would be set to html, but we can't easily verify this
        # without inspecting the MIMEText object

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 