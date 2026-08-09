# Handoff — parallel build split

Eight tracks, eight worktrees, eight agents. **No two tracks write the same file**, so all eight can start at once and merge without conflicts.

Read [`docs/PRD.md`](../PRD.md) first — it is the spec. These handoff docs do not repeat it; they say *which slice you own* and *what contract you must not break*.

Platform is **Windows 11**. PRD v1.0 was macOS; v2.0 replaced the whole context layer. If you find yourself reaching for `osascript`, `pbpaste`, or `xattr`, you are reading the wrong document.

---

## The split

| Track | Owns (exclusive) | Depends on | Blocking? |
|---|---|---|---|
| **A** — MCP server & output | `server.py` | contract only | no |
| **B** — Windows context capture | `context.py`, `scripts/` | contract only | no |
| **C** — Signals engine | `signals.py`, `data/brands.py`, `test_signals.py` | — | **owns the contract** |
| **D** — Convex backend | `convex/**` | — | **owns the API surface** |
| **E** — Convex Python client | `convex_client.py` | D's function names (specified, PRD §6.7) | no |
| **F** — Guardian dashboard | `dashboard/**` | D's schema (specified, PRD §6.6) | no |
| **G** — Explanation layer | `explain.py` | contract only | no |
| **H** — Eval harness & corpus | `eval/**`, `data/corpus/**` | `analyze()` (already exists) | no |

Shared, read-only for everyone except its owner: `requirements.txt` (append your deps in your own track's line, conflicts here are trivial to resolve).

**C and D are contract owners.** They can change what everyone else builds against. Both are constrained below to append-only changes. If either needs a breaking change, they announce it before making it.

---

## The frozen contract

Everything hangs off this. It already exists in `signals.py` at the repo root. **Track C may add to it; nobody may change what is already there.**

```python
# signals.py — the seam between capture, detection, and presentation

class Severity(IntEnum):  INFO=0 LOW=1 MEDIUM=2 HIGH=3 CRITICAL=4
class Verdict(IntEnum):   SAFE=0 CAUTION=1 DANGER=2

@dataclass
class Finding:
    code: str; severity: Severity; title: str; evidence: str; surface: str
    def as_dict(self) -> dict: ...

@dataclass
class ScreenContext:
    # every field optional — the engine degrades gracefully
    text: str = ""
    links: list[tuple[str, str]] = []        # (anchor_text, href)
    page_url: Optional[str] = None
    iframe_origins: list[str] = []
    from_display / from_address / reply_to: Optional[str]
    displayed_address / clipboard_address: Optional[str]
    prior_addresses: list[str] = []
    download_url / download_filename / download_button_text / content_type
    file_size_bytes: Optional[int]

def analyze(ctx: ScreenContext, domain_created: Optional[datetime] = None) -> dict:
    # returns:
    # {
    #   "verdict":       "SAFE" | "CAUTION" | "DANGER",
    #   "findings":      [ {code, severity:int, title, evidence, surface}, ... ],  # max 3
    #   "finding_count": int,      # total before truncation
    #   "action":        str,      # exactly one instruction
    #   "explainable":   bool,
    # }
```

Track C is adding three fields for Windows (PRD §6.4): `clipboard_text`, `download_host_url`, `download_referrer_url`. Track B produces them; nobody else needs to care.

**Rules for everyone:**
- Import `ScreenContext`, `Finding`, `analyze` from `signals`. Do not redefine them.
- Do not add a field to `ScreenContext` from outside Track C. Ask C.
- `analyze()` is the only entry point. Do not call individual `check_*` functions from other modules.

---

## Non-negotiables (violating any of these breaks the product's core claim)

1. **The LLM never decides the verdict.** `analyze()` runs first and its verdict is final. `explain.py` restates findings; it cannot add, drop, or reweight one. This is what makes the tool prompt-injection-proof — see PRD §3.1 and §9.7.
2. **Local-first.** A verdict must be producible with the network down. Convex is enrichment. Every network call gets a hard timeout and a fallback path.
3. **Never `print()` to stdout** in any module that `server.py` imports. In stdio transport, stdout is the JSON-RPC wire. Log to stderr.
4. **No PowerShell subprocess in the hot path.** `powershell.exe` cold-start is 300–600 ms — a fifth of the latency budget. Everything in `context.py` is a Python API call, a loopback HTTP GET, or a file read.
5. **Every finding quotes real observed text.** If you can't quote it, don't emit it.
6. **Zero false positives on the control set** beats detection rate. See PRD §10.
7. **Loopback only.** If you bind a port, bind `127.0.0.1`.
8. **Raw clipboard text never leaves the machine.** Not to Convex, not to Claude. It routinely contains passwords.

---

## Worktree setup

The repo needs one base commit before worktrees can branch from it:

```powershell
git add -A
git commit -m "base: PRD v2.0, signals.py, handoff docs"
```

Then, per track:

```powershell
git worktree add ..\sp-<track> -b track/<track>
# e.g.  git worktree add ..\sp-context -b track/context
```

Suggested branch names: `track/server`, `track/context`, `track/signals`, `track/convex`, `track/convex-client`, `track/dashboard`, `track/explain`, `track/eval`.

Merge order when integrating: **C and D first** (contract owners), then everything else in any order, then a single integration pass wiring `server.py` → `context.capture()` → `analyze()` → `explain()`.

---

## The one thing that will actually kill the demo

Chrome ≥136 refuses `--remote-debugging-port` on the default user-data-dir. Track B verifies this on the real demo machine **at hour 0**, not hour 6. PRD §6.3.1. Everything else has a fallback; this one doesn't announce itself until you need it.

---

## Track docs

- [A — MCP server & output contract](A-mcp-server.md)
- [B — Windows context capture](B-context-capture.md)
- [C — Signals engine hardening](C-signals-engine.md)
- [D — Convex backend](D-convex-backend.md)
- [E — Convex Python client](E-convex-client.md)
- [F — Guardian dashboard](F-guardian-dashboard.md)
- [G — Explanation layer](G-explain-layer.md)
- [H — Eval harness & corpus](H-eval-harness.md)
