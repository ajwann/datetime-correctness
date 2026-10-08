#!/usr/bin/env python3
"""Print the DST transitions of an IANA zone for a year, plus the local times they skip or repeat.

Usage:
    dst_check.py America/New_York 2026
    dst_check.py Europe/London            # current year
    dst_check.py Australia/Sydney 2026 --check "2026-04-05 02:30"

Each transition shows the UTC instant, the offset before and after, and whether
local wall-clock times are skipped (a gap: those times never happen) or
repeated (an overlap: those times happen twice). With --check, it reports
whether that local time is normal, nonexistent, or ambiguous in the zone, and
the UTC instant(s) it maps to.

Standard library only (zoneinfo, Python 3.9+).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def find_transitions(tz: ZoneInfo, year: int) -> list[tuple[datetime, timedelta, timedelta]]:
    """Return (utc_instant, offset_before, offset_after) for each offset change in the year."""
    start = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC)
    transitions = []
    step = timedelta(hours=1)
    t = start
    prev = t.astimezone(tz).utcoffset()
    while t < end:
        nxt = t + step
        off = nxt.astimezone(tz).utcoffset()
        if off != prev:
            # Binary-search the exact second inside this hour.
            lo, hi = t, nxt
            while hi - lo > timedelta(seconds=1):
                mid = lo + (hi - lo) / 2
                if mid.astimezone(tz).utcoffset() == prev:
                    lo = mid
                else:
                    hi = mid
            transitions.append((hi, prev, off))
            prev = off
        t = nxt
    return transitions


def fmt_offset(off: timedelta) -> str:
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


def classify_local(tz: ZoneInfo, local: datetime) -> str:
    """Describe how a naive local wall-clock time maps onto instants in tz."""
    instants = set()
    for fold in (0, 1):
        aware = local.replace(tzinfo=tz, fold=fold)
        utc = aware.astimezone(UTC)
        # A real local time round-trips; a gap time does not.
        if utc.astimezone(tz).replace(tzinfo=None) == local:
            instants.add(utc)
    if not instants:
        return f"{local:%Y-%m-%d %H:%M} does NOT EXIST in {tz.key} (skipped by a DST gap)"
    if len(instants) == 2:
        a, b = sorted(instants)
        return (
            f"{local:%Y-%m-%d %H:%M} is AMBIGUOUS in {tz.key}: happens twice, "
            f"at {a:%Y-%m-%dT%H:%M}Z (fold=0) and {b:%Y-%m-%dT%H:%M}Z (fold=1)"
        )
    (only,) = instants
    return f"{local:%Y-%m-%d %H:%M} is a normal time in {tz.key} = {only:%Y-%m-%dT%H:%M}Z"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("zone", help="IANA zone name, e.g. America/New_York")
    p.add_argument("year", nargs="?", type=int, default=datetime.now(UTC).year)
    p.add_argument("--check", metavar="'YYYY-MM-DD HH:MM'", help="classify one local wall-clock time")
    args = p.parse_args(argv)

    try:
        tz = ZoneInfo(args.zone)
    except ZoneInfoNotFoundError:
        print(f"Unknown zone {args.zone!r}. Use an IANA name like Europe/Berlin, not an abbreviation like CET/EST.", file=sys.stderr)
        return 2

    transitions = find_transitions(tz, args.year)
    if not transitions:
        jan = datetime(args.year, 1, 1, tzinfo=UTC).astimezone(tz)
        print(f"{tz.key} has no offset changes in {args.year} (fixed at UTC{fmt_offset(jan.utcoffset())}).")
    for utc, before, after in transitions:
        local_before = (utc - timedelta(seconds=1)).astimezone(tz)
        delta = after - before
        kind = "GAP (spring forward)" if delta > timedelta(0) else "OVERLAP (fall back)"
        # Wall clock reading at the instant of the change, on the old offset.
        wall_at_change = utc.replace(tzinfo=None) + before
        if delta > timedelta(0):
            # Clocks jump forward: [change, change + delta) is skipped.
            wall_start, wall_end = wall_at_change, wall_at_change + delta
        else:
            # Clocks fall back: the last |delta| before the change repeats.
            wall_start, wall_end = wall_at_change + delta, wall_at_change
        verb = "never happen" if delta > timedelta(0) else "happen twice"
        print(
            f"{utc:%Y-%m-%dT%H:%M:%S}Z  {kind}: UTC{fmt_offset(before)} -> UTC{fmt_offset(after)} "
            f"({local_before.tzname()} -> {utc.astimezone(tz).tzname()})\n"
            f"    local times {wall_start:%Y-%m-%d %H:%M} to {wall_end:%H:%M} {verb}"
        )

    if args.check:
        try:
            local = datetime.strptime(args.check, "%Y-%m-%d %H:%M")
        except ValueError:
            print("--check expects 'YYYY-MM-DD HH:MM'", file=sys.stderr)
            return 2
        print(classify_local(tz, local))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
