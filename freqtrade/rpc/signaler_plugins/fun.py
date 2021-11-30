import requests
from freqtrade.rpc.signaler import Signaler
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from random import choice


RUN_STRINGS = (
    "Now you see me, now you don't." "ε=ε=ε=ε=┌(;￣▽￣)┘",
    "Get back here!",
    "REEEEEEEEEEEEEEEEEE!!!!!!!",
    "Look out for the wall!",
    "Don't leave me alone with them!!",
    "You've got company!",
    "Chotto matte!",
    "Yare yare daze",
    "*Naruto run activated*",
    "Run everyone, they just dropped a bomb 💣💣",
    "And they disappeared forever, never to be seen again.",
    "Legend has it, they're still running.",
    "Hasta la vista, baby.",
    "Ah, what a waste. I liked that one.",
    "As The Doctor would say... RUN!",
)


@Signaler.on_message(filters.command('run'))
async def run(client, message):
    await message.reply_text(choice(RUN_STRINGS))
    return


# credits to NKsamaX Komi-San bot https://github.com/NksamaX/Komi-San
@Signaler.on_callback_query(filters.regex('meme'))
def callback_meme(client: Signaler, query: CallbackQuery):
    query.message.delete()
    res = requests.get('https://nksamamemeapi.pythonanywhere.com').json()
    img = res['image']
    title = res['title']
    client.send_photo(query.message.chat.id, img, caption=title, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Next mémé", callback_data="meme:next")],
    ]))


# credits to NKsamaX Komi-San bot https://github.com/NksamaX/Komi-San
@Signaler.on_message(filters.command('meme'))
def rmeme(client: Signaler, message: Message):
    res = requests.get('https://nksamamemeapi.pythonanywhere.com').json()
    img = res['image']
    title = res['title']
    client.send_photo(message.chat.id, img, caption=title, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Next mémé", callback_data="meme")]
    ]))

