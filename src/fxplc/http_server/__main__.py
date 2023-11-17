import argparse
import logging

from fxplc.http_server.server import run_server

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


def main() -> None:
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--path", type=str, required=True)
    argparser.add_argument("--variables", type=str, required=False)
    argparser.add_argument('--debug', action='store_true')
    argparser.add_argument('--base-href', type=str, default="/")

    args = argparser.parse_args()

    logging.basicConfig()
    log = logging.getLogger()
    if args.debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    run_server(args)


if __name__ == "__main__":
    main()
