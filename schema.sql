CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE NGO (
    ngo_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    trust_score FLOAT DEFAULT 0,
    allowed_event_types TEXT[],
    blocked_event_types TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Event (
    event_id UUID PRIMARY KEY,
    ngo_id UUID REFERENCES NGO(ngo_id) ON DELETE CASCADE,
    title TEXT,
    description TEXT,
    category TEXT,
    subtype TEXT,
    location_name TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    area_size DOUBLE PRECISION,
    severity_score DOUBLE PRECISION,
    severity_level TEXT,
    status TEXT,
    tags TEXT[],
    volunteers_required INT,
    volunteers_assigned INT DEFAULT 0,
    event_date TIMESTAMP,
    is_ongoing BOOLEAN DEFAULT TRUE,
    supporting_docs JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Volunteer (
    volunteer_id UUID PRIMARY KEY,
    name TEXT,
    email TEXT UNIQUE,
    password_hash TEXT,
    age INT,
    skills TEXT[],
    certifications JSONB,
    preferred_categories TEXT[],
    preferred_location TEXT,
    max_travel_distance DOUBLE PRECISION,
    reliability_score DOUBLE PRECISION DEFAULT 0,
    volunteer_points INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Assignment (
    assignment_id UUID PRIMARY KEY,
    event_id UUID REFERENCES Event(event_id) ON DELETE CASCADE,
    volunteer_id UUID REFERENCES Volunteer(volunteer_id) ON DELETE CASCADE,
    assignment_type TEXT,
    status TEXT DEFAULT 'pending',
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP
);

CREATE TABLE Audit (
    audit_id UUID PRIMARY KEY,
    event_id UUID REFERENCES Event(event_id) ON DELETE CASCADE,
    volunteer_id UUID REFERENCES Volunteer(volunteer_id) ON DELETE CASCADE,
    ngo_id UUID REFERENCES NGO(ngo_id) ON DELETE CASCADE,
    attendance BOOLEAN,
    volunteer_rating INT,
    ngo_rating INT,
    feedback TEXT,
    goal_achieved BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);