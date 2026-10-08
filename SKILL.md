---
name: datetime-correctness
description: Language-agnostic rules for writing and reviewing date, time, and timezone code correctly. Covers instants vs. local date-times vs. date-only values, storing UTC plus IANA zones, DST gaps and overlaps, "end of day" and day-boundary bugs, recurring schedules and cron in local time, timestamp parsing and serialization, and tests that pin the clock and cross DST. Includes a DST probe script. Use whenever code creates, parses, stores, compares, formats, or does arithmetic on dates or times in any language (Python datetime/zoneinfo/pendulum, JS Date/Temporal/Luxon/date-fns, SQL timestamp/timestamptz, Go time, Java java.time, cron), when a bug report mentions times off by an hour, wrong day, timezone, DST, UTC, midnight, or reports landing in the wrong day, or when designing a schema or API field that holds time, even if the user never says "timezone".
---

# Date and time correctness

Most date bugs come from one confusion: treating three different kinds of
value as if they were the same. Decide which kind you have, then follow the
rules for that kind.

## The three kinds of value

| Kind | What it means | Example | Store as |
|---|---|---|---|
| **Instant** | A single point on the global timeline | "payment captured", log timestamp, `created_at` | UTC (`timestamptz`, epoch, ISO 8601 with `Z`) |
| **Local date-time + zone** | A wall-clock time somewhere, usually in the future | "meeting 9:00 every Monday in Berlin", "store opens 08:00" | local time + IANA zone name, *not* converted to UTC |
| **Date only** | A calendar day with no time of day | birthday, due date, holiday, "report for 2026-03-08" | `date` / `LocalDate` / `YYYY-MM-DD` string |

Typical failures from mixing them:
- A birthday stored as a UTC midnight instant shows up a day early west of Greenwich.
- A future meeting converted to UTC drifts by an hour once DST rules apply,
  or once a government changes its zone's rules before the meeting.
- An instant rendered without a zone gets read in the server's local time.

## Rules

1. **Never trust the process's local zone.** Servers, CI runners and
   containers each have their own `TZ`. Pass zones in explicitly. Treat a naive
   (zoneless) datetime crossing a function boundary as a bug unless it is
   explicitly a local or date-only value.
2. **Use IANA zone names** (`America/New_York`), never fixed offsets
   (`-05:00`) or abbreviations (`EST`, `CST`, `IST`). An offset is only true
   for one instant, and abbreviations are ambiguous (IST is India, Ireland and
   Israel).
3. **Convert at the edges.** Parse input into the right kind as soon as it
   arrives. Keep instants in UTC inside the system. Convert to the viewer's
   zone only for display.
4. **Do arithmetic in the right space.** "Add 24 hours" is instant arithmetic.
   "Same time tomorrow" is local arithmetic, and across DST the two differ by
   an hour. Day, month and year math belongs in local date space; durations
   belong in instant space.
5. **Day boundaries are local.** "Today's orders" means
   `[local midnight, next local midnight)` in a *specific* zone, converted to
   two UTC instants. That day can be 23 or 25 hours long. Use half-open
   ranges. Never use `<= 23:59:59`, which drops events in the last second and
   fractional seconds.
6. **Handle DST gaps and overlaps on purpose.** In a gap, a local time doesn't
   exist (02:30 on spring-forward day in New York). In an overlap, a local time
   happens twice (01:30 on fall-back day). Choose and document a policy:
   usually shift forward for gaps and take the earlier instant for overlaps.
   Python uses `fold`, Java uses `ZonedDateTime.ofLocal` with a preferred
   offset, and Temporal uses `disambiguation`.
7. **Serialize unambiguously.** For instants, use ISO 8601 / RFC 3339 with an offset or `Z`.
   For local values, send the zone name alongside. For date-only values, use
   `YYYY-MM-DD` with no time component. Don't send epoch milliseconds in some
   places and seconds in others.
8. **Know your platform's traps.**
   - JS `new Date("2026-03-08")` parses as UTC midnight, but
     `new Date("2026-03-08T00:00")` parses as *local* time, and months are
     0-based. Prefer Temporal or Luxon.
   - Python `datetime.utcnow()` returns a naive value (deprecated in 3.12).
     Use `datetime.now(UTC)`. `pytz` needs `localize()`, and passing
     `tzinfo=` gives LMT offsets like -04:56. Use `zoneinfo`.
   - Postgres `timestamp` (without time zone) discards the zone, while
     `timestamptz` stores the instant. `AT TIME ZONE` flips between them,
     which confuses people.
   - Java/Kotlin: use `java.time` and avoid `Date`/`Calendar`. `LocalDateTime`
     is not an instant.
   - Go: `time.Parse` without a zone gives UTC. Use `time.ParseInLocation` for
     local input.
9. **Cron and schedulers.** Cron runs in the host's zone unless configured
   otherwise. A job at 02:30 local is skipped on spring-forward day and may
   run twice on fall-back day. Schedule in UTC, or pick a time outside 01:00–03:00,
   or use a scheduler that supports zones and documents its DST behavior.
10. **Store the user's zone, not their offset.** Their offset changes twice a
    year.

## Testing

- Pin the clock (`freezegun`/`time-machine`, `vi.useFakeTimers`,
  an injected `Clock` in Java, an injected `now func()` in Go). Never assert
  against the real clock.
- Run the suite with a non-UTC `TZ` at least once
  (`TZ=America/Los_Angeles npm test`, `TZ=Asia/Kolkata pytest`). Many bugs
  only show up off UTC. A zone with a half-hour offset also catches
  "offsets are whole hours" assumptions.
- Add cases on both sides of a DST transition and at the gap and overlap
  times. Use the probe script to get exact transition times:

```bash
python3 scripts/dst_check.py America/New_York 2026
python3 scripts/dst_check.py Europe/London 2026 --check "2026-03-29 01:30"
```

  It prints each transition's UTC instant and offsets, which local times are
  skipped or repeated, and whether a given local time is normal, nonexistent
  or ambiguous.

## Reviewing date code

Ask of every date value in the diff:
- Which of the three kinds is it?
- Where does its zone come from?
- Is any arithmetic done in the right space (local vs. instant)?
- What happens on a 23-hour day and on a 25-hour day?

Report the answer when it's wrong, along with the specific input that breaks it, for example "an order at 23:30 PST on Mar 7 is counted in Mar 8's report."
