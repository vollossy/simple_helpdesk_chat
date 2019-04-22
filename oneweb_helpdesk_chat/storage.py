"""
Хранилище бизнес-объектов(работа с базой данных).
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Query, scoped_session

_engine = None


def engine():
    global _engine
    if _engine is None:
        # todo: сделать вариацию для получения именно тестовой бд
        _engine = sqlalchemy.create_engine(
            'postgresql://postgres:simplepass@localhost/oneweb_helpdesk_chat_test',
            echo=True, pool_size=10, max_overflow=0
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

    # todo: добавить обработку случаев, когда в сообщении отправлен не текст( пока что будем делать уведомление, что
    #   такие сообщения не принимаются)
    text = Column(Text, nullable=False)
    datetime = Column(DateTime, nullable=False, server_default=func.now())

    dialog = relationship("Dialog", back_populates="messages")
