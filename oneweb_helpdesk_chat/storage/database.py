"""
Модуль, отвечающий за взаимодействие с базой данных. Данный модуль содержит
объявления моделей
"""
import asyncio
import typing
from abc import ABCMeta
from concurrent.futures import ThreadPoolExecutor

import sqlalchemy
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Text, DateTime, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    relationship, sessionmaker, Query, scoped_session, Session)

from oneweb_helpdesk_chat import config
from . import domain

_engine = None


def engine():
    global _engine
    if _engine is None:
        # todo: сделать вариацию для получения именно тестовой бд
        _engine = sqlalchemy.create_engine(
            config.DB_URL, echo=False, pool_size=10, max_overflow=0
        )
    return _engine


AppSession = sessionmaker()
ScopedAppSession = scoped_session(sessionmaker())

executor = ThreadPoolExecutor(10)


async def fetch_results(query: Query, fetch_method="all", *args):
    """
    Простая обертка для получения результатов запроса асинхронно(внутри используется
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


async def perform_commit(session: sqlalchemy.orm.Session):
    """
    Обертка для асинхронного коммита в бд
    :param session: Сессия, которую нужно закоммитить
    :return:
    """
    return await asyncio.get_event_loop().run_in_executor(
        executor, session.commit
    )

Base = declarative_base()


class Customer(Base, domain.Customer):
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


class User(Base, domain.User):
    """
    Пользователь, сотрудник техподдержки
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    login = Column(String, nullable=False)
    password = Column(String, nullable=False)
    dialogs = relationship("Dialog", back_populates="assigned_user")


class Dialog(Base, domain.Dialog):
    __tablename__ = "dialogs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    # assigned_user_id будет постоянно меняться
    # todo: нужно будет добавть логгирование смены пользователя
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    customer = relationship("Customer", back_populates="dialogs")
    assigned_user = relationship("User", back_populates="dialogs")
    messages = relationship("Message", back_populates="dialog")  # type: list


class Message(Base, domain.Message):
    """
    Отдельное сообщение от клиента пользователю и обратно.

    :ivar int user_id: Идентификатор работника тп-отправителя сообщения, если null, значит сообщение было отправлено
      клиентом из указанного диалога
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(Integer, nullable=True)
    channel = Column(
        sqlalchemy.Enum(domain.Channel, name='channels'),
        nullable=False
    )
    # метаданные сообщения, пришедшие от канала
    # channel_metadata = Column(sqlalchemy.JSON, nullable=True)
    # идентификатор связанного диалога
    dialog_id = Column(Integer, ForeignKey("dialogs.id"), nullable=True)

    # todo: добавить обработку случаев, когда в сообщении отправлен не текст(
    #  пока что будем делать уведомление, что такие сообщения не принимаются)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    dialog = relationship("Dialog", back_populates="messages")


DT = typing.TypeVar("DT", domain.Dialog, domain.Customer, User)
DBT = typing.TypeVar("DBT", Dialog, Customer)


class BaseRepository(typing.Generic[DT], metaclass=ABCMeta):
    """
    Базовый класс для репозиториев, связанных с бд
    """

    model_class = None

    def __init__(
            self,
            session_constructor: typing.Callable[[], Session] = ScopedAppSession
    ) -> None:
        super().__init__()
        self.session_constructor = session_constructor  # type: typing.Callable[[], Session]

    async def save(self, obj: DT):
        """
        Производит сохранение объекта в бд
        :param obj: объект доменной модели, который нужно сохранить
        :return:
        """
        session = self.session_constructor()
        session.add(obj)
        await perform_commit(session)

    async def get_by_id(self, pk: int) -> DT:
        """
        Возвращает объект из хранилища по его идентификатору
        :param pk: Идентификатор, по котоорому нужно будет найти объект
        :return:
        """
        session = self.session_constructor()  # type: Session
        query = session.query(self.model_class).filter(
            self.model_class.id == pk
        )
        return await fetch_results(query, 'first')

    async def get_one_by_field(self, field: str, value: typing.Any) -> DT:
        """
        Возвращает первый найденный экземпляр объекта по указанному полу
        :param field: Название поля
        :param value: Значение поля для поиска
        :return:
        """
        db_field = getattr(self.model_class, field)
        query = self.session_constructor().query(self.model_class).filter(
            db_field == value
        )
        return await fetch_results(query, 'first')


class CustomerRepository(BaseRepository[domain.Customer]):
    """
    Репозиторий для работы с клиентами
    """

    async def get_by_phone(self, phone_number: str) -> domain.Customer:
        """
        Возвращает клиента по указанному номеру телефона
        :param phone_number: номер телефона
        :return:
        """
        session = self.session_constructor()
        query = session.query(Customer).filter(
            Customer.phone_number == phone_number
        )
        return await fetch_results(query, 'first')


class DialogRepository(BaseRepository[domain.Dialog]):
    """
    Репозиторий для работы с диалогами. базовая реализация взаимодействует с бд
    посредством sqlalchemy
    """

    async def get_by_phone(self, phone_number: str) -> domain.Dialog:
        """
        Возвращает диалог по номеру телефона кастомера
        :param phone_number: Номер телефона для поиска диалога.
        :return:
        """
        # todo: добавить форматирование номера телефона при помощи google phone
        #  library
        session = self.session_constructor()  # type: Session
        query = session.query(Dialog).join(Customer).filter(
            Customer.phone_number == phone_number
        )
        return await fetch_results(query, 'first')


class UserRepository(BaseRepository[User]):
    """
    Репозиторий для пользователей
    """
    model_class = User

    async def get_by_login(self, login: str) -> User:
        """
        Возвращает пользователя с  указанным логином
        :param login: логин для поиска
        :return:
        """
        return await self.get_one_by_field('login', login)


