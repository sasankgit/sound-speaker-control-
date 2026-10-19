"""Command-line interface for Windows system audio routing."""

import argparse

from audio_control.devices import list_devices
from audio_control.mirroring import mirror


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    subparsers.add_parser("list", help="list available Windows WASAPI outputs")
    route_parser = subparsers.add_parser(
        "route",
        help="route system audio from a playback device to additional outputs",
    )
    route_parser.add_argument(
        "--source",
        required=True,
        help="loopback source ID shown by 'list'",
    )
    route_parser.add_argument(
        "--out",
        nargs="+",
        required=True,
        help="destination output indices shown by 'list'",
    )

    args = parser.parse_args()
    if args.cmd == "list":
        list_devices()
    elif args.cmd == "route":
        mirror(args.source, args.out)
