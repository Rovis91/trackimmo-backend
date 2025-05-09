# Structure de la Base de Données TrackImmo

Ce document détaille le schéma de la base de données PostgreSQL utilisée par TrackImmo, avec toutes les entités, relations et contraintes.

## Vue d'ensemble

La base de données comprend plusieurs tables principales:

1. **clients**: Utilisateurs du système
2. **cities**: Villes et communes
3. **addresses**: Propriétés immobilières
4. **client_addresses**: Association entre clients et propriétés
5. **dpe**: Diagnostics de performance énergétique

## Types d'énumération

```sql
-- Types d'énumération pour contraindre les valeurs possibles
CREATE TYPE property_type_enum AS ENUM ('house', 'apartment', 'land', 'commercial', 'other');
CREATE TYPE subscription_type_enum AS ENUM ('decouverte', 'pro', 'entreprise');
CREATE TYPE user_role_enum AS ENUM ('admin', 'user');
CREATE TYPE address_status_enum AS ENUM ('new', 'contacted', 'meeting', 'negotiation', 'sold', 'mandate');
CREATE TYPE dpe_class_enum AS ENUM ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'N');
CREATE TYPE sale_horizon_option_enum AS ENUM ('3 mois', '6 mois', '9 mois', '1 an');
CREATE TYPE follow_up_option_enum AS ENUM ('1m', '3m', '6m', '1y');
CREATE TYPE heating_type_option_enum AS ENUM ('electric', 'gas', 'oil', 'wood', 'district');
CREATE TYPE client_status_enum AS ENUM ('active', 'inactive', 'test', 'pending');
```

## Schéma détaillé

### Table: cities

