# Documentation du Module de Scraping des Villes

Ce module est responsable de la collecte automatisée des données sur les villes françaises, incluant les codes INSEE, les codes postaux, les départements et les prix moyens immobiliers.

## Structure générale

Le module city_scraper est organisé selon l'architecture suivante:

```
trackimmo/
└── modules/
    └── city_scraper/
        ├── __init__.py                # Exports des classes et fonctions principales
        ├── city_scraper.py            # Classe principale de scraping
        └── db_operations.py           # Opérations de base de données
```

## Fonctionnalités principales

Le module permet de:

1. **Récupérer les codes INSEE** pour les villes françaises
2. **Extraire les prix immobiliers moyens** (maisons et appartements) à partir de sources web
3. **Enrichir la base de données** avec ces informations
4. **Automatiser le processus** de mise à jour des données des villes

## CityDataScraper (city_scraper.py)

Cette classe est responsable de l'extraction des données des villes à partir de différentes sources.

### Méthodes principales

#### `scrape_city(city_name, postal_code, insee_code=None)`

```python
async def scrape_city(self, city_name: str, postal_code: str, insee_code: Optional[str] = None) -> Dict[str, Any]:
```

Cette méthode extrait les données d'une ville spécifique:
- Récupère le code INSEE si non fourni
- Extrait les informations de département et région
- Scrape les prix immobiliers moyens des sites spécialisés

#### `_get_geocoding_data(city_name, postal_code)`

```python
def _get_geocoding_data(self, city_name: str, postal_code: str) -> Optional[Dict[str, str]]:
```

Utilise l'API de géocodage française pour obtenir:
- Code INSEE
- Code postal normalisé
- Département
- Région

#### `_scrape_prices(url)`

```python
async def _scrape_prices(self, url: str) -> Dict[str, Optional[int]]:
```

Extrait les prix immobiliers moyens:
- Prix moyen des maisons (€/m²)
- Prix moyen des appartements (€/m²)

### Fonction de façade

```python
async def scrape_cities(cities_data, max_retries=3, sleep_time=1.0):
```

Cette fonction facilite le scraping de plusieurs villes:
- Traite une liste de villes en parallèle
- Gère automatiquement la limitation de débit
- Retourne les résultats compilés

## CityDatabaseOperations (db_operations.py)

Cette classe gère les opérations de base de données pour les villes.

### Méthodes principales

#### `update_cities(cities_data)`

```python
def update_cities(self, cities_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
```

Met à jour plusieurs villes en base de données:
- Traite un lot de villes en une seule opération
- Capture et journalise les erreurs
- Retourne les résultats avec statut de succès/échec

#### `update_city(city_data)`

```python
def update_city(self, city_data: Dict[str, Any]) -> Dict[str, Any]:
```

Met à jour une ville individuelle:
- Vérifie l'existence de la ville par code INSEE
- Effectue une opération UPSERT (insert ou update)
- Met à jour les prix moyens si disponibles

## Exemple d'utilisation

### Scraping d'une ville individuelle

```python
import asyncio
from trackimmo.modules.city_scraper import CityDataScraper

async def scrape_single_city():
    scraper = CityDataScraper()
    city_data = await scraper.scrape_city("Paris", "75001")
    print(city_data)

asyncio.run(scrape_single_city())
```

### Scraping et mise à jour de plusieurs villes

```python
import asyncio
from trackimmo.modules.city_scraper import scrape_cities, CityDatabaseOperations

async def update_multiple_cities():
    # Préparer les données des villes
    cities_to_scrape = [
        {"name": "Paris", "postal_code": "75001"},
        {"name": "Lyon", "postal_code": "69001"},
        {"name": "Marseille", "postal_code": "13001"}
    ]
    
    # Scraper les données
    scraped_cities = await scrape_cities(cities_to_scrape)
    
    # Mettre à jour la base de données
    db_ops = CityDatabaseOperations()
    results = db_ops.update_cities(scraped_cities)
    
    # Afficher les résultats
    for city in results:
        print(f"{city['name']}: {city['status']}")

asyncio.run(update_multiple_cities())
```

## Dépendances

Le module requiert les packages suivants:
- `playwright` pour l'automation du navigateur
- `beautifulsoup4` pour le parsing HTML
- `requests` pour les requêtes HTTP
- `asyncio` pour les opérations asynchrones

## Notes d'implémentation

- **Géocodage**: Utilisation de l'API officielle française pour des données précises
- **Limitation de débit**: Mécanismes intégrés pour respecter les limites des sites sources
- **Robustesse**: Gestion des erreurs et mécanismes de retry pour une meilleure fiabilité
- **Asynchrone**: Utilisation de async/await pour un traitement efficace de multiples villes 