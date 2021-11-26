"""
This signaler submodule contains the classes to persist information into SQLite
"""
import logging
from datetime import datetime
from typing import Any, List, Dict

from sqlalchemy import (Boolean, Column, DateTime, Integer, String,
                        create_engine)
from sqlalchemy.exc import NoSuchModuleError, NoResultFound
from sqlalchemy.orm import  declarative_base, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from freqtrade.exceptions import OperationalException
from freqtrade.rpc.signaler_messages import OWNER_MESSAGE, GUEST_MESSAGE,\
    USER_MENU_MARKUP, OWNER_MENU_MARKUP, MENTION
from pyrogram import Client, emoji
from pyrogram.types import ReplyKeyboardMarkup, Message


logger = logging.getLogger(__name__)


_DECL_BASE: Any = declarative_base()
_SQL_DOCS_URL = 'http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls'


class SignalerUser(_DECL_BASE):
    """
    Users database model.
    Also handles updating and querying users
    """
    __tablename__ = 'users'

    use_db: bool = True

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_name = Column(String, nullable=False, index=True)
    is_owner = Column(Boolean, nullable=False, index=False)
    # last signal received

    # there is 3 'states' of approval for a user.
    # 1. is_allowed and has_demand is false (can ask to be allowed, first interaction)
    # 2. is_allowed is True (therefore has_demand aswell)
    # 3. is_allowed is False and has_demand is True (has asked to be allowed and got denied)
    is_allowed = Column(Boolean, nullable=False, index=True)
    has_demanded = Column(Boolean, nullable=False, index=True, default=False)
    join_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    def delete(self) -> None:
        """
        Delete from signaler database
        """
        SignalerUser.query.session.delete(self)
        SignalerUser.query.session.commit()

    def allow_user(self) -> None:
        """
        Allow this user
        """
        self.is_allowed = True
        SignalerUser.query.session.commit()

    def deny_user(self) -> None:
        """
        Deny this user
        """
        self.is_allowed = False
        SignalerUser.query.session.commit()

    def set_owner(self) -> None:
        """
        Set this user as owner
        """
        self.is_owner = True
        self.is_allowed = True
        SignalerUser.query.session.commit()

    def disallow_user(self) -> None:
        """
        Disallow this user
        """
        self.is_owner = False
        self.is_allowed = False
        SignalerUser.query.session.commit()

    def set_name(self, name: str) -> None:
        """
        Set this user's name
        """
        self.user_name = name
        SignalerUser.query.session.commit()

    def just_demanded(self) -> None:
        """
        Set has_demanded to True
        """
        self.has_demanded = True
        SignalerUser.query.session.commit()

    @staticmethod
    def reply_menu_markup(user_id: int) -> ReplyKeyboardMarkup:
        if SignalerUser.allow_owners_only(user_id):
            return OWNER_MENU_MARKUP
        else:
            return USER_MENU_MARKUP

    @staticmethod
    async def user_ownership_message(message: Message, text):
        if SignalerUser.allow_owners_only(message.chat.id):
            text = text + OWNER_MESSAGE.format(emoji.CROWN, emoji.CROWN)
        else:
            owner = SignalerUser.get_owners()[0]
            owner_markup = MENTION.format(owner.user_name, owner.id)
            text = text + GUEST_MESSAGE.format(emoji.CHAINS, owner_markup, emoji.CHAINS)
        return text

    @staticmethod
    def add_new_user(user_id: int, user_name: str) -> 'SignalerUser':
        SignalerUser.query.session.add(SignalerUser(user_id=user_id, user_name=user_name,
                                                    is_owner=False, is_allowed=False,
                                                    has_demanded=False))
        SignalerUser.query.session.commit()
        return SignalerUser.get_user(user_id)

    @staticmethod
    def get_owners() -> List['SignalerUser']:
        """
        Retrieve all owners
        """
        return SignalerUser.query.filter(SignalerUser.is_owner.is_(True)).all()

    @staticmethod
    def get_allowed_users() -> List['SignalerUser']:
        """
        Retrieve all approved users
        """
        return SignalerUser.query.filter(SignalerUser.is_allowed.is_(True)).all()

    @staticmethod
    def get_users() -> List['SignalerUser']:
        """
        Retrieve all users
        """
        return SignalerUser.query.all()

    @staticmethod
    def get_user(user_id: int) -> 'SignalerUser':
        """
        Retrieve a specific user
        :param user_id: user_id of target
        """
        try:
            return SignalerUser.query.filter(SignalerUser.user_id.is_(user_id)).one()
        except NoResultFound:
            logger.warning(f'Was asked about user_id ({user_id}) '
                           'and he was not found.')

    @staticmethod
    def get_join_date(user_id: int) -> DateTime:
        """
        Retrieve join date for a specific user
        :param user_id: user_id of target
        :return:
        """
        return SignalerUser.get_user(user_id).get('join_date')

    @staticmethod
    def user_is_allowed(user_id: int) -> bool:
        """
        Check if a user is allowed
        :param user_id: user_id of target
        """
        return SignalerUser.get_user(user_id).is_allowed

    @staticmethod
    def user_has_demanded(user_id: int) -> bool:
        """
        Check if a user has already demanded
        """
        return SignalerUser.get_user(user_id).has_demanded

    @staticmethod
    def allow_owners_only(user_id: int, command=None) -> bool:
        if SignalerUser.get_user(user_id).is_owner:
            return True
        else:
            if command is not None:
                logger.info("Signaler received unauthorized "
                            f"command {command} from {user_id}", command, user_id)
            return False

    @staticmethod
    def owner_info(is_owner: bool) -> str:
        if is_owner:
            return OWNER_MESSAGE
        else:
            return GUEST_MESSAGE

    @staticmethod
    def get_main_owner() -> 'SignalerUser':
        return SignalerUser.query.filter(SignalerUser.is_owner.is_(True), SignalerUser.join_date.asc()).one()


def init_db(config: Dict[str, Any], client: Client) -> None:
    """
    Initializes the signaler module database
    :param config: Freqtrade configuration
    :param client: Pyrogram client
    :return: None
    """
    kwargs = {}
    logger.info('rpc.signaler database is initializing.')
    db_url = config.get('db_url', None)
    if db_url == 'sqlite://':
        kwargs.update({
            'poolclass': StaticPool,
        })
    # Take care of thread ownership
    if db_url.startswith('sqlite://'):
        kwargs.update({
            'connect_args': {'check_same_thread': False},
        })

    try:
        engine = create_engine(db_url, future=True, **kwargs)
        _DECL_BASE.metadata.bind = engine
        _DECL_BASE.metadata.create_all(engine)
    except NoSuchModuleError:
        raise OperationalException(f"Given value for db_url: '{db_url}' "
                                   f"is no valid database URL! (See {_SQL_DOCS_URL})")
    logger.info('rpc.signaler database is initialized.')
    # https://docs.sqlalchemy.org/en/13/orm/contextual.html#thread-local-scope
    # Scoped sessions proxy requests to the appropriate thread-local session.
    # We should use the scoped_session object - not a seperately initialized version
    SignalerUser._session = scoped_session(sessionmaker(bind=engine, autoflush=True))
    SignalerUser.query = SignalerUser._session.query_property()
    logger.info('rpc.signaler user database is loaded.')

