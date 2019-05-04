import logging
from unittest import TestCase
from unittest.mock import MagicMock


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class BaseTestCase(TestCase):
    """
    Базовый кейс, используемый в наших тестах. Он убирает лишнее логгирование
    из дополнительных библиотек(таких как sqlalchemy)
    """

    def setUp(self) -> None:
        super().setUp()
        logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

    def tearDown(self) -> None:
        super().tearDown()
        logging.getLogger('sqlalchemy').setLevel(logging.INFO)