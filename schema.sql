-- TrackImmo Reference Schema
-- Based on Rovis91's Project Database Structure
-- This file provides a reference for key tables and their relationships that can be adapted for the TrackImmo project

-- Enums
CREATE TYPE property_type_enum AS ENUM ('house', 'apartment', 'land', 'commercial', 'other');
CREATE TYPE subscription_type_enum AS ENUM ('decouverte', 'pro', 'entreprise');
CREATE TYPE user_role_enum AS ENUM ('admin', 'user');
CREATE TYPE address_status_enum AS ENUM ('new', 'contacted', 'meeting', 'negotiation', 'sold', 'mandate');
CREATE TYPE dpe_class_enum AS ENUM ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'N');
CREATE TYPE sale_horizon_option_enum AS ENUM ('3 mois', '6 mois', '9 mois', '1 an');
CREATE TYPE follow_up_option_enum AS ENUM ('1m', '3m', '6m', '1y');
CREATE TYPE heating_type_option_enum AS ENUM ('electric', 'gas', 'oil', 'wood', 'district');
CREATE TYPE client_status_enum AS ENUM ('active', 'inactive', 'test', 'pending');
CREATE TYPE property_condition_enum AS ENUM ('needs_refreshment', 'average', 'good_condition', 'renovated');
CREATE TYPE exterior_feature_enum AS ENUM ('garden', 'terrace', 'balcony');

-- Cities Table: Stores information about cities
CREATE TABLE cities (
    city_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    postal_code VARCHAR NOT NULL CHECK (postal_code ~ '^\\d{5}$'),
    insee_code VARCHAR NOT NULL UNIQUE CHECK (insee_code ~ '^\\d{5}$'),
    region VARCHAR,
    department VARCHAR NOT NULL CHECK (department ~ '^\\d{2,3}$'),
    last_scraped TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    house_price_avg INTEGER,
    apartment_price_avg INTEGER
);

-- Clients Table: Stores information about clients/users
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
    first_report_date DATE,
    last_updated TIMESTAMP
);

-- Secondary Users Table: For Enterprise plans with multiple users
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

-- Addresses Table: Stores property information
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

-- Client_Addresses Table: Junction table that also stores client-specific property tracking data
CREATE TABLE client_addresses (
  client_id UUID NOT NULL,
  address_id UUID NOT NULL,
  send_date TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  validation BOOLEAN DEFAULT false,
  status address_status_enum DEFAULT 'new'::address_status_enum,
  notes TEXT,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  owner_name VARCHAR(255),
  owner_phone VARCHAR(20),
  owner_email VARCHAR(255),
  is_owner_occupant BOOLEAN,
  contact_date DATE,
  potential_interest_in_selling BOOLEAN,
  sale_horizon sale_horizon_option_enum,
  desired_price NUMERIC(10, 2),
  travaux_effectue BOOLEAN,
  travaux_necessaire BOOLEAN,
  required_renovations TEXT,
  estimation_travaux NUMERIC(10, 2),
  dpe_energy_class dpe_class_enum,
  dpe_ges_class dpe_class_enum,
  is_archived BOOLEAN DEFAULT false,
  client_address_id UUID NOT NULL DEFAULT gen_random_uuid(),
  is_rented BOOLEAN,
  accord_estimation BOOLEAN,
  follow_up follow_up_option_enum,
  rental_yield NUMERIC(5, 2),
  heating_type heating_type_option_enum,
  floor INTEGER,
  has_elevator BOOLEAN,
  has_parking BOOLEAN,
  construction_year INTEGER,
  last_renovation_year INTEGER,
  contact_established BOOLEAN,
  property_condition property_condition_enum,
  exterior_features exterior_feature_enum[],
  CONSTRAINT client_addresses_pkey PRIMARY KEY (client_id, address_id, client_address_id),
  CONSTRAINT client_addresses_client_address_id_key UNIQUE (client_address_id),
  CONSTRAINT client_addresses_client_id_fkey FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE,
  CONSTRAINT client_addresses_address_id_fkey FOREIGN KEY (address_id) REFERENCES addresses(address_id) ON DELETE CASCADE,
  CONSTRAINT client_addresses_floor_check CHECK ((floor IS NULL) OR (floor >= 0)),
  CONSTRAINT client_addresses_last_renovation_year_check CHECK (
    (last_renovation_year IS NULL) OR 
    ((last_renovation_year >= construction_year) AND 
     (last_renovation_year::numeric <= EXTRACT(year FROM CURRENT_DATE)))
  ),
  CONSTRAINT client_addresses_owner_email_check CHECK (
    (owner_email IS NULL) OR 
    (owner_email::text ~* '^[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$'::text)
  ),
  CONSTRAINT client_addresses_owner_phone_check CHECK (
    (owner_phone IS NULL) OR 
    (owner_phone::text ~ '^\+?[0-9\s-]{8,20}$'::text)
  ),
  CONSTRAINT client_addresses_rental_yield_check CHECK (
    (rental_yield IS NULL) OR (rental_yield >= 0::numeric)
  ),
  CONSTRAINT client_addresses_construction_year_check CHECK (
    (construction_year IS NULL) OR 
    ((construction_year > 1000) AND 
     (construction_year::numeric <= EXTRACT(year FROM CURRENT_DATE)))
  ),
  CONSTRAINT client_addresses_desired_price_check CHECK (
    (desired_price IS NULL) OR (desired_price >= 0::numeric)
  ),
  CONSTRAINT client_addresses_estimation_travaux_check CHECK (
    (estimation_travaux IS NULL) OR (estimation_travaux >= 0::numeric)
  )
);

