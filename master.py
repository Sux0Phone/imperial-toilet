import os
import random
import asyncio
import aiocron
import logging
import discord
from discord.ext import commands
from telethon import TelegramClient, events, sync
from telethon.sessions import StringSession
from telethon.tl.types import InputChannel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(level=logging.WARNING)
logger = logging.getLogger(__name__)

TG_STR_SESSION = os.getenv('TG_STR_SESSION') 
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_REACTIONS = ['🤙', '👎'] #эти реакции будут ставиться под кааждый пост, можете добавить свои

tg_client = TelegramClient(StringSession(TG_STR_SESSION), api_id=TG_API_ID, api_hash=TG_API_HASH)
tg_client.connect()

intents = discord.Intents.all()
ds_bot = commands.Bot(command_prefix="нинужон", intents=intents)

input_tg_channel_names = ['Название 1', 'Название 2'] #имя... просто имя кaнaлa, не юзернейм и не линк, просто имя, кaк в списке чaтов
input_tg_channel_ids = [1042549367, 1378136676] #ID кaнaлa можно получить, если взять обычный ID кaнaлa в боте @userinfobot и убрaть -100 в нaчaле 
input_tg_channels_entities = []
output_discord_channels_id = [932421348108693604]

for d in tg_client.iter_dialogs():
    if d.name in input_tg_channel_names or d.entity.id in input_tg_channel_ids:
        input_tg_channels_entities.append(InputChannel(d.entity.id, d.entity.access_hash))

logging.info(f"Listening on {len(input_tg_channels_entities)} Telegram channels. Forwarding messages to {len(output_discord_channels_id)} Discord channels.")

async def random_filename_generator():
    symbols_list = [chr(x) for x in range(ord('a'), ord('z') + 1)] + [chr(x) for x in range(ord('A'), ord('Z') + 1)] + [chr(x) for x in range(ord('0'), ord('9') + 1)]
    return ''.join([random.choice(symbols_list) for i in range(0, 15)])

async def discord_poster(discord_channel_id, tg_message_text, mystery_file_obj, media_flag):
    channel = discord_channel_id
    if media_flag == True:
        if len(mystery_file_obj) > 1:
            if tg_message_text == '':    
                ds_message = await channel.send(files=mystery_file_obj)
            else:
                ds_message = await channel.send(tg_message_text, files=mystery_file_obj)
        else:
            if tg_message_text == '': 
                ds_message = await channel.send(file=discord.File(mystery_file_obj[0]))
            else:
                ds_message = await channel.send(tg_message_text, file=discord.File(mystery_file_obj[0]))
    elif tg_message_text != '':
        ds_message = await channel.send(tg_message_text)
    else:
        return 'Nothing to send!'

    for emoji in DISCORD_REACTIONS:
        await ds_message.add_reaction(emoji)
    return 'Success'

async def file_cleaner(media_names):
    if len(media_names) < 1:
        return
    else:
        for media_name in media_names:
            os.remove(media_name)

async def files_size_calculate(files_names):
    all_sizes = 0
    for file_name in files_names:
        all_sizes += os.path.getsize(file_name)
    return all_sizes

async def solo_preparator(discord_channel_id, tg_message):
    if tg_message.media:
        if tg_message.file.size >= 8388000:
           return 'So big file!', 'So big file!'
        media_name = []
        media_name.append(await tg_client.download_media(tg_message, await random_filename_generator()))
        return media_name, media_name
    else:
        return [], []

async def album_preparator(discord_channel_id, tg_messages):
    media_names = []   
    ds_file_objects = []
    for tg_message in tg_messages:
        if tg_message.file.size >= 8388000:
            if len(media_names) > 1:
                await file_cleaner(media_names)
            return 'So big file in album!', 'So big file in album!'
        media_names.append(await tg_client.download_media(tg_message, await random_filename_generator()))
        if await files_size_calculate(media_names) >= 8388000:
            await file_cleaner(media_names)
            return 'So big album size!', 'So big album size!'
    for media_name in media_names:
        ds_file_objects.append(discord.File(media_name))
    return media_names, ds_file_objects

@aiocron.crontab('*/20 * * * *') #пингер, чтоб скрипт не заглох из-за лимитов Heroku
async def pinger():
    logging.info("I'm alive!")

@tg_client.on(events.Album(chats=input_tg_channels_entities))
async def album_handler(event):
    for output_discord_channel_id in output_discord_channels_id:
        media_names, mystery_file_obj = await album_preparator(output_discord_channel_id, event.messages)
        if type(media_names) != list:
            logging.info(f"I can't send this album. Reason: {media_names}")
            return
        media_flag = True
        ds_channel = ds_bot.get_channel(output_discord_channel_id)
        repost_status = await discord_poster(ds_channel, event.text, mystery_file_obj, media_flag)
        if repost_status != 'Success':
            logging.info(f"I can't send this album. Reason: {repost_status}")
        else:
            await file_cleaner(media_names)
            logging.info(f'Album has been sent to Discord channel with ID {output_discord_channel_id}.')

@tg_client.on(events.NewMessage(chats=input_tg_channels_entities))
async def message_handler(event):
    for output_discord_channel_id in output_discord_channels_id:
        if event.message.grouped_id:
            return
        media_name, mystery_file_obj = await solo_preparator(output_discord_channel_id, event.message)
        if type(media_name) != list:
            logging.info(f"I can't send this message. Reason: {media_name}")
            return
        if len(mystery_file_obj) > 0:
            media_flag = True
        else:
            media_flag = False
        ds_channel = ds_bot.get_channel(output_discord_channel_id)
        repost_status = await discord_poster(ds_channel, event.message.raw_text, mystery_file_obj, media_flag)
        if repost_status != 'Success':
            logging.info(f"I can't send this message. Reason: {repost_status}")
        else:
            await file_cleaner(media_name)
            logging.info(f'Message has been sent to Discord channel with ID {output_discord_channel_id}.')

@ds_bot.event
async def on_ready():
    logging.info(f"Discord Bot is ready!")

ds_bot.run(DISCORD_TOKEN)
tg_client.run_until_disconnected()
