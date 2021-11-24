import logging
from typing import Dict, Any

from freqtrade.configuration import setup_utils_configuration, Configuration
from freqtrade.enums import RunMode
from freqtrade.rpc import RPC, Signaler
from freqtrade.freqtradebot import FreqtradeBot

logger = logging.getLogger(__name__)


def start_signaler(args: Dict[str, Any]) -> int:
    """
    Entry point for signaler
    """
    configuration = Configuration(args, RunMode.DRY_RUN)
    config = configuration.get_config()
    freqtrade = FreqtradeBot(config)
    rpc = RPC(freqtrade)
    signaler = init_signaler(rpc, config, freqtrade)
    logger.info('rpc.signaler successfully instanciated.')
    signaler.start_signaler()
    logger.info('rpc.signaler successfully shut down.')
    return 0


def init_signaler(rpc: RPC, config: Dict[str, Any], freqtrade: FreqtradeBot) -> Signaler:
    return Signaler(rpc, config, freqtrade)
