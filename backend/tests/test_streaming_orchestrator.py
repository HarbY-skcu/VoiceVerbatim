"""Ticket 04.1: streaming orchestrator.

Bridges a StreamingTranscriptionSession's results into the Note via
insert_streaming, mirroring how TranscriptionPipeline bridges the batch
service into insert_at_cursor. Kept separate from the WebSocket endpoint
so this logic is testable without spinning up a socket.
"""

import asyncio

from backend.app.note import ActiveNote
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


async def test_interim_results_are_reflected_into_the_note_as_they_arrive():
    note = ActiveNote()
    note.text = "hello "
    note.cursor = 6
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )
    await orchestrator.start()

    await session.push(StreamingResult(text="wor", final=False))
    await asyncio.sleep(0)

    assert note.text == "hello wor"

    await session.push(StreamingResult(text="world", final=True))
    await session.finish()
    await orchestrator.stop_consuming()

    assert note.text == "hello world"
    assert note.cursor == len("hello world")


async def test_audio_chunks_are_forwarded_to_the_session():
    note = ActiveNote()
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )
    await orchestrator.start()

    await orchestrator.send_audio(b"chunk-1")

    assert session.sent == [b"chunk-1"]
    await session.finish()
    await orchestrator.stop_consuming()


async def test_implicit_pause_closes_the_session_without_forcing_a_final():
    note = ActiveNote()
    note.text = "hello "
    note.cursor = 6
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )
    await orchestrator.start()
    await session.push(StreamingResult(text="wor", final=False))
    await asyncio.sleep(0)

    await orchestrator.stop()

    assert session.closed
    assert note.text == "hello wor"


async def test_send_audio_with_no_open_session_is_silently_dropped():
    """Regression test: the frontend keeps its WebSocket open across
    Pause/Resume and only closes/reopens it after the Pause request
    completes, so a trailing MediaRecorder chunk can arrive after
    orchestrator.stop() has already closed the session. That's an
    expected race, not an error -- send_audio() must drop the chunk
    quietly rather than raising and crashing the WebSocket connection.
    """
    note = ActiveNote()
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )
    await orchestrator.start()
    await session.finish()
    await orchestrator.stop()

    # No session is open anymore; this must not raise.
    await orchestrator.send_audio(b"trailing-chunk")

    assert session.sent == []


async def test_concurrent_stop_and_send_audio_do_not_interleave():
    """Regression test: a concurrent Pause/Stop/Navigation-Stop request
    (which calls orchestrator.stop(), closing the session and tearing down
    its underlying transport) used to be able to race a WebSocket handler's
    in-flight send_audio() call, letting send_audio() reach a session that
    close() had already torn down mid-call (surfaced as
    ConnectionResetError against the real ffmpeg subprocess). The
    orchestrator's lock must serialize these so send_audio() either
    completes fully before close() starts, or sees `_session is None`
    afterwards -- never a partially-closed session.
    """
    note = ActiveNote()
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )
    await orchestrator.start()

    send_task = asyncio.create_task(orchestrator.send_audio(b"chunk-1"))
    stop_task = asyncio.create_task(orchestrator.stop())
    await asyncio.gather(send_task, stop_task, return_exceptions=False)

    assert session.closed
    # Whichever won the race, send_audio() ran to completion (appended the
    # chunk) rather than being interrupted mid-call by close().
    assert session.sent == [b"chunk-1"]
