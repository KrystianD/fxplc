import argparse
import asyncio
import logging

from fxplc.client.FXPLCClient import FXPLCClient, RegisterDef, RegisterType
from fxplc.client.errors import NoResponseError, NotSupportedCommandError, ResponseMalformedError
from fxplc.transports.ITransport import ITransport
from fxplc.transports.TransportSerial import TransportSerial
from fxplc.transports.TransportTCP import TransportTCP


async def main() -> None:
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-d', '--debug', action='store_true')
    argparser.add_argument('-p', '--path', type=str, metavar="PATH", required=True)
    argparser.add_argument('--timeout', type=int, default=1)

    op_sp = argparser.add_subparsers(title="operation")

    sp = op_sp.add_parser('read')
    sp.set_defaults(cmd="read")
    sp.add_argument("register", type=str, nargs='*')

    sp = op_sp.add_parser('read_bit')
    sp.set_defaults(cmd="read_bit")
    sp.add_argument("register")

    sp = op_sp.add_parser('read_bytes')
    sp.set_defaults(cmd="read_bytes")
    sp.add_argument("register")
    sp.add_argument("count", type=int, default=1, nargs='?')

    sp = op_sp.add_parser('read_int')
    sp.set_defaults(cmd="read_int")
    sp.add_argument("register")

    sp = op_sp.add_parser('write_bit')
    sp.set_defaults(cmd="write_bit")
    sp.add_argument("register")
    sp.add_argument("value", type=str, choices=["1", "0", "on", "off", "yes", "no", "true", "false"])

    sp = op_sp.add_parser('write_int')
    sp.set_defaults(cmd="write_int")
    sp.add_argument("register")
    sp.add_argument("value", type=int)

    args = argparser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="[%(asctime)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    transport: ITransport
    if args.path.startswith("tcp:"):
        _, host, port = args.path.split(":")
        tcp_transport = TransportTCP(host, int(port), timeout=args.timeout)
        await tcp_transport.connect()
        transport = tcp_transport
    else:
        transport = TransportSerial(args.path, timeout=args.timeout)
    fx = FXPLCClient(transport)

    try:
        if args.cmd == "read":
            for r in args.register:
                reg = RegisterDef.parse(r)
                bit = await fx.read_bit(r)
                bit_str = "on" if bit else "off"
                if reg.type == RegisterType.Timer:
                    cnt = fx.read_int(r)
                    print(f"{reg} = {bit_str}, counter: {cnt}")
                else:
                    print(f"{reg} = {bit_str}")

        if args.cmd == "read_bit":
            resp_bit = await fx.read_bit(args.register)
            print(resp_bit)

        if args.cmd == "write_bit":
            on = args.value in ("1", "on", "yes", "true")
            await fx.write_bit(args.register, on)

        if args.cmd == "read_bytes":
            resp_data = await fx.read_bytes(args.register, args.count)
            print(resp_data)

        if args.cmd == "read_int":
            resp_value = await fx.read_int(args.register)
            print(resp_value)

        if args.cmd == "write_int":
            await fx.write_int(args.register, args.value)
    except NotSupportedCommandError:
        print("[ERROR] Command not supported")
        exit(1)
    except NoResponseError:
        print("[ERROR] No response")
        exit(1)
    except ResponseMalformedError:
        print("[ERROR] Response malformed")
        exit(1)
    finally:
        fx.close()


def main_cli() -> None:
    asyncio.run(main())
