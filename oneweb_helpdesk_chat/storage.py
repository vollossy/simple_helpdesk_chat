"""
Хранилище бизнес-объектов(работа с базой данных).
"""
import asyncio
import hashlib
import binascii
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import secrets

import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Query, scoped_session

from oneweb_helpdesk_chat import config

_engine = None


def engine():
    global _engine
    if _engine is None:
        # todo: сделать вариацию для получения именно тестовой бд
        _engine = sqlalchemy.create_engine(
            config.DB_URL, echo=True, pool_size=10, max_overflow=0
        )
    return _engine


AppSession = sessionmaker()
ScopedAppSession = scoped_session(sessionmaker())

executor = ThreadPoolExecutor(10)


async def fetch_results(query: Query, fetch_method="all", *args):
    """
    простая обертка для получения результатов запроса асинхронно(внутри используется
    asyncio.get_event_loop().run_in_executor)
    :param query: Запрос, который нужно выполнить
    :param fetch_method: Метод, который используется для получения
    :param args: Аргументы для метода fetch_method
    :return:
    """
    return await asyncio.get_event_loop().run_in_executor(
        executor,
        getattr(query, fetch_method),
        *args
    )


class Channels(Enum):
    """
    Доступные каналы для
    """
    WHATSAPP = "whatsapp"
    VIBER = "VIBER"


Base = declarative_base()


class Customer(Base):
    """
    Клиент. Тот, кто обращается к нам
    :type dialogs: list(Dialog)
    :ivar str phone_number: Номер телефона клиента, по нему мы связываем нескольких клиентов, пришедших из разных
      каналов.
      todo: некоторые каналы могут не иметь номер телефона, тогда нам нужно еще добавить какие-то другие
        алиасы, причем по нескольку, но это довольно сложная задача
    """
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    dialogs = relationship("Dialog", back_populates="customer")  # type:


class User(Base):
    """
    Пользователь, сотрудник техподдержки
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    login = Column(String, nullable=False)
    password = Column(String, nullable=False)
    dialogs = relationship("Dialog", back_populates="assigned_user")


class Dialog(Base):
    __tablename__ = "dialogs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    # assigned_user_id будет постоянно меняться
    # todo: нужно будет добавть логгирование смены пользователя
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    customer = relationship("Customer", back_populates="dialogs")
    assigned_user = relationship("User", back_populates="dialogs")
    messages = relationship("Message", back_populates="dialog") # type: list


class Message(Base):
    """
    Отдельное сообщение от клиента пользователю и обратно.

    :ivar int user_id: Идентификатор работника тп-отправителя сообщения, если null, значит сообщение было отправлено
      клиентом из указанного диалога
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(Integer, nullable=True)
    channel = Column(
        sqlalchemy.Enum(Channels, name='channels'),
        nullable=False
    )
    # метаданные сообщения, пришедшие от канала
    # channel_metadata = Column(sqlalchemy.JSON, nullable=True)
    # идентификатор связанного диалога
    dialog_id = Column(Integer, ForeignKey("dialogs.id"), nullable=True)

    # todo: добавить обработку случаев, когда в сообщении отправлен не текст(
    #  пока что будем делать уведомление, что такие сообщения не принимаются)
    text = Column(Text, nullable=False)
    datetime = Column(DateTime, nullable=False, server_default=func.now())

    dialog = relationship("Dialog", back_populates="messages")


def _generate_password_hash_internal(password, algorithm, salt) -> str:
    """
    Приватная функция, которая выполняет генерацию хеша для пароля. В отличие от
    метода :meth:`~.create_password_hash`, данный метод не генерирует соль
    автоматически, а также возвращает **только** пароль без дополнительной
    мета-информации
    :param password: пароль для генерации хеша
    :param algorithm: алгортим хеширования
    :param salt: соль для хеша
    :return: str
    """
    return binascii.hexlify(hashlib.pbkdf2_hmac(
        algorithm, password.encode('utf8'), salt.encode(), 10000
    )).decode()


def create_password_hash(
        password: str,
        algorithm: str = config.HASHING_ALGORITHM
) -> str:
    """
    Генерирует хеш пароля используя предоставленный алгоритм а также соль.
    Для генерации пароля используется метод :meth:`hashlib.pbkdf2_hmac`.
    :param password: Пароль, хеш которого нужно сгененрировать
    :param algorithm: Алгоритм хеширования
    :return:
    """
    salt = binascii.hexlify(secrets.token_bytes(32)).decode()

    return '$'.join([
        algorithm,
        salt,
        _generate_password_hash_internal(password, algorithm, salt)
    ])


def validate_password(pw_hash: str, password: str) -> bool:
    """
    Проверяет пароль на соответствие хешу. Хеш должен содержать также информацию
    об алгоритме и соли, использованной для при генерации хеша. Изначально эта
    функция подразумевает проверку паролей, сформированных функцией
    :meth:`~.create_password_hash`
    :param pw_hash: Хеш для проверки
    :param password: Пароль, который нужно проверить
    :return: bool Соответствует ли предоставленный пароль указанному хешу
    """
    splitted_hash = pw_hash.split('$')
    if len(splitted_hash) != 3:
        return False
    algorithm, salt, hashed_password = splitted_hash
    return secrets.compare_digest(
        hashed_password,
        _generate_password_hash_internal(password, algorithm, salt)
    )


def create_user(name: str, login: str, password: str) -> User:
    """
    Создает нового пользователя в бд и автоматически хеширует его пароль.
    Внимание, данная функцися выполняется синхронно. Для работы в асинхронном
    контексте используй функцию :meth:`~.create_user_async`
    :param name: Полное имя пользователя
    :param login: Логин пользователя
    :param password: **Чистый** пароль(т.е. не хешированный)
    :return: созданный пользователь
    """

    user = User(name=name, login=login, password=create_password_hash(password))
    session = ScopedAppSession()
    session.add(user)
    session.commit()
    return user


async def create_user_async(name: str, login: str, password: str):
    """
    Асинхронный вариант функции :meth:`~.create_user`
    :param name: Полное имя пользователя
    :param login: Логин пользователя
    :param password: **Чистый** пароль(т.е. не хешированный)
    :return: созданный пользователь
    """
    return await asyncio.get_event_loop().run_in_executor(
        executor, create_user, name, login, password
    )
