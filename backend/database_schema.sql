-- Simplified PostgreSQL schema for the real-estate voice assistant
-- This supports leads, sessions, call logs, property suggestions, and bookings.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(30),
    customer_name VARCHAR(150),
    city VARCHAR(100),
    area VARCHAR(100),
    budget VARCHAR(100),
    property_type VARCHAR(50),
    purpose VARCHAR(50),
    appointment_interest BOOLEAN DEFAULT FALSE,
    profile_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE IF EXISTS leads
    ADD COLUMN IF NOT EXISTS profile_data JSONB DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS call_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
    call_sid VARCHAR(150),
    source VARCHAR(50) DEFAULT 'twilio',
    transcript TEXT,
    intent VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS property_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES call_sessions(id) ON DELETE CASCADE,
    property_id VARCHAR(50),
    property_name VARCHAR(200),
    city VARCHAR(100),
    area VARCHAR(100),
    price NUMERIC(18,2),
    recommended_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
    session_id UUID REFERENCES call_sessions(id) ON DELETE SET NULL,
    property_id VARCHAR(50),
    property_name VARCHAR(200),
    client_name VARCHAR(150),
    client_phone VARCHAR(30),
    scheduled_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'confirmed',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS followups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
    session_id UUID REFERENCES call_sessions(id) ON DELETE SET NULL,
    note TEXT,
    scheduled_for TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone_number);
CREATE INDEX IF NOT EXISTS idx_sessions_lead ON call_sessions(lead_id);
CREATE INDEX IF NOT EXISTS idx_appointments_lead ON appointments(lead_id);
CREATE INDEX IF NOT EXISTS idx_followups_lead ON followups(lead_id);
