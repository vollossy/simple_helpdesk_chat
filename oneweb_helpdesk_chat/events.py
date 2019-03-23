"""
Различные события, которые нужно пересылать клиентам. Доступные типы событий:

* Клиент открыл диалог(написал новое сообщение в тех. поддержку), это
    уведомление получат все пользователи.
* Клиент написал сообщение
* Новое сообщение от техподдержки
"""
from asyncio import Queue
from enum import Enum

events_queue = Queue()
subscribed_users = []


class EventType(Enum):
    """
    Тип события. Доступные значения:
      * NEW_UNASSIGNED_DIALOG_MESSAGE: новое сообщение в диалоге без
      назначенного пользователя
    """
    NEW_UNASSIGNED_DIALOG_MESSAGE = "NEW_UNASSIGNED_DIALOG_MESSAGE"


class Event:
    """
    Событие в системе
    """

    def __init__(self, event_type: EventType, payload: dict) -> None:
        super().__init__()
        self.event_type = event_type
        self.payload = payload

    def as_json(self):
        return {"event_type": self.event_type.value, "payload": self.payload}
