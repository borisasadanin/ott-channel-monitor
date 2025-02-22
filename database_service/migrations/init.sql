-- Skapa tabellen 'channels' om den inte finns
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    channel_key TEXT NOT NULL UNIQUE,
    channel_url TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    channel_description TEXT
);

-- Skapa tabellen 'settings' om den inte finns
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Förhindra dubbletter vid insert av settings
INSERT INTO settings (key, value) VALUES
    ('monitor_interval', '10'),
    ('alert_threshold', '5')
ON CONFLICT (key) DO NOTHING;

-- Förhindra dubbletter vid insert av channels
INSERT INTO channels (channel_key, channel_url, channel_name, channel_description) VALUES
    ('channel1', 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8', 'Test Channel', 'Test Stream')
ON CONFLICT (channel_key) DO NOTHING;
