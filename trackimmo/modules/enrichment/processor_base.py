import logging
import os
import pandas as pd
from typing import Optional

class ProcessorBase:
    """Classe de base pour tous les processeurs d'enrichissement."""
    
    def __init__(self, input_path: str = None, output_path: str = None):
        """
        Initialise le processeur avec les chemins d'entrée/sortie.
        Args:
            input_path: Chemin du fichier d'entrée (CSV)
            output_path: Chemin du fichier de sortie (CSV)
        """
        self.input_path = input_path
        self.output_path = output_path
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process(self, **kwargs) -> bool:
        """
        Traite les données d'entrée et produit les données de sortie.
        À implémenter dans les classes dérivées.
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        raise NotImplementedError("La méthode process() doit être implémentée")
    
    def load_csv(self, file_path: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Charge un fichier CSV en DataFrame.
        Args:
            file_path: Chemin du fichier à charger (utilise self.input_path si None)
        Returns:
            Optional[pd.DataFrame]: DataFrame chargé ou None en cas d'erreur
        """
        path = file_path or self.input_path
        if not path:
            self.logger.error("Aucun chemin de fichier spécifié")
            return None
        try:
            df = pd.read_csv(path)
            self.logger.info(f"Chargé {len(df)} lignes depuis {path}")
            return df
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de {path}: {str(e)}")
            return None
    
    def save_csv(self, df: pd.DataFrame, file_path: Optional[str] = None) -> bool:
        """
        Sauvegarde un DataFrame en CSV.
        Args:
            df: DataFrame à sauvegarder
            file_path: Chemin de sauvegarde (utilise self.output_path si None)
        Returns:
            bool: True si la sauvegarde a réussi, False sinon
        """
        path = file_path or self.output_path
        if not path:
            self.logger.error("Aucun chemin de sortie spécifié")
            return False
        try:
            # Only create directory if path contains a directory component
            dir_path = os.path.dirname(path)
            if dir_path:  # Only if directory path is not empty
                os.makedirs(dir_path, exist_ok=True)
            df.to_csv(path, index=False)
            self.logger.info(f"Sauvegardé {len(df)} lignes dans {path}")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde dans {path}: {str(e)}")
            return False 