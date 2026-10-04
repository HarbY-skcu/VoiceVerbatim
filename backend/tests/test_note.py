"""Ticket 14: ActiveNote after cursor/insertion-position ownership moved to
the frontend. ActiveNote is now a dumb sink: it holds text/title and
observes saves, with no splicing or cursor tracking of its own.
"""

from backend.app.note import ActiveNote


def test_set_text_overwrites_whatever_was_there_before():
    note = ActiveNote()
    note.text = "hello"

    note.set_text("hello world")

    assert note.text == "hello world"


def test_set_text_can_shrink_the_text_too():
    note = ActiveNote()
    note.text = "hello world"

    note.set_text("hello")

    assert note.text == "hello"


def test_save_copies_the_current_text_into_saved_text():
    note = ActiveNote()
    note.set_text("hello world")

    note.save()

    assert note.saved_text == "hello world"
