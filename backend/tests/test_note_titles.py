"""Ticket 14: gap-filling auto-generated titles for Notes created on record start.

A Note gets a generic "Untitled N" title the moment it's created (record
start), per CONTEXT.md's Note Title language: "if text content is less
than a sentence at save time, a generic title is assigned ... incrementing
globally". Ticket 14 needs the title *at creation time* (displayed on
screen while recording), not just at save time -- so the numbering must
gap-fill (reuse the lowest free "Untitled N" slot) rather than grow
unboundedly as notes are created and discarded/replaced across a session.
"""

from backend.app.note_store import NoteTitleGenerator


def test_first_note_is_untitled_1():
    gen = NoteTitleGenerator()
    assert gen.next_title() == "Untitled 1"


def test_second_note_increments():
    gen = NoteTitleGenerator()
    gen.next_title()
    assert gen.next_title() == "Untitled 2"


def test_releasing_a_title_lets_it_be_reused_gap_filling():
    gen = NoteTitleGenerator()
    first = gen.next_title()
    gen.next_title()
    gen.release(first)

    assert gen.next_title() == "Untitled 1"


def test_releasing_a_non_lowest_title_does_not_affect_the_next_allocation():
    gen = NoteTitleGenerator()
    gen.next_title()
    second = gen.next_title()
    gen.release(second)

    assert gen.next_title() == "Untitled 2"
