# Documentation de l'API de Géocodage

Cette documentation détaille l'utilisation de l'API de géocodage gouvernementale française.

## Aperçu

L'API Base Adresse Nationale est le service officiel de géocodage pour la France. Elle permet de transformer des adresses textuelles en coordonnées géographiques (latitude/longitude).

URL de base: `https://api-adresse.data.gouv.fr/`

## Méthodes principales

### 1. Recherche d'adresse (GET)

Endpoint: `https://api-adresse.data.gouv.fr/search/`

Paramètres:

- `q` (obligatoire): Adresse recherchée
- `limit` (optionnel): Nombre de résultats (défaut: 5, max: 100)
- `type` (optionnel): Type de résultat (housenumber, street, locality, municipality)
- `postcode` (optionnel): Code postal pour filtrer les résultats
- `citycode` (optionnel): Code INSEE pour filtrer les résultats

Exemple de requête:

``` txt
GET https://api-adresse.data.gouv.fr/search/?q=8+bd+du+port&postcode=80000
```

Exemple de réponse:

```json
{
  "type": "FeatureCollection",
  "version": "draft",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [2.292131, 49.897443]
      },
      "properties": {
        "label": "8 Boulevard du Port 80000 Amiens",
        "score": 0.9,
        "housenumber": "8",
        "id": "80021_0237_00008",
        "type": "housenumber",
        "name": "8 Boulevard du Port",
        "city": "Amiens",
        "postcode": "80000",
        "citycode": "80021",
        "x": 648952.58,
        "y": 6977867.25,
        "context": "80, Somme, Hauts-de-France"
      }
    }
  ]
}
```

### Recherche par lot CSV (POST)

Endpoint: `<https://api-adresse.data.gouv.fr/search/csv/>`
Cette méthode est particulièrement adaptée à notre cas d'usage, car elle permet de géocoder plusieurs adresses en une seule requête.
Paramètres:

- `data` (obligatoire): Fichier CSV à traiter
- `columns` (optionnel): Noms des colonnes utilisées pour l'adresse, séparés par des virgules
- `result_columns` (optionnel): Colonnes supplémentaires à inclure dans le résultat

Format CSV d'entrée:

``` csv
address,city
8 bd du port,Amiens
4 rue de la Mairie,Paris
```

Implémentation:

``` python
def geocode_addresses(addresses_df):
    """
    Géocode un DataFrame d'adresses en utilisant l'API BAN.
    
    Args:
        addresses_df: DataFrame avec colonnes 'address' et 'city'
        
    Returns:
        DataFrame avec les colonnes originales + coordonnées géographiques
    """
    # Sauvegarder en CSV temporaire
    temp_file = "temp_geocoding.csv"
    addresses_df[['address', 'city']].to_csv(temp_file, index=False)
    
    # Préparer la requête
    url = "https://api-adresse.data.gouv.fr/search/csv/"
    with open(temp_file, 'rb') as f:
        files = {'data': f}
        data = {'columns': 'address,city'}
        
        # Envoyer la requête
        response = requests.post(url, files=files, data=data)
    
    # Traiter la réponse
    if response.status_code == 200:
        # Sauvegarder la réponse CSV
        with open("geocoded.csv", 'wb') as f:
            f.write(response.content)
        
        # Charger le CSV résultant
        result_df = pd.read_csv("geocoded.csv")
        return result_df
    else:
        raise Exception(f"Erreur lors du géocodage: {response.status_code}")
```

#### Colonnes ajoutées dans le résultat

Le service ajoute les colonnes suivantes au CSV d'entrée:

`latitude`: Latitude en degrés décimaux (WGS-84)
`longitude`: Longitude en degrés décimaux (WGS-84)
`result_label`: Adresse complète formatée
`result_score`: Score de confiance de 0 à 1
`result_type`: Type de résultat (housenumber, street, etc.)
`result_id`: Identifiant BAN
`result_housenumber`: Numéro de rue
`result_name`: Nom de la voie
`result_street`: Nom de la rue
`result_postcode`: Code postal
`result_city`: Commune
`result_context`: Region, département
`result_citycode`: Code INSEE

### Limites et bonnes pratiques

Quota: Maximum 10 requêtes par seconde
Taille maximale du CSV: 50 Mo
Nombre maximum d'adresses par lot: 10 000
Encodage: UTF-8 (obligatoire)

### Gestion des erreurs

Code 400: Paramètres de requête invalides
Code 403: Quota dépassé
Code 500: Erreur serveur

### Stratégie d'implémentation

Regrouper les adresses par lots de 1000 maximum
Ajouter des délais entre les requêtes (100ms minimum)
Réessayer en cas d'erreur (maximum 3 tentatives)
Valider les résultats avec un score minimal (0.5 recommandé)

### Exemple de code complet

``` python
import time
import pandas as pd
import requests
from pathlib import Path

def geocode_batch(df, batch_size=1000, min_delay=0.1, max_retries=3):
    """
    Géocode un DataFrame par lots avec gestion des erreurs.
    """
    result_dfs = []
    
    # Diviser en lots
    batches = [df[i:i+batch_size] for i in range(0, len(df), batch_size)]
    
    for batch_idx, batch in enumerate(batches):
        retry_count = 0
        success = False
        
        while not success and retry_count < max_retries:
            try:
                # Créer fichier temporaire
                temp_file = f"temp_geocoding_batch_{batch_idx}.csv"
                batch[['address', 'city']].to_csv(temp_file, index=False)
                
                # Envoyer requête
                url = "https://api-adresse.data.gouv.fr/search/csv/"
                with open(temp_file, 'rb') as f:
                    files = {'data': f}
                    data = {'columns': 'address,city'}
                    response = requests.post(url, files=files, data=data)
                
                if response.status_code == 200:
                    # Sauvegarder résultat
                    result_file = f"geocoded_batch_{batch_idx}.csv"
                    with open(result_file, 'wb') as f:
                        f.write(response.content)
                    
                    # Charger le résultat
                    result_df = pd.read_csv(result_file)
                    
                    # Ajouter index original pour la fusion ultérieure
                    result_df['original_index'] = batch.index
                    
                    result_dfs.append(result_df)
                    success = True
                    
                    # Supprimer fichiers temporaires
                    Path(temp_file).unlink(missing_ok=True)
                    Path(result_file).unlink(missing_ok=True)
                else:
                    retry_count += 1
                    print(f"Erreur {response.status_code} sur lot {batch_idx}. Retry {retry_count}/{max_retries}")
                    time.sleep(min_delay * (2 ** retry_count))  # Délai exponentiel
            
            except Exception as e:
                retry_count += 1
                print(f"Exception sur lot {batch_idx}: {str(e)}. Retry {retry_count}/{max_retries}")
                time.sleep(min_delay * (2 ** retry_count))
        
        # Respecter le quota
        time.sleep(min_delay)
    
    # Combiner tous les résultats
    if result_dfs:
        combined_df = pd.concat(result_dfs)
        combined_df = combined_df.sort_values('original_index')
        combined_df = combined_df.drop(columns=['original_index'])
        return combined_df
    else:
        return pd.DataFrame()
```
