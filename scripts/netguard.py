"""Optional runtime socket guard (--paranoid). Import this BEFORE rank.py's work to make
any socket creation raise. Used by the sandbox/paranoid reproduction path; the default
graded path relies on `--network none` + the no-socket test instead.
"""

from __future__ import annotations

import socket


class _BlockedSocket(socket.socket):
    def __init__(self, *a, **k):  # noqa: D401
        raise RuntimeError("network access is blocked by netguard (Plane B is offline)")


def enable() -> None:
    socket.socket = _BlockedSocket  # type: ignore[misc,assignment]

    def _blocked(*a, **k):
        raise RuntimeError("network access is blocked by netguard (Plane B is offline)")

    socket.create_connection = _blocked  # type: ignore[assignment]


if __name__ == "__main__":
    enable()
    print("netguard enabled: sockets blocked.")
