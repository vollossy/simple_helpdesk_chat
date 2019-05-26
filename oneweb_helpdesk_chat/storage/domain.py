"""
Здесь у нас хранятся интерфейсы моделей предметной области(чтобы можно было
абстрагироваться от них и реализовывать хранение в бд, например).

По дефолту они наледуются в модуле :module:`~.database` в моделях sqlalchemy и
уже эти модели используются в реальном приложении через импорт в корне текущего
модуля. Такой подход позволяет избжать совокупления с sqlalchemy(он не очень
хорошо работает с "голыми" классами), а также в  случае возникновения подобных
ситуаций в будущем с другими хранилищами заменять используемые классы
относительно малой кровью.
"""
from enum import Enum

import typing
from datetime import datetime


class Channel(Enum):
    """
    Доступные каналы для связи с клиентами
    """
    WHATSAPP = "whatsapp"
    VIBER = "VIBER"


class Customer:
    """
    Клиент. Тот, кто обращается к нам
    :type dialogs: list(Dialog)
    :ivar str phone_number: Номер телефона клиента, по нему мы связываем
      нескольких клиентов, пришедших из разных каналов.
      todo: некоторые каналы могут не иметь номер телефона, тогда нам нужно еще добавить какие-то другие
        алиасы, причем по нескольку, но это довольно сложная задача
    """

    def __init__(self, ident: int = None, name: str = None,
                 phone_number: str = None, dialogs: typing.List['Dialog'] = None
                 ) -> None:
        if dialogs is None:
            dialogs = []

        super().__init__()
        self.id = ident
        self.name = name
        self.phone_number = phone_number
        self.dialogs = dialogs


class User:
    """
    Пользователь, сотрудник техподдержки
    """

    def __init__(self, ident: int = None, name: str = None, login: str = None,
                 password: str = None, dialogs: typing.List['Dialog'] = None
                 ) -> None:
        super().__init__()
        self.id = ident
        self.name = name
        self.login = login
        self.password = password
        self.dialogs = dialogs


class Dialog:
    """
    Диалог хранит ссылки на сообщения, отправленные каждой из сторон. Диалог
    всегда привязан к одному клиенту. Также может быть привязан или не привязан
    к отдельному сотрутнику тех. поддержки.
    todo: Описать, когда привязка к сотруднику т.п. появляется, а когда исчезает
    todo: В будущем, каждый диалог будет отображать отдельное обращение клиента
      в тех. поддержку: у диалога будет несколько доступных состояний и когда
      проблема клиента решена, диалог будет помечаться как "закрытый", при
      последующем обращении будет создан новый диалог.
    """

    def __init__(self, ident: int = None, customer: Customer = None,
                 assigned_user: User = None,
                 messages: typing.List['Message'] = None) -> None:
        if messages is None:
            messages = []

        super().__init__()
        self.id = ident
        self.customer = customer
        self.assigned_user = assigned_user
        self.messages = messages


class Message:
    """
    Отдельное сообщение от клиента пользователю и обратно.

    :ivar int user_id: Идентификатор работника тп-отправителя сообщения, если null, значит сообщение было отправлено
      клиентом из указанного диалога
    """
    def __init__(self, ident:int = None, channel: Channel = None,
                 text: str = None, created_at: datetime = None,
                 dialog: Dialog = None) -> None:
        super().__init__()
        self.id = ident
        self.channel = channel
        self.text = text
        self.created_at = created_at
        self.dialog = dialog

