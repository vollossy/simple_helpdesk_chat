"""
Тестовые кейсы для хука, взаимодействующего с провайдером. Здесь не тестируется конкретная реализация, только общий
интерфейс
"""
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp.web_app import Application
from unittest.mock import MagicMock

from oneweb_helpdesk_chat import storage
from oneweb_helpdesk_chat.gateways import repository
from tests.utils import AsyncMock


class GatewayHookTestCase(AioHTTPTestCase):
    """
    Функциональный тест эндпоинта для хука клиентского приложения
    """

    async def get_application(self) -> Application:
        from oneweb_helpdesk_chat import app
        return await app.make_app()

    def setUp(self) -> None:
        super().setUp()
        self.dialog = storage.Dialog(id=1)

        self.gateway_stub = MagicMock()
        self.gateway_stub.handle_message = AsyncMock(
            return_value=storage.Message(dialog=self.dialog)
        )

        repository.register_gateway("example", self.gateway_stub)

    def tearDown(self):
        super().tearDown()
        repository.unregister_gateway("example")

    @unittest_run_loop
    async def test_simple(self):
        """
        Простейший тестовый кейс. Хук должен вызывать требуемый gateway из
        репозитория с необходимыми параметрами
        """
        await self.client.request(
            "GET",
            self.app.router["gateway-hook"].url_for(gateway_alias="example")
        )
        self.gateway_stub.handle_message.assert_called()
