"""
Contains the signaler messages
"""
import logging
from pyrogram.types import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

SIGNALER_VERSION = "0.0.3"
MENTION = "**[{}](tg://user?id={})**"  # User mention markup
STARTED_MESSAGE = "{} Welcome to [Freqtrade's Signaler](https://freqtrade.io/en/stable) {}! \n" \
                  " Successfully connected with {}. \n" \
                  " You are using Signaler module v.{} \n"

OWNER_STARTUP_MESSAGE = f" Hello!\n" \
                        f" [Freqtrade's Signaler](https://freqtrade.io/en/stable) v{SIGNALER_VERSION}\n" \
                        " successfully started!{}\n" \
                        " You are part of the **{}** owners!\n" \
                        " There is currently **{}** users in the DB\n" \
                        " Current Freqtrade strategy: **{}**\n"

OWNER_MESSAGE = "  {} You are one of this bot's owners! {}"
GUEST_MESSAGE = "  {} You are using {}'s bot {} \n " \
                "\n Use the demand button to ask the owners for access! "

APPROVAL_MESSAGE = " {} {} is demanding access to the bot {} \n "

WHOIS_MESSAGE = "**[{}](tg://user?id={})**\n"\
    " * UserID: `{}`\n"\
    " * First Name: `{}`\n"\
    " * Last Name: `{}`\n"\
    " * Username: `{}`\n"\
    " * Status: `{}`\n"\
    " * Join date: `{}`\n"\
    " * Approved: `{}`\n"\
    " * Owner: `{}`\n"\
    " * Spammer Level: `{}`\n"

OWNER_MENU_MARKUP = ReplyKeyboardMarkup(
    [
        ["/run", "/listusers"],
        ["/restart", "/stop"]
    ],
    resize_keyboard=True
)

USER_MENU_MARKUP = ReplyKeyboardMarkup(
    [
        ["/demand", "/run"]
    ],
    resize_keyboard=True
)
