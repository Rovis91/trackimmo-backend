# Documentation de l'API DPE (Diagnostic de Performance Énergétique)

Cette documentation détaille l'utilisation de l'API de l'ADEME pour récupérer les données de Diagnostic de Performance Énergétique (DPE) des bâtiments.

## Aperçu

L'API DPE permet d'accéder aux données des diagnostics énergétiques des bâtiments en France, fournissant des informations sur leur consommation énergétique et leur impact environnemental.

## Endpoints principaux

Deux endpoints principaux sont utilisés selon le type de bâtiment:

1. **Bâtiments existants**:
   `https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines`

2. **Bâtiments neufs**:
   `https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-neufs/lines`

## Méthode de requête

### Requête par code INSEE

Méthode: `GET`

Paramètres principaux:

- `size`: Nombre de résultats à retourner (max: 10000)
- `select`: Liste des champs à inclure dans la réponse (séparés par des virgules)
- `q`: Terme de recherche (généralement code INSEE)
- `q_mode`: Mode de recherche (simple, complex, simple_forward, etc.)
- `q_fields`: Champs dans lesquels rechercher

Exemple de requête:

``` txt
GET https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines?size=50&select=N%C2%B0DPE,Date_r%C3%A9ception_DPE,Etiquette_GES,Etiquette_DPE,Ann%C3%A9e_construction,Adresse_brute,Nom__commune_(BAN),Code_INSEE_(BAN)&q=59350&q_mode=simple&q_fields=Code_INSEE_(BAN)
```

## Champs importants dans la réponse

```yaml
N°DPE:
  description: "Numéro unique d'identification du DPE"
  format: "Chaîne de caractères"
  exemple: "2169E0753607"

Date_réception_DPE:
  description: "Date de réalisation du diagnostic"
  format: "YYYY-MM-DD"
  exemple: "2021-07-15"

Etiquette_DPE:
  description: "Classe énergétique (consommation)"
  format: "Lettre de A à G"
  exemple: "D"

Etiquette_GES:
  description: "Classe d'émission de gaz à effet de serre"
  format: "Lettre de A à G"
  exemple: "B"

Année_construction:
  description: "Année de construction du bâtiment"
  format: "Année (YYYY)"
  exemple: "1982"

Adresse_brute:
  description: "Adresse complète du bâtiment"
  format: "Texte libre"
  exemple: "12 RUE DES LILAS"

Nom__commune_(BAN):
  description: "Nom de la commune (Base Adresse Nationale)"
  format: "Texte"
  exemple: "LILLE"

Code_INSEE_(BAN):
  description: "Code INSEE de la commune"
  format: "5 chiffres"
  exemple: "59350"
```

### Structure de la réponse

``` json
{
  "total": 245,
  "results": [
    {
      "N°DPE": "2169E0753607",
      "Date_réception_DPE": "2021-07-15",
      "Etiquette_GES": "B",
      "Etiquette_DPE": "D",
      "Année_construction": "1982",
      "Adresse_brute": "12 RUE DES LILAS",
      "Nom__commune_(BAN)": "LILLE",
      "Code_INSEE_(BAN)": "59350"
    },
    // ...autres résultats
  ]
}
```

## Stratégie d'enrichissement

Pour associer un DPE à une adresse, nous utilisons une approche en plusieurs étapes:

1. Recherche par code INSEE: Filtrer d'abord par commune
2. Filtrage par adresse: Comparer les adresses normalisées
3. Fallback par date: Pour les bâtiments neufs, vérifier d'abord dans les données récentes

### Implémentation

