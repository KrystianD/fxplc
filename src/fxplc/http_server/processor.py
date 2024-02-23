import asyncio
import logging
import traceback
from asyncio import QueueFull
from contextlib import closing
from typing import Any, Callable, Awaitable, TypeVar

from fastapi import HTTPException

from fxplc.client.FXPLCClient import FXPLCClient, RegisterDef, RegisterType
from fxplc.client.errors import ResponseMalformedError, NoResponseError
from fxplc.client.number_type import NumberType
from fxplc.http_server.exceptions import RequestException, RequestTimeoutException
from fxplc.http_server.transport import connect_to_transport, TransportConfig


class FXRequest:
    future: asyncio.Future[Any]
    callback: Callable[[FXPLCClient], Awaitable[Any]]
    timeout_handle: asyncio.TimerHandle


T = TypeVar("T")

RequestTimeout = 10

transport_config: TransportConfig | None = None
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


async def perform_register_read(register: str, number_type: NumberType) -> int | float | bool:
    register_def = RegisterDef.parse(register)

    async def cb(fx: FXPLCClient) -> int | float | bool:
        if register_def.type in (RegisterType.Input, RegisterType.Output, RegisterType.Memory,
                                 RegisterType.State, RegisterType.Timer):
            return await fx.read_bit(register_def)
        elif register_def.type in (RegisterType.Data, RegisterType.Counter):
            return await fx.read_number(register_def, number_type)
        else:
            raise Exception("unsupported")

    return await do_request(cb)


async def perform_register_write(register: str, value: int | bool, number_type: NumberType) -> int | bool:
    register_def = RegisterDef.parse(register)

    async def cb(fx: FXPLCClient) -> int | bool:
        if register_def.type in (RegisterType.Input, RegisterType.Output, RegisterType.Memory,
                                 RegisterType.State, RegisterType.Timer):
            await fx.write_bit(register_def, bool(value))
            return bool(value)
        elif register_def.type in (RegisterType.Data, RegisterType.Counter):
            await fx.write_number(register_def, int(value), number_type)
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
        except (ConnectionRefusedError, ConnectionError, TimeoutError) as e:
            logging.warning(f"connection error ({type(e).__name__}): {e}")
            await asyncio.sleep(1)
        except:
            traceback.print_exc()
            await asyncio.sleep(1)


async def serial_task_loop() -> None:
    if transport_config is None:
        raise Exception("transport_config is not configured")

    logging.info("connecting to FX...")
    transport = await connect_to_transport(transport_config)
    with closing(FXPLCClient(transport)) as fx:
        logging.info("connection opened")
        while True:
            req = await queue.get()
            if not await perform_single_request(fx, req):
                logging.info("request processing error")
                return


async def perform_single_request(fx: FXPLCClient, req: FXRequest) -> bool:
    for i in range(5):
        try:
            if req.future.done():
                return True
            res = await req.callback(fx)
            req.timeout_handle.cancel()
            if not req.future.done():
                req.future.set_result(res)
            return True
        except (ResponseMalformedError, NoResponseError) as e:
            logging.error(f"retryable request error ({type(e).__name__}) {e}")
            await asyncio.sleep(0.5)
        except Exception as e:
            logging.error(f"general request error ({type(e).__name__}) {e}")
            req.timeout_handle.cancel()
            req.future.set_exception(RequestException())
            return False

    req.timeout_handle.cancel()
    if not req.future.done():
        req.future.set_exception(RequestException())
    return False


def run_serial_task(transport_config_: TransportConfig) -> None:
    global transport_config
    transport_config = transport_config_

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
