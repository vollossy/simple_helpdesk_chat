"""
Шлюзы для взаимодейстия с серверами чатов. Данный модуль предназначен для
обработки http-запросов от сервисов
"""
import string
from aiohttp import web
import storage
from abc import ABCMeta, abstractmethod


class Gateway(metaclass=ABCMeta):
    """
    Базовый класс для шлюзов. Шлюз представляет собой прослойку, которая отвечает за взаимодействие с сервисом.
    Каждый шлюз должен реализовывать методы handle_message и send_message. Шлюзы используются в методе
    :meth:`app.gateway_hook`, а также в модуле :mod:`chat` для отправки сообщений в сервис
    """

    def handle_message(self, request: web.Request) -> storage.Message:
        """
        Обработка пришедшего сообщения от сервиса
        :param request:
        :return:
        """


    @abstractmethod
    async def parse_message(self, request):
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
