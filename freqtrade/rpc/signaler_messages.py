"""
Contains the signaler messages
"""
import logging
from pyrogram.types import ReplyKeyboardMarkup, Message

logger = logging.getLogger(__name__)

SIGNALER_VERSION = "0.0.2"
MENTION = "[{}](tg://user?id={})"  # User mention markup
STARTED_MESSAGE = "{} Welcome to [Freqtrade's Signaler](https://freqtrade.io/en/stable) {}! \n" \
                  " Successfully connected with {}. \n" \
                  " You are using Signaler module v.{} \n"

OWNER_MESSAGE = "  {} You are this bot's owner! {}"
GUEST_MESSAGE = "  {} You are using {}'s bot {} \n " \
                "(some commands are limited)"

OWNER_MENU_MARKUP = ReplyKeyboardMarkup(
    [
        ["/test"],
        ["/restart", "/stop"]
    ],
    resize_keyboard=True
)

USER_MENU_MARKUP = ReplyKeyboardMarkup(
    [
        ["/test"]
    ],
    resize_keyboard=True
)