import logging
from typing import Union

logger = logging.getLogger(__name__)


async def extract_user_id(query: Union[str, bytes, None]) -> int:
    return int(''.join(c for c in query if c.isdigit()))