-- DPE Table: Energy performance diagnostics for properties
CREATE TABLE dpe (
    dpe_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address_id UUID NOT NULL REFERENCES addresses(address_id),
    department VARCHAR NOT NULL,
    construction_year SMALLINT CHECK (construction_year >= 1800 AND construction_year <= EXTRACT(year FROM CURRENT_DATE)),
    dpe_date DATE NOT NULL,
    dpe_energy_class dpe_class_enum NOT NULL,
    dpe_ges_class dpe_class_enum,
    dpe_number VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Row Level Security (RLS) Policies
-- These should be implemented to secure data access

-- For clients table
CREATE POLICY "Clients can view their own data" ON clients
    FOR SELECT USING (auth.uid() = client_id);

CREATE POLICY "Clients can update their own data" ON clients
    FOR UPDATE USING (auth.uid() = client_id);

-- For client_addresses table
CREATE POLICY "Clients can view their own addresses" ON client_addresses
    FOR SELECT USING (auth.uid() = client_id);

CREATE POLICY "Clients can update their own addresses" ON client_addresses
    FOR UPDATE USING (auth.uid() = client_id);

CREATE POLICY "Clients can insert their own addresses" ON client_addresses
    FOR INSERT WITH CHECK (auth.uid() = client_id);

-- For addresses table
CREATE POLICY "Clients can view addresses linked to them" ON addresses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM client_addresses 
            WHERE client_addresses.address_id = addresses.address_id 
            AND client_addresses.client_id = auth.uid()
        )
    );

-- Enable Row Level Security on all tables
ALTER TABLE cities ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE addresses ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_addresses ENABLE ROW LEVEL SECURITY;
ALTER TABLE dpe ENABLE ROW LEVEL SECURITY;
ALTER TABLE secondary_users ENABLE ROW LEVEL SECURITY;

-- Functions and Triggers

-- Timestamp update function for tracking record modifications
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = current_timestamp;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updating timestamps
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

CREATE TRIGGER update_secondary_users_timestamp
BEFORE UPDATE ON secondary_users
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Function to find or create cities by name and postal code
CREATE OR REPLACE FUNCTION find_or_create_cities(city_names text[], postal_codes text[], departments text[] DEFAULT NULL::text[])
RETURNS uuid[]
LANGUAGE plpgsql
SECURITY DEFINER
AS $function$
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
$function$;

