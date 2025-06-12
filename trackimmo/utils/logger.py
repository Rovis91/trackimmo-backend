"""
Configuration du logger pour TrackImmo.
"""

import os
import sys
import logging
from pathlib import Path

# Créer le dossier de logs s'il n'existe pas
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def get_logger(name):
    """
    Crée et configure un logger pour le module spécifié.
    
    Args:
        name: Nom du module
        
    Returns:
        logging.Logger: Logger configuré
    """
    logger = logging.getLogger(name)
    
    # Ne pas reconfigurer si déjà fait
    if logger.handlers:
        return logger
    
    # Import settings here to avoid circular imports
    try:
        from trackimmo.config import settings
        log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.ERROR)
    except ImportError:
        # Fallback if settings not available
        log_level = logging.ERROR
        
    logger.setLevel(log_level)
    
    # Formatage
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler fichier (toujours tous les niveaux pour débugger au besoin)
    file_handler = logging.FileHandler(LOG_DIR / f"{name.split('.')[-1]}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger