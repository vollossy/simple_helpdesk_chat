"""
Хранилище бизнес-объектов(работа с базой данных).
"""
import asyncio
from enum import Enum

import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Query
from sqlalchemy.orm.session import Session

_engine = None

AppSession = sessionmaker()


def engine():
    global _engine
    if _engine is None:
        _engine = sqlalchemy.create_engine('sqlite:///:memory:', echo=True)
    return _engine


def session() -> Session:
    if not _engine:
        AppSession.configure(bind=engine())
    return AppSession()


async def fetch_results(query: Query, fetch_method="all", *args):
    """
    простая обертка для получения результатов запроса асинхронно(внутри используется
    asyncio.get_event_loop().run_in_executor)
    :param query: Запрос, который нужно выполнить
    :param fetch_method: Метод, который используется для получения
    :param args: Аргументы для метода fetch_method
    :return:
    """
    return asyncio.get_event_loop().run_in_executor(
        None,
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
    messages = relationship("Message", back_populates="dialog")


class Message(Base):
    """
    Отдельное сообщение от клиента пользователю и обратно.

    :ivar int user_id: Идентификатор работника тп-отправителя сообщения, если null, значит сообщение было отправлено
      клиентом из указанного диалога
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(Integer, nullable=True)
    # destination - то же самое, что и source только для получателя сообщения
    destination = Column(Integer, nullable=False)
    channel = Column(sqlalchemy.Enum, sqlalchemy.Enum(Channels), nullable=False)
    # метаданные сообщения, пришедшие от канала
    channel_metadata = Column(sqlalchemy.JSON, nullable=True)
    # идентификатор связанного диалога
    dialog_id = Column(Integer, ForeignKey("dialogs.id"), nullable=True)

    # todo: добавить обработку случаев, когда в сообщении отправлен не текст( пока что будем делать уведомление, что
    #   такие сообщения не принимаются)
    text = Column(Text, nullable=False)
    datetime = Column(DateTime, nullable=False, server_default=func.now())

    dialog = relationship("Dialog", back_populates="messages")