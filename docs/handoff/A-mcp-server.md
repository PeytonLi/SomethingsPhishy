# Track A — MCP server & output contract

**Branch:** `track/server` · **Owns:** `server.py` · **Read first:** [`docs/PRD.md`](../PRD.md) §6.2, §6.9, §18 and [`README.md`](README.md)

## Mission

The VoiceOS-facing surface. You own how a scared person's sentence becomes a tool call, and how a `Finding[]` becomes something that reads well on screen *and* sounds right spoken aloud.

## Why this matters more than it looks

Two things in this track are the highest-leverage prompt surfaces in the whole project:

- **Tool docstrings are the routing prompt.** VoiceOS's agent picks the tool from the description. If "hey, something's phishy — is this safe?" doesn't land on `check_this_page`, nothing else you built matters. Write for how a frightened 74-year-old talks, not how an engineer would phrase it.
- **The output string is the entire product experience.** Everything upstream exists to produce three bullets and one instruction.

## Build

1. **Transport, both modes** (PRD §6.2.1). One `--http` flag switches `mcp.run(transport=...)` between `stdio` and `streamable-http` on `127.0.0.1:8765`. Default to HTTP for development — you get your own logs and can restart without touching VoiceOS.
2. **Six tools** (PRD §18): `check_this_page`, `check_this_download`, `check_this_transaction`, `check_my_clipboard`, `why_is_that_bad(finding_code)`, `alert_my_guardian`.
3. **Verdict card renderer** (PRD §6.9). Verdict line first (⛔ / ⚠️ / ✅), max 3 bullets quoting real evidence, exactly one action line. No risk scores. No jargon. No JSON.
4. **Orchestration**: `context.capture()` → `analyze()` → optional Convex enrich → optional `explain()` → render. Every optional stage is skippable on timeout, and the card still renders.

## Contract

You consume, never define:
```python
from signals import ScreenContext, analyze          # Track C
from context import capture                          # Track B
from explain import humanize                         # Track G
from convex_client import enrich, record_scan        # Track E
```

**Unblock yourself immediately** — do not wait for B, E, or G. Stub them:
```python
# stubs.py (yours, delete at integration)
def capture(surface="any") -> ScreenContext:
    return ScreenContext(text="...", links=[("paypal.com", "https://paypa1-secure.ru/x")])
```
Build the whole pipeline against a fake `ScreenContext`. Swap in the real modules at integration.

## Gotchas

- **`print()` kills stdio mode silently.** stdout is the JSON-RPC wire. `logging.basicConfig(stream=sys.stderr)`. Audit imported libraries too — third-party code prints.
- **The process inherits no environment.** In stdio mode VoiceOS spawns you with no shell env and no useful cwd. `load_dotenv(Path(__file__).parent / ".env.local")`, and every path absolute.
- **Use `py -3`, not `python`,** in the registration command. `python` may resolve to the Microsoft Store stub, which exits silently.
- **A hung tool call looks like a frozen VoiceOS.** Hard-timeout everything. Worse on stage than a wrong answer.
- Verify at hour 0 whether VoiceOS confirms before invoking a tool — a confirmation dialog mid-demo changes the script's pacing (PRD §16.3).

## Done when

- [ ] Voice phrase → `check_this_page` → card, end to end in VoiceOS
- [ ] All six tools registered and individually invocable
- [ ] Card renders correctly for SAFE, CAUTION, DANGER with 0/1/3 findings
- [ ] Every downstream call has a timeout; killing Convex/Claude still produces a card
- [ ] Zero stdout writes outside the MCP protocol (`py -3 server.py 2>/dev/null` emits only JSON-RPC)

## Suggested skills

`superpowers:brainstorming` before designing the docstrings — the phrasings are the deliverable, and they're worth diverging on before converging. `everything-claude-code:mcp-server-patterns` for transport and tool-definition idiom. `superpowers:test-driven-development` for the renderer: it's pure `dict → str`, so tests are trivial and catch every formatting regression.
