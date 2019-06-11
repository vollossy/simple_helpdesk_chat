"""
Тесты непосредственно для чата
"""
import asyncio
import json
from datetime import datetime
from unittest import TestCase, mock
from aiohttp import web, ClientWebSocketResponse
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp.web_app import Application

from oneweb_helpdesk_chat.chat import ChatHandler, DEFAULT_DT_FORMAT
from oneweb_helpdesk_chat.queues import DictRepository
from oneweb_helpdesk_chat.storage import Dialog, User, Customer, Message
from oneweb_helpdesk_chat.storage.database import MessagesRepository
from tests import utils
from oneweb_helpdesk_chat.gateways import Repository
from tests.utils import BaseTestCase
from oneweb_helpdesk_chat import app, storage


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


class ChatEndpointTestCase(AioHTTPTestCase, BaseTestCase):
    """
    Функциональные тесты для эндпоинта чата(`/chat/{dialog_id}/`)
    """

    def setUp(self) -> None:
        super().setUp()
        self.dialogs_repository_mock = mock.MagicMock(
            spec=storage.DialogRepository
        )
        default_dialogs_repository_patch = mock.patch(
            'oneweb_helpdesk_chat.app.storage.default_dialogs_repository',
            return_value=self.dialogs_repository_mock
        )
        default_dialogs_repository_patch.start()
        self.addCleanup(default_dialogs_repository_patch.stop)

        self.users_repository_mock = mock.MagicMock(
            spec=storage.UserRepository
        )
        default_user_repository_patch = mock.patch(
            'oneweb_helpdesk_chat.app.storage.default_user_repository',
            return_value=self.users_repository_mock
        )
        default_user_repository_patch.start()
        self.addCleanup(default_user_repository_patch.stop)

        get_session_patch = mock.patch(
            'oneweb_helpdesk_chat.app.get_session',
            new=utils.AsyncMock()
        )
        self.get_session = get_session_patch.start()
        self.addCleanup(get_session_patch.stop)

    async def get_application(self) -> Application:
        return await app.make_app()

    @unittest_run_loop
    async def test_customer_message_received(self):
        """
        Кейс для случая, когда пришло сообщение от клиента. Работает таким
        образом: в шлюз приходит сообщение от клиента(в данном случае это
        заглушка, в реальности сервис сообщений стучится к эндпоинту
        `/gateways/{gateway_alias}/`), данное сообщение ставится в очередь при
        помощи провайдера очередей, а уже из очереди это сообщение берется
        обработчиком чата и пишется в вебсокет клиента.
        """
        customer = Customer(
            id=2, name="Example customer", phone_number="+7987654321"
        )
        dialog = Dialog(
            id=1, customer_id=2, assigned_user_id=3, customer=customer
        )
        message = Message(
            id=4, dialog_id=dialog.id, text="Example message", dialog=dialog,
            created_at=datetime.today()
        )
        user = User(id=5)
        self.get_session.return_value = {"id": user.id}

        await app.dialogs_queues.put(str(dialog.id), message)

        self.dialogs_repository_mock.get_by_id = utils.AsyncMock(
            return_value=dialog
        )
        self.users_repository_mock.get_by_id = utils.AsyncMock(
            return_value=user
        )

        ws_conn = await self.client.ws_connect(
            '/chat/{}'.format(dialog.id)
        )  # type: ClientWebSocketResponse
        resp = await ws_conn.receive_json(timeout=3)
        await ws_conn.close(message=json.dumps({"closed": True}).encode())
        # ожидаем, пока слушатели на веб-сокете закроются
        await asyncio.sleep(0.1)
        self.assertEqual(message.text, resp['text'])
        self.assertEqual(customer.id, resp['customer']['id'])
        self.assertEqual(
            message.created_at.replace(microsecond=0),
            datetime.strptime(resp['datetime'], DEFAULT_DT_FORMAT)

        )
        self.users_repository_mock.get_by_id.assert_called_with(user.id)
        self.dialogs_repository_mock.get_by_id.assert_called_with(dialog.id)

