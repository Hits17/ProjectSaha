-- Migration: raw materials secondary marketplace (2026-06-10)
-- Apply to an existing database:
--   psql "postgresql://saha:<password>@localhost:5432/saha" -f 2026-06-10-raw-materials.sql
-- Fresh installs get this automatically via init-scripts/01-schema.sql.

CREATE TYPE material_status AS ENUM ('active', 'paused', 'archived');

CREATE TABLE raw_material_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    seller_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    price_per_unit DECIMAL(12, 2) NOT NULL CHECK (price_per_unit > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    min_order_quantity DECIMAL(12, 2),
    monthly_capacity VARCHAR(255),
    lead_time_days INTEGER,
    status material_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_raw_materials_seller_id ON raw_material_listings(seller_id);
CREATE INDEX idx_raw_materials_status ON raw_material_listings(status);
CREATE INDEX idx_raw_materials_category ON raw_material_listings(category);
CREATE INDEX idx_raw_materials_region ON raw_material_listings(region);
CREATE INDEX idx_raw_materials_country ON raw_material_listings(country);
