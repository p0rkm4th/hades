"""Harden the pinned Open WebUI SSE delta splitter against null stream values.

The pinned frontend assumes every non-terminal parsed SSE event has a string
``value``.  Provider disconnects and malformed/late events can violate that
assumption during abandonment/re-entry, causing ``value.length`` to throw and
poisoning the visible conversation lifecycle.  This exact build-time patch
turns such events into an empty delta and lets the normal stream completion
path continue.

Remove this compatibility layer when the pinned upstream frontend validates
the delta value before chunking it.
"""

from pathlib import Path


CHUNKS = Path("/app/build/_app/immutable/chunks")
OLD = 'let s=t.value;if(s.length<5)'
NEW = 'let s=t.value;if(typeof s!=="string")s="";if(s.length<5)'


def main() -> None:
    matches = []
    for path in sorted(CHUNKS.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        count = text.count(OLD)
        if count:
            matches.append((path, count))

    if len(matches) != 1 or matches[0][1] != 1:
        raise SystemExit(f"expected one pinned SSE splitter, found {matches!r}")

    path, _ = matches[0]
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print(f"PASS Open WebUI SSE delta null-value compatibility patch applied: {path.name}")


if __name__ == "__main__":
    main()
