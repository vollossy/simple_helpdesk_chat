import logging
from unittest import TestCase
from unittest.mock import MagicMock

import sqlalchemy

from oneweb_helpdesk_chat import config


_engine = None


def test_engine():
    global _engine
    if _engine is None:
        # todo: сделать вариацию для получения именно тестовой бд
        _engine = sqlalchemy.create_engine(
            config.TEST_DB_URL, echo=False, pool_size=10, max_overflow=0
        )
    return _engine


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


class AsyncIterator:
    def __init__(self, seq):
        self.iter = iter(seq)

    async def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration
