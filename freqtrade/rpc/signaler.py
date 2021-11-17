"""
Run a pyrogram bot that can call freqtrade sub-commands
"""
import os
import logging
from typing import Dict, Any

from pyrogram import Client, __version__
from freqtrade.rpc import RPC, RPCHandler, RPCException
from freqtrade.exceptions import OperationalException

logger = logging.getLogger(__name__)

logger.debug('Included module rpc.signaler ...')


class AdaptedRPCHandler(RPCHandler):
    """ Adapter for RPCHandler """

    def __init__(self, rpc: RPC, config: Dict[str, Any]) -> None:
        """
        Init the Telegram call, and init the super class RPCHandler
        :param rpc: instance of RPC Helper class
        :param config: Configuration object
        :return: None
        """
        super().__init__(rpc, config)

    def send_msg(self, msg: Dict[str, str]) -> None:
        pass

    def cleanup(self) -> None:
        pass


class Signaler(Client, AdaptedRPCHandler):
    """ This class handles all signaler communication """

    def __init__(self, rpc: RPC, config: Dict[str, Any]) -> None:
        """
        Init the Signaler call, and init both super class Client and RPCHandler
        :param rpc:
        :param config:
        :return: None
        """
        self._rpc_handler = AdaptedRPCHandler(rpc, config)
        if not config['telegram']['app_id']:
            raise OperationalException("Missing telegram app_id configuration.")
        elif not config['telegram']['app_hash']:
            raise OperationalException("Missing telegram app_hash configuration.")
        elif not config['telegram']['token']:
            raise OperationalException("Missing telegram token configuration.")
        super().__init__(
            api_id=config['telegram']['app_id'],
            api_hash=config['telegram']['app_hash'],
            bot_token=config['telegram']['token'],
            parse_mode="html",
            sleep_threshold=60,
            workdir=config['user_data_dir'],
            test_mode=True
        )

    async def start(self) -> None:
        await super(Signaler, self).start()
        logger.info(
            'rpc.signaler is now running.'
            f' Powered by Pyrogram v{__version__}'
        )

    async def stop(self, *args) -> None:
        await super(Signaler, self).stop()
        logger.info(
            'rpc.signaler is now stopped.'
        )
