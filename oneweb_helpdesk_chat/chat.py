"""
Специфичные для чата компоненты
"""
from asyncio import Queue

from aiohttp import web

from oneweb_helpdesk_chat import gateways
from oneweb_helpdesk_chat.gateways import Repository
from oneweb_helpdesk_chat.queues import DictRepository
from oneweb_helpdesk_chat.storage import Message, Dialog, User
import json

DEFAULT_DT_FORMAT = "%Y-%m-%d %H:%M:%S"


class MessageEncoder(json.JSONEncoder):
    """
    Кодировщик для отдельного сообщения. Данный класс предполагает преобразование сообщение в dict, подходящий для
    передачи в соответствии с протоколом.
    """

    def default(self, o: Message):
        return {
            "text": o.text,
            "customer": {
                "id": o.dialog.customer.id,
                "name": o.dialog.customer.name
            },
            "datetime": o.created_at.strftime(DEFAULT_DT_FORMAT)
        }


class MessageDecoder(json.JSONDecoder):
    """
    Декодировщик для отдельного сообщения, преобразует словарь в экземпляр сообщения
    """

    def decode(self, s, *args):
        obj = super().decode(s, *args)
        message = Message(text=obj["text"])
        return message


class ChatHandler:
    """
    Хендлер для обработки чтения сообщения от клиента и отправки их ему же.
    Это просто класс, который объединяет в себе задачу чтения сообщения от
    клиента и задачу отправки.
    """

    def __init__(
            self, ws: web.WebSocketResponse, dialog: Dialog, user: User,
            queues_repository: DictRepository,
            gateways_repository: Repository = None
    ) -> None:
        super().__init__()
        self.ws = ws
        self.dialog = dialog
        self.user = user
        self.queues_repository = queues_repository
        self.gw_repository = (
            gateways_repository if gateways_repository else  gateways.repository
        )

    async def read_from_customer(self):
        """
        Таска, которая обрабатывает сообщения от клиента и пишет их в открытый
        в данный момент вебсокет. Чтение  прекращается, когда соединение с
        вебсокетом разрывается.
        """
        try:
            while not self.ws.closed:
                message = await self.queues_repository.get(
                    str(self.dialog.id)
                )  # type: Message
                await self.ws.send_json(
                    message, dumps=lambda x: json.dumps(x, cls=MessageEncoder)
                )
        except:
            # todo: добавить сюда логгирование исключения
            raise

    async def write_to_customer(self):
        """
        Обработка отправки сообщения клиенту. Эта таска читает сообщение от
        клиента пользователя(сотрудника тп), сохраняет его в бд и отправляет
        через шлюз клиенту
        :return:
        """
        while not self.ws.closed:
            message = await self.ws.receive_json(
                loads=lambda x: json.loads(x, cls=MessageDecoder)
            )
            message.dialog = self.dialog
            gateway = self.gw_repository.get_gateway(message.channel)
            gateway.send_message(message)
