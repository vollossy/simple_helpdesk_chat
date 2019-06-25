"""
Модульные тесты для класса шлюза
"""
import asyncio
from unittest import mock

from aiohttp import web
from sqlalchemy.orm import Session, Query

from oneweb_helpdesk_chat.storage.domain import Channel
from oneweb_helpdesk_chat.storage import database
from oneweb_helpdesk_chat.gateways import Gateway, Message
from tests.utils import AsyncMock, BaseTestCase


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
        return Channel.TEST


class GatewayTestCase(BaseTestCase):
    """
    Тест для базового интерфейса шлюзов
    """

    def setUp(self) -> None:
        super().setUp()
        self.loop = asyncio.new_event_loop()
        database.Base.metadata.drop_all(database.engine())
        database.Base.metadata.create_all(database.engine())

        database.ScopedAppSession.configure(bind=database.engine())

        self.gateway = TestGateway(
            customer_repository=database.CustomerRepository(),
            dialog_repository=database.DialogRepository()
        )
        self.request_mock = mock.MagicMock(spec=web.Request)

    def tearDown(self) -> None:
        super().tearDown()
        database.ScopedAppSession.commit()
        database.ScopedAppSession.remove()
        database.Base.metadata.drop_all(database.engine())
        self.loop.close()

    def test_handle_message_without_dialog(self):
        """
        В случае, когда сообщение еще не привязано ни к одному диалогу, то метод
        :meth:`oneweb_helpdesk_chat.gateways.Gateway.handle_message` должен
        создавать новый диалог и привязывать к нему
        полученное сообщение
        """
        message_patch = Message("+79876543210", "Example text")
        dialogs_query = database.ScopedAppSession().query(
            database.Dialog
        )  # type: Query
        with mock.patch.object(
            self.gateway, 'parse_message', return_value=message_patch,
            new_callable=AsyncMock
        ):
            # Список имеющихся диалогов
            dialogs = list(dialogs_query)
            message = self.loop.run_until_complete(
                self.gateway.handle_message(self.request_mock)
            )  # type: database.Message
            self.assertNotIn(message.dialog, dialogs)

        self.assertIn(message.dialog, dialogs_query)

    def test_handle_message_with_dialog(self):
        """
        Когда сообщение уже привязано к диалогу, новый диалог не должен
        создаваться
        """
        phone_number = "+79876543210"
        customer = database.Customer(
            name="Example user", phone_number=phone_number
        )
        dialog = database.Dialog(
            customer=customer, channel=self.gateway.get_channel()
        )
        session = database.ScopedAppSession()  # type: Session
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
            )  # type: database.Message
            self.assertEqual(message.dialog, dialog)
            self.assertEqual(dialog.messages[0], message)