-- Function to get client properties
CREATE OR REPLACE FUNCTION get_client_addresses_before_date(
  client_uuid UUID,
  before_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
  client_address_id UUID,
  address_id UUID,
  address_raw VARCHAR,
  department VARCHAR,
  city_name VARCHAR,
  postal_code VARCHAR,
  property_type property_type_enum,
  sale_date DATE,
  price INTEGER,
  estimated_price INTEGER,
  surface INTEGER,
  rooms INTEGER,
  status address_status_enum,
  send_date TIMESTAMP,
  validation BOOLEAN,
  notes TEXT,
  owner_name VARCHAR,
  owner_phone VARCHAR,
  owner_email VARCHAR,
  is_owner_occupant BOOLEAN,
  contact_date DATE,
  potential_interest_in_selling BOOLEAN,
  sale_horizon sale_horizon_option_enum,
  desired_price NUMERIC,
  travaux_effectue BOOLEAN,
  travaux_necessaire BOOLEAN,
  required_renovations TEXT,
  estimation_travaux NUMERIC,
  dpe_energy_class dpe_class_enum,
  dpe_ges_class dpe_class_enum,
  is_archived BOOLEAN,
  is_rented BOOLEAN,
  accord_estimation BOOLEAN,
  follow_up follow_up_option_enum,
  rental_yield NUMERIC,
  heating_type heating_type_option_enum,
  floor INTEGER,
  has_elevator BOOLEAN,
  has_parking BOOLEAN,
  construction_year INTEGER,
  last_renovation_year INTEGER,
  contact_established BOOLEAN,
  property_condition property_condition_enum,
  exterior_features exterior_feature_enum[]
)
LANGUAGE SQL
STABLE
AS $$
  SELECT 
    ca.client_address_id,
    a.address_id,
    a.address_raw,
    a.department,
    c.name AS city_name,
    c.postal_code,
    a.property_type,
    a.sale_date,
    a.price,
    a.estimated_price,
    a.surface,
    a.rooms,
    ca.status,
    ca.send_date,
    ca.validation,
    ca.notes,
    ca.owner_name,
    ca.owner_phone,
    ca.owner_email,
    ca.is_owner_occupant,
    ca.contact_date,
    ca.potential_interest_in_selling,
    ca.sale_horizon,
    ca.desired_price,
    ca.travaux_effectue,
    ca.travaux_necessaire,
    ca.required_renovations,
    ca.estimation_travaux,
    ca.dpe_energy_class,
    ca.dpe_ges_class,
    ca.is_archived,
    ca.is_rented,
    ca.accord_estimation,
    ca.follow_up,
    ca.rental_yield,
    ca.heating_type,
    ca.floor,
    ca.has_elevator,
    ca.has_parking,
    ca.construction_year,
    ca.last_renovation_year,
    ca.contact_established,
    ca.property_condition,
    ca.exterior_features
  FROM 
    addresses a
    JOIN client_addresses ca ON a.address_id = ca.address_id
    JOIN cities c ON a.city_id = c.city_id
  WHERE 
    ca.client_id = client_uuid
    AND (before_date IS NULL OR ca.send_date <= before_date)
  ORDER BY 
    ca.send_date DESC;
$$;

-- Function to get client cities
CREATE OR REPLACE FUNCTION get_client_cities(client_uuid UUID)
RETURNS TABLE (
  city_id UUID,
  name VARCHAR,
  postal_code VARCHAR,
  department VARCHAR,
  region VARCHAR,
  house_price_avg INTEGER,
  apartment_price_avg INTEGER
)
LANGUAGE SQL
STABLE
AS $$
  SELECT 
    c.city_id,
    c.name,
    c.postal_code,
    c.department,
    c.region,
    c.house_price_avg,
    c.apartment_price_avg
  FROM 
    cities c
  WHERE 
    c.city_id = ANY(
      SELECT chosen_cities 
      FROM clients 
      WHERE client_id = client_uuid
    )
  ORDER BY 
    c.name;
