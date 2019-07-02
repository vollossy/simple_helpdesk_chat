"""
Конфигурация для проекта
"""
import os

# URL базы данных
DB_URL = os.environ.get(
    'DB_URL',
    'postgresql://postgres:simplepass@localhost/oneweb_helpdesk_chat'
)

TEST_DB_URL = os.environ.get(
    'TEST_DB_URL',
    'postgresql://postgres:simplepass@localhost/oneweb_helpdesk_chat_test'
)

# Алгоритм хеширования, используемый для всякого стаффа типа генерации паролей
HASHING_ALGORITHM = os.environ.get('HASHING_ALGORITHM', 'sha256')
# Секретный ключ для приложения, используемый для подсоления хешей
APP_SECRET = os.environ.get('APP_SECRET', 'example_secret_key')
