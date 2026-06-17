import asyncio
import websockets
import json

async def run():
    uri = 'ws://localhost:8765'
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({'event':'handshake','token':None}))
            for _ in range(5):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    print('RECV:', msg)
                except asyncio.TimeoutError:
                    break
    except Exception as e:
        print('ERROR', e)

if __name__ == '__main__':
    asyncio.run(run())
