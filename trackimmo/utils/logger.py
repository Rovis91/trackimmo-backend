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
        
    logger.setLevel(logging.INFO)
    
    # Formatage
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler fichier
    file_handler = logging.FileHandler(LOG_DIR / f"{name.split('.')[-1]}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger