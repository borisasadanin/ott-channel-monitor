import pytest
import os
import sys
import httpx
import m3u8
from unittest.mock import AsyncMock, patch
import asyncio

# Se till att Python hittar projektets rotmapp
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitor_service.monitor import fetch_manifest, fetch_segment, monitor_hls_channel

# ✅ Test för att hämta M3U8-manifest
@pytest.mark.asyncio
async def test_fetch_manifest():
    fake_manifest = """
    #EXTM3U
    #EXT-X-STREAM-INF:BANDWIDTH=1280000
    variant1.m3u8
    """

    fake_response = AsyncMock()
    fake_response.status_code = 200
    fake_response.text = fake_manifest
    fake_response.raise_for_status = lambda: None  # ✅ Gör raise_for_status awaitable
    fake_response.elapsed = AsyncMock()  # ✅ Lägg till detta
    fake_response.elapsed.total_seconds = lambda: 0.123  # ✅ Se till att det returnerar ett riktigt tal


    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = fake_response  
        manifest = await fetch_manifest("https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8")
        print(f"Manifest: {manifest}")  # Debugging
        mock_get.assert_called_once()
        assert manifest is not None, "Manifestet kunde inte hämtas"
        assert isinstance(manifest, m3u8.M3U8), "Manifestet är inte av typen M3U8"

# ✅ Test för att hämta ett HLS-segment
@pytest.mark.asyncio
async def test_fetch_segment():
    fake_response = AsyncMock()
    fake_response.status_code = 200
    fake_response.elapsed = AsyncMock()
    fake_response.elapsed.total_seconds = lambda: 0.4  
    fake_response.raise_for_status = lambda: None  # ✅ Gör raise_for_status awaitable

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = fake_response
        response_time = await fetch_segment("https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8")
        print(f"Segment response time: {response_time}")  # Debugging

        mock_get.assert_called_once()
        assert response_time == 0.4, f"Segmentets svarstid var felaktig: {response_time}"

# ✅ Test för att hantera timeout korrekt
@pytest.mark.asyncio
async def test_fetch_segment_timeout():
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout!")) as mock_get:
        response_time = await fetch_segment("https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8")
        print(f"Segment response time on timeout: {response_time}")  # Debugging

        mock_get.assert_called_once()
        assert response_time is None, f"Segmentet borde returnera None vid timeout men fick {response_time}"

# ✅ Test för att `monitor_hls_channel()` fungerar och avslutas korrekt
@pytest.mark.asyncio
async def test_monitor_hls_channel():
    fake_manifest = """
    #EXTM3U
    #EXT-X-STREAM-INF:BANDWIDTH=1280000
    variant1.m3u8
    """
    
    fake_segment_time = 0.5  # Simulerar att segmenten svarar snabbt

    with patch("monitor_service.monitor.fetch_manifest", new_callable=AsyncMock) as mock_fetch_manifest, \
         patch("monitor_service.monitor.fetch_segment", new_callable=AsyncMock) as mock_fetch_segment:
        
        mock_fetch_manifest.return_value = m3u8.loads(fake_manifest)
        mock_fetch_segment.return_value = fake_segment_time

        async def test_run():
            await monitor_hls_channel()

        # Kör övervakningen i en begränsad tidsperiod
        task = asyncio.create_task(test_run())
        await asyncio.sleep(1)  # Vänta kort för att simulera en körning
        task.cancel()  # Avbryt övervakningen

        try:
            await task
        except asyncio.CancelledError:
            print("Monitoreringen avbruten")

        mock_fetch_manifest.assert_called()
        mock_fetch_segment.assert_called()
