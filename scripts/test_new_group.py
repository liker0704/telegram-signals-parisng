#!/usr/bin/env python3
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient
from telethon.sessions import StringSession

async def test():
    client = TelegramClient(
        StringSession(os.getenv('PUBLISHER_SESSION_STRING')),
        int(os.getenv('PUBLISHER_API_ID')),
        os.getenv('PUBLISHER_API_HASH')
    )
    await client.connect()

    # New supergroup ID with -100 prefix
    new_id = -1003384570794

    print(f'Testing ID: {new_id}')

    try:
        entity = await client.get_entity(new_id)
        print(f'Entity: {entity.title}')

        msg = await client.send_message(entity, 'Test - will delete')
        print(f'SENT! ID: {msg.id}')
        await msg.delete()
        print('Deleted')
    except Exception as e:
        print(f'Error: {e}')

    await client.disconnect()

asyncio.run(test())
