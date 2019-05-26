"""
Этот пакет представляет уровень доступа к данным
"""
from .database import DialogRepository, CustomerRepository, UserRepository
from .database import Customer, Dialog, Message, User


_ur_instance = None
_dr_instance = None


def default_user_repository() -> UserRepository:
    """
    Возвращает репозиторий по умолчанию, который будет использован для работы
    с пользователями
    :return:
    """
    global _ur_instance
    if not _ur_instance:
        _ur_instance = UserRepository()
    return _ur_instance


def default_dialogs_repository() -> DialogRepository:
    global _dr_instance
    if not _dr_instance:
        _dr_instance = DialogRepository()
    return _dr_instance
