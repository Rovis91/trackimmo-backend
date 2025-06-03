import pandas as pd
import requests
import io
import logging
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter

from trackimmo.modules.db_manager import DBManager, city as city_crud
from .processor_base import ProcessorBase

class CityResolver(ProcessorBase):
    """Processeur pour résoudre les villes et obtenir les codes postaux."""
    
    # URL de l'API de géocodage
    GEOCODING_API = "https://api-adresse.data.gouv.fr/search/csv/"
    
    def __init__(self, input_path: str = None, output_path: str = None):
        super().__init__(input_path, output_path)
        self.db_manager = None
    
    def process(self, **kwargs) -> bool:
        """
        Résout les villes et récupère les codes postaux.
        
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
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
        self.logger.info(f"Début du traitement avec {initial_count} lignes")
        
        try:
            # Regrouper par ville
            city_groups = df.groupby('city_name')
            distinct_cities = city_groups.size().reset_index(name='count')
            self.logger.info(f"Traitement de {len(distinct_cities)} villes distinctes")
            
            # Récupérer les villes existantes dans la base de données
            with self.db_manager as db:
                existing_cities = city_crud.get_by_names(db, names=distinct_cities['city_name'].tolist())
            
            self.logger.info(f"Trouvé {len(existing_cities)} villes existantes en base")
            
            # Identifier les villes manquantes
            existing_city_names = {city['name'].upper() for city in existing_cities}
            missing_cities = distinct_cities[~distinct_cities['city_name'].str.upper().isin(existing_city_names)]
            
            if not missing_cities.empty:
                self.logger.info(f"Résolution de {len(missing_cities)} villes manquantes")
                resolved_cities = self.resolve_missing_cities(missing_cities, df)
                
                # Ajouter les villes résolues à la base de données
                if resolved_cities:
                    self.add_cities_to_db(resolved_cities)
                    
                # Mettre à jour la liste des villes existantes
                all_cities = existing_cities + resolved_cities
            else:
                all_cities = existing_cities
            
            # Créer un dictionnaire de correspondance ville → données
            city_data = {city['name'].upper(): city for city in all_cities}
            
            # Enrichir le DataFrame avec les données de ville
            df['city_id'] = df['city_name'].str.upper().map(lambda x: city_data.get(x, {}).get('city_id'))
            df['postal_code'] = df['city_name'].str.upper().map(lambda x: city_data.get(x, {}).get('postal_code'))
            df['insee_code'] = df['city_name'].str.upper().map(lambda x: city_data.get(x, {}).get('insee_code'))
            df['department'] = df['city_name'].str.upper().map(lambda x: city_data.get(x, {}).get('department'))
            
            # Filtrer les propriétés sans ville résolue
            valid_mask = df['city_id'].notna()
            invalid_count = (~valid_mask).sum()
            
            if invalid_count > 0:
                self.logger.warning(f"Suppression de {invalid_count} propriétés sans ville résolue")
                df = df[valid_mask]
            
            # Statistiques finales
            final_count = len(df)
            self.logger.info(f"Traitement terminé: {final_count} lignes valides")
            
            # Sauvegarder le résultat
            return self.save_csv(df)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la résolution des villes: {str(e)}")
            return False
    
    def resolve_missing_cities(self, missing_cities: pd.DataFrame, 
                              all_properties: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Résout les villes manquantes en utilisant l'API de géocodage.
        
        Args:
            missing_cities: DataFrame des villes manquantes
            all_properties: DataFrame de toutes les propriétés
            
        Returns:
            List[Dict[str, Any]]: Liste des villes résolues
        """
        resolved_cities = []
        
        for _, city_row in missing_cities.iterrows():
            city_name = city_row['city_name']
            
            # Obtenir toutes les propriétés pour cette ville
            city_properties = all_properties[all_properties['city_name'] == city_name]
            
            if city_properties.empty:
                continue
                
            self.logger.info(f"Résolution de la ville: {city_name} ({len(city_properties)} propriétés)")
            
            # Créer un CSV temporaire avec les adresses
            # Selon la documentation de l'API, on doit utiliser une colonne 'q' pour l'adresse complète
            temp_df = pd.DataFrame({
                'q': city_properties['address_raw'] + " " + city_name
            })
            
            # Récupérer les codes postaux via l'API de géocodage
            postal_codes, insee_codes = self.get_city_codes_from_geocoding(temp_df)
            
            if postal_codes and insee_codes:
                # Prendre le code postal et INSEE le plus fréquent
                # Convertir en chaîne car les codes peuvent être des entiers dans la réponse
                postal_code = str(postal_codes[0])
                insee_code = str(insee_codes[0])
                
                # Nettoyer le code postal - retirer points décimaux et s'assurer qu'il a 5 chiffres
                if '.' in postal_code:
                    postal_code = postal_code.split('.')[0]
                postal_code = postal_code.strip()
                
                # Vérifier que le code postal a 5 chiffres, sinon le formater
                if len(postal_code) > 5:
                    postal_code = postal_code[:5]  # Tronquer si trop long
                    self.logger.warning(f"Code postal tronqué pour {city_name}: {postal_code}")
                elif len(postal_code) < 5:  # Si trop court
                    postal_code = postal_code.zfill(5)
                    self.logger.warning(f"Code postal complété pour {city_name}: {postal_code}")
                
                # Extraire le département (2 premiers chiffres du code postal)
                department = postal_code[:2]
                
                # Nettoyer le code INSEE
                insee_code = insee_code.strip()
                if '.' in insee_code:
                    insee_code = insee_code.split('.')[0]
                
                # Valider et formater le code INSEE
                # Les codes INSEE doivent être de 5 caractères alphanumériques
                if not insee_code or insee_code.lower() in ['nan', 'none', 'null']:
                    self.logger.warning(f"Code INSEE vide ou invalide pour {city_name}, ignorer cette ville")
                    continue
                
                # Vérifier que le code INSEE a exactement 5 caractères
                if len(insee_code) < 5:
                    insee_code = insee_code.zfill(5)  # Compléter avec des zéros à gauche
                    self.logger.warning(f"Code INSEE complété pour {city_name}: {insee_code}")
                elif len(insee_code) > 5:
                    insee_code = insee_code[:5]  # Tronquer
                    self.logger.warning(f"Code INSEE tronqué pour {city_name}: {insee_code}")
                
                # Vérifier que le code INSEE ne contient que des caractères valides (chiffres et lettres)
                if not insee_code.replace('A', '').replace('B', '').isdigit():
                    # Pour la Corse, on peut avoir 2A ou 2B au début
                    if not (insee_code.startswith('2A') or insee_code.startswith('2B')) or len(insee_code) != 5:
                        self.logger.warning(f"Code INSEE invalide pour {city_name}: {insee_code}, ignoré")
                        continue
                
                resolved_cities.append({
                    "name": city_name,
                    "postal_code": postal_code,
                    "insee_code": insee_code,
                    "department": department
                })
                
                self.logger.info(f"Ville résolue: {city_name} → CP: {postal_code}, INSEE: {insee_code}")
            else:
                self.logger.warning(f"Impossible de résoudre la ville: {city_name}")
        
        return resolved_cities
    
    def get_city_codes_from_geocoding(self, addresses_df: pd.DataFrame) -> Tuple[List, List]:
        """
        Obtient les codes postaux et INSEE en envoyant les adresses à l'API de géocodage.
        
        Args:
            addresses_df: DataFrame contenant la colonne 'q' pour les adresses complètes
            
        Returns:
            Tuple[List, List]: 
                Codes postaux et INSEE les plus fréquents (triés par fréquence)
        """
        try:
            # Convertir le DataFrame en CSV
            csv_buffer = io.StringIO()
            addresses_df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()
            
            # Log le contenu pour le débogage
            self.logger.info(f"Envoi du CSV à l'API avec les colonnes: {list(addresses_df.columns)}")
            self.logger.info(f"Exemple de la première ligne: {addresses_df.iloc[0].to_dict() if not addresses_df.empty else 'DataFrame vide'}")
            
            # Préparer les paramètres pour l'API
            # L'API utilise la colonne 'q' par défaut ou on peut spécifier la colonne avec le paramètre 'q'
            files = {'data': ('addresses.csv', csv_content.encode('utf-8'), 'text/csv')}
            
            # Appeler l'API de géocodage
            response = requests.post(
                self.GEOCODING_API,
                files=files
            )
            
            if response.status_code != 200:
                self.logger.error(f"Erreur API géocodage: {response.status_code}")
                self.logger.error(f"Détail de l'erreur: {response.text}")
                return [], []
            
            # Parser la réponse CSV
            result_df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            # Afficher un échantillon des résultats pour le débogage
            self.logger.info(f"Colonnes reçues: {list(result_df.columns)}")
            if not result_df.empty:
                self.logger.info(f"Première ligne de résultat: {result_df.iloc[0].to_dict()}")
            
            # Compter les codes postaux et INSEE
            # Convertir les valeurs en chaînes pour éviter les problèmes avec les types entiers
            result_df['result_postcode'] = result_df['result_postcode'].astype(str)
            result_df['result_citycode'] = result_df['result_citycode'].astype(str)
            
            postal_counts = Counter(result_df['result_postcode'].dropna())
            insee_counts = Counter(result_df['result_citycode'].dropna())
            
            # Trier par fréquence décroissante et renvoyer les codes directement
            postal_codes = [code for code, _ in sorted(postal_counts.items(), key=lambda x: x[1], reverse=True)]
            insee_codes = [code for code, _ in sorted(insee_counts.items(), key=lambda x: x[1], reverse=True)]
            
            return postal_codes, insee_codes
            
        except Exception as e:
            self.logger.error(f"Erreur lors du géocodage: {str(e)}")
            return [], []
    
    def add_cities_to_db(self, cities: List[Dict[str, Any]]) -> bool:
        """
        Ajoute les villes résolues à la base de données.
        
        Args:
            cities: Liste des villes à ajouter
            
        Returns:
            bool: True si l'ajout a réussi, False sinon
        """
        if not cities:
            return True
            
        try:
            successful_cities = []
            
            with self.db_manager as db:
                for city_data in cities:
                    try:
                        # S'assurer que les données sont conformes aux contraintes de la base
                        postal_code = str(city_data["postal_code"]).strip()
                        if len(postal_code) > 5:
                            postal_code = postal_code[:5]
                        
                        department = str(city_data["department"]).strip()
                        if len(department) > 2:
                            department = department[:2]
                        
                        insee_code = str(city_data["insee_code"]).strip()
                        if len(insee_code) > 10:
                            insee_code = insee_code[:10]
                        
                        # Préparer les données pour l'insertion
                        insert_data = {
                            "name": city_data["name"],
                            "postal_code": postal_code,
                            "insee_code": insee_code,
                            "department": department,
                            "created_at": "now()",
                            "updated_at": "now()"
                        }
                        
                        # Log des données qui seront insérées pour le débogage
                        self.logger.info(f"Insertion ville: {insert_data}")
                        
                        # Insérer avec gestion des conflits
                        supabase_client = db.get_client()
                        
                        # Use upsert to handle duplicates gracefully
                        result = supabase_client.table("cities").upsert(
                            insert_data,
                            on_conflict="insee_code"
                        ).execute()
                        
                        if result.data and len(result.data) > 0:
                            city_id = result.data[0].get("city_id")
                            city_data["city_id"] = city_id
                            successful_cities.append(city_data)
                            self.logger.info(f"Ville ajoutée/mise à jour: {city_data['name']} (ID: {city_id})")
                        else:
                            self.logger.warning(f"Aucune donnée retournée pour la ville {city_data['name']}")
                    except Exception as e:
                        error_msg = str(e)
                        if "duplicate key value violates unique constraint" in error_msg:
                            # City already exists, try to get its ID
                            try:
                                existing_city = supabase_client.table("cities").select("*").eq("insee_code", insee_code).execute()
                                if existing_city.data and len(existing_city.data) > 0:
                                    city_id = existing_city.data[0].get("city_id")
                                    city_data["city_id"] = city_id
                                    successful_cities.append(city_data)
                                    self.logger.info(f"Ville existante trouvée: {city_data['name']} (ID: {city_id})")
                                else:
                                    self.logger.error(f"Ville {city_data['name']} existe mais impossible de récupérer l'ID")
                            except Exception as e2:
                                self.logger.error(f"Erreur lors de la récupération de la ville existante {city_data['name']}: {str(e2)}")
                        else:
                            self.logger.error(f"Erreur lors de l'ajout de la ville {city_data['name']}: {error_msg}")
            
            self.logger.info(f"Ajouté {len(successful_cities)} villes à la base de données sur {len(cities)} tentées")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'ajout des villes: {str(e)}")
            return False

if __name__ == "__main__":
    import argparse
    
    # Configurer la journalisation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Analyser les arguments
    parser = argparse.ArgumentParser(description="Résolution des villes et codes postaux")
    parser.add_argument("--input", help="Fichier CSV d'entrée", required=True)
    parser.add_argument("--output", help="Fichier CSV de sortie", required=False)
    
    args = parser.parse_args()
    output = args.output or args.input.replace(".csv", "_cities_resolved.csv")
    
    # Exécuter le processeur
    resolver = CityResolver(args.input, output)
    success = resolver.process()
    
    exit(0 if success else 1) 