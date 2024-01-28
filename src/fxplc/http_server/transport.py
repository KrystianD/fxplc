import logging
from dataclasses import dataclass

from fxplc.transports.ITransport import ITransport
from fxplc.transports.TransportSerial import TransportSerial
from fxplc.transports.TransportTCP import TransportTCP


@dataclass
class TransportConfig:
    path: str


async def connect_to_transport(config: TransportConfig) -> ITransport:
    logging.info("connecting to FX...")
    transport: ITransport
    if config.path.startswith("tcp:"):
        _, host, port = config.path.split(":")
        tcp_transport = TransportTCP(host, int(port))
        logging.info("connecting TCP transport...")
        await tcp_transport.connect()
        logging.info("connection done")
        transport = tcp_transport
    else:
        transport = TransportSerial(config.path)

    return transport
