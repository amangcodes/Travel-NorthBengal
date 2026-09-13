-- Run this in your Supabase SQL Editor to create the necessary tables

-- 1. Table for travel destinations and points of interest
CREATE TABLE IF NOT EXISTS places (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    csv_category TEXT,
    type TEXT,
    destination TEXT,
    area TEXT,
    price TEXT,
    rating FLOAT DEFAULT 0,
    description TEXT,
    latitude FLOAT,
    longitude FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS) but allow public read access for now
ALTER TABLE places ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to places" ON places
    FOR SELECT USING (true);


-- 2. Table to store AI conversation history/generated itineraries
CREATE TABLE IF NOT EXISTS trip_history (
    id SERIAL PRIMARY KEY,
    prompt TEXT NOT NULL,
    response JSONB NOT NULL,
    destination TEXT,
    total_budget FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS for trip_history
ALTER TABLE trip_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to history" ON trip_history
    FOR SELECT USING (true);

CREATE POLICY "Allow public insert to history" ON trip_history
    FOR INSERT WITH CHECK (true);
