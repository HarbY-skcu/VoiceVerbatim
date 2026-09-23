"""Test collection ordering.

test_recording_stream_ws.py exercises real WebSocket connections through
TestClient's anyio portal. That portal's background thread/event loop can
outlive the test (a known TestClient/anyio teardown quirk -- see the
comments in test_recording_stream_ws.py and main.py's stream_audio) and,
because every test module shares the same FastAPI `app` and its module-level
singletons (recording_session, streaming_orchestrator, ...), a dangling
websocket portal thread can intermittently interfere with later modules'
plain HTTP requests against those same singletons.

Running the WebSocket module last means any such leakage has no later test
left to pollute.
"""

WS_TEST_MODULE = "test_recording_stream_ws.py"


def pytest_collection_modifyitems(items):
    ws_items = [item for item in items if WS_TEST_MODULE in str(item.fspath)]
    other_items = [item for item in items if WS_TEST_MODULE not in str(item.fspath)]
    items[:] = other_items + ws_items
