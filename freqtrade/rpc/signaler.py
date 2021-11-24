"""
Run a pyrogram bot that can call freqtrade sub-commands (and send buy/sell signals)
"""
import logging
import signal
from typing import Dict, Any

from pyrogram import Client, __version__, emoji, filters, idle
from pyrogram.types import Message, User
from pyrogram.handlers import MessageHandler
from pyrogram.errors import BadRequest, RPCError, PeerIdInvalid
from freqtrade.rpc import RPC
from freqtrade.rpc.signaler_database import init_db
from freqtrade.exceptions import OperationalException
from freqtrade.freqtradebot import FreqtradeBot
from freqtrade.rpc.signaler_messages import OWNER_MENU_MARKUP,\
    SIGNALER_VERSION, STARTED_MESSAGE, MENTION
from freqtrade.rpc.signaler_database import SignalerUser


logger = logging.getLogger(__name__)

logger.debug('Included module rpc.signaler ...')


class Signaler:
    """ This class handles all signaler communication """

    def __init__(self, rpc: RPC, config: Dict[str, Any], freqtradebot: FreqtradeBot) -> None:
        """
        Init the Signaler class, and init Pyrogram Client superclass
        :param rpc: Instance of Freqtrade's RPC Helper class
        :param config: Freqtrade's configuration object
        :return: None
        """
        self._rpc = rpc
        self._config = config
        self._freqtradebot = freqtradebot
        if not self._config['telegram']['api_id']:
            raise OperationalException("Missing telegram api_id configuration.")
        elif not self._config['telegram']['api_hash']:
            raise OperationalException("Missing telegram api_hash configuration.")
        elif not self._config['telegram']['token']:
            raise OperationalException("Missing telegram token configuration.")
        self._client = Client(
            api_id=self._config['telegram']['api_id'],
            api_hash=self._config['telegram']['api_hash'],
            bot_token=self._config['telegram']['token'],
            parse_mode="markdown",
            sleep_threshold=60,
            workdir=self._config['user_data_dir'],
            session_name="Freqsignaler_bot"
        )
        init_db(self._config, self._client)

    def start_signaler(self) -> None:
        logger.info(
            'rpc.signaler is now running.'
            f' Powered by Pyrogram v{__version__}'
        )
        self.init_handlers()
        try:
            self._client.start()
            self.send_started_message()
            idle()
            self._client.stop()
        except ConnectionError as e:
            logger.warning(str(e) + ". This is often due to the signaler "
                                    "being shut down via the stop command.")
        except BadRequest as e:
            raise OperationalException(str(e))
        except RPCError as e:
            raise OperationalException("Pyrogram had an error : " + str(e))

    def init_handlers(self):
        # Generate the handlers
        welcome_user_handler = MessageHandler(self.start_handler, filters.command(["start"]))
        restart_handler = MessageHandler(self.restart_handler, filters.command(["restart"]))
        stop_handler = MessageHandler(self.stop_handler, filters.command(["stop"]))
        test_handler = MessageHandler(self.test_handler, filters.command(["test"]))
        # Add the handlers to the client
        self._client.add_handler(welcome_user_handler)
        self._client.add_handler(restart_handler)
        self._client.add_handler(stop_handler)
        self._client.add_handler(test_handler)

    def restart_handler(self, client: Client, message: Message):
        """
        Restart the client (this is not working entirely as intended for now!)
        dont async this
        """
        if SignalerUser.allow_owners_only(message.chat.id, "restart"):
            logger.info("rpc.signaler received the restart command.")
            message.reply_text("Restarting the signaler.")
            client.restart(block=False)
            self.init_handlers()
            self.send_started_message()

    def send_started_message(self):
        """
        Send started message to owners
        """
        logger.info("rpc.signaler was started.")
        # Make sure the freqtrade bot owner is considered a owner by the signaler module
        if not SignalerUser.get_owners():
            logger.info("rpc.signaler is missing owners!.")
            owner = self._client.get_users(self._config['telegram']['chat_id'])
            owner_id = owner.id
            if not SignalerUser.get_user(owner_id) and owner_id:
                logger.warning('Didn''t find the freqtrade bot owner in the signaler user DB.'
                               'Adding him with owner rights')
                bot_owner = SignalerUser.add_new_user(owner_id, self.get_username(owner))
                SignalerUser.set_owner(bot_owner)
                SignalerUser.query.session.commit()
        for owner in SignalerUser.get_owners():
            logger.info(f'rpc.signaler sent startup message to {owner.user_name}')
            try:
                self._client.send_message(owner.user_id,
                                          "Signaler is started homie.",
                                          reply_markup=OWNER_MENU_MARKUP)
            except PeerIdInvalid:
                me = self._client.get_me()
                logger.info(f'rpc.signaler tried to send startup message to {owner.user_name}'
                            f'but was unsucessful. Make sure you interacted with {me.username} first!')

    @staticmethod
    async def test_handler(client: Client, message: Message):
        """

        :param client:
        :param message:
        :return:
        """
        logger.info("rpc.signaler received the test command.")
        user_name = message.chat.first_name
        text = f"Wow, {user_name}. Great moves. Keep it up. Proud of you. \n"
        text = await SignalerUser.user_ownership_message(message, text)
        await message.reply_text(text=text, reply_markup=SignalerUser.reply_menu_markup(message.chat.id))

    @staticmethod
    def stop_handler(client: Client, message: Message):
        """
        Handle /stop sent to the bot (stops the signaler/freqtrade instance)
        """
        if SignalerUser.allow_owners_only(message.chat.id, "stop"):
            logger.info("rpc.signaler received the stop command.")
            message.reply_text("Stopping the signaler.")
            client.stop(block=False)
            signal.raise_signal(signal.SIGINT)

    @staticmethod
    async def start_handler(client: Client, message: Message):
        """
        Handle /start sent to the bot (sends greetings and allow asking for permission by users)
        """
        logger.info("rpc.signaler sent a welcome message!")
        user = message.chat.username
        user_id = message.chat.id
        user_markup = MENTION.format(user, user_id)
        text = STARTED_MESSAGE.format(emoji.PARTY_POPPER, emoji.PARTY_POPPER, user_markup, SIGNALER_VERSION)
        text = await SignalerUser.user_ownership_message(message, text)
        await message.reply_text(text, disable_web_page_preview=True, reply_markup=SignalerUser.reply_menu_markup(user_id))

    @staticmethod
    def get_username(user: User) -> str:
        if user.username is None:
            return user.first_name
        return user.username




