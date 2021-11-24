from pyrogram import Client, filters
from pyrogram.types import Message
from freqtrade.rpc.signaler_database import SignalerUser


@Client.on_message(filters.command(["approve"]))
async def approve_user(_, message: Message):
    user = SignalerUser.get_user(message.from_user.id)
    if not user:
        await message.reply_text(f"Could not find {user.user_name} in the signaler database!")
    elif user.is_allowed:
        return None


@Client.on_message(filters.command(["test"]))
async def test_handler(client: Client, message: Message):
    """
    :param client:
    :param message:
    :return:
    """
    user_name = message.chat.first_name
    text = f"Wow, {user_name}. Great moves. Keep it up. Proud of you. \n"
    text = await SignalerUser.user_ownership_message(message, text)
    await message.reply_text(text=text, reply_markup=SignalerUser.reply_menu_markup(message.chat.id))
