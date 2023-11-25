import asyncio
import logging
import traceback
from asyncio import QueueFull
from contextlib import closing
from typing import Any, Callable, Awaitable, TypeVar

from fastapi import HTTPException

from fxplc.client.FXPLCClient import FXPLCClient, RegisterDef, RegisterType
from fxplc.client.errors import ResponseMalformedError, NoResponseError
from fxplc.http_server.exceptions import RequestException, RequestTimeoutException
from fxplc.transports.ITransport import ITransport
from fxplc.transports.TransportSerial import TransportSerial
from fxplc.transports.TransportTCP import TransportTCP


class FXRequest:
    future: asyncio.Future[Any]
    callback: Callable[[FXPLCClient], Awaitable[Any]]
    timeout_handle: asyncio.TimerHandle


T = TypeVar("T")

RequestTimeout = 10

app_args: Any = None
serial_task_handle: asyncio.Task[None] | None = None
queue = asyncio.Queue[FXRequest](maxsize=10)


async def do_request(callback: Callable[[FXPLCClient], Awaitable[T]]) -> T:
    if not is_running():
        raise HTTPException(status_code=503, detail="server is paused")

    loop = asyncio.get_event_loop()

    fxr = FXRequest()
    fxr.future = asyncio.Future[T]()
    fxr.callback = callback
    fxr.timeout_handle = loop.call_later(RequestTimeout, fxr.future.set_exception, RequestTimeoutException())

    try:
        queue.put_nowait(fxr)
        return await fxr.future
    except QueueFull:
        raise HTTPException(status_code=429, detail="requests queue full")
    except RequestTimeoutException:
        raise HTTPException(status_code=400, detail="request timeout")
    except RequestException:
        raise HTTPException(status_code=400, detail="request error")


async def perform_register_read(register: str) -> int | bool:
    register_def = RegisterDef.parse(register)

    async def cb(fx: FXPLCClient) -> int | bool:
        if register_def.type in (RegisterType.Input, RegisterType.Output, RegisterType.Memory,
                                 RegisterType.State, RegisterType.Timer):
            return await fx.read_bit(register_def)
        elif register_def.type in (RegisterType.Data, RegisterType.Counter):
            return await fx.read_int(register_def)
        else:
            raise Exception("unsupported")

    return await do_request(cb)


async def perform_register_write(register: str, value: int | bool) -> int | bool:
    register_def = RegisterDef.parse(register)

    async def cb(fx: FXPLCClient) -> int | bool:
        if register_def.type in (RegisterType.Input, RegisterType.Output, RegisterType.Memory,
                                 RegisterType.State, RegisterType.Timer):
            await fx.write_bit(register_def, bool(value))
            return bool(value)
        elif register_def.type in (RegisterType.Data, RegisterType.Counter):
            await fx.write_int(register_def, int(value))
            return int(value)
        else:
            raise Exception("unsupported")

    return await do_request(cb)


async def perform_register_read_bit(register: str) -> bool:
    register_def = RegisterDef.parse(register)

    async def cb(fx: FXPLCClient) -> bool:
        return await fx.read_bit(register_def)

    return await do_request(cb)


async def perform_register_write_bit(register: str, value: bool) -> int:
    register_def = RegisterDef.parse(register)

    async def cb(fx: FXPLCClient) -> bool:
        await fx.write_bit(register_def, value)
        return bool(value)

    return await do_request(cb)


async def serial_task() -> None:
    logging.info("serial task started")
    while True:
        try:
            await serial_task_loop()
        except asyncio.exceptions.CancelledError:
            logging.info("serial task stopped")
            return
        except:
            traceback.print_exc()
            await asyncio.sleep(1)


async def serial_task_loop() -> None:
    global app_args

    logging.info("connecting to FX...")
    transport: ITransport
    if app_args.path.startswith("tcp:"):
        _, host, port = app_args.path.split(":")
        tcp_transport = TransportTCP(host, int(port))
        await tcp_transport.connect()
        transport = tcp_transport
    else:
        transport = TransportSerial(app_args.path)
    fx = FXPLCClient(transport)
    logging.info("connection opened")

    async def perform_single_request(req_: FXRequest) -> None:
        for i in range(5):
            try:
                if req_.future.done():
                    return
                res = await req_.callback(fx)
                req_.timeout_handle.cancel()
                req_.future.set_result(res)
                return
            except (ResponseMalformedError, NoResponseError):
                print('error, retry')

        req_.timeout_handle.cancel()
        req_.future.set_exception(RequestException())

    with closing(FXPLCClient(transport)) as fx:
        while True:
            req = await queue.get()
            await perform_single_request(req)


def run_serial_task(args: Any) -> None:
    global app_args
    app_args = args

    resume_serial()


def is_running() -> bool:
    return serial_task_handle is not None


def pause_serial() -> None:
    global serial_task_handle

    if serial_task_handle is None:
        return
    logging.info("pausing connection...")
    serial_task_handle.cancel()
    serial_task_handle = None
    logging.info("task stopped")


def resume_serial() -> None:
    global serial_task_handle

    if serial_task_handle is None:
        serial_task_handle = asyncio.create_task(serial_task())