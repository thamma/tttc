from telethon import sync, TelegramClient
import os

if not ("TTTC_API_ID" in os.environ or "TTTC_API_HASH" in os.environ):
    print("Please set your environment variables \"TTTC_API_ID\" and \"TTTC_API_HASH\" accordingly.")
    print("Please consult https://core.telegram.org/api/obtaining_api_id on how to get your own API id and hash.")
    quit(1)
api_id = os.environ["TTTC_API_ID"]
api_hash = os.environ["TTTC_API_HASH"]

client = TelegramClient("tttc", api_id, api_hash)
client.connect()
chats = client.get_dialogs()
print("client: TelegramClient   chats: [Dialog]")
