"""
Различный стафф для безопаснсти
"""
import asyncio
import binascii
import hashlib
import secrets

from oneweb_helpdesk_chat import config, storage


def _generate_password_hash_internal(password, algorithm, salt) -> str:
    """
    Приватная функция, которая выполняет генерацию хеша для пароля. В отличие от
    метода :meth:`~.create_password_hash`, данный метод не генерирует соль
    автоматически, а также возвращает **только** пароль без дополнительной
    мета-информации
    :param password: пароль для генерации хеша
    :param algorithm: алгортим хеширования
    :param salt: соль для хеша
    :return: str
    """
    return binascii.hexlify(hashlib.pbkdf2_hmac(
        algorithm, password.encode('utf8'), salt.encode(), 10000
    )).decode()


def create_password_hash(
        password: str,
        algorithm: str = config.HASHING_ALGORITHM
) -> str:
    """
    Генерирует хеш пароля используя предоставленный алгоритм а также соль.
    Для генерации пароля используется метод :meth:`hashlib.pbkdf2_hmac`.
    :param password: Пароль, хеш которого нужно сгененрировать
    :param algorithm: Алгоритм хеширования
    :return:
    """
    salt = binascii.hexlify(secrets.token_bytes(32)).decode()

    return '$'.join([
        algorithm,
        salt,
        _generate_password_hash_internal(password, algorithm, salt)
    ])


def validate_password(pw_hash: str, password: str) -> bool:
    """
    Проверяет пароль на соответствие хешу. Хеш должен содержать также информацию
    об алгоритме и соли, использованной для при генерации хеша. Изначально эта
    функция подразумевает проверку паролей, сформированных функцией
    :meth:`~.create_password_hash`
    :param pw_hash: Хеш для проверки
    :param password: Пароль, который нужно проверить
    :return: bool Соответствует ли предоставленный пароль указанному хешу
    """
    splitted_hash = pw_hash.split('$')
    if len(splitted_hash) != 3:
        return False
    algorithm, salt, hashed_password = splitted_hash
    return secrets.compare_digest(
        hashed_password,
        _generate_password_hash_internal(password, algorithm, salt)
    )


async def create_user(
        name: str, login: str, password: str,
        repository: storage.UserRepository = None
) -> storage.User:
    """
    Создает нового пользователя в бд и автоматически хеширует его пароль.
    Внимание, данная функцися выполняется синхронно. Для работы в асинхронном
    контексте используй функцию :meth:`~.create_user_async`.
    Это асинхронная функция
    :param repository: Репозиторий, используемый для сохранения пользователя в
      хранилище. Если репозиторийне указан, то будет взять дефолтный, возвраемый
      методом :meth:`~.storage.default_user_repository`
    :param name: Полное имя пользователя
    :param login: Логин пользователя
    :param password: **Чистый** пароль(т.е. не хешированный)
    :return: созданный пользователь
    """
    if repository is None:
        repository = storage.default_user_repository()

    user = storage.User(
        name=name, login=login, password=create_password_hash(password)
    )
    await repository.save(user)
    return user
