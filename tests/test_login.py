"""
Тесты для логина пользователя
"""
from aiohttp import ClientResponse
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop, TestClient
from aiohttp.web_app import Application
from sqlalchemy.orm import Session

from oneweb_helpdesk_chat import storage
import faker

from tests.utils import BaseTestCase


class LoginTestCase(AioHTTPTestCase, BaseTestCase):
    """
    Функциональные тесты для логина пользователя

    :ivar TestClient client:
    """
    def setUp(self) -> None:
        super().setUp()
        storage.Base.metadata.create_all(storage.engine())
        fake = faker.Faker()

        storage.ScopedAppSession.configure(bind=storage.engine())

        self.session = storage.ScopedAppSession()  # type: Session

        self.user_password = fake.password()
        self.user = storage.create_user(
            fake.name(), fake.email(), self.user_password
        )

    def tearDown(self) -> None:
        super().tearDown()
        self.session.commit()

        storage.ScopedAppSession.remove()
        storage.Base.metadata.drop_all(storage.engine())

    async def get_application(self) -> Application:
        from oneweb_helpdesk_chat import app
        return await app.make_app()

    @unittest_run_loop
    async def test_login_success(self):
        """
        Простейший тест -- успешный логин. Сессия должна быть установлена
        """
        response = await self.client.request(
            "POST",
            self.app.router["login"].url_for(),
            data={"login": self.user.login, "password": self.user_password}
        )  # type: ClientResponse
        self.assertEqual(
            response.status,
            200,
            response.content.read_nowait().decode('utf8')
        )

    @unittest_run_loop
    async def test_login_not_success(self):
        """
        Кейс для случая, когда пользователь ввел неверный логин или пароль
        """
        response = await self.client.request(
            "POST",
            self.app.router["login"].url_for(),
            data={"login": self.user.login, "password": 'balh-blah-blah'}
        )  # type: ClientResponse
        self.assertEqual(
            response.status,
            401,
            response.content.read_nowait().decode('utf8')
        )
