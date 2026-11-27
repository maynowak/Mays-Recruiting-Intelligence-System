"""Run one local test command with external network access blocked."""

from __future__ import annotations

import argparse
import ipaddress
import socket
import sys
import unittest


def install_network_guard() -> None:
    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def loopback(host: object) -> bool:
        value = host.decode("ascii", "ignore") if isinstance(host, bytes) else str(host)
        if value.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(value.split("%", 1)[0]).is_loopback
        except ValueError:
            return False

    def guarded_getaddrinfo(host: object, *args: object, **kwargs: object):
        if not loopback(host):
            raise OSError("Unified QA guard blocked non-loopback DNS access")
        return original_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(sock: socket.socket, address: object):
        if isinstance(address, tuple) and address and not loopback(address[0]):
            raise OSError("Unified QA guard blocked non-loopback socket access")
        return original_connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: object):
        if isinstance(address, tuple) and address and not loopback(address[0]):
            raise OSError("Unified QA guard blocked non-loopback socket access")
        return original_connect_ex(sock, address)

    socket.getaddrinfo = guarded_getaddrinfo
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pytest", action="store_true")
    parser.add_argument("--unittest-start")
    parser.add_argument("--unittest-top-level")
    parser.add_argument("--unittest-module")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args, extra = parser.parse_known_args()
    install_network_guard()

    if args.pytest:
        import pytest

        return int(pytest.main([*args.arguments, *extra]))
    if args.unittest_module:
        suite = unittest.defaultTestLoader.loadTestsFromName(args.unittest_module)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.unittest_start:
        suite = unittest.defaultTestLoader.discover(
            args.unittest_start,
            top_level_dir=args.unittest_top_level,
        )
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    parser.error("choose --pytest or --unittest-start")
    return 2


if __name__ == "__main__":
    sys.exit(main())
