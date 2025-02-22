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

-- Grundläggande systeminställningar
INSERT INTO settings (key, value) VALUES
    ('monitor_interval', '10'),
    ('alert_threshold', '5'),
    ('max_retries', '3'),
    ('retry_delay', '5'),
    ('stream_timeout', '30'),
    ('health_check_interval', '60')
ON CONFLICT (key) DO NOTHING;

-- Test channel för utveckling
INSERT INTO channels (channel_key, channel_url, channel_name, channel_description) VALUES
    ('test_channel', 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8', 'Test Channel', 'Test Stream')
ON CONFLICT (channel_key) DO NOTHING; 