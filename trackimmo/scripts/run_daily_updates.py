#!/usr/bin/env python3
"""
Daily client update script for TrackImmo.
"""
import os
import sys
import logging
import time
import calendar
from datetime import datetime
import requests

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trackimmo.config import settings
from trackimmo.utils.logger import get_logger
from trackimmo.modules.db_manager import DBManager

logger = get_logger("daily_updates")

def is_last_day_of_month():
    """Check if today is the last day of the month."""
    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return today.day == days_in_month

def get_clients_for_update(day):
    """
    Get clients scheduled for update on a specific day.
    
    Args:
        day: Day of the month
        
    Returns:
        List of client data
    """
    with DBManager() as db:
        response = db.get_client().table("clients").select("*") \
            .eq("status", "active") \
            .eq("send_day", day) \
            .execute()
        return response.data

def main():
    """Run daily client updates."""
    logger.info("Starting daily client updates")
    
    # Get current day of month
    today = datetime.now().day
    
    # Get clients matching today's day
    clients = get_clients_for_update(today)
    logger.info(f"Found {len(clients)} clients scheduled for today (day {today})")
    
    # Handle month-end edge case
    if is_last_day_of_month():
        logger.info("Today is the last day of the month, checking for additional clients")
        for day in range(today + 1, 32):  # Check days 29, 30, 31 if today is 28
            additional_clients = get_clients_for_update(day)
            clients.extend(additional_clients)
            logger.info(f"Added {len(additional_clients)} clients with send_day={day}")
    
    # Process each client
    for client in clients:
        try:
            logger.info(f"Processing client {client['client_id']}")
            response = requests.post(
                f"{settings.API_BASE_URL}/api/process-client",
                json={"client_id": client["client_id"]},
                headers={"X-API-Key": settings.API_KEY}
            )
            response.raise_for_status()
            logger.info(f"Successfully processed client {client['client_id']}")
            
            # Add a small delay between clients to avoid overloading the server
            time.sleep(5)
        except Exception as e:
            logger.error(f"Failed to process client {client['client_id']}: {str(e)}")
    
    # Process retry queue
    logger.info("Processing retry queue")
    try:
        response = requests.post(
            f"{settings.API_BASE_URL}/api/process-retry-queue",
            headers={"X-API-Key": settings.API_KEY}
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"Retry queue processing: {result.get('processed', 0)} processed, {result.get('failed', 0)} failed")
    except Exception as e:
        logger.error(f"Failed to process retry queue: {str(e)}")
    
    logger.info("Daily client updates completed")

if __name__ == "__main__":
    # Check if it's midnight (for auto-reset)
    current_hour = datetime.now().hour
    if current_hour == 0:
        logger.info("Midnight reset detected")
        # Simple implementation - just log the reset
        # In production, you would add code to restart your service
        # For example: os.system("systemctl restart trackimmo")
    
    # Run the main function
    main()