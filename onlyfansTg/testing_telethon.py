from telethon import TelegramClient

import configparser


config = configparser.ConfigParser()
config.read('config.ini')

api_id = config['Telegram']['api_id']
api_hash = config['Telegram']['api_hash']
username = config['Telegram']['username']

client = TelegramClient(username, api_id, api_hash)


async def main():
    me = await client.get_me()
    print(me)

# main()
