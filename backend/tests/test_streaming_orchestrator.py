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


class FakeResultsChannel:
    """Test double for the results-delivery channel (ticket 13), external
    to production code per the Protocol + Fake* pattern used elsewhere."""

    def __init__(self):
        self.sent: list[tuple[str, bool]] = []

    async def send(self, *, text: str, final: bool) -> None:
        self.sent.append((text, final))


async def test_results_are_forwarded_to_an_attached_results_channel():
    note = ActiveNote()
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
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


async def test_results_channel_is_detached_once_a_final_result_is_forwarded():
    note = ActiveNote()
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )
    channel = FakeResultsChannel()
    orchestrator.attach_results_channel(channel)
    await orchestrator.start()

    await session.push(StreamingResult(text="world", final=True))
    await session.finish()
    await orchestrator.stop_consuming()

    assert orchestrator.has_results_channel is False


async def test_results_channel_stays_attached_across_pause_and_resume():
    """Only a forwarded final result detaches the channel -- Pause/stop()
    with no pending final must not clear it, so the same channel keeps
    receiving results from a subsequent Resume's new session."""
    note = ActiveNote()
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )
    channel = FakeResultsChannel()
    orchestrator.attach_results_channel(channel)
    await orchestrator.start()
    await session.push(StreamingResult(text="wor", final=False))
    await asyncio.sleep(0)

    await orchestrator.stop()

    assert orchestrator.has_results_channel is True


async def test_has_results_channel_is_false_until_one_is_attached():
    note = ActiveNote()
    session = FakeStreamingSession()
    orchestrator = StreamingTranscriptionOrchestrator(
        note=note, service=FakeStreamingService(session)
    )

    assert orchestrator.has_results_channel is False

    orchestrator.attach_results_channel(FakeResultsChannel())

    assert orchestrator.has_results_channel is True
