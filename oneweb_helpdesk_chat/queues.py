"""
Данный модуль предоставляет различные реализации очередей для взаимодействия с
чатом. Предполагается, что этот модуль будет использован как для простой
реализации репозитория очередей и самих очередей, так и для более продвинутой
реализации, например на базе redis'а.
"""
import asyncio

from oneweb_helpdesk_chat.storage import Message


class DictRepository:
    """
    Самая примитивная реализация репозитория. Данный репозиторий использует
    словарь для хранения очередей и asyncio.Queue для хранения элементов очереди

    """
    def __init__(self) -> None:
        super().__init__()
        self.dict = {}

    async def put(self, queue_name: str, message: Message):
        """
        Сохранение сообщения в очерди
        :param queue_name: Название очереди, если ее нет, то будет созадана
        :param message: Сообщение, которое нужно будет сохранить
        :return:
        """
        return await self.dict.setdefault(queue_name, asyncio.Queue()).put(
            message
        )

    async def get(self, queue_name: str) -> Message:
        """
        Получить сообщение из указанной очереди. Помните, что при получении
        сообщения из очереди, оно будет удалено из нее
        :param queue_name: Название очереди, откуда нужно получить сообщение
        :return:
        """
        return await self.dict.setdefault(queue_name, asyncio.Queue()).get()
