# Track H — Eval harness & corpus

**Branch:** `track/eval` · **Owns:** `eval/**`, `data/corpus/**` · **Read first:** [`docs/PRD.md`](../PRD.md) §10, §12, §13 and [`README.md`](README.md)

## Mission

Produce the numbers the pitch is built on, against **real** samples rather than hand-written ones. Track C owns `test_signals.py` (unit-level); you own the corpus-scale harness. Different files, no conflict.

## Why this track exists

Anyone can build a tool that flags everything. The claim that wins is:

> *"Zero false positives on legitimate controls. 80%+ detection on real phishing."*

You are the only track that can make that sentence true — or discover it isn't, while there's still time to fix it.

## Build

1. **Attack corpus.** PhishTank and OpenPhish publish live feeds; the Nazario corpus is the academic standard. Real captured samples let the pitch honestly say "tested against N real-world samples." Target n≥50.
2. **Control set — this is the more important half.** Build by hand:
   - A real Amazon order confirmation **with its tracking links intact**
   - A real Stripe checkout
   - A legitimate GitHub release download
   - A real bank notification
   - A normal ETH transfer
   - A legitimate `.exe` installer from a vendor site
   - A domain containing "rn" (e.g. `modern-bank.com`) — see PRD §6.4.1 defect 3
   - **A clipboard holding a legitimate developer PowerShell command**
3. **Harness**: run every sample through `analyze()`, report precision, recall, and the FP list by sample.
4. Write results to Convex `scans` so the dashboard can show live precision/recall during the demo.

The last two controls are new in v2.0 and both exist to catch a specific known defect. The clipboard one proves `CLIPBOARD_PAYLOAD` is calibrated rather than trigger-happy — without it, that check will flag every developer in the audience.

## Report the FP number, not just detection

A false positive is worse than a miss. Flag one legitimate bank email and the user disables the tool, which leaves them worse off than before they installed it. **Rank your output by false positives first.** If a control fails, that's a P0 bug for Track C — tell them immediately rather than filing it.

You are likely to find that `LINK_TEXT_HREF_MISMATCH` fires on real marketing email (PRD §6.4.1 defect 1). That's expected and already assigned to C. Confirm it empirically and hand them the failing sample.

## Gotchas

- **Handle live phishing samples carefully.** Fetch as text, never execute, never open in the demo browser profile. Don't commit raw feed dumps (`.gitignore` covers `data/corpus/*.raw`).
- Samples decay — live phishing URLs die within days. Snapshot the parsed `ScreenContext`, not the URL, so the eval is reproducible on demo day.
- Scrub PII from anything committed: real phishing samples contain real victim addresses.
- Import `analyze` from `signals`; don't call individual `check_*` functions.

## Done when

- [ ] ≥50 real attack samples, parsed into `ScreenContext` fixtures
- [ ] All 8 controls present and passing SAFE with **zero** findings
- [ ] Harness prints precision, recall, and a per-sample FP list
- [ ] Results written to Convex `scans`
- [ ] One number, stated plainly, for the slide: FP rate on controls, detection rate on attacks

## Suggested skills

`everything-claude-code:eval-harness` for structuring the runner and metrics. `superpowers:verification-before-completion` before reporting numbers — a pitch metric that turns out to be wrong on stage is worse than no metric, so verify the harness measures what you think it measures.
