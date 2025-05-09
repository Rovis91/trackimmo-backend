# Documentation de l'API TrackImmo

Cette documentation détaille les endpoints de l'API TrackImmo, leur utilisation et les formats de données.

## Base URL

L'API est accessible à l'URL de base:

``` txt
https://api.trackimmo.app/v1
```

## Authentification

L'API utilise une authentification par token JWT. Le token doit être inclus dans l'en-tête HTTP `Authorization`:

``` txt
Authorization: Bearer <votre_token>
```

Pour obtenir un token, utilisez l'endpoint `/auth/token`.

## Format des réponses

Toutes les réponses sont au format JSON avec une structure standard:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

En cas d'erreur:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Description de l'erreur"
  }
}
```

## Endpoints

### Auth

#### POST /auth/token

Génère un token d'authentification.

**Corps de la requête**:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Réponse**:

```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": "2023-12-31T23:59:59Z"
  },
  "error": null
}
```

### Traitement de villes

#### POST /process/city

Déclenche le processus complet (scraping, enrichissement, intégration DB) pour une ville.

**Corps de la requête**:

```json
{
  "city_name": "Paris",
  "postal_code": "75001",
  "property_types": ["house", "apartment"],
  "start_date": "01/2023",
  "end_date": "12/2023"
}
```

**Réponse**:

```json
{
  "success": true,
  "data": {
    "job_id": "5f7b5c9e-7b1a-4c3e-9b0a-8c1c9e9c9b9c",
    "status": "queued",
    "estimated_time": 3600
  },
  "error": null
}
```

#### GET /process/status/{job_id}

Récupère le statut d'un job de traitement.

**Réponse**:

```json
{
  "success": true,
  "data": {
    "job_id": "5f7b5c9e-7b1a-4c3e-9b0a-8c1c9e9c9b9c",
    "status": "running",
    "progress": 45,
    "created_at": "2023-06-01T10:35:12Z",
    "updated_at": "2023-06-01T11:15:45Z",
    "current_stage": "enrichment",
    "stages_completed": ["scraping"],
    "stages_pending": ["enrichment", "database"],
    "errors": []
  },
  "error": null
}
```

#### GET /process/history

Récupère l'historique des jobs de traitement.

**Paramètres**:

- **limit** (optionnel): Nombre maximum de résultats (défaut: 20)
- **offset** (optionnel): Décalage pour pagination (défaut: 0)
- **status** (optionnel): Filtre par statut (completed, failed, running, queued)

**Réponse**:

```json
{
  "success": true,
  "data": {
    "count": 15,
    "total": 30,
    "jobs": [
      {
        "job_id": "5f7b5c9e-7b1a-4c3e-9b0a-8c1c9e9c9b9c",
        "city_name": "Paris",
        "postal_code": "75001",
        "status": "completed",
        "created_at": "2023-06-01T10:35:12Z",
        "completed_at": "2023-06-01T11:35:42Z",
        "properties_found": 128
      },
      // ... autres jobs
    ]
  },
  "error": null
}
```

### Gestion des clients

#### GET /clients/{client_id}/properties

Récupère les propriétés associées à un client.

**Paramètres**:

- **status** (optionnel): Filtre par statut (new, contacted, meeting, negotiation, sold, mandate)
- **property_type** (optionnel): Filtre par type de propriété
- **limit** (optionnel): Nombre maximum de résultats (défaut: 50)
- **offset** (optionnel): Décalage pour pagination (défaut: 0)

**Réponse**:

```json
{
  "success": true,
  "data": {
    "count": 15,
    "total": 32,
    "properties": [
      {
        "address_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "address": "123 Rue de Paris",
        "city": "Paris",
        "postal_code": "75001",
        "property_type": "apartment",
        "surface": 85,
        "rooms": 3,
        "price": 450000,
        "estimated_price": 470000,
        "status": "new",
        "dpe_energy_class": "C",
        "dpe_ges_class": "D",
        "sale_date": "15/03/2023",
        "coordinates": {
          "latitude": 48.8566,
          "longitude": 2.3522
        }
      },
      // ... autres propriétés
    ]
  },
  "error": null
}
```

#### PATCH /clients/{client_id}/properties/{property_id}

Met à jour le statut d'une propriété pour un client.

**Corps de la requête**:

```json
{
  "status": "contacted",
  "notes": "Premier contact établi par téléphone",
  "owner_name": "Jean Dupont",
  "owner_phone": "+33612345678",
  "owner_email": "jean.dupont@example.com"
}
```

**Réponse**:

```json
{
  "success": true,
  "data": {
    "property_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "contacted",
    "updated_at": "2023-06-05T14:22:18Z"
  },
  "error": null
}
```

### Gestion des villes

#### GET /cities

Récupère la liste des villes disponibles.

**Paramètres**:

- **search** (optionnel): Terme de recherche
- **department** (optionnel): Filtre par département
- **limit** (optionnel): Nombre maximum de résultats (défaut: 50)
- **offset** (optionnel): Décalage pour pagination (défaut: 0)

**Réponse**:

```json
{
  "success": true,
  "data": {
    "count": 15,
    "total": 36125,
    "cities": [
      {
        "city_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "Paris",
        "postal_code": "75001",
        "insee_code": "75101",
        "department": "75",
        "region": "Île-de-France",
        "property_count": 1245,
        "last_scraped": "2023-05-15T09:30:00Z"
      },
      // ... autres villes
    ]
  },
  "error": null
}
```

#### POST /cities

Ajoute une nouvelle ville au système.

**Corps de la requête**:

```json
{
  "name": "Marseille",
  "postal_code": "13001",
  "insee_code": "13201",
  "department": "13",
  "region": "Provence-Alpes-Côte d'Azur"
}
```

**Réponse**:

```json
{
  "success": true,
  "data": {
    "city_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "Marseille",
    "postal_code": "13001",
    "created_at": "2023-06-05T14:30:22Z"
  },
  "error": null
}
```

### Statistiques

#### GET /statistics/global

Récupère des statistiques globales du système.

**Réponse**:

```json
{
  "success": true,
  "data": {
    "properties": {
      "total": 324500,
      "by_type": {
        "apartment": 210365,
        "house": 98231,
        "land": 12640,
        "commercial": 3264
      }
    },
    "cities": {
      "total": 5426,
      "by_department": {
        "75": 20,
        "92": 36,
        "93": 40,
        // ... autres départements
      }
    },
    "clients": {
      "total": 128,
      "by_subscription": {
        "decouverte": 45,
        "pro": 65,
        "entreprise": 18
      }
    }
  },
  "error": null
}
```

#### GET /statistics/client/{client_id}

Récupère des statistiques spécifiques à un client.

**Réponse**:

``` json
{
  "success": true,
  "data": {
    "properties": {
      "total": 521,
      "by_status": {
        "new": 320,
        "contacted": 86,
        "meeting": 35,
        "negotiation": 12,
        "sold": 48,
        "mandate": 20
      }
    },
    "activity": {
      "last_30_days": {
        "properties_added": 45,
        "status_changes": 28
      },
      "conversion_rate": 0.15
    }
  },
  "error": null
}
```

## Codes d'erreur

- **AUTH_REQUIRED**: Authentification requise
- **INVALID_CREDENTIALS**: Identifiants invalides
- **PERMISSION_DENIED**: Permissions insuffisantes
- **RESOURCE_NOT_FOUND**: Ressource non trouvée
- **INVALID_REQUEST**: Requête invalide
- **VALIDATION_ERROR**: Erreur de validation des données
- **RATE_LIMITED**: Limite de requêtes atteinte
- **SERVER_ERROR**: Erreur serveur interne

## Modèles de données

### Propriété (Property)

```json
{
  "address_id": "UUID",
  "address_raw": "string",
  "city_id": "UUID",
  "city_name": "string",
  "postal_code": "string",
  "property_type": "string (apartment, house, land, commercial, other)",
  "surface": "number",
  "rooms": "number",
  "price": "number",
  "sale_date": "string (DD/MM/YYYY)",
  "estimated_price": "number",
  "latitude": "number",
  "longitude": "number",
  "dpe_energy_class": "string (A-G)",
  "dpe_ges_class": "string (A-G)",
  "construction_year": "number",
  "created_at": "string (ISO date)",
  "updated_at": "string (ISO date)"
}
```

### Client

```json
{
  "client_id": "UUID",
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "telephone": "string",
  "company_name": "string",
  "subscription_type": "string (decouverte, pro, entreprise)",
  "status": "string (active, inactive, test, pending)",
  "chosen_cities": ["UUID"],
  "property_type_preferences": ["string"],
  "created_at": "string (ISO date)",
  "updated_at": "string (ISO date)"
}
```

### Ville (City)

```json
{
  "city_id": "UUID",
  "name": "string",
  "postal_code": "string",
  "insee_code": "string",
  "department": "string",
  "region": "string",
  "last_scraped": "string (ISO date)",
  "created_at": "string (ISO date)",
  "updated_at": "string (ISO date)"
}
```

### Association Client-Adresse

```json
{
  "client_id": "UUID",
  "address_id": "UUID",
  "status": "string (new, contacted, meeting, negotiation, sold, mandate)",
  "send_date": "string (ISO date)",
  "validation": "boolean",
  "notes": "string",
  "owner_name": "string",
  "owner_phone": "string",
  "owner_email": "string",
  "created_at": "string (ISO date)",
  "updated_at": "string (ISO date)"
}
```

## Pagination

La pagination est standardisée à travers l'API:

- **limit**: Nombre maximum d'éléments à retourner
- **offset**: Nombre d'éléments à sauter
- **count**: Nombre d'éléments retournés
- **total**: Nombre total d'éléments disponibles

## Versions de l'API

La version actuelle est v1. La version est spécifiée dans l'URL:

``` txt
https://api.trackimmo.app/v1/...
```

Les changements majeurs seront introduits dans de nouvelles versions, tandis que les changements mineurs et correctifs seront appliqués aux versions existantes.
