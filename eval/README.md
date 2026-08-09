# Evaluation harness

The harness evaluates scrubbed `ScreenContext` snapshots, never live URLs. The
attack set contains 60 messages parsed from the public Nazario phishing mbox;
live paths and queries are removed, victim data is scrubbed, and the raw mbox
is not committed. The eight controls cover every PRD §13 case.

Run from the repository root on Windows 11:

```powershell
py -m eval.run
```

A nonzero exit means at least one control produced a false positive or a
finding lacked evidence. Output lists false positives before attack metrics.
Optional integrations:

```powershell
py -m eval.run --json-out eval/results.json
py -m eval.run --record-convex
```

The Convex mode sends only verdict, finding codes, domain, and a SHA-256
fixture identifier through `convex_client.record_scan`; raw context and
clipboard text never leave the machine.

To rebuild snapshots from a locally downloaded Nazario mbox without opening
any extracted URL:

```powershell
py eval/build_nazario.py phishing0.mbox data/corpus/attacks.jsonl --limit 60
```
