"""Shared pytest setup for the Campus Event Booking tests.

You normally do NOT need to start the website yourself: the `base_url`
fixture below starts a tiny local web server for the whole test run and
stops it afterwards.

If you already have the site running (for example `python serve.py`) you can
point the tests at it instead:

    python -m pytest --base-url http://127.0.0.1:8000
"""
import threading

import pytest

from serve import AppHandler, make_server


class _QuietHandler(AppHandler):
    """Same server as serve.py, but without one log line per request."""

    def log_message(self, format, *args):  # noqa: A002 (name fixed by the base class)
        pass


@pytest.fixture(scope="session")
def base_url(pytestconfig):
    """Address of the website under test, e.g. http://127.0.0.1:54321"""
    configured = pytestconfig.getoption("base_url")
    if configured:
        yield configured
        return

    # Port 0 = "pick any free port", so tests never clash with another server.
    server = make_server(port=0, handler_class=_QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
