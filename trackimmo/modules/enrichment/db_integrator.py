import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import logging
import uuid
import os
import dotenv
import json
import re
from pathlib import Path

from .processor_base import ProcessorBase
from trackimmo.modules.db_manager import DBManager

# Load environment variables
dotenv.load_dotenv()

class DBIntegrationService(ProcessorBase):
    """Processor for integrating enriched properties into the database."""
    
    def __init__(self, input_path: str = None, output_path: str = None,
                 db_url: str = None):
        super().__init__(input_path, output_path)
        self.db_url = db_url
        self.db_manager = None
        
        # Configure logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Use configured log level instead of hardcoded INFO
        try:
            from trackimmo.config import settings
            log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.ERROR)
        except ImportError:
            log_level = logging.ERROR
            
        self.logger.setLevel(log_level)
        
        # Disable verbose HTTP logging
        logging.getLogger('httpcore.connection').setLevel(logging.WARNING)
        logging.getLogger('hpack.hpack').setLevel(logging.WARNING)
        logging.getLogger('httpcore.http2').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('hpack.table').setLevel(logging.WARNING)
    
    def process(self, **kwargs) -> bool:
        """
        Integrate enriched properties into the database.
        
        Args:
            **kwargs: Additional arguments
                - batch_size: Batch size for insertion (default: 100)
                
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        # Get parameters
        batch_size = kwargs.get('batch_size', 100)
        
        # Load data
        df = self.load_csv()
        if df is None:
            return False
        
        # Initialize database manager
        try:
            self.db_manager = DBManager()
            self.logger.info("Database connection established")
        except Exception as e:
            self.logger.error(f"Database connection error: {str(e)}")
            return False
        
        # Initial statistics
        initial_count = len(df)
        self.logger.info(f"Starting integration of {initial_count} properties")
        
        try:
            # Create DataFrame for integration report
            report_df = pd.DataFrame(columns=['address_id', 'address_raw', 'city_id', 'success', 'error'])
            
            # Filter out records with missing required fields
            required_fields = ['address_raw', 'city_id', 'department', 'sale_date', 'property_type']
            
            valid_df = df.copy()
            for field in required_fields:
                valid_df = valid_df[pd.notna(valid_df[field])]
            
            skipped_count = len(df) - len(valid_df)
            if skipped_count > 0:
                self.logger.warning(f"Skipped {skipped_count} properties with missing required fields")
            
            # Process in batches
            batches = [valid_df[i:i+batch_size] for i in range(0, len(valid_df), batch_size)]
            
            for i, batch_df in enumerate(batches):
                self.logger.info(f"Processing batch {i+1}/{len(batches)} ({len(batch_df)} properties)")
                
                # Insert properties
                batch_report = self.insert_properties_batch(batch_df)
                
                # Add to report
                report_df = pd.concat([report_df, pd.DataFrame(batch_report)])
            
            # Final statistics
            success_count = report_df['success'].sum()
            success_rate = (success_count / len(valid_df)) * 100 if len(valid_df) > 0 else 0
            
            self.logger.info(f"Integration complete: {success_count}/{len(valid_df)} properties integrated ({success_rate:.1f}%)")
            
            # Save report
            return self.save_csv(report_df)
            
        except Exception as e:
            self.logger.error(f"Error during integration: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def insert_properties_batch(self, batch_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Insert a batch of properties into the database.
        
        Args:
            batch_df: DataFrame of properties to insert
            
        Returns:
            List[Dict[str, Any]]: Integration report for each property
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
                    # Insert into addresses table
                    address_id = self.insert_address(supabase_client, row)
                    
                    # Skip if address insertion was skipped due to duplicate URL
                    if address_id is None:
                        report_entry['success'] = True  # It's a success, just skipped
                        report_entry['skipped'] = True
                        report_entry['reason'] = 'Duplicate URL skipped'
                        batch_report.append(report_entry)
                        continue
                    
                    report_entry['address_id'] = address_id
                    
                    # If DPE present, insert into dpe table
                    if pd.notna(row.get('dpe_number', None)) or pd.notna(row.get('dpe_energy_class', None)):
                        self.insert_dpe(supabase_client, row, address_id)
                    
                    report_entry['success'] = True
                    
                except Exception as e:
                    report_entry['error'] = str(e)
                    self.logger.error(f"Error inserting {row['address_raw']}: {str(e)}")
                
                batch_report.append(report_entry)
        
        return batch_report
    
    def insert_address(self, supabase_client, property_data: pd.Series) -> str:
        """
        Insert a property into the addresses table.
        
        Args:
            supabase_client: Supabase client
            property_data: Property data
            
        Returns:
            str: Address ID
        """
        # Check if this URL already exists in database to avoid duplicate constraint violations
        source_url = property_data.get('source_url')
        if pd.notna(source_url) and source_url:
            try:
                # Check if URL already exists
                existing_response = supabase_client.table('addresses').select('address_id').eq('immodata_url', source_url).execute()
                if existing_response.data and len(existing_response.data) > 0:
                    existing_id = existing_response.data[0]['address_id']
                    self.logger.debug(f"Property with URL {source_url} already exists (ID: {existing_id}), skipping insertion")
                    return existing_id
            except Exception as e:
                self.logger.warning(f"Could not check for existing URL {source_url}: {str(e)}")
        
        # Generate UUID
        address_id = str(uuid.uuid4())
        
        # Prepare PostGIS geometry (as JSON format compatible with PostGIS)
        geojson = None
        if pd.notna(property_data.get('longitude')) and pd.notna(property_data.get('latitude')):
            geojson = {
                "type": "Point",
                "coordinates": [
                    float(property_data['longitude']),
                    float(property_data['latitude'])
                ]
            }
        
        # Format sale date
        sale_date = None
        if pd.notna(property_data['sale_date']):
            try:
                date_obj = pd.to_datetime(property_data['sale_date'])
                sale_date = date_obj.strftime('%Y-%m-%d')
            except Exception as e:
                self.logger.warning(f"Invalid sale date format: {property_data['sale_date']} - {str(e)}")
                return None
        
        # Validate and prepare numeric fields
        surface = self.safe_numeric_conversion(property_data.get('surface'), int)
        rooms = self.safe_numeric_conversion(property_data.get('rooms'), int)
        price = self.safe_numeric_conversion(property_data.get('price'), int)
        estimated_price = self.safe_numeric_conversion(property_data.get('estimated_price'), int)
        
        # Validate department format
        department = str(property_data['department'])
        if not re.match(r'^\d{2,3}$', department):
            department = department[:3]  # Take first 2-3 digits
        
        # Prepare address data
        address_data = {
            'address_id': address_id,
            'department': department,
            'city_id': property_data['city_id'],
            'address_raw': property_data['address_raw'],
            'sale_date': sale_date,
            'property_type': property_data['property_type'],
            'surface': surface,
            'rooms': rooms,
            'price': price,
            'immodata_url': source_url if pd.notna(source_url) else None,
            'estimated_price': estimated_price,
            'geoposition': json.dumps(geojson) if geojson else None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Execute insertion with error handling for duplicates
        try:
            response = supabase_client.table('addresses').insert(address_data).execute()
            
            if response.data and len(response.data) > 0:
                return address_id
            else:
                self.logger.warning(f"No response from API for address insertion {address_id}")
                return address_id  # Return ID anyway as insertion probably succeeded
                
        except Exception as e:
            error_str = str(e)
            # Handle duplicate URL constraint violations gracefully
            if "duplicate key value violates unique constraint" in error_str and "unique_immodata_url" in error_str:
                self.logger.debug(f"Duplicate URL constraint violation for {source_url}, attempting to find existing record")
                try:
                    # Try to find the existing record
                    existing_response = supabase_client.table('addresses').select('address_id').eq('immodata_url', source_url).execute()
                    if existing_response.data and len(existing_response.data) > 0:
                        existing_id = existing_response.data[0]['address_id']
                        self.logger.debug(f"Found existing record with ID: {existing_id}")
                        return existing_id
                except Exception as find_error:
                    self.logger.warning(f"Could not find existing record for duplicate URL: {str(find_error)}")
                
                # If we can't find the existing record, log and skip
                self.logger.warning(f"Skipping duplicate URL {source_url}")
                return None
            else:
                # For other errors, log and re-raise
                self.logger.error(f"Error inserting address: {error_str}")
                raise
    
    def insert_dpe(self, supabase_client, property_data: pd.Series, address_id: str) -> None:
        """
        Insert a DPE into the dpe table.
        
        Args:
            supabase_client: Supabase client
            property_data: Property data
            address_id: Address ID
        """
        # Generate UUID
        dpe_id = str(uuid.uuid4())
        
        # Format DPE date
        dpe_date = None
        if pd.notna(property_data.get('dpe_date')):
            try:
                date_obj = pd.to_datetime(property_data['dpe_date'])
                dpe_date = date_obj.strftime('%Y-%m-%d')
            except:
                dpe_date = datetime.now().strftime('%Y-%m-%d')  # Fallback to current date
        else:
            dpe_date = datetime.now().strftime('%Y-%m-%d')  # Required field
        
        # Validate construction year
        construction_year = None
        if pd.notna(property_data.get('construction_year')):
            try:
                year = int(property_data['construction_year'])
                if 1800 <= year <= datetime.now().year:
                    construction_year = year
            except:
                pass
        
        # Validate department format
        department = str(property_data['department'])
        if not re.match(r'^\d{2,3}$', department):
            department = department[:3]  # Take first 2-3 digits
        
        # Prepare energy and GES classes with fallbacks
        dpe_energy_class = property_data.get('dpe_energy_class') if pd.notna(property_data.get('dpe_energy_class')) else 'N'
        dpe_ges_class = property_data.get('dpe_ges_class') if pd.notna(property_data.get('dpe_ges_class')) else 'N'
        
        # Get DPE number with fallback
        dpe_number = property_data.get('dpe_number') if pd.notna(property_data.get('dpe_number')) else f"AUTO-{address_id[:8]}"
        
        # Prepare DPE data
        dpe_data = {
            'dpe_id': dpe_id,
            'address_id': address_id,
            'department': department,
            'construction_year': construction_year,
            'dpe_date': dpe_date,
            'dpe_energy_class': dpe_energy_class,
            'dpe_ges_class': dpe_ges_class,
            'dpe_number': dpe_number,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Execute insertion
        try:
            response = supabase_client.table('dpe').upsert(dpe_data).execute()
            
            if not response.data or len(response.data) == 0:
                self.logger.warning(f"No response from API for DPE insertion {dpe_id}")
        except Exception as e:
            self.logger.error(f"Error inserting DPE: {str(e)}")
            raise
    
    def safe_numeric_conversion(self, value, target_type=int, default=None):
        """
        Safely convert a value to a numeric type.
        
        Args:
            value: Value to convert
            target_type: Target numeric type (int or float)
            default: Default value if conversion fails
            
        Returns:
            Converted value or default
        """
        if pd.isna(value):
            return default
            
        try:
            if target_type == int:
                return int(float(value))
            elif target_type == float:
                return float(value)
        except (ValueError, TypeError):
            return default
            
        return default


if __name__ == "__main__":
    import argparse
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Integration of enriched properties")
    parser.add_argument("--input", help="Input CSV file", required=True)
    parser.add_argument("--output", help="Output CSV file", required=False)
    parser.add_argument("--batch", type=int, default=1000, help="Batch size for insertion")
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_db_report.csv")
    
    # Run processor
    integrator = DBIntegrationService(args.input, output)
    success = integrator.process(batch_size=args.batch)
    
    exit(0 if success else 1)