import sys
import asyncio
import websockets
import json

# Default to the active live auction in the database, or accept command-line argument
DEFAULT_AUCTION_ID = "fc10b076-877b-45aa-af1d-55ba267cc0da"
AUCTION_ID = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AUCTION_ID
WS_URL = f"ws://localhost:8000/ws/auctions/{AUCTION_ID}/"

async def listen():
    print(f"Connecting to {WS_URL}...")
    async with websockets.connect(WS_URL) as ws:
        print("Connected to Auction WebSocket successfully!")
        msg = await ws.recv()
        print("Received event:", json.loads(msg))

if __name__ == "__main__":
    asyncio.run(listen())