import configparser
import json

from telethon.sync import TelegramClient
from telethon import connection

# для корректного переноса времени сообщений в json
from datetime import date, datetime

# классы для работы с каналами
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch

# класс для работы с сообщениями
from telethon.tl.functions.messages import GetHistoryRequest

# Считываем учетные данные
config = configparser.ConfigParser()
config.read("config.ini")

# Присваиваем значения внутренним переменным
api_id = config['Telegram']['api_id']
api_hash = config['Telegram']['api_hash']
username = config['Telegram']['username']

client = TelegramClient(username, api_id, api_hash)

# proxy = ('31.134.6.59', '59100', 'pePIP8meKP')
#
# client = TelegramClient(username, api_id, api_hash,
#                         connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
#                         proxy=proxy)

client.start()

# url = input("Введите ссылку на канал или чат: ")
# channel = await client.get_entity(url)

messages = client.get_participants('Алексей')
print(messages)

