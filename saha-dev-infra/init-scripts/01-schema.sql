-- Saha Platform — Initial Schema
-- Runs automatically on first PostgreSQL container start

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- LAYER 1: IDENTITY
-- ============================================================

CREATE TYPE user_role AS ENUM ('creator', 'manufacturer', 'legal', 'admin');
CREATE TYPE kyc_status AS ENUM ('pending', 'in_review', 'verified', 'rejected');
CREATE TYPE kyb_status AS ENUM ('pending', 'in_review', 'verified', 'rejected');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'creator',
    kyc_status kyc_status NOT NULL DEFAULT 'pending',
    kyc_inquiry_id VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    -- Account protection (enterprise auth hardening, 2026-07-01)
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    email_verified_at TIMESTAMPTZ,
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    mfa_secret VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE enterprises (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    registration_number VARCHAR(255),
    country VARCHAR(100) NOT NULL,
    kyb_status kyb_status NOT NULL DEFAULT 'pending',
    kyb_reference VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE enterprise_members (
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_owner BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (enterprise_id, user_id)
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    family_id UUID NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_family_id ON refresh_tokens(family_id);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    ai_provider VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- ============================================================
-- LAYER 2: DISCOVERY — IP LISTINGS
-- ============================================================

CREATE TYPE listing_status AS ENUM ('draft', 'ai_generating', 'review', 'published', 'archived');

CREATE TABLE ip_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    creator_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    product_category VARCHAR(255),
    tags TEXT[] DEFAULT '{}',
    equipment_requirements TEXT[] DEFAULT '{}',
    batch_size_definition VARCHAR(500),
    public_description TEXT,
    status listing_status NOT NULL DEFAULT 'draft',
    view_count INTEGER NOT NULL DEFAULT 0,
    qdrant_point_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ip_listings_creator_id ON ip_listings(creator_id);
CREATE INDEX idx_ip_listings_status ON ip_listings(status);
CREATE INDEX idx_ip_listings_tags ON ip_listings USING GIN(tags);

CREATE TABLE bom_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID NOT NULL REFERENCES ip_listings(id) ON DELETE CASCADE,
    material_name VARCHAR(255) NOT NULL,
    specification TEXT,
    quantity_per_unit DECIMAL(15, 6) NOT NULL,
    unit_of_measure VARCHAR(50) NOT NULL,
    shelf_life_days INTEGER,
    procurement_cadence VARCHAR(20) CHECK (procurement_cadence IN ('weekly', 'monthly', 'quarterly')),
    is_critical BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_bom_items_listing_id ON bom_items(listing_id);

CREATE TABLE ip_vault_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID NOT NULL REFERENCES ip_listings(id) ON DELETE CASCADE,
    storage_key VARCHAR(1000) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    content_type VARCHAR(255),
    encryption_key_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_vault_assets_listing_id ON ip_vault_assets(listing_id);

CREATE TABLE demand_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    parsed_intent JSONB,
    result_count INTEGER NOT NULL DEFAULT 0,
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_demand_signals_created_at ON demand_signals(created_at);

-- ============================================================
-- LAYER 3: NEGOTIATION
-- ============================================================

CREATE TYPE proposal_status AS ENUM (
    'draft', 'submitted', 'nda_pending', 'nda_signed',
    'negotiating', 'accepted', 'rejected', 'withdrawn'
);

CREATE TABLE proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID NOT NULL REFERENCES ip_listings(id),
    buyer_id UUID NOT NULL REFERENCES users(id),
    seller_id UUID NOT NULL REFERENCES users(id),
    status proposal_status NOT NULL DEFAULT 'draft',
    offer_amount_usd DECIMAL(15, 2),
    license_type VARCHAR(100),
    territory VARCHAR(255),
    duration_months INTEGER,
    ai_draft_used BOOLEAN NOT NULL DEFAULT false,
    nda_docusign_envelope_id VARCHAR(255),
    nda_signed_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_proposals_listing_id ON proposals(listing_id);
CREATE INDEX idx_proposals_buyer_id ON proposals(buyer_id);
CREATE INDEX idx_proposals_seller_id ON proposals(seller_id);
CREATE INDEX idx_proposals_status ON proposals(status);

CREATE TABLE proposal_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    offer_amount_usd DECIMAL(15, 2),
    license_type VARCHAR(100),
    territory VARCHAR(255),
    duration_months INTEGER,
    proposed_by_id UUID NOT NULL REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id),
    encrypted_content BYTEA NOT NULL,
    is_blocked BOOLEAN NOT NULL DEFAULT false,
    block_reason VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_messages_proposal_id ON messages(proposal_id);
CREATE INDEX idx_messages_sender_id ON messages(sender_id);

-- ============================================================
-- LAYER 4: LEGAL
-- ============================================================

CREATE TYPE transaction_status AS ENUM (
    'pending_legal', 'contract_drafting', 'contract_review',
    'signing_pending', 'signed', 'escrow_pending', 'escrow_funded',
    'disbursement_pending', 'completed', 'disputed', 'cancelled'
);

CREATE TABLE law_firm_partners (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    jurisdictions TEXT[] DEFAULT '{}',
    contact_email VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES proposals(id),
    listing_id UUID NOT NULL REFERENCES ip_listings(id),
    buyer_id UUID NOT NULL REFERENCES users(id),
    seller_id UUID NOT NULL REFERENCES users(id),
    law_firm_id UUID REFERENCES law_firm_partners(id),
    status transaction_status NOT NULL DEFAULT 'pending_legal',
    deal_value_usd DECIMAL(15, 2) NOT NULL,
    saha_commission_usd DECIMAL(15, 2),
    legal_fee_usd DECIMAL(15, 2),
    escrow_fee_usd DECIMAL(15, 2),
    deal_summary JSONB,
    contract_docusign_envelope_id VARCHAR(255),
    contract_storage_key VARCHAR(1000),
    stripe_payment_intent_id VARCHAR(255),
    escrow_funded_at TIMESTAMPTZ,
    disbursed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_transactions_proposal_id ON transactions(proposal_id);
CREATE INDEX idx_transactions_buyer_id ON transactions(buyer_id);
CREATE INDEX idx_transactions_seller_id ON transactions(seller_id);
CREATE INDEX idx_transactions_status ON transactions(status);

CREATE TABLE disbursements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID NOT NULL REFERENCES transactions(id),
    ip_holder_amount_usd DECIMAL(15, 2) NOT NULL,
    saha_commission_usd DECIMAL(15, 2) NOT NULL,
    legal_fee_usd DECIMAL(15, 2) NOT NULL,
    escrow_fee_usd DECIMAL(15, 2) NOT NULL,
    stripe_transfer_ids JSONB,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- LAYER 5: SETTLEMENT — REVIEWS
-- ============================================================

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID NOT NULL REFERENCES transactions(id),
    reviewer_id UUID NOT NULL REFERENCES users(id),
    reviewee_id UUID NOT NULL REFERENCES users(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_reviews_reviewee_id ON reviews(reviewee_id);

-- ============================================================
-- LAYER 6: SECONDARY MARKETPLACE — RAW MATERIALS
-- ============================================================

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

-- ============================================================
-- LAYER 7: SOCIAL — IP R&D COMMUNITIES + GROUP CHAT
-- ============================================================

CREATE TYPE community_visibility AS ENUM ('public', 'private');
CREATE TYPE membership_role AS ENUM ('owner', 'moderator', 'member');

CREATE TABLE communities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(140) UNIQUE NOT NULL,
    description TEXT,
    topic VARCHAR(80) NOT NULL,
    visibility community_visibility NOT NULL DEFAULT 'public',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_communities_topic ON communities(topic);
CREATE INDEX idx_communities_visibility ON communities(visibility);
CREATE INDEX idx_communities_created_by ON communities(created_by);

CREATE TABLE community_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    role membership_role NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_community_member UNIQUE (community_id, user_id)
);

CREATE INDEX idx_memberships_community ON community_memberships(community_id);
CREATE INDEX idx_memberships_user ON community_memberships(user_id);

CREATE TABLE community_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_community_messages_community ON community_messages(community_id, created_at);

-- ============================================================
-- NOTIFICATIONS (in-app + SSE real-time feed, 2026-07-01)
-- ============================================================

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    type VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT,
    link VARCHAR(512),
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread ON notifications (user_id, is_read);
CREATE INDEX idx_notifications_user_created ON notifications (user_id, created_at DESC);

-- ============================================================
-- SEED DATA
-- ============================================================

INSERT INTO law_firm_partners (name, jurisdictions, contact_email) VALUES
    ('Meridian IP Law', ARRAY['US', 'CA', 'UK'], 'intake@meridianip.saha.local'),
    ('Pacific Ventures Legal', ARRAY['US', 'AU', 'SG'], 'deals@pacificventures.saha.local'),
    ('Europa IP Counsel', ARRAY['DE', 'FR', 'NL', 'EU'], 'counsel@europaip.saha.local');

-- ============================================================
-- OPEN INNOVATION LIBRARY (admin-curated open resources, 2026-07-02)
-- ============================================================

CREATE TYPE open_resource_type AS ENUM ('patent', 'research_paper', 'trademark');

CREATE TABLE open_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_type open_resource_type NOT NULL,
    title VARCHAR(300) NOT NULL,
    summary TEXT,
    authors VARCHAR(500),
    organization VARCHAR(255),
    identifier VARCHAR(120),              -- patent number or DOI
    source_url VARCHAR(1000) NOT NULL,
    license VARCHAR(120) NOT NULL,        -- e.g. 'Public domain (expired patent)', 'CC BY 4.0'
    category VARCHAR(100),                -- R&D domain, mirrors community topics
    tags TEXT[] NOT NULL DEFAULT '{}',
    published_year INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT true,
    view_count INTEGER NOT NULL DEFAULT 0,
    added_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_open_resources_active_created ON open_resources (is_active, created_at DESC);
CREATE INDEX idx_open_resources_type ON open_resources (resource_type);
CREATE INDEX idx_open_resources_category ON open_resources (category);

-- Open Library v2 (2026-07-02): member submissions + build declarations
CREATE TYPE open_resource_status AS ENUM ('pending', 'approved', 'rejected');
ALTER TABLE open_resources ADD COLUMN status open_resource_status NOT NULL DEFAULT 'approved';

CREATE TABLE open_resource_builds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_id UUID NOT NULL REFERENCES open_resources(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    note VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (resource_id, user_id)
);

CREATE INDEX idx_open_resource_builds_resource ON open_resource_builds (resource_id);
CREATE INDEX idx_open_resources_status ON open_resources (status);

-- User profile pictures (2026-07-02): MinIO key, served via authenticated endpoint
ALTER TABLE users ADD COLUMN avatar_key VARCHAR(500);