$$;

-- Function to update client cities
CREATE OR REPLACE FUNCTION update_client_cities(
  client_uuid UUID,
  city_ids UUID[]
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE clients
  SET chosen_cities = city_ids,
      updated_at = now()
  WHERE client_id = client_uuid;
END;
$$;

-- Function to handle new user registration
CREATE OR REPLACE FUNCTION handle_new_user() 
RETURNS TRIGGER 
LANGUAGE plpgsql
SECURITY DEFINER 
AS $$
BEGIN
  INSERT INTO public.clients (
    client_id,
    first_name,
    last_name,
    email,
    status,
    addresses_per_report,
    subscription_type,
    role
  ) VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'first_name', ''),
    COALESCE(NEW.raw_user_meta_data->>'last_name', ''),
    NEW.email,
    'pending',
    10,
    'decouverte',
    'admin'
  );
  
  RETURN NEW;
END;
$$;

-- Create trigger for new user registration
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Function to migrate garden property to exterior features array
CREATE OR REPLACE FUNCTION migrate_garden_to_exterior_features()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  -- Create exterior_features as empty array on all rows
  ALTER TABLE client_addresses 
  ADD COLUMN IF NOT EXISTS exterior_features exterior_feature_enum[] DEFAULT NULL;
  
  -- Update all records that have garden = true
  UPDATE client_addresses
  SET exterior_features = array_append(COALESCE(exterior_features, '{}'::exterior_feature_enum[]), 'garden'::exterior_feature_enum)
  WHERE garden = true;
  
  -- If garden column exists, drop it (optional)
  -- ALTER TABLE client_addresses DROP COLUMN IF EXISTS garden;
END;
$$;

-- Trigger to migrate garden data to exterior_features
CREATE TRIGGER migrate_garden_data
AFTER INSERT OR UPDATE OF garden ON client_addresses
FOR EACH ROW EXECUTE FUNCTION migrate_garden_to_exterior_features();

-- Function to validate additional users exist
CREATE OR REPLACE FUNCTION check_additional_users_exist()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.additional_users IS NOT NULL AND array_length(NEW.additional_users, 1) > 0 THEN
    IF EXISTS (
      SELECT 1 
      FROM unnest(NEW.additional_users) AS user_id 
      LEFT JOIN secondary_users ON unnest.user_id = secondary_users.user_id
      WHERE secondary_users.user_id IS NULL
    ) THEN
      RAISE EXCEPTION 'One or more additional_users do not exist in the secondary_users table';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to validate additional users exist
CREATE TRIGGER validate_additional_users
BEFORE INSERT OR UPDATE ON clients
FOR EACH ROW EXECUTE FUNCTION check_additional_users_exist();

-- Function to update client last_updated timestamp
CREATE OR REPLACE FUNCTION update_client_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    -- When a new client_address is added, update the client's last_updated timestamp
    UPDATE clients
    SET last_updated = NEW.send_date
    WHERE client_id = NEW.client_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update client's last_updated timestamp when an address is modified
CREATE TRIGGER update_client_last_updated_on_address_change
AFTER INSERT OR UPDATE ON client_addresses
FOR EACH ROW EXECUTE FUNCTION update_client_last_updated();

-- Notes for TrackImmo Implementation:
-- 1. This schema supports tracking properties, their owners, and related client activities
-- 2. The client_addresses junction table is central to the application and stores client-specific property data
-- 3. Role-based access control is implemented through user_role_enum and RLS policies
-- 4. Subscription management is integrated with Stripe (stripe_* fields)
-- 5. Support for team functionality through secondary_users for Enterprise subscription
-- 6. Robust tracking of property details including DPE energy ratings
-- 7. Client preferences and property matching capabilities