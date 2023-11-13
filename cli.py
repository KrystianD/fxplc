import logging
import argparse

from fxplc import FXPLC, RegisterDef, RegisterType, NoResponseError, ResponseMalformedError, NotSupportedCommandError


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-d', '--debug', action='store_true')
    argparser.add_argument('-p', '--path', type=str, metavar="PATH", required=True)

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

    sp = op_sp.add_parser('read_counter')
    sp.set_defaults(cmd="read_counter")
    sp.add_argument("register")

    sp = op_sp.add_parser('write_bit')
    sp.set_defaults(cmd="write_bit")
    sp.add_argument("register")
    sp.add_argument("value", type=str, choices=["1", "0", "on", "off", "yes", "no", "true", "false"])

    sp = op_sp.add_parser('write')
    sp.set_defaults(cmd="write")
    sp.add_argument("register")
    sp.add_argument("value", type=int)

    args = argparser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="[%(asctime)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    fx = FXPLC(args.path)

    try:
        if args.cmd == "read":
            for r in args.register:
                reg = RegisterDef.parse(r)
                bit = fx.read_bit(r)
                bit_str = "on" if bit else "off"
                if reg.type == RegisterType.Timer:
                    cnt = fx.read_counter(r)
                    print(f"{reg} = {bit_str}, counter: {cnt}")
                else:
                    print(f"{reg} = {bit_str}")

        if args.cmd == "read_bit":
            d = fx.read_bit(args.register)
            print(d)

        if args.cmd == "write_bit":
            on = args.value in ("1", "on", "yes", "true")
            fx.write_bit(args.register, on)

        if args.cmd == "read_bytes":
            d = fx.read_bytes(args.register, args.count)
            print(d)

        if args.cmd == "read_counter":
            d = fx.read_counter(args.register)
            print(d)

        if args.cmd == "write":
            fx.write_data(args.register, args.value)
    except NotSupportedCommandError:
        print("[ERROR] Command not supported")
        exit(1)
    except NoResponseError:
        print("[ERROR] No response")
        exit(1)
    except ResponseMalformedError:
        print("[ERROR] Response malformed")
        exit(1)


main()
