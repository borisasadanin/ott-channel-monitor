import os
import sys
import logging
import time
import requests
import m3u8
from urllib.parse import urljoin
import signal
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from circuitbreaker import circuit

# Konfigurera loggning
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# Global flagga för att kontrollera om vi ska fortsätta köra
running = True

def get_settings(database_url):
    """Hämta inställningar från databasen"""
    try:
        response = requests.get(f"{database_url}/settings")
        if response.status_code == 200:
            settings = response.json()
            return {
                'monitor_interval': int(settings.get('monitor_interval', 10)),
                'alert_threshold': int(settings.get('alert_threshold', 5))
            }
        else:
            logger.error(f"❌ Kunde inte hämta inställningar. Status: {response.status_code}")
            return {'monitor_interval': 10, 'alert_threshold': 5}  # Default värden
    except Exception as e:
        logger.error(f"❌ Fel vid hämtning av inställningar: {str(e)}")
        return {'monitor_interval': 10, 'alert_threshold': 5}  # Default värden

@circuit(failure_threshold=5, recovery_timeout=60)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def check_stream_status(url):
    try:
        # Hämta HLS manifest
        logger.info(f"🔍 Hämtar HLS manifest från: {url}")
        response = requests.get(url)
        response.raise_for_status()
        
        # Parsa M3U8
        m3u8_obj = m3u8.loads(response.text)
        
        # Kontrollera om det är en master playlist genom att kolla efter playlists
        if hasattr(m3u8_obj, 'playlists') and m3u8_obj.playlists:
            logger.info(f"Master playlist detekterad med {len(m3u8_obj.playlists)} kvalitetsnivåer")
            
            # Kontrollera första variant-strömmen
            variant_url = m3u8_obj.playlists[0].uri
            if not variant_url.startswith('http'):
                variant_url = url.rsplit('/', 1)[0] + '/' + variant_url
            
            logger.info(f"Kontrollerar variant-ström: {variant_url}")
            variant_response = requests.get(variant_url)
            variant_response.raise_for_status()
            variant_m3u8 = m3u8.loads(variant_response.text)
            
            if hasattr(variant_m3u8, 'segments') and variant_m3u8.segments:
                logger.info(f"✅ Strömmen är aktiv med {len(variant_m3u8.segments)} segment")
                return f"Strömmen är aktiv med {len(variant_m3u8.segments)} segment"
            else:
                logger.warning("⚠️ Inga segment hittades i strömmen")
                return "Inga segment hittades"
        else:
            # Det är en media playlist
            if hasattr(m3u8_obj, 'segments') and m3u8_obj.segments:
                logger.info(f"✅ Strömmen är aktiv med {len(m3u8_obj.segments)} segment")
                return f"Strömmen är aktiv med {len(m3u8_obj.segments)} segment"
            else:
                logger.warning("⚠️ Inga segment hittades i strömmen")
                return "Inga segment hittades"
                
    except Exception as e:
        logger.error(f"❌ Fel vid kontroll av ström: {e}")
        return f"Fel vid kontroll: {str(e)}"

def monitor_stream(channel_url):
    """
    Övervakar en HLS-ström kontinuerligt.
    """
    while True:
        try:
            status = check_stream_status(channel_url)
            if status != "Strömmen är aktiv med segment":
                logger.warning(f"⚠️ Problem: {status}")
            time.sleep(5)  # Vänta 5 sekunder mellan kontroller
        except Exception as e:
            logger.error(f"❌ Oväntat fel vid övervakning av {channel_url}: {str(e)}")
            time.sleep(5)

def signal_handler(signum, frame):
    """Hantera shutdown signaler"""
    global running
    logger.info("📥 Tar emot shutdown signal...")
    running = False

def main():
    # Registrera signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("🚀 Monitor service startar...")
    
    # Hämta miljövariabler
    channel_url = os.getenv('CHANNEL_URL')
    if not channel_url:
        logger.error("❌ Ingen CHANNEL_URL angiven i miljövariabler")
        exit(1)
        
    while running:  # Använd running flaggan istället för True
        try:
            logger.info("\n=== Stream Status Kontroll ===")
            logger.info(f"URL: {channel_url}")
            logger.info("Kontrollintervall: 10 sekunder")
            
            status = check_stream_status(channel_url)
            logger.info(f"✅ Status: {status}")
            logger.info("⏳ Väntar 10 sekunder till nästa kontroll...")
            logger.info("================================\n")
                
        except Exception as e:
            logger.error(f"❌ Fel vid kontroll av ström: {e}")
        
        # Använd kortare sleep-intervaller för snabbare shutdown
        for _ in range(10):
            if not running:
                break
            time.sleep(1)
    
    logger.info("👋 Monitor service avslutas...")
    sys.exit(0)

if __name__ == "__main__":
    main()
