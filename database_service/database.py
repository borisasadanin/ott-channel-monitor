from flask import Flask, jsonify, request
import os
import psycopg2
import uuid  # Importera för att generera unika keys
from dotenv import load_dotenv
import signal
import sys
from waitress import serve  # eller gunicorn för Linux
from prometheus_client import Counter, Histogram, generate_latest
import time

# Ladda miljövariabler från .env
load_dotenv()

DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'channeldb'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD'),  # Hämta från miljövariabel
    'host': os.environ.get('DB_HOST', 'postgres_db'),
    'port': os.environ.get('DB_PORT', '5432')
}

app = Flask(__name__)

request_count = Counter('http_requests_total', 'Total HTTP requests')
request_latency = Histogram('http_request_duration_seconds', 'HTTP request latency')

@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    request_count.inc()
    request_latency.observe(time.time() - request.start_time)
    return response

@app.route("/metrics")
def metrics():
    return generate_latest()

def get_db_connection():
    """Returnerar en ny databasanslutning."""
    return psycopg2.connect(**DB_CONFIG)

@app.route("/channels", methods=["GET"])
def get_channels():
    """Hämtar alla kanaler från databasen."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, channel_name, channel_url FROM channels;")  # ✅ Hämtar ID, namn och URL
    channels = [{"id": row[0], "name": row[1], "url": row[2]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({"channels": channels})

@app.route("/channels", methods=["POST"])
def add_channel():
    """Lägger till en ny kanal i databasen med ett automatiskt genererat kanal-ID och channel_key."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        name = data.get("name")
        url = data.get("url")
        channel_key = data.get("channel_key", str(uuid.uuid4()))

        if not name or not url:
            return jsonify({"error": "Name and URL are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Hämta det högsta befintliga kanal-ID:t och räkna ut nästa ID
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM channels;")
        new_id = cur.fetchone()[0]

        # Lägg till kanalen med det nya kanal-ID:t och genererat `channel_key`
        cur.execute(
            "INSERT INTO channels (id, channel_key, channel_name, channel_url) VALUES (%s, %s, %s, %s) RETURNING id, channel_key, channel_name, channel_url;",
            (new_id, channel_key, name, url)
        )
        
        new_channel = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "message": "Channel added successfully",
            "channel": {
                "id": new_channel[0],
                "channel_key": new_channel[1],
                "name": new_channel[2],
                "url": new_channel[3]
            }
        }), 201

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/channels/<int:channel_id>", methods=["GET"])
def get_channel(channel_id):
    """Hämtar en specifik kanal från databasen."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, channel_name, channel_url FROM channels WHERE id = %s;", (channel_id,))
    channel = cur.fetchone()
    cur.close()
    conn.close()
    
    if channel is None:
        return jsonify({"error": "Channel not found"}), 404
        
    return jsonify({
        "id": channel[0],
        "name": channel[1],
        "url": channel[2]
    })

@app.route("/health")
def health_check():
    """Enkel hälsokontroll endpoint."""
    try:
        # Testa databasanslutning med timeout
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
        conn.close()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route("/settings", methods=["GET"])
def get_settings():
    """Hämtar alla inställningar från databasen."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM settings;")
    settings = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return jsonify(settings)

@app.route("/settings/<key>", methods=["PUT"])
def update_setting(key):
    """Uppdaterar en specifik inställning i databasen."""
    data = request.json
    value = data.get("value")
    
    if not value:
        return jsonify({"error": "Value is required"}), 400
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE settings SET value = %s WHERE key = %s RETURNING key, value;",
        (value, key)
    )
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    if updated:
        return jsonify({"key": updated[0], "value": updated[1]})
    return jsonify({"error": "Setting not found"}), 404

@app.route("/channels/<int:channel_id>", methods=["DELETE"])
def delete_channel(channel_id):
    """Tar bort en kanal från databasen."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM channels WHERE id = %s RETURNING id;", (channel_id,))
        deleted = cur.fetchone()
        
        conn.commit()
        cur.close()
        conn.close()
        
        if deleted:
            return jsonify({"message": f"Channel {channel_id} deleted successfully"}), 200
        return jsonify({"error": "Channel not found"}), 404
        
    except Exception as e:
        print(f"Error deleting channel: {e}")
        return jsonify({"error": str(e)}), 500

def wait_for_db():
    """Väntar på att databasen ska bli tillgänglig."""
    max_retries = 30
    retry_interval = 1

    for i in range(max_retries):
        try:
            conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
            conn.close()
            print("✅ Databasanslutning etablerad")
            return True
        except psycopg2.Error as e:
            print(f"⏳ Väntar på databas... försök {i+1}/{max_retries}")
            time.sleep(retry_interval)
    
    print("❌ Kunde inte ansluta till databasen")
    return False

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    
    print("🚀 Starting database service...")
    
    # Vänta på att databasen ska bli tillgänglig
    if wait_for_db():
        serve(app, host='0.0.0.0', port=5000)
    else:
        sys.exit(1)