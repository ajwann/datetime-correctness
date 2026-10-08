# datetime-correctness

An [Agent Skill](https://agentskills.io): **date and time correctness**.

Language-agnostic rules for writing and reviewing date, time, and timezone code correctly. Covers instants vs. local date-times vs. date-only values, storing UTC plus IANA zones, DST gaps and overlaps, "end of day" and day-boundary bugs, recurring schedules and cron in local time, timestamp parsing and serialization, and tests that pin the clock and cross DST. Includes a DST probe script.

## Install

```bash
npx skills add ajwann/datetime-correctness
```

Or copy this directory to `~/.claude/skills/datetime-correctness/` (Claude Code) or your agent's skills folder.

## Contents

- `SKILL.md`: the instructions the agent loads (the frontmatter `description` says when it triggers)
- `scripts/dst_check.py`

## License

MIT
