from telethon import sync, TelegramClient
import tttcutils
import os

api_id, api_hash = tttcutils.assert_environment()

client = TelegramClient(tttcutils.sessionfile(), api_id, api_hash)
client.connect()
chats = client.get_dialogs()
print("client: TelegramClient   chats: [Dialog]")
