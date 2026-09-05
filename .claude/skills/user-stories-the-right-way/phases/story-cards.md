# Create Story Cards

## Story Types

User stories can be:

- Epic
- Story

An epic is a story that has not yet been explored.

A story is an explored piece of business narrative defining:

- what
- why
- completion condition

## Format

A user story has the form:

"As a (persona) I want (feature) so I can (benefit)"

Every story must also have a satisfaction condition. For epics, the 
satisfaction condition can be other stories.

## Levels

### Abstract

The satisfaction condition is the completion of other stories.

### Concrete

The story has a well-defined, measurable outcome.

Examples:

- pages load in 200 ms
- the user can change text in their files

## Story-building approach

Start by telling the whole story.

Think:

> mile-wide, inch-deep

Build stories horizontally across the journey of each persona.

Start with abstract stories.

Add concrete stories afterward.

Do not prematurely add implementation details.

## Technical Details

User stories should generally be solution agnostic.

Technical details are appropriate when they are intrinsic to the
problem.

Technical constraints may appear in acceptance criteria.

Examples:

- The checkout system must handle 10,000 concurrent transactions.
- The search results page must load in under 200 milliseconds.

## Save User Stories

Save all user stories generated during this planning session as a
markdown file in `/agent_gen_docs/`.

Create a new file for every planning session.

Associate the story filename with its respective persona document.

Claude chooses the filename based on the content.

The filename must:

- be lowercase
- use kebab-case
- clearly describe the subject
- end in `.md`

Before creating the file, check `/agent_gen_docs/`.

Do not ask the user for a filename unless one cannot reasonably
be determined.