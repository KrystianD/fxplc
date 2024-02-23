import asyncio
import functools
import traceback
from asyncio import CancelledError
from contextlib import closing
from typing import Any

from fxplc.http_server import processor
from fxplc.http_server.transport import TransportConfig, connect_to_transport
from fxplc.transports.TransportTCP import NotConnectedError


async def handle_aux_client(transport_config: TransportConfig, reader: Any, writer: Any) -> None:
    print("pause_serial")
    processor.pause_serial()

    try:
        transport = await connect_to_transport(transport_config)

        with closing(transport):
            async def tcp_to_transport() -> None:
                while True:
                    try:
                        data = await reader.read(100)
                        if len(data) == 0:
                            transport.close()
                            writer.close()
                            return
                        print(f"< {data!r}")
                        await transport.write(data)
                    except:
                        traceback.print_exc()

            async def transport_to_tcp() -> None:
                while True:
                    try:
                        data = await transport.read(100)
                        if len(data) == 0:
                            transport.close()
                            writer.close()
                            return
                        print(f"> {data!r}")
                        writer.write(data)
                        await writer.drain()
                    except NotConnectedError:
                        return
                    except TimeoutError:
                        pass

            await asyncio.gather(tcp_to_transport(), transport_to_tcp())
            print("Close the AUX connection")
            writer.close()
            await writer.wait_closed()
    except:
        traceback.print_exc()
    finally:
        print("resume_serial")
        processor.resume_serial()


async def run_aux_server(transport_config: TransportConfig) -> None:
    try:
        server = await asyncio.start_server(functools.partial(handle_aux_client, transport_config), '0.0.0.0', 8889)
        addresses = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        print(f"Serving on {addresses}")
        async with server:
            await server.serve_forever()
    except CancelledError:
        return
