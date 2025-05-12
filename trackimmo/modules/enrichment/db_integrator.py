import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import logging
import uuid
import os
import dotenv
import json
from pathlib import Path

from .processor_base import ProcessorBase
from trackimmo.modules.db_manager import DBManager

# Load environment variables
dotenv.load_dotenv()

class DBIntegrationService(ProcessorBase):
    """Processeur pour intégrer les propriétés enrichies dans la base de données."""
    
    def __init__(self, input_path: str = None, output_path: str = None,
                 db_url: str = None):
        super().__init__(input_path, output_path)
        self.db_url = db_url  # Conservé pour compatibilité mais non utilisé
        self.db_manager = None
    
    def process(self, **kwargs) -> bool:
        """
        Intègre les propriétés enrichies dans la base de données.
        
        Args:
            **kwargs: Arguments additionnels
                - batch_size: Taille des lots pour l'insertion (défaut: 100)
                
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        # Récupérer les paramètres
        batch_size = kwargs.get('batch_size', 100)
        
        # Charger les données
        df = self.load_csv()
        if df is None:
            return False
        
        # Initialiser le gestionnaire de base de données
        try:
            self.db_manager = DBManager()
            self.logger.info("Connexion à la base de données établie")
        except Exception as e:
            self.logger.error(f"Erreur de connexion à la base de données: {str(e)}")
            return False
        
        # Statistiques initiales
        initial_count = len(df)
        self.logger.info(f"Début de l'intégration de {initial_count} propriétés")
        
        try:
            # Créer un DataFrame pour le rapport d'intégration
            report_df = pd.DataFrame(columns=['address_id', 'address_raw', 'city_id', 'success', 'error'])
            
            # Traiter par lots
            batches = [df[i:i+batch_size] for i in range(0, len(df), batch_size)]
            
            for i, batch_df in enumerate(batches):
                self.logger.info(f"Traitement du lot {i+1}/{len(batches)} ({len(batch_df)} propriétés)")
                
                # Insérer les propriétés
                batch_report = self.insert_properties_batch(batch_df)
                
                # Ajouter au rapport
                report_df = pd.concat([report_df, pd.DataFrame(batch_report)])
            
            # Statistiques finales
            success_count = report_df['success'].sum()
            success_rate = (success_count / initial_count) * 100 if initial_count > 0 else 0
            
            self.logger.info(f"Intégration terminée: {success_count}/{initial_count} propriétés intégrées ({success_rate:.1f}%)")
            
            # Sauvegarder le rapport
            return self.save_csv(report_df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'intégration: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def insert_properties_batch(self, batch_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Insère un lot de propriétés dans la base de données.
        
        Args:
            batch_df: DataFrame des propriétés à insérer
            
        Returns:
            List[Dict[str, Any]]: Rapport d'intégration pour chaque propriété
        """
        batch_report = []
        
        with self.db_manager as db:
            supabase_client = db.get_client()
            
            for _, row in batch_df.iterrows():
                report_entry = {
                    'address_raw': row['address_raw'],
                    'city_id': row['city_id'],
                    'success': False,
                    'error': None
                }
                
                try:
                    # Insérer dans la table addresses
                    address_id = self.insert_address(supabase_client, row)
                    report_entry['address_id'] = address_id
                    
                    # Si DPE présent, insérer dans la table dpe
                    if pd.notna(row.get('dpe_number', None)):
                        self.insert_dpe(supabase_client, row, address_id)
                    
                    report_entry['success'] = True
                    
                except Exception as e:
                    report_entry['error'] = str(e)
                    self.logger.error(f"Erreur lors de l'insertion de {row['address_raw']}: {str(e)}")
                
                batch_report.append(report_entry)
        
        return batch_report
    
    def insert_address(self, supabase_client, property_data: pd.Series) -> str:
        """
        Insère une propriété dans la table addresses.
        
        Args:
            supabase_client: Client Supabase
            property_data: Données de la propriété
            
        Returns:
            str: ID de l'adresse insérée
        """
        # Générer un UUID
        address_id = str(uuid.uuid4())
        
        # Préparer la géométrie PostGIS (dans Supabase, on stocke en format JSON la géométrie)
        # Le format est compatible avec PostGIS et peut être utilisé avec des fonctions spatiales
        geojson = {
            "type": "Point",
            "coordinates": [
                float(property_data['longitude']) if pd.notna(property_data['longitude']) else 0,
                float(property_data['latitude']) if pd.notna(property_data['latitude']) else 0
            ]
        }
        
        # Valider les données et remplacer NaN par None pour Supabase
        address_data = {
            'address_id': address_id,
            'department': property_data['department'] if pd.notna(property_data['department']) else None,
            'city_id': property_data['city_id'] if pd.notna(property_data['city_id']) else None,
            'address_raw': property_data['address_raw'] if pd.notna(property_data['address_raw']) else None,
            'sale_date': property_data['sale_date'] if pd.notna(property_data['sale_date']) else None,
            'property_type': property_data['property_type'] if pd.notna(property_data['property_type']) else None,
            'surface': float(property_data['surface']) if pd.notna(property_data['surface']) else None,
            'rooms': int(property_data['rooms']) if pd.notna(property_data['rooms']) else None,
            'price': float(property_data['price']) if pd.notna(property_data['price']) else None,
            'source_url': property_data['source_url'] if pd.notna(property_data['source_url']) else None,
            'estimated_price': float(property_data['estimated_price']) if pd.notna(property_data['estimated_price']) else None,
            'geoposition': json.dumps(geojson),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Exécuter l'insertion
        try:
            response = supabase_client.table('addresses').upsert(address_data).execute()
            
            if response.data and len(response.data) > 0:
                return address_id
            else:
                self.logger.warning(f"Pas de réponse de l'API pour l'insertion de l'adresse {address_id}")
                return address_id  # Retourne quand même l'ID car l'insertion a probablement réussi
        except Exception as e:
            self.logger.error(f"Erreur lors de l'insertion de l'adresse: {str(e)}")
            raise
    
    def insert_dpe(self, supabase_client, property_data: pd.Series, address_id: str) -> None:
        """
        Insère un DPE dans la table dpe.
        
        Args:
            supabase_client: Client Supabase
            property_data: Données de la propriété
            address_id: ID de l'adresse associée
        """
        # Générer un UUID
        dpe_id = str(uuid.uuid4())
        
        # Convertir la date DPE
        dpe_date = property_data.get('dpe_date')
        if pd.notna(dpe_date):
            try:
                dpe_date = pd.to_datetime(dpe_date).strftime('%Y-%m-%d')
            except:
                dpe_date = None
        
        # Valider les données et remplacer NaN par None pour Supabase
        dpe_data = {
            'dpe_id': dpe_id,
            'address_id': address_id,
            'department': property_data['department'] if pd.notna(property_data['department']) else None,
            'construction_year': int(property_data['construction_year']) if pd.notna(property_data.get('construction_year')) else None,
            'dpe_date': dpe_date,
            'dpe_energy_class': property_data.get('dpe_energy_class') if pd.notna(property_data.get('dpe_energy_class')) else None,
            'dpe_ges_class': property_data.get('dpe_ges_class') if pd.notna(property_data.get('dpe_ges_class')) else None,
            'dpe_number': property_data.get('dpe_number') if pd.notna(property_data.get('dpe_number')) else None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Exécuter l'insertion
        try:
            response = supabase_client.table('dpe').upsert(dpe_data).execute()
            
            if not response.data or len(response.data) == 0:
                self.logger.warning(f"Pas de réponse de l'API pour l'insertion du DPE {dpe_id}")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'insertion du DPE: {str(e)}")
            raise


if __name__ == "__main__":
    import argparse
    
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Analyser les arguments
    parser = argparse.ArgumentParser(description="Intégration des propriétés enrichies")
    parser.add_argument("--input", help="Fichier CSV d'entrée", required=True)
    parser.add_argument("--output", help="Fichier CSV de sortie", required=False)
    parser.add_argument("--batch", type=int, default=100, help="Taille des lots pour l'insertion")
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_db_report.csv")
    
    # Exécuter le processeur
    integrator = DBIntegrationService(args.input, output)
    success = integrator.process(batch_size=args.batch)
    
    exit(0 if success else 1) 