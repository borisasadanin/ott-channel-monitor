from flask import Flask, jsonify, request
import os
import psycopg2
import uuid  # Importera för att generera unika keys
from dotenv import load_dotenv

# Ladda miljövariabler från .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

app = Flask(__name__)

def get_db_connection():
    """Returnerar en ny databasanslutning."""
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

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
    data = request.json
    name = data.get("name")
    url = data.get("url")
    channel_key = data.get("channel_key", str(uuid.uuid4()))  # Generera UUID om den saknas

    if not name or not url:
        return jsonify({"error": "Name and URL are required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    # Hämta det högsta befintliga kanal-ID:t och räkna ut nästa ID
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM channels;")
    new_id = cur.fetchone()[0]

    # Lägg till kanalen med det nya kanal-ID:t och genererat `channel_key`
    cur.execute(
        "INSERT INTO channels (id, channel_key, channel_name, channel_url) VALUES (%s, %s, %s, %s);",
        (new_id, channel_key, name, url)
    )
    
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Channel added", "id": new_id, "channel_key": channel_key}), 201


@app.route("/health")
def health_check():
    """Enkel hälsokontroll endpoint."""
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

