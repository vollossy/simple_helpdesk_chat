"""
Тесты непосредственно для чата
"""
import asyncio
from datetime import datetime
from unittest import TestCase, mock
from aiohttp import web

from oneweb_helpdesk_chat.chat import ChatHandler
from oneweb_helpdesk_chat.queues import DictRepository
from oneweb_helpdesk_chat.storage import Dialog, User, Customer, Message
from oneweb_helpdesk_chat.storage.database import MessagesRepository
from tests import utils
from oneweb_helpdesk_chat.gateways import Repository


class ChatHandlerTestCase(TestCase):
    """
    Тестовый кейс для класса  :class:`oneweb_helpdesk_chat.chat.ChatHandler`.

    :ivar MagicMock ws_mock: mock for web socket
    """

    def setUp(self) -> None:
        super().setUp()

        self.ws_mock = mock.MagicMock(spec=web.WebSocketResponse)
        self.ws_mock.send_json = utils.AsyncMock()
        self.ws_mock.receive_json = utils.AsyncMock()
        type(self.ws_mock).closed = mock.PropertyMock(
            side_effect=(False, True)
        )
        self.queues_repository = DictRepository()
        self.messages_repository = mock.MagicMock(spec=MessagesRepository)
        self.messages_repository.save = utils.AsyncMock()

    def test_read_from_customer(self):
        """
        Простой тест для чтения сообщений от клиента. При поступлении нового
        сообщения в очередь, запись должна производиться в веб сокет.
        :return:
        """
        dialog = Dialog(id=123)
        dialog.customer = Customer(id=1, name="Example customer")
        user = User(id=123)
        message = Message(
            text="This is example message", created_at=datetime.today()
        )

        asyncio.get_event_loop().run_until_complete(
            self.queues_repository.put(str(dialog.id), message)
        )
        handler = ChatHandler(
            ws=self.ws_mock, dialog=dialog, user=user,
            queues_repository=self.queues_repository
        )

        asyncio.get_event_loop().run_until_complete(
            handler.read_from_customer()
        )

        self.ws_mock.send_json.assert_called()

    def test_write_to_customer(self):
        """
        Простой тест для отправки сообщений клиенту(кастомеру). В этом случае
        все происходит довольно просто и тупо: приходит сообщение в веб-сокет
        и оно уже отправляется через шлюз непосредственно в сервис, который
        работает с этими сообщениями. при этом сообщение будет сохранено в бд
        """
        message_to_send = Message(
            text="example text", channel="example"
        )
        self.ws_mock.receive_json.return_value = message_to_send
        dialog = Dialog(id=123)
        dialog.customer = Customer(id=1, name="Example customer")
        user = User(id=123)

        gateway_mock = mock.MagicMock()

        gateways_repository = Repository()
        gateways_repository.register_gateway(
            "example", gateway_mock
        )

        handler = ChatHandler(
            ws=self.ws_mock, dialog=dialog, user=user,
            queues_repository=self.queues_repository,
            gateways_repository=gateways_repository,
            messages_repository=self.messages_repository
        )
        asyncio.get_event_loop().run_until_complete(
            handler.write_to_customer()
        )

        # Проверяем, сохранилось ли сообщение в бд
        self.messages_repository.save.assert_called_with(
            message_to_send
        )

        gateway_mock.send_message.assert_called_with(message_to_send)
        self.assertEqual(dialog, message_to_send.dialog)
