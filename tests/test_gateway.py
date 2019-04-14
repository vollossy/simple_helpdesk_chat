"""
Модульные тесты для класса шлюза
"""
import unittest
import asyncio
from unittest import mock

from aiohttp import web

from oneweb_helpdesk_chat import storage
from oneweb_helpdesk_chat.gateways import Gateway, Message
from tests.utils import AsyncMock


class TestGateway(Gateway):

    async def parse_message(self, request) -> Message:
        pass

    def send_message(self, message):
        pass

    def get_channel(self):
        return storage.Channels.WHATSAPP


class GatewayTestCase(unittest.TestCase):

    def test_handle_message_without_dialog(self):
        """
        В случае, когда сообщение еще не привязано ни к одному диалогу, то метод
        :meth:`oneweb_helpdesk_chat.gateways.Gateway.handle_message` должен создавать новый диалог и привязывать к нему
        полученное сообщение
        """

        storage.Base.metadata.create_all(storage.engine())
        loop = asyncio.get_event_loop()

        gateway = TestGateway()
        request_mock = mock.MagicMock(spec=web.Request)
        message_patch = Message("+79876543210", "Example text")
        with mock.patch.object(gateway, 'parse_message', return_value=message_patch, new_callable=AsyncMock):
            dialogs = storage.session().query(storage.Dialog)
            message = loop.run_until_complete(gateway.handle_message(request_mock))  # type: storage.Message
            self.assertNotIn(message.dialog, dialogs)

        loop.close()
        storage.executor.shutdown()
        storage.Base.metadata.drop_all(storage.engine())

