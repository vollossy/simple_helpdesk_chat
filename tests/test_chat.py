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
from tests import utils


class ChatHandlerTestCase(TestCase):
    """
    Тестовый кейс для класса  :class:`oneweb_helpdesk_chat.chat.ChatHandler`.

    :ivar MagicMock ws_mock: mock for web socket
    """

    def setUp(self) -> None:
        super().setUp()

        self.ws_mock = mock.MagicMock(spec=web.WebSocketResponse)
        self.ws_mock.send_json = utils.AsyncMock()
        type(self.ws_mock).closed = mock.PropertyMock(
            side_effect=(False, False, True)
        )
        self.queues_repository = DictRepository()

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
