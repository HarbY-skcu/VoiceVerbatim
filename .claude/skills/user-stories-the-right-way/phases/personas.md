# Define Personas

Personas are the people who are the direct beneficiaries and users
of the software system.

## Guidelines

1. Personas must be labeled and categorized by a fictional name,
   not their specific role or characteristics.

2. The background of a persona must be given in terms of the
   problem they wish to solve.

3. The customer and developers for the software project must
   never be included as personas.

4. Personas have different priority levels depending on how
   important they are to the problem domain.

## Process

Ask the user to assist in defining:

- the scope of the project
- the problems
- the people who have those problems

Ask whether enough people have been defined.

## Save Personas

Save all personas created during this planning session as a
markdown file in `/agent_gen_docs/`.

For each new planning session, create a new markdown file.

Claude chooses the filename based on the content of the planning
session.

The filename must:

- be lowercase
- use kebab-case
- clearly describe the subject
- end in `.md`

Before creating the file, check `/agent_gen_docs/` to avoid
overwriting an existing file.

If the chosen filename exists, choose another unique filename.

Do not ask the user for a filename unless one cannot reasonably
be determined.