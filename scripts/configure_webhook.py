#!/usr/bin/env python3
"""
Скрипт для настройки webhook на терминале
"""
import asyncio
import httpx

async def configure_webhook():
    """Настраиваем webhook на терминале."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                'http://localhost/api/devices/1/webhook/configure',
                json={
                    'server_ip': '192.168.78.1',
                    'server_port': 8000,
                    'url_path': '/events/webhook',
                    'protocol': 'http'
                }
            )
            print(f'✅ HTTP {response.status_code}')
            print(f'📄 Response: {response.text}')
        except Exception as e:
            print(f'❌ Error: {e}')

if __name__ == "__main__":
    asyncio.run(configure_webhook())
