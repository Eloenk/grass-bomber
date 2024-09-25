import asyncio
import random
import ssl
import json
import time
import uuid
import requests
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent

user_agent = UserAgent()
random_user_agent = user_agent.random  # Cache user agent globally

# Limit number of concurrent connections
semaphore = asyncio.Semaphore(10)  # Adjust the limit as needed

# Exponential backoff strategy for retries
async def exponential_backoff(retries):
    delay = min(60, (2 ** retries) + random.uniform(0.1, 1.0))  # Max out at 60 seconds
    await asyncio.sleep(delay)

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    retries = 0
    logger.info(f"Connecting with Device ID: {device_id}")
    
    async with semaphore:  # Limit concurrency
        while retries < 5:  # Limit retries to avoid infinite loop
            try:
                await asyncio.sleep(random.uniform(0.1, 1.0))  # More granular random delay
                custom_headers = {
                    "User-Agent": random_user_agent,  # Re-using the same user agent
                    "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi"
                }
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                uri = "wss://proxy.wynd.network:4444/"
                server_hostname = "proxy.wynd.network"
                proxy = Proxy.from_url(socks5_proxy)

                async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                         extra_headers=custom_headers) as websocket:
                    
                    async def send_ping():
                        while True:
                            send_message = json.dumps(
                                {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}}
                            )
                            logger.debug(f"Sending ping: {send_message}")
                            await websocket.send(send_message)
                            await asyncio.sleep(20)

                    ping_task = asyncio.create_task(send_ping())  # Create ping task

                    while True:
                        response = await websocket.recv()
                        message = json.loads(response)
                        logger.info(f"Received message: {message}")
                        
                        if message.get("action") == "AUTH":
                            auth_response = {
                                "id": message["id"],
                                "origin_action": "AUTH",
                                "result": {
                                    "browser_id": device_id,
                                    "user_id": user_id,
                                    "user_agent": custom_headers['User-Agent'],
                                    "timestamp": int(time.time()),
                                    "device_type": "extension",
                                    "version": "4.0.1"
                                }
                            }
                            logger.debug(f"Sending auth response: {auth_response}")
                            await websocket.send(json.dumps(auth_response))

                        elif message.get("action") == "PONG":
                            pong_response = {"id": message["id"], "origin_action": "PONG"}
                            logger.debug(f"Sending pong response: {pong_response}")
                            await websocket.send(json.dumps(pong_response))
                    
            except (asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"Connection error with proxy {socks5_proxy}: {e}")
                retries += 1
                await exponential_backoff(retries)
            except Exception as e:
                logger.error(f"Unexpected error with proxy {socks5_proxy}: {e}")
                break  # Exit the loop on unknown errors

async def main():
    # Fetch proxies from remote URL
    r = requests.get("https://github.com/monosans/proxy-list/raw/main/proxies/http.txt", stream=True)
    if r.status_code == 200:
        proxies = r.text.splitlines()  # Read proxies from response, avoiding file I/O

    with open('data.txt', 'r') as file:
        _user_id = file.read().strip()

    # Create and gather tasks
    tasks = [asyncio.create_task(connect_to_wss('http://'+i, _user_id)) for i in proxies]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
