"""
Шлюзы для взаимодейстия с серверами чатов. Данный модуль предназначен для
обработки http-запросов от сервисов
"""
import string
from aiohttp import web
from sqlalchemy.orm import Query

from oneweb_helpdesk_chat import storage
from abc import ABCMeta, abstractmethod


class Message:
    """
    Объект сообщения только для использования в текущем модуле, предоставляет информацию о полученном сообщении
    """

    def __init__(self, phone_number, text, user_name="") -> None:
        super().__init__()
        self.phone_number = phone_number
        self.text = text
        self.user_name = user_name


class Gateway(metaclass=ABCMeta):
    """
    Базовый класс для шлюзов. Шлюз представляет собой прослойку, которая отвечает за взаимодействие с сервисом.
    Каждый шлюз должен реализовывать методы handle_message и send_message. Шлюзы используются в методе
    :meth:`app.gateway_hook`, а также в модуле :mod:`chat` для отправки сообщений в сервис
    """

    def __init__(self) -> None:
        super().__init__()
        self.session = storage.session()
        self.get_dialog_query = self.session.query(storage.Dialog).join(storage.Customer)  # type: Query
        self.get_customer_query = self.session.query(storage.Customer)

    async def handle_message(self, request: web.Request) -> storage.Message:
        """
        Обработка пришедшего сообщения от сервиса. Данный метод вызывает парсинг тела сообщения а также привязывает
        сообщение к имеющемуся диалогу
        :param request:
        :return:
        """
        raw_message = await self.parse_message(request)
        dialog = await storage.fetch_results(
            query=self.get_dialog_query.filter(storage.Customer.phone_number == raw_message.phone_number),
            fetch_method="first"
        )
        if dialog is None:
            customer = await storage.fetch_results(
                self.get_customer_query.filter(storage.Customer.phone_number == raw_message.phone_number),
                fetch_method="first"
            )
            if customer is None:
                customer = self.session.add(
                    storage.Customer(name=raw_message.user_name, phone_number=raw_message.phone_number)
                )
            # todo: добавить здесь атачмент сообщения
            dialog = storage.Dialog(customer=customer)

        message = storage.Message(channel=self.get_channel(), text=raw_message.text)
        dialog.messages.append(message)
        self.session.add(dialog)

        self.session.commit()
        return message

    @abstractmethod
    def get_channel(self):
        pass

    @abstractmethod
    async def parse_message(self, request) -> Message:
        """
        Парсинг тела сообщения
        :param request:
        :return:
        """

    @abstractmethod
    def send_message(self, message):
        """
        Отправка собщения в сервис
        :param message:
        :return:
        """


class Repository:
    """
    Реозиторий для шлюзов
    """

    def __init__(self) -> None:
        super().__init__()

        self._repository = {}

    def register_gateway(self, alias: str, gateway: Gateway):
        """
        Регистрирует шлюз в репозитории. Один и тот же шлюз может быть
        зарегистрирован под разными названиями.
        :param alias: Название для шлюза. Не должно содержать пробелов
        :param gateway: Непосредственно шлюз
        :return:
        """
        if string.whitespace in alias:
            raise ValueError("Gateway alias can't contain any whitespace characters")
        self._repository[alias] = gateway

    def unregister_gateway(self, alias: str):
        """
        Убрать шлюз из репозитория
        :param alias:
        :return:
        """
        return self._repository.pop(alias)

    def get_gateway(self, alias: str) -> Gateway:
        """
        Возвращает шлюз из репозитория по его псевдониму
        :param alias:
        :return:
        """
        return self._repository[alias]


class WhatsappGateway(Gateway):
    """
    Шлюз для общения с Вотсаппом
    """


repository = Repository()
