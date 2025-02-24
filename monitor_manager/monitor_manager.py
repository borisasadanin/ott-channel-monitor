import time
import docker
import requests
import logging
from typing import Dict
import signal
import sys
import os

# Konfigurera loggning
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# Global flagga för att kontrollera om vi ska fortsätta köra
running = True

def signal_handler(signum, frame):
    """Hantera shutdown signaler"""
    global running
    logger.info("📥 Tar emot shutdown signal...")
    running = False

class MonitorManager:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.database_url = os.getenv('DATABASE_SERVICE_URL')
        self.docker_network = os.getenv('DOCKER_NETWORK')
        self.active_containers: Dict[int, str] = {}

    def get_channels(self):
        """Hämta kanaler från databasen"""
        try:
            response = requests.get(f"{self.database_url}/channels")
            response.raise_for_status()
            return response.json()['channels']
        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av kanaler: {e}")
            return []

    def update_containers(self):
        """Uppdatera monitor_service containrar baserat på kanaldata från databasen"""
        try:
            channels = self.get_channels()
            current_channel_ids = {channel['id'] for channel in channels}
            
            # Hämta ALLA containrar (både körande och stoppade)
            all_containers = {
                int(c.name.split('_')[-1]): c 
                for c in self.docker_client.containers.list(all=True)  # Notera all=True här
                if c.name.startswith('monitor_service_')
            }

            # Starta nya containrar för kanaler som saknar en
            for channel in channels:
                channel_id = channel['id']
                container_name = f'monitor_service_{channel_id}'
                
                #ERSÄTTER STYCKET NEDANFÖR 
                if channel_id in all_containers:
                    container = all_containers[channel_id]
                    
                    #Kontrollera om containern körs, då ska vi inte göra något
                    if container.status == "running":
                        logger.info(f"✅ Container {container_name} körs redan, ingen åtgärd behövs.")
                        continue  # Hoppa över denna kanal, containern körs redan

                    # Om containern existerar men är stoppad, ta bort och starta om den
                    try:
                        container.remove(force=True)
                        logger.info(f"🗑️ Tog bort stoppad container: {container_name}")
                    except Exception as e:
                        logger.error(f"❌ Kunde inte ta bort container {container_name}: {e}")


                """# Om containern finns men inte kör, ta bort den först (ERSATT AV STYCKET OVANFÖR)
                if channel_id in all_containers:
                    try:
                        all_containers[channel_id].remove(force=True)
                        logger.info(f"🗑️ Tog bort gammal container: {container_name}")
                    except Exception as e:
                        logger.error(f"❌ Kunde inte ta bort gammal container {container_name}: {e}")"""



                #ERSÄTTER STYCKET NEDANFÖR
                if channel_id not in all_containers:
                    try:
                        container = self.docker_client.containers.run(
                            'monitor_service_image',
                            environment={
                                'CHANNEL_ID': str(channel_id),
                                'CHANNEL_URL': channel['url'],
                                'DATABASE_SERVICE_URL': self.database_url
                            },
                            name=container_name,
                            detach=True,
                            network=self.docker_network
                        )
                        logger.info(f"✅ Startade ny övervakningscontainer för kanal {channel_id}")
                    except Exception as e:
                        logger.error(f"❌ Kunde inte starta övervakning av kanal {channel_id}: {e}")
                else:
                    logger.info(f"🔄 Container för kanal {channel_id} körs redan, hoppar över.")



                """ERSATT AV STYCKET OVANFÖR
                # Starta ny container
                try:
                    container = self.docker_client.containers.run(
                        'monitor_service_image',
                        environment={
                            'CHANNEL_ID': str(channel_id),
                            'CHANNEL_URL': channel['url'],
                            'DATABASE_SERVICE_URL': self.database_url
                        },
                        name=container_name,
                        detach=True,
                        network=self.docker_network
                    )
                    logger.info(f"✅ Startade övervakning av kanal {channel_id}")
                except Exception as e:
                    logger.error(f"❌ Kunde inte starta övervakning av kanal {channel_id}: {e}")"""

            # Ta bort containrar för borttagna kanaler
            for container_id in all_containers:
                if container_id not in current_channel_ids:
                    try:
                        all_containers[container_id].remove(force=True)
                        logger.info(f"✅ Stoppade övervakning av borttagen kanal {container_id}")
                    except Exception as e:
                        logger.error(f"❌ Kunde inte stoppa övervakning av kanal {container_id}: {e}")

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av containrar: {e}")

    def cleanup(self):
        """Städa upp alla monitor_service containrar vid shutdown"""
        try:
            containers = self.docker_client.containers.list(
                filters={"name": "monitor_service_"}
            )
            for container in containers:
                try:
                    container.stop(timeout=5)
                    container.remove()
                    logger.info(f"✅ Städade upp container: {container.name}")
                except Exception as e:
                    logger.error(f"❌ Kunde inte städa upp container {container.name}: {e}")
        except Exception as e:
            logger.error(f"❌ Fel vid cleanup: {e}")

    def run(self):
        """Kör monitor manager"""
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("🚀 Monitor Manager startar...")
        
        try:
            while running:
                try:
                    self.update_containers()
                    time.sleep(10)
                except Exception as e:
                    logger.error(f"❌ Fel i Monitor Manager: {e}")
                    time.sleep(1)
        finally:
            logger.info("🧹 Påbörjar cleanup...")
            self.cleanup()
            logger.info("👋 Monitor Manager avslutas...")
            sys.exit(0)

if __name__ == "__main__":
    manager = MonitorManager()
    manager.run()
