# Track E — Convex Python client

**Branch:** `track/convex-client` · **Owns:** `convex_client.py` · **Read first:** [`docs/PRD.md`](../PRD.md) §6.7, §11, §9 and [`README.md`](README.md)

## Mission

A thin wrapper around the Convex Python SDK whose entire job is **making the network optional**. Small track, disproportionate impact: you are the reason a verdict still appears when the venue wifi dies mid-demo.

## Build

```python
def enrich(domain: str, timeout: float = 1.5) -> dict:
    """Domain intel + community flag. Returns {} on any failure."""

def record_scan(verdict: str, codes: list[str], domain: str | None, ...) -> None:
    """Fire and forget. Never raises, never blocks the verdict."""
```

Against Track D's surface (PRD §6.7): `intel:getDomainIntel`, `intel:refreshDomainIntel`, `community:getCommunityFlag`, `community:reportDanger`, `scans:recordScan`.

Both calls run in a thread pool with a **hard 1.5 s cap on the aggregate**, not per-call. On timeout: return what arrived, signal reduced confidence, move on.

## Don't wait for Track D

Their function names are specified in the PRD. Write against the spec, stub the responses, and integrate when D lands. If D deviates, they'll tell you.

## Gotchas

- **`client.subscribe()` blocks as a generator.** It works, but only in a separate watcher process — calling it inside an MCP tool call hangs the tool, which looks like a frozen VoiceOS. There is no use for it in this module.
- **Timeouts must be enforced by you, not hoped for.** A hung socket with no deadline is the failure mode that ruins the demo, and it won't reproduce on your fast home wifi.
- **Never raise into the caller.** `server.py` calls you inside the verdict path. A Convex outage must degrade to a local verdict, never to a stack trace. Swallow, log to stderr, return empty.
- **Egress allowlist** (PRD §9.2). Only these leave the machine: registrable domains, finding codes, verdict, SHA-256 of normalized text. **Never** raw page text, email bodies, clipboard contents, or crypto addresses. You are the chokepoint where this is enforced — if a caller hands you raw text, drop it.
- Never `print()`. `server.py` imports you.

## Done when

- [ ] `enrich()` returns useful data on a live Convex deployment
- [ ] With Convex unreachable, `enrich()` returns `{}` in ≤1.5 s and raises nothing
- [ ] With Convex unreachable, `record_scan()` is a no-op and raises nothing
- [ ] **Airplane-mode test:** full `server.py` run produces a correct local verdict with no network
- [ ] Egress audit: log every outbound payload once, read them, confirm no raw text

## Suggested skills

`superpowers:test-driven-development` — the failure paths *are* the feature here, and they're the ones you cannot test by hand on stage. Write the "Convex is down" test before the happy path. `everything-claude-code:python-review` for the thread-pool and timeout handling, which is the only genuinely subtle code in this track.