``` python
class DPEEnrichmentService:
    """Service d'enrichissement des propriétés avec les données DPE."""
    
    EXISTING_BUILDINGS_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines"
    NEW_BUILDINGS_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-neufs/lines"
    MAX_RETRIES = 3
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def normalize_address(self, address):
        """Normalise une adresse pour la comparaison."""
        if not address:
            return ""
        
        # Supprimer les accents
        address = unicodedata.normalize('NFKD', address).encode('ASCII', 'ignore').decode('utf-8')
        
        # Convertir en majuscules
        address = address.upper()
        
        # Supprimer la ponctuation et les caractères spéciaux
        address = re.sub(r'[^\w\s]', '', address)
        
        # Supprimer les mots communs non significatifs
        common_words = ['RUE', 'AVENUE', 'AV', 'BOULEVARD', 'BD', 'PLACE', 'PL', 'ALLEE', 'IMPASSE', 'IMP']
        words = address.split()
        words = [word for word in words if word not in common_words]
        
        # Reconstituer l'adresse
        return ' '.join(words)
    
    async def query_dpe_api(self, insee_code, api_url, retry_count=0):
        """Interroge l'API DPE pour récupérer les données d'une commune."""
        if retry_count >= self.MAX_RETRIES:
            self.logger.warning(f"Nombre maximum de tentatives atteint pour le code INSEE {insee_code}")
            return None
        
        try:
            # Construire les paramètres de la requête
            select_fields = (
                "N°DPE,Date_réception_DPE,Etiquette_GES,Etiquette_DPE,"
                "Année_construction,Adresse_brute,Nom__commune_(BAN),"
                "Code_INSEE_(BAN),Code_postal_(BAN)"
            )
            
            params = {
                "size": 1000,
                "select": select_fields,
                "q": insee_code,
                "q_mode": "simple",
                "q_fields": "Code_INSEE_(BAN)"
            }
            
            self.logger.info(f"Interrogation de l'API pour le code INSEE {insee_code}")
            response = requests.get(api_url, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if "results" in data:
                    self.logger.info(f"Trouvé {len(data['results'])} résultats pour le code INSEE {insee_code}")
                    return data["results"]
            
            # En cas d'erreur, attendre et réessayer
            await asyncio.sleep(1 * (retry_count + 1))
            return await self.query_dpe_api(insee_code, api_url, retry_count + 1)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'interrogation de l'API DPE: {str(e)}")
            await asyncio.sleep(1 * (retry_count + 1))
            return await self.query_dpe_api(insee_code, api_url, retry_count + 1)
    
    def find_best_dpe_match(self, property_address, dpe_results):
        """Trouve le meilleur DPE correspondant à une adresse."""
        if not dpe_results:
            return None
        
        normalized_property_address = self.normalize_address(property_address)
        
        best_match = None
        best_score = 0
        
        for dpe in dpe_results:
            dpe_address = dpe.get("Adresse_brute", "")
            normalized_dpe_address = self.normalize_address(dpe_address)
            
            # Calculer un score de similarité
            if normalized_property_address and normalized_dpe_address:
                similarity = difflib.SequenceMatcher(None, normalized_property_address, normalized_dpe_address).ratio()
                
                if similarity > best_score and similarity > 0.8:  # Seuil de confiance
                    best_score = similarity
                    best_match = dpe
        
        return best_match
    
    async def enrich_property(self, property_data):
        """Enrichit une propriété avec des données DPE."""
        insee_code = property_data.get("insee_code")
        if not insee_code:
            self.logger.warning("Code INSEE manquant, impossible d'enrichir avec DPE")
            return property_data
        
        property_address = property_data.get("address", "")
        
        # D'abord vérifier dans les bâtiments existants
        existing_dpe_results = await self.query_dpe_api(insee_code, self.EXISTING_BUILDINGS_API)
        best_match = self.find_best_dpe_match(property_address, existing_dpe_results)
        
        # Si pas de résultat et construction récente, vérifier les bâtiments neufs
        sale_year = None
        if property_data.get("sale_date"):
            try:
                sale_year = datetime.strptime(property_data["sale_date"], "%d/%m/%Y").year
            except ValueError:
                pass
        
        if not best_match and sale_year and sale_year >= 2021:
            new_dpe_results = await self.query_dpe_api(insee_code, self.NEW_BUILDINGS_API)
            best_match = self.find_best_dpe_match(property_address, new_dpe_results)
        
        # Enrichir les données de la propriété
        if best_match:
            property_data["dpe_number"] = best_match.get("N°DPE")
            property_data["dpe_date"] = best_match.get("Date_réception_DPE")
            property_data["dpe_energy_class"] = best_match.get("Etiquette_DPE")
            property_data["dpe_ges_class"] = best_match.get("Etiquette_GES")
            
            if best_match.get("Année_construction"):
                try:
                    property_data["construction_year"] = int(best_match["Année_construction"])
                except ValueError:
                    pass
        
        return property_data
```

## Limites et bonnes pratiques

- Quota: Respect du rate limiting (5 requêtes par seconde maximum)
- Taille des requêtes: Demander uniquement les champs nécessaires
- Cache local: Stocker les résultats par code INSEE pour éviter des requêtes répétées
- Timeout: Prévoir un timeout d'au moins 60 secondes pour les grandes communes

## Gestion des erreurs

- Les erreurs de connexion doivent être gérées avec des retries (backoff exponentiel)
- En cas d'indisponibilité prolongée, prévoir un fallback vers des données locales
- Monitorer le taux de succès des enrichissements DPE
