import asyncio

import pytest

from backend.app.silence_timeout import SilenceTimeoutMonitor


class FakeClock:
    """A controllable clock so tests don't wait on real wall-clock time."""

    def __init__(self) -> None:
        self.now = 0.0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


@pytest.mark.asyncio
async def test_fires_on_timeout_after_the_configured_silence_period():
    clock = FakeClock()
    fired = asyncio.Event()

    async def on_timeout():
        fired.set()

    monitor = SilenceTimeoutMonitor(
        on_timeout, timeout_seconds=1.0, poll_interval=0.01, clock=clock
    )
    monitor.start()

    for _ in range(20):
        clock.advance(0.1)
        await asyncio.sleep(0.02)
        if fired.is_set():
            break

    assert fired.is_set()
    assert not monitor.is_running


@pytest.mark.asyncio
async def test_notify_speech_resets_the_silence_window():
    clock = FakeClock()
    fired = asyncio.Event()

    async def on_timeout():
        fired.set()

    monitor = SilenceTimeoutMonitor(
        on_timeout, timeout_seconds=1.0, poll_interval=0.01, clock=clock
    )
    monitor.start()

    # Advance close to, but not past, the timeout, then reset it via speech.
    for _ in range(8):
        clock.advance(0.1)
        await asyncio.sleep(0.02)
    assert not fired.is_set()

    monitor.notify_speech()

    for _ in range(8):
        clock.advance(0.1)
        await asyncio.sleep(0.02)
    assert not fired.is_set()  # window was reset, so still under threshold

    for _ in range(20):
        clock.advance(0.1)
        await asyncio.sleep(0.02)
        if fired.is_set():
            break
    assert fired.is_set()


@pytest.mark.asyncio
async def test_cancel_stops_watching_without_firing():
    clock = FakeClock()
    fired = asyncio.Event()

    async def on_timeout():
        fired.set()

    monitor = SilenceTimeoutMonitor(
        on_timeout, timeout_seconds=1.0, poll_interval=0.01, clock=clock
    )
    monitor.start()
    monitor.cancel()

    for _ in range(20):
        clock.advance(0.1)
        await asyncio.sleep(0.01)

    assert not fired.is_set()
    assert not monitor.is_running


@pytest.mark.asyncio
async def test_start_is_idempotent_and_restarts_the_window():
    clock = FakeClock()
    fired = asyncio.Event()

    async def on_timeout():
        fired.set()

    monitor = SilenceTimeoutMonitor(
        on_timeout, timeout_seconds=1.0, poll_interval=0.01, clock=clock
    )
    monitor.start()
    clock.advance(0.9)
    await asyncio.sleep(0.02)

    monitor.start()  # restarts the window instead of stacking a second task

    clock.advance(0.9)
    await asyncio.sleep(0.02)
    assert not fired.is_set()
