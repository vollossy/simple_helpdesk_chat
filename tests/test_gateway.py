"""
Модульные тесты для класса шлюза
"""
import unittest
import asyncio
from unittest import mock

from aiohttp import web
from sqlalchemy.orm import Session

from oneweb_helpdesk_chat import storage
from oneweb_helpdesk_chat.gateways import Gateway, Message
from tests.utils import AsyncMock


class TestGateway(Gateway):
    """
    Тестовый шлюз, который имеет все необходимые заглушки(возможно, нужно будет
    его переделать на использование magic mock'а)
    """
    async def parse_message(self, request) -> Message:
        pass

    def send_message(self, message):
        pass

    def get_channel(self):
        return storage.Channels.WHATSAPP


class GatewayTestCase(unittest.TestCase):
    """
    Тест для базового интерфейса шлюзов
    """

    def setUp(self) -> None:
        super().setUp()
        self.loop = asyncio.get_event_loop()
        storage.Base.metadata.drop_all(storage.engine())
        storage.Base.metadata.create_all(storage.engine())

        storage.ScopedAppSession.configure(bind=storage.engine())

        self.gateway = TestGateway(get_session=storage.ScopedAppSession)
        self.request_mock = mock.MagicMock(spec=web.Request)

    def tearDown(self) -> None:
        super().tearDown()
        storage.ScopedAppSession.commit()
        storage.ScopedAppSession.remove()
        storage.Base.metadata.drop_all(storage.engine())

    def test_handle_message_without_dialog(self):
        """
        В случае, когда сообщение еще не привязано ни к одному диалогу, то метод
        :meth:`oneweb_helpdesk_chat.gateways.Gateway.handle_message` должен
        создавать новый диалог и привязывать к нему
        полученное сообщение
        """
        message_patch = Message("+79876543210", "Example text")
        dialogs_query = storage.ScopedAppSession().query(storage.Dialog)
        with mock.patch.object(
            self.gateway, 'parse_message', return_value=message_patch,
            new_callable=AsyncMock
        ):
            # Список имеющихся диалогов
            dialogs = list(dialogs_query)
            message = self.loop.run_until_complete(
                self.gateway.handle_message(self.request_mock)
            )  # type: storage.Message
            self.assertNotIn(message.dialog, dialogs)

        self.assertIn(message.dialog, dialogs_query)

    def test_handle_message_with_dialog(self):
        """
        Когда сообщение уже привязано к диалогу, новый диалог не должен
        создаваться
        """
        phone_number = "+79876543210"
        customer = storage.Customer(
            name="Example user", phone_number=phone_number
        )
        dialog = storage.Dialog(customer=customer)
        session = storage.ScopedAppSession()  # type: Session
        session.add(customer)
        session.add(dialog)
        session.commit()

        message_patch = Message(phone_number, "Example text")
        with mock.patch.object(
                self.gateway, 'parse_message', return_value=message_patch,
                new_callable=AsyncMock
        ):
            message = self.loop.run_until_complete(
                self.gateway.handle_message(self.request_mock)
            )  # type: storage.Message
            self.assertEqual(message.dialog, dialog)
