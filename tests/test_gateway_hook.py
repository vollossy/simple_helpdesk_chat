"""
Тестовые кейсы для хука, взаимодействующего с провайдером. Здесь не тестируется конкретная реализация, только общий
интерфейс
"""
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp.web_app import Application
from unittest.mock import patch, MagicMock

import storage
from oneweb_helpdesk_chat.gateways import Repository, Gateway, repository
from tests.utils import AsyncMock


class GatewayHookTestCase(AioHTTPTestCase):
    """
    Функциональный тест эндпоинта для хука клиентского приложения
    """

    async def get_application(self) -> Application:
        from oneweb_helpdesk_chat import app
        return app.app

    def setUp(self) -> None:
        super().setUp()

        self.gateway_stub = MagicMock()
        self.gateway_stub.handle_message = AsyncMock(return_value=storage.Message())

        repository.register_gateway("example", self.gateway_stub)

    def tearDown(self):
        super().tearDown()
        repository.unregister_gateway("example")

    @unittest_run_loop
    async def test_simple(self):
        """
        Простейший тестовый кейс. Хук должен вызывать требуемый gateway из репозитория
        """
        # асинхронная заглушка для обработки сообщений(нужна для взаимодействия с asyncio)

        await self.client.request("GET", self.app.router["gateway-hook"].url_for(gateway_alias="example"))
        self.gateway_stub.handle_message.assert_called()
