import asyncio
import logging
from typing import Optional, Sequence, Mapping, Any

from aiohttp import web
from aiohttp.log import web_logger
from aiohttp.web_app import _Middleware
from aiohttp.web_urldispatcher import UrlDispatcher
from aiohttp_session import get_session, setup, SimpleCookieStorage
from oneweb_helpdesk_chat import events, gateways, storage, security
from oneweb_helpdesk_chat.chat import ChatHandler
from . import events as app_events
from . import queues


routes = web.RouteTableDef()


class Application(web.Application):
    """
    Кастомный класс приложения.
    """

    def __init__(
            self, *, logger: logging.Logger = web_logger,
            router: Optional[UrlDispatcher] = None,
            middlewares: Sequence[_Middleware] = (),
            handler_args: Mapping[str, Any] = None,
            client_max_size: int = 1024 ** 2,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            debug: Any = ...,
            dialogs_queues: queues.DictRepository = queues.DictRepository()
    ) -> None:
        super().__init__(logger=logger, router=router, middlewares=middlewares,
                         handler_args=handler_args,
                         client_max_size=client_max_size, loop=loop,
                         debug=debug)
        # маппинг очередей сообщений для отдельных диалогов. В качестве ключей
        # используется идентификатор диалога в нашей бд, в качестве значений -
        # очередь сообщений. Каждый раз, когда приходит новое сообщение в
        # диалог, оно будет добавлено в очередь для этого диалога. Этот объект
        # должен реализовывать интерфейс словаря(методы __set__, __get__ и
        # get()).
        self.dialogs_queues = dialogs_queues


@routes.route("*", "/gateways/{gateway_alias}", name="gateway-hook")
async def gateway_hook(request: web.Request):
    """
    Хук для сообщения от im-сервиса. Сообщение преобразуется в наш внутренний
    формат и привязывается к имеющемуся диалогу, если диалога нет, то он будет
    создан. Если в диалоге не указан ответственный, то при каждом новом
    сообщении будет отправлено уведомление о событии в шину событий
    :param request: Запрос
    :return:
    """
    gateway = gateways.repository.get_gateway(
        request.match_info["gateway_alias"]
    )
    # асинхронный вызов, т.к. обработка может быть довольно длительной
    message = await gateway.handle_message(request)

    await request.app.dialogs_queues.put(str(message.dialog_id), message)

    if not message.dialog.assigned_user:
        await app_events.events_queue.put(app_events.Event(
            app_events.EventType.NEW_UNASSIGNED_DIALOG_MESSAGE,
            message.dialog.id
        ))

    return web.Response()


@routes.route("POST", "/login/", name="login")
async def login(request: web.Request):
    """
    Производит логин пользователя и сохраняет его идентификатор в сессии, если
    успешно
    :param request:
    :return:
    """
    post_data = await request.post()
    user = await storage.default_user_repository().get_by_login(
        post_data['login']
    )
    password_valid = security.validate_password(
        getattr(user, 'password', ''), post_data['password']
    )
    if not user or not password_valid:
        raise web.HTTPUnauthorized()
    sess = await get_session(request)
    sess["user_id"] = user.id
    return web.Response()


@routes.route("GET", "/events/")
async def events(request: web.Request):
    """
    Различные события, не связанные с чатом. Клиент подписывается на этот канал
    для получения уведомлений о новых диалогах и прочем
    :param request:
    :return:
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    while True:
        event = await events.events_queue.get()  # type: events.Event
        try:
            await ws.send_json(event.as_json())
        except:
            # todo: log error here
            break

    return ws


@routes.route("GET", "/chat/{dialog_id}")
async def chat(request: web.Request):
    """
    Непосредственно чат между кастомером и работником тп. В данном случае
    клиентом будет всегда клиентское устройство работника т.п.
    :param request:
    :return:
    """
    # todo: здесь нужна проверка на то, саассайнен ли пользователь на диалог
    ws = web.WebSocketResponse()
    await  ws.prepare(request)
    dialog = await storage.default_dialogs_repository().get_by_id(
        int(request.match_info["dialog_id"])
    )
    if not dialog:
        raise web.HTTPNotFound

    sess = await get_session(request)
    user = await storage.default_user_repository().get_by_id(int(sess['id']))
    handler = ChatHandler(
        ws=ws, dialog=dialog, user=user,
        queues_repository=request.app.dialogs_queues
    )
    await asyncio.gather(
        handler.read_from_customer(), handler.write_to_customer()
    )

    return ws


async def make_app():
    """
    Фабрика для создания приложения
    """
    app = Application(dialogs_queues=queues.DictRepository())
    setup(app, SimpleCookieStorage())
    app.add_routes(routes)
    return app
