"""Evaluate scrubbed ScreenContext fixtures through signals.analyze."""
from __future__ import annotations
import argparse
import hashlib
import inspect
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from signals import ScreenContext, analyze  # noqa: E402


def load(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
    return records


def make_context(raw: dict[str, Any]) -> ScreenContext:
    """Support append-only context fields before Track C merges them."""
    supported = {item.name for item in fields(ScreenContext)}
    values = {key: value for key, value in raw.items() if key in supported}
    if "links" in values:
        values["links"] = [tuple(link) for link in values["links"]]
    return ScreenContext(**values)


def domain_of(context: dict[str, Any]) -> str | None:
    urls = [context.get("page_url"), context.get("download_url")]
    urls += [link[1] for link in context.get("links", []) if len(link) == 2]
    for url in filter(None, urls):
        hostname = urlsplit(url).hostname
        if hostname:
            return hostname.lower()
    return None


def recorder() -> Callable[..., Any] | None:
    try:
        from convex_client import record_scan
        return record_scan
    except (ImportError, AttributeError):
        return None


def send(rec: Callable[..., Any], sample: dict[str, Any], result: dict[str, Any]) -> None:
    """Send only allowlisted metadata, never context or clipboard text."""
    allowed = {
        "verdict": result["verdict"],
        "codes": [finding["code"] for finding in result["findings"]],
        "domain": domain_of(sample["context"]),
        "text_hash": hashlib.sha256(sample["id"].lower().encode()).hexdigest(),
    }
    signature = inspect.signature(rec)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
        rec(**allowed)
    else:
        rec(**{key: value for key, value in allowed.items() if key in signature.parameters})


def evaluate(samples: list[dict[str, Any]], rec: Callable[..., Any] | None) -> list[dict[str, Any]]:
    outcomes = []
    for sample in samples:
        result = analyze(make_context(sample["context"]))
        outcomes.append({"id": sample["id"], "label": sample["label"], "result": result})
        if rec:
            send(rec, sample, result)
    return outcomes


def report(outcomes: list[dict[str, Any]]) -> int:
    controls = [x for x in outcomes if x["label"] == "control"]
    attacks = [x for x in outcomes if x["label"] == "attack"]
    fps = [x for x in controls if x["result"]["verdict"] != "SAFE"]
    tps = [x for x in attacks if x["result"]["verdict"] != "SAFE"]
    misses = [x for x in attacks if x["result"]["verdict"] == "SAFE"]
    precision = len(tps) / (len(tps) + len(fps)) if tps or fps else 0.0
    recall = len(tps) / len(attacks) if attacks else 0.0
    fp_rate = len(fps) / len(controls) if controls else 0.0

    print("FALSE POSITIVES (ranked first)")
    if not fps:
        print("  none")
    for item in fps:
        codes = ", ".join(f["code"] for f in item["result"]["findings"])
        print(f"  {item['id']}: {item['result']['verdict']} — {codes}")
    print("\nMETRICS")
    print(f"  controls: {len(controls)}")
    print(f"  false positives: {len(fps)}")
    print(f"  false-positive rate: {fp_rate:.1%}")
    print(f"  attacks: {len(attacks)}")
    print(f"  detected attacks: {len(tps)}")
    print(f"  missed attacks: {len(misses)}")
    print(f"  precision: {precision:.1%}")
    print(f"  recall / detection rate: {recall:.1%}")
    print("\nSLIDE")
    print(f"  {fp_rate:.1%} FP rate on {len(controls)} controls; "
          f"{recall:.1%} detection on {len(attacks)} real phishing samples.")

    empty_evidence = {x["id"] for x in outcomes for f in x["result"]["findings"]
                      if not f.get("evidence", "").strip()}
    if empty_evidence:
        print("\nERROR: findings without evidence: " + ", ".join(sorted(empty_evidence)))
        return 2
    return 1 if fps else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "data" / "corpus")
    parser.add_argument("--record-convex", action="store_true")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    samples = load(args.corpus_dir / "controls.jsonl") + load(args.corpus_dir / "attacks.jsonl")
    rec = recorder() if args.record_convex else None
    if args.record_convex and rec is None:
        raise SystemExit("convex_client.record_scan is unavailable")
    outcomes = evaluate(samples, rec)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(outcomes, indent=2) + "\n", encoding="utf-8")
    return report(outcomes)


if __name__ == "__main__":
    raise SystemExit(main())
