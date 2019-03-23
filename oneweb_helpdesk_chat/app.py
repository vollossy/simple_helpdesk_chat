from aiohttp import web
from aiohttp_session import get_session, setup, SimpleCookieStorage
import asyncio
import storage
from oneweb_helpdesk_chat import events, gateways
from oneweb_helpdesk_chat.chat import ChatHandler

app = web.Application()
routes = web.RouteTableDef()
setup(app, SimpleCookieStorage())

# маппинг очередей сообщений для отдельных диалогов. В качестве ключей исполь
# зуется идентификатор диалога в нашей бд, в качестве значений - очередь
# сообщений. Каждый раз, когда приходит новое сообщение в диалог, оно будет
# добавлено в очередь для этого диалога
# todo: это нужно будет перепилить для меньшего потребления памяти
dialogs_queues = {}


@routes.route("*", "/gateways/{gateway_alias}", name="gateway-hook")
async def gateway_hook(request: web.Request):
    """
    Хук для сообщения от im-сервиса. Сообщение преобразуется в наш внутренний
    формат и привязывается к имеющемуся диалогу, если диалога нет, то он будет
    создан. Если в диалоге не указан ответственный, то при каждом новом
    сообщении будет отправлено уведомление о событии в
    :param request: Запрос
    :return:
    """
    gateway = gateways.repository.get_gateway(
        request.match_info["gateway_alias"]
    )
    # асинхронный вызов, т.к. обработка может быть довольно длительной
    message = await gateway.handle_message(request)
    if not message.dialog_id:
        new_dialog = storage.Dialog(
            customer_id=message.sender
        )
        await asyncio.get_event_loop().run_in_executor(
            None, storage.session().add(new_dialog)
        )
        message.dialog_id = new_dialog.id
        await asyncio.get_event_loop().run_in_executor(
            None, storage.session().commit()
        )

    if message.dialog_id not in dialogs_queues:
        dialogs_queues[message.dialog_id] = asyncio.Queue()

    await dialogs_queues[message.dialog_id].put(message)

    if not message.dialog.assigned_user:
        await events.events_queue.put(events.Event(
            events.EventType.NEW_UNASSIGNED_DIALOG_MESSAGE,
            message.dialog.id
        ))

    return web.Response()


@routes.route("POST", "/login/")
async def login(request: web.Request):
    """
    Производит логин пользователя и сохраняет его идентификатор в сессии, если
    успешно
    :param request:
    :return:
    """
    post_data = await request.post()
    user = await asyncio.get_event_loop().run_in_executor(
        None,
        storage.session().query(storage.User).filter,
        storage.User.name == post_data["login"],
        storage.User.password == post_data["password"]
    )
    if not user:
        return web.Response(status=400)
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
    Непосредственно чат между кастомером и работником тп. В данном случае клиентом будет всегда клиентское устройство
    работника т.п.
    :param request:
    :return:
    """
    # todo: здесь нужна проверка на то, саассайнен ли пользователь на диалог
    ws = web.WebSocketResponse()
    await  ws.prepare(request)
    dialog = await storage.fetch_results(
        storage.session().query(storage.Dialog).filter(storage.Dialog.id == request.match_info["dialog_id"]),
        "one"
    ) # type: storage.Dialog
    if not dialog:
        raise web.HTTPNotFound()

    messages = dialogs_queues[dialog.id]
    user_id = get_session(request)["id"]
    user = await storage.fetch_results(
        storage.session().query(storage.User).filter(storage.User.id == user_id)
    )

    handler = ChatHandler(ws=ws, dialog=dialog, user=user)

    await asyncio.gather(handler.read_from_customer(messages), handler.write_to_customer())

    return ws

app.add_routes(routes)