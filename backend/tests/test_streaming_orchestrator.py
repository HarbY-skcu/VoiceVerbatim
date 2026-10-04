"""Ticket 04.1: streaming orchestrator.

Ticket 14: composition/positioning ownership moved to the frontend, so the
orchestrator no longer writes streamed results into the Note -- it only
forwards results to an attached results channel. Kept separate from the
WebSocket endpoint so this logic is testable without spinning up a socket.
"""

import asyncio

from backend.app.streaming_orchestrator import StreamingTranscriptionOrchestrator
from backend.app.transcription import StreamingResult


class FakeStreamingSession:
    def __init__(self):
        self.sent: list[bytes] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def send_audio(self, chunk: bytes) -> None:
        self.sent.append(chunk)

    async def results(self):
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def close(self) -> None:
        self.closed = True
        await self._queue.put(None)

    async def push(self, result: StreamingResult) -> None:
        await self._queue.put(result)

    async def finish(self) -> None:
        await self._queue.put(None)


class FakeStreamingService:
    def __init__(self, session: FakeStreamingSession):
        self.session = session

    async def start_session(self):
        return self.session


class FakeResultsChannel:
    """Test double for the results-delivery channel (ticket 13), external
    to production code per the Protocol + Fake* pattern used elsewhere."""

    def __init__(self):
        self.sent: list[tuple[str, bool]] = []
        self.closed = False

    async def send(self, *, text: str, final: bool) -> None:
        self.sent.append((text, final))

    async def close(self) -> None:
        self.closed = True


async def test_interim_and_final_results_are_forwarded_to_an_attached_channel():
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )
    channel = FakeResultsChannel()
    orchestrator.attach_results_channel(channel)
    await orchestrator.start()

    await session.push(StreamingResult(text="wor", final=False))
    await asyncio.sleep(0)

    assert channel.sent == [("wor", False)]

    await session.push(StreamingResult(text="world", final=True))
    await session.finish()
    await orchestrator.stop_consuming()

    assert channel.sent == [("wor", False), ("world", True)]


async def test_audio_chunks_are_forwarded_to_the_session():
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )
    await orchestrator.start()

    await orchestrator.send_audio(b"chunk-1")

    assert session.sent == [b"chunk-1"]
    await session.finish()
    await orchestrator.stop_consuming()


async def test_stop_closes_the_session_without_forcing_a_final():
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )
    await orchestrator.start()
    await session.push(StreamingResult(text="wor", final=False))
    await asyncio.sleep(0)

    await orchestrator.stop()

    assert session.closed


async def test_send_audio_with_no_open_session_is_silently_dropped():
    """Regression test: a trailing MediaRecorder chunk can arrive after
    orchestrator.stop() has already closed the session (e.g. right around
    a Stop request). That's an expected race, not an error -- send_audio()
    must drop the chunk quietly rather than raising and crashing the
    WebSocket connection.
    """
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )
    await orchestrator.start()
    await session.finish()
    await orchestrator.stop()

    # No session is open anymore; this must not raise.
    await orchestrator.send_audio(b"trailing-chunk")

    assert session.sent == []


async def test_concurrent_stop_and_send_audio_do_not_interleave():
    """Regression test: a concurrent Stop/Navigation-Stop request
    (which calls orchestrator.stop(), closing the session and tearing down
    its underlying transport) used to be able to race a WebSocket handler's
    in-flight send_audio() call, letting send_audio() reach a session that
    close() had already torn down mid-call (surfaced as
    ConnectionResetError against the real ffmpeg subprocess). The
    orchestrator's lock must serialize these so send_audio() either
    completes fully before close() starts, or sees `_session is None`
    afterwards -- never a partially-closed session.
    """
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )
    await orchestrator.start()

    send_task = asyncio.create_task(orchestrator.send_audio(b"chunk-1"))
    stop_task = asyncio.create_task(orchestrator.stop())
    await asyncio.gather(send_task, stop_task, return_exceptions=False)

    assert session.closed
    # Whichever won the race, send_audio() ran to completion (appended the
    # chunk) rather than being interrupted mid-call by close().
    assert session.sent == [b"chunk-1"]


async def test_results_channel_stays_attached_across_an_interim_final_result():
    """A forwarded final result no longer detaches the channel on its own
    -- a long Recording with natural pauses between sentences produces
    many Vosk finals, and the channel must stay open for all of them.
    Only stop() (manual Stop, Navigation Stop, Silence Timeout, dropped
    socket) actually ends things."""
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )
    channel = FakeResultsChannel()
    orchestrator.attach_results_channel(channel)
    await orchestrator.start()

    await session.push(StreamingResult(text="world", final=True))
    await asyncio.sleep(0)

    assert orchestrator.has_results_channel is True
    assert channel.closed is False

    await session.finish()
    await orchestrator.stop_consuming()


async def test_stop_detaches_and_closes_the_results_channel():
    """stop() is the only thing that ends a Recording's results channel --
    it both detaches it from the orchestrator and calls close() on it,
    which is the frontend's (WebSocket) signal that the Recording is
    actually over."""
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )
    channel = FakeResultsChannel()
    orchestrator.attach_results_channel(channel)
    await orchestrator.start()
    await session.push(StreamingResult(text="wor", final=False))
    await asyncio.sleep(0)

    await orchestrator.stop()

    assert orchestrator.has_results_channel is False
    assert channel.closed is True


async def test_on_result_fires_for_every_interim_and_final_result():
    """The orchestrator's seam for the Silence Timeout monitor: every
    result (interim or final) forwarded to the results channel counts as
    \"still talking\", not just finals -- otherwise a long uninterrupted
    sentence could time out mid-utterance."""
    session = FakeStreamingSession()
    calls = 0

    def on_result() -> None:
        nonlocal calls
        calls += 1

    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session), on_result=on_result
    )
    await orchestrator.start()

    await session.push(StreamingResult(text="wor", final=False))
    await asyncio.sleep(0)
    await session.push(StreamingResult(text="world", final=True))
    await asyncio.sleep(0)

    assert calls == 2

    await session.finish()
    await orchestrator.stop_consuming()


async def test_has_results_channel_is_false_until_one_is_attached():
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        service=FakeStreamingService(session)
    )

    assert orchestrator.has_results_channel is False

    orchestrator.attach_results_channel(FakeResultsChannel())

    assert orchestrator.has_results_channel is True