```sql
CREATE TABLE cities (
    city_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    postal_code VARCHAR NOT NULL CHECK (postal_code ~ '^\\d{5}$'),
    insee_code VARCHAR NOT NULL UNIQUE CHECK (insee_code ~ '^\\d{5}$'),
    region VARCHAR,
    department VARCHAR NOT NULL CHECK (department ~ '^\\d{2,3}$'),
    last_scraped TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Description**: Stocke les informations sur les villes/communes françaises, utilisées pour le géocodage et l'organisation des propriétés.

**Champs clés**:

- **city_id**: Identifiant unique (UUID)
- **name**: Nom de la ville
- **postal_code**: Code postal (format 5 chiffres)
- **insee_code**: Code INSEE unique (format 5 chiffres)
- **department**: Département (2 ou 3 chiffres)
- **last_scraped**: Date de dernier scraping de cette ville

### Table: clients

```sql
CREATE TABLE clients (
    client_id UUID PRIMARY KEY,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE CHECK (email ~* '^[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$'),
    telephone VARCHAR,
    company_name VARCHAR,
    subscription_type subscription_type_enum,
    status client_status_enum NOT NULL,
    subscription_start_date DATE,
    send_day INTEGER CHECK (send_day >= 1 AND send_day <= 31),
    addresses_per_report INTEGER DEFAULT 0 CHECK (addresses_per_report >= 0),
    template_name VARCHAR,
    info TEXT,
    chosen_cities UUID[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stripe_customer_id VARCHAR,
    stripe_subscription_id VARCHAR,
    stripe_subscription_status VARCHAR,
    stripe_subscription_end_date TIMESTAMP,
    property_type_preferences property_type_enum[] DEFAULT '{}',
    role user_role_enum DEFAULT 'admin',
    additional_users UUID[] DEFAULT '{}',
    company_address VARCHAR,
    first_report_date DATE
);
```

**Description**: Stocke les informations des utilisateurs de l'application, y compris les préférences et détails d'abonnement.

**Champs clés**:

- **client_id**: Identifiant unique (UUID)
- **email**: Email unique avec validation de format
- **subscription_type**: Type d'abonnement (découverte, pro, entreprise)
- **status**: Statut du client (actif, inactif, test, en attente)
- **chosen_cities**: Tableau d'UUID de villes sélectionnées par le client
- **property_type_preferences**: Types de propriétés préférés
- **additional_users**: Pour les abonnements Entreprise, liste d'utilisateurs secondaires

### Table: secondary_users

```sql
CREATE TABLE secondary_users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(client_id),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role user_role_enum DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Description**: Utilisateurs secondaires pour les comptes entreprise.

**Champs clés**:

- **user_id**: Identifiant unique (UUID)
- **client_id**: Référence au client principal
- **role**: Rôle de l'utilisateur (user ou admin)

### Table: addresses

```sql
CREATE TABLE addresses (
    address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department VARCHAR NOT NULL CHECK (department ~ '^\\d{2,3}$'),
    city_id UUID NOT NULL REFERENCES cities(city_id),
    address_raw VARCHAR NOT NULL,
    sale_date DATE NOT NULL,
    property_type property_type_enum NOT NULL,
    surface INTEGER CHECK (surface >= 0),
    rooms INTEGER CHECK (rooms >= 0),
    price INTEGER CHECK (price >= 0),
    immodata_url TEXT,
    dpe_number VARCHAR,
    estimated_price INTEGER,
    geoposition GEOMETRY,
    boundary GEOMETRY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Description**: Stocke les informations sur les propriétés immobilières, y compris les détails physiques et les données de transaction.

**Champs clés**:

- **address_id**: Identifiant unique (UUID)
- **department**: Département (2 ou 3 chiffres)
- **city_id**: Référence à la ville
- **address_raw**: Adresse brute
- **sale_date**: Date de la transaction
- **property_type**: Type de propriété (maison, appartement, terrain, etc.)
- **surface**: Surface en m²
- **rooms**: Nombre de pièces
- **price**: Prix de vente
- **estimated_price**: Prix estimé actuellement
- **geoposition**: Coordonnées géographiques (point)

### Table: client_addresses

```sql
CREATE TABLE client_addresses (
  client_id uuid not null,
  address_id uuid not null,
  send_date timestamp without time zone null default CURRENT_TIMESTAMP,
  validation boolean null default false,
  status public.address_status_enum null default 'new'::address_status_enum,
  notes text null,
  created_at timestamp without time zone null default CURRENT_TIMESTAMP,
  updated_at timestamp without time zone null default CURRENT_TIMESTAMP,
  owner_name character varying(255) null,
  owner_phone character varying(20) null,
  owner_email character varying(255) null,
  is_owner_occupant boolean null,
  contact_date date null,
  potential_interest_in_selling boolean null,
  sale_horizon public.sale_horizon_option_enum null,
  desired_price numeric(10, 2) null,
  travaux_effectue boolean null,
  travaux_necessaire boolean null,
  required_renovations text null,
  estimation_travaux numeric(10, 2) null,
  dpe_energy_class public.dpe_class_enum null,
  dpe_ges_class public.dpe_class_enum null,
  is_archived boolean null default false,
  client_address_id uuid not null default gen_random_uuid (),
  is_rented boolean null,
  accord_estimation boolean null,
  follow_up public.follow_up_option_enum null,
  rental_yield numeric(5, 2) null,
  heating_type public.heating_type_option_enum null,
  floor integer null,
  has_elevator boolean null,
  has_parking boolean null,
  construction_year integer null,
  last_renovation_year integer null,
  contact_established boolean null,
  property_condition public.property_condition_enum null,
  exterior_features exterior_feature_enum[] null,
  constraint client_addresses_pkey primary key (client_id, address_id, client_address_id),
  constraint client_addresses_client_address_id_key unique (client_address_id),
  constraint client_addresses_client_id_fkey foreign KEY (client_id) references clients (client_id) on delete CASCADE,
  constraint client_addresses_address_id_fkey foreign KEY (address_id) references addresses (address_id) on delete CASCADE
);
```

**Description**: Table de jonction qui associe les clients aux adresses avec des informations de suivi commercial.

**Champs clés**:

- **client_id, address_id**: Clés étrangères vers clients et addresses
- **status**: Statut du suivi (nouveau, contacté, rendez-vous, négociation, vendu, mandat)
- **notes**: Notes du client sur la propriété
- **owner_name, owner_phone, owner_email**: Informations sur le propriétaire
- **potential_interest_in_selling**: Intérêt potentiel du propriétaire à vendre
- **dpe_energy_class, dpe_ges_class**: Classes énergétiques
- **is_archived**: Indique si l'adresse est archivée pour ce client

### Table: dpe

```sql
CREATE TABLE dpe (
    dpe_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address_id UUID NOT NULL REFERENCES addresses(address_id),
    department VARCHAR NOT NULL,
    construction_year SMALLINT CHECK (construction_year >= 1800 AND construction_year <= EXTRACT(year FROM CURRENT_DATE)),
    dpe_date DATE NOT NULL,
    dpe_energy_class dpe_class_enum NOT NULL,
    dpe_ges_class dpe_class_enum NOT NULL,
    dpe_number VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Description**: Stocke les informations de diagnostic de performance énergétique pour les propriétés.

**Champs clés**:

- **dpe_id**: Identifiant unique (UUID)
- **address_id**: Référence à la propriété
- **construction_year**: Année de construction
- **dpe_energy_class**: Classe énergétique (A-G)
- **dpe_ges_class**: Classe d'émission de gaz à effet de serre (A-G)
- **dpe_number**: Numéro unique du DPE

## Relations principales

- **clients ↔ addresses**: Relation many-to-many via client_addresses
- **cities ↔ addresses**: Relation one-to-many (une ville a plusieurs adresses)
- **addresses ↔ dpe**: Relation one-to-one (une adresse a un DPE)
- **clients ↔ secondary_users**: Relation one-to-many (un client peut avoir plusieurs utilisateurs secondaires)
- **clients ↔ cities**: Relation many-to-many via le tableau chosen_cities

## Indexation

```sql
CREATE INDEX idx_client_addresses_client_id ON client_addresses(client_id);
CREATE INDEX idx_client_addresses_address_id ON client_addresses(address_id);
CREATE INDEX idx_client_addresses_status ON client_addresses(status);
CREATE INDEX idx_addresses_city_id ON addresses(city_id);
CREATE INDEX idx_addresses_property_type ON addresses(property_type);
CREATE INDEX idx_addresses_geoposition ON addresses USING GIST(geoposition);
CREATE INDEX idx_cities_postal_code ON cities(postal_code);
CREATE INDEX idx_cities_insee_code ON cities(insee_code);
CREATE INDEX idx_secondary_users_client_id ON secondary_users(client_id);
```

Des index sont définis pour optimiser les requêtes courantes sur:

- L'association client-adresse
- La recherche d'adresses par ville
- Le filtrage par type de propriété
- La recherche spatiale (index GiST)
- La recherche de villes par code postal ou INSEE

## Sécurité au niveau des lignes (RLS)

La base de données utilise Row Level Security pour garantir que les clients ne peuvent accéder qu'à leurs propres données:

```sql
-- For clients table
CREATE POLICY "Clients can view their own data" ON clients
    FOR SELECT USING (auth.uid() = client_id);

-- For client_addresses table
CREATE POLICY "Clients can view their own addresses" ON client_addresses
    FOR SELECT USING (auth.uid() = client_id);

-- For addresses table
CREATE POLICY "Clients can view addresses linked to them" ON addresses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM client_addresses 
            WHERE client_addresses.address_id = addresses.address_id 
            AND client_addresses.client_id = auth.uid()
        )
    );
```

## Fonctions utiles

### update_timestamp()

```sql
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = CURRENT_TIMESTAMP;
   RETURN NEW;
END;
$$ language 'plpgsql';
```

Fonction utilisée par les triggers pour mettre à jour automatiquement le champ updated_at.

### find_or_create_cities()

```sql
CREATE OR REPLACE FUNCTION find_or_create_cities(
  city_names text[],
  postal_codes text[],
  departments text[] DEFAULT NULL
)
RETURNS uuid[] 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result_ids uuid[];
  i integer;
  city_id uuid;
  curr_dept text;
  array_length_check integer;
BEGIN
  -- Validation des entrées
  IF city_names IS NULL OR postal_codes IS NULL THEN
    RAISE EXCEPTION 'city_names and postal_codes cannot be null';
  END IF;
  
  array_length_check := array_length(city_names, 1);
  IF array_length_check IS NULL OR array_length_check = 0 THEN
    RETURN '{}'::uuid[];
  END IF;
  
  IF array_length(postal_codes, 1) != array_length_check THEN
    RAISE EXCEPTION 'city_names and postal_codes arrays must have the same length';
  END IF;
  
  -- Initialize result array
  result_ids := '{}'::uuid[];
  
  -- Process each city
  FOR i IN 1..array_length_check LOOP
    -- Skip invalid entries
    IF city_names[i] IS NULL OR postal_codes[i] IS NULL THEN
      result_ids := array_append(result_ids, NULL);
      CONTINUE;
    END IF;
    
    -- Check if city already exists
    SELECT c.city_id INTO city_id
    FROM public.cities c
    WHERE LOWER(c.name) = LOWER(city_names[i]) AND c.postal_code = postal_codes[i];
    
    -- If city doesn't exist, create it
    IF city_id IS NULL THEN
      -- Determine department from postal code if not provided
      IF departments IS NULL OR departments[i] IS NULL THEN
        curr_dept := substring(postal_codes[i] from 1 for 2);
      ELSE
        curr_dept := departments[i];
      END IF;
      
      -- Create new city
      BEGIN
        INSERT INTO public.cities (
          name, 
          postal_code, 
          insee_code, 
          department,
          region,
          created_at,
          updated_at
        ) 
        VALUES (
          city_names[i], 
          postal_codes[i], 
          postal_codes[i], -- Temporary value as insee_code
          curr_dept,
          NULL,
          now(),
          now()
        )
        RETURNING cities.city_id INTO city_id;
      EXCEPTION WHEN unique_violation THEN
        -- Handle potential race condition - try to fetch again
        SELECT c.city_id INTO city_id
        FROM public.cities c
        WHERE LOWER(c.name) = LOWER(city_names[i]) AND c.postal_code = postal_codes[i];
        
        -- If still NULL, something's wrong
        IF city_id IS NULL THEN
          RAISE EXCEPTION 'Could not retrieve or create city: % (%)', city_names[i], postal_codes[i];
        END IF;
      END;
    END IF;
    
    -- Add to result array
    result_ids := array_append(result_ids, city_id);
  END LOOP;
  
  RETURN result_ids;
END;
$$;
```

Fonction qui trouve ou crée des villes par nom et code postal.

### calculate_property_roi()

```sql
CREATE OR REPLACE FUNCTION calculate_property_roi(
    property_price NUMERIC,
    estimated_rental_income NUMERIC,
    estimated_expenses NUMERIC,
    renovation_cost NUMERIC DEFAULT 0
)
RETURNS NUMERIC AS $$
DECLARE
    total_investment NUMERIC;
    annual_net_income NUMERIC;
    roi NUMERIC;
BEGIN
    total_investment := property_price + renovation_cost;
    annual_net_income := estimated_rental_income - estimated_expenses;
    
    IF total_investment = 0 THEN
        RETURN 0;
    END IF;
    
    roi := (annual_net_income / total_investment) * 100;
    RETURN ROUND(roi::numeric, 2);
END;
$$ LANGUAGE plpgsql;
```

Fonction qui calcule le retour sur investissement pour une propriété.

## Triggers

Des triggers sont définis pour diverses opérations automatiques:

```sql
CREATE TRIGGER update_clients_timestamp
BEFORE UPDATE ON clients
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_addresses_timestamp
BEFORE UPDATE ON addresses
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_client_addresses_timestamp
BEFORE UPDATE ON client_addresses
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_cities_timestamp
BEFORE UPDATE ON cities
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_dpe_timestamp
BEFORE UPDATE ON dpe
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER create_client_table_on_insert
    AFTER INSERT ON clients
    FOR EACH ROW
    EXECUTE FUNCTION create_client_table_trigger();

CREATE TRIGGER drop_client_table_on_delete
    BEFORE DELETE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION drop_client_table_trigger();
```

## Notes techniques

- La base de données utilise PostgreSQL avec l'extension PostGIS pour les données spatiales
- L'authentification et les permissions sont gérées via Row Level Security
- Les clients peuvent avoir accès à plusieurs villes via un tableau d'UUIDs
- Les types énumérés garantissent l'intégrité des valeurs possibles
- Les contraintes CHECK garantissent la validité des données (formats d'email, codes postaux, etc.)
