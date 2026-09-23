"""Ticket 04.1: streaming interim/final text reconciliation on ActiveNote.

Batch transcription (ticket 04) inserts atomically via insert_at_cursor.
Streaming introduces a second insertion mode: interim results must be
replaceable (the speech engine revises its guess as more audio arrives)
without the caller tracking offsets itself.
"""

from backend.app.note import ActiveNote


def test_first_interim_update_inserts_at_the_cursor():
    note = ActiveNote()
    note.text = "hello "
    note.cursor = 6

    note.insert_streaming("wor", final=False)

    assert note.text == "hello wor"


def test_second_interim_update_replaces_the_first_not_appends():
    note = ActiveNote()
    note.text = "hello "
    note.cursor = 6

    note.insert_streaming("wor", final=False)
    note.insert_streaming("world", final=False)

    assert note.text == "hello world"


def test_final_update_commits_and_cursor_lands_after_it():
    note = ActiveNote()
    note.text = "hello "
    note.cursor = 6

    note.insert_streaming("wor", final=False)
    note.insert_streaming("world", final=True)

    assert note.text == "hello world"
    assert note.cursor == len("hello world")


def test_next_utterance_after_a_final_starts_a_fresh_span_not_replacing_the_committed_text():
    note = ActiveNote()
    note.text = "hello "
    note.cursor = 6

    note.insert_streaming("world", final=True)
    note.insert_streaming(" again", final=False)

    assert note.text == "hello world again"


def test_streaming_text_preserves_content_after_the_original_cursor_position():
    note = ActiveNote()
    note.text = "hello there"
    note.cursor = 6

    note.insert_streaming("world", final=True)

    assert note.text == "hello worldthere"
