# `/plan-beans` Skill: Synchronize Tickets with Beans

The `/plan-beans` command synchronizes ticket declarations from `/to-tickets` with Beans, converting ticket dependency declarations into a Beans dependency graph. It does not redesign, split, merge, or semantically re-plan tickets—it faithfully reflects the ticket structure into Beans.

## Use This Skill For

- Synchronizing tickets created by `/to-tickets` into Beans for execution tracking
- Validating ticket dependencies for cycles and conflicts
- Viewing the current execution frontier (ready vs. blocked tickets)
- Updating Beans when ticket dependencies change

## Workflow

# Find Tickets

Locate the feature's tickets directory:

```
.scratch/<feature-slug>/issues/
```

If the feature is not specified:
- Use the only feature containing tickets
- If multiple features exist, ask the user which one to plan

Read the `/to-tickets` skill only to understand the ticket format. For normal operation, extract only:
- Ticket number
- Ticket title
- `Blocked by` field
- Beans ID

Do not analyze ticket descriptions or acceptance criteria unless needed to resolve an error.

# Beans ID Assignment

Each ticket must contain a stable Beans ID in its frontmatter:

```yaml
---
beans_id: <beans-id>
---
```

Example:
```yaml
---
beans_id: abc123
title: Implement user authentication
number: 01
---
```

If `beans_id` is missing:
- Create the corresponding Beans task
- Record its Beans ID in the ticket frontmatter
- Continue

Do not create a second Beans task if `beans_id` already exists. The ticket's `beans_id` is the authoritative mapping between the Markdown ticket and Beans.

# Read Dependencies

For each ticket, read its `Blocked by` field.

Example:
```
Blocked by:
- 01
- 02
```

This declares:
```
01 → current ticket
02 → current ticket
```

A ticket with no blockers has no incoming dependency.

Do not infer dependencies that are not declared by `/to-tickets`.

# Validate

Before modifying Beans, validate the dependency graph:
- Every blocker exists
- No ticket blocks itself
- No dependency cycle exists
- Every ticket has a valid `beans_id`

If validation fails, stop and report the problem. Do not guess.

# Synchronize Beans

Compare the declared dependencies with the existing Beans graph.

For each missing dependency, run:
```bash
beans dep add <blocker-beans-id> <blocked-beans-id>
```

Do not remove existing Beans dependencies automatically. If Beans contains a dependency that conflicts with the ticket declarations, report it and ask the user what to do.

# Confirmation

Before adding dependencies, show a concise dry run:

```
Plan for <feature>

Dependencies to add:
  01 → 03
  02 → 03
  03 → 04

No conflicts detected.

Apply these changes? [y/N]
```

Do not modify Beans until the user confirms.

# Show Execution Frontier

After synchronization, run:

```bash
beans --json ready
```

Present the result grouped as parallel work:

```
Ready now:

1. <ticket title>
2. <ticket title>

These tickets are currently independent and can be worked on in parallel.

Blocked:

3. <ticket title> — blocked by 01
4. <ticket title> — blocked by 03
```

Do not claim or execute any ticket.

## Ownership

- Ticket decomposition & dependency decisions — `/to-tickets` declares what tickets exist and which block which
- Synchronization & validation — `/plan-beans` ensures Beans reflects ticket declarations
- Execution state — Beans tracks claim status, start/completion
- Ticket-to-Beans identity — `beans_id` is the stable mapping in ticket frontmatter
- Dependency declarations — `Blocked by` declared in ticket frontmatter
- Current execution frontier — `beans ready` is query-only, authoritative view

## Rules

- Never invent dependencies—only add what `/to-tickets` declares
- Never execute tickets during `/plan-beans`—only synchronize and validate
- Ticket-to-Beans mapping is stable—once assigned, `beans_id` is permanent
- Conflicts require user decision—do not auto-resolve conflicting dependencies
- Validation is mandatory—stop on any error and ask the user
- Dry run before commit—always show the plan before applying changes
- Preserve existing Beans state—only add missing dependencies, never remove

## Example Workflow

```
$ /plan-beans feature-auth

Found 4 tickets in .scratch/feature-auth/issues/

Validating…
✓ All blockers exist
✓ No cycles detected
✓ All tickets have beans_id

Plan for feature-auth

Dependencies to add:
  t_auth_01 → t_auth_02
  t_auth_01 → t_auth_03
  t_auth_02 → t_auth_04

No conflicts detected.

Apply these changes? [y/N] y

Adding dependencies…
✓ Added t_auth_01 → t_auth_02
✓ Added t_auth_01 → t_auth_03
✓ Added t_auth_02 → t_auth_04

Ready now:

1. Setup auth service (01)
2. Configure database schema (03)

These tickets are currently independent and can be worked on in parallel.

Blocked:

3. Implement login endpoint (02) — blocked by 01
4. Add password reset flow (04) — blocked by 02
```

## Error Handling

### Missing Beans ID
```
❌ Ticket 02 missing beans_id

Action: Create the corresponding Beans task, record its ID in the ticket frontmatter, then re-run /plan-beans.
```

### Blocker Not Found
```
❌ Ticket 03 blocked by 99, but ticket 99 does not exist

Action: Check /to-tickets for ticket 99 or remove the blocker declaration from ticket 03.
```

### Dependency Cycle
```
❌ Cycle detected: 01 → 02 → 03 → 01

Action: Break the cycle by modifying the Blocked by declarations in /to-tickets.
```

### Conflicting Dependencies
```
⚠ Beans contains: 01 → 02
⚠ Tickets declare: 02 → 01

Action: Resolve the conflict. Update Beans manually or change the ticket declarations?
```

## Integration with Related Skills

- **`/to-tickets`** — Defines tickets and their blocking relationships. `/plan-beans` consumes this output.
- **`Beans`** — Dependency graph storage and execution tracking. `/plan-beans` synchronizes tickets into Beans.
- **`beans ready`** — Query-only; shows current execution frontier after `/plan-beans` completes.

---
