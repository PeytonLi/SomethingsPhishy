# Track C — Signals engine hardening

**Branch:** `track/signals` · **Owns:** `signals.py`, `data/brands.py`, `test_signals.py` · **Read first:** [`docs/PRD.md`](../PRD.md) §6.4, §6.4.1, §7 (all), §10 and [`README.md`](README.md)

## Mission

You own the deterministic engine — the thing that makes the whole product's central claim true. **You are also a contract owner:** `ScreenContext`, `Finding`, and `analyze()` are the seam every other track builds against. Additions are free; changes are not. If you need a breaking change, announce it before making it.

`signals.py` already works: 7 attack cases caught, 3 legitimate controls clean. Your job is to fix three real defects and add the Windows detection surface without regressing those controls.

## Fix these three first (PRD §6.4.1)

**1. `check_link_mismatch` false-positives on real marketing email. Highest priority — this one can lose the demo.**

Genuine PayPal email links anchor text "paypal.com" to `epl.paypal-communication.com`. Amazon uses `awstrack.me`. Both trip `LINK_TEXT_HREF_MISMATCH`, which is `CRITICAL` and in `DECISIVE` — so **one hit alone produces DANGER on a legitimate bank email.** That is exactly the failure mode PRD §10 says kills the product. The current Amazon control passes only because its fixture links carry no tracking.

Fix: an ESP/tracking-domain allowlist in `data/brands.py`, checked before emitting. Keep it small and specific — `paypal-communication.com`, `awstrack.me`, `sendgrid.net`, `list-manage.com`, `exacttarget.com`. Then add a control fixture with *real* tracking links and confirm it comes back SAFE.

**2. `registrable()` is a hardcoded two-part-TLD guess.** It handles `.co.uk` and silently misclassifies everything else. Swap in `tldextract` — one call, five minutes, removes a whole class of latent wrongness. Do it early; it touches every check.

**3. `_fold()` applies `"rn" → "m"` unconditionally.** Ordinary labels containing "rn" get mangled before the Levenshtein comparison. No false positive in the current test set, but it's untested surface. Add a `modern-bank.com`-style control so a regression becomes visible instead of latent.

## Then add

- **Three `ScreenContext` fields** (append-only): `clipboard_text: str = ""`, `download_host_url: Optional[str] = None`, `download_referrer_url: Optional[str] = None`. Track B fills them. Do this early — B is blocked on it.
- **`CLIPBOARD_PAYLOAD`** (PRD §7.5.1). The demo-winning check. The token table is in the PRD; so are the two calibration rules that keep it near-zero-FP. Read them — an ungated `iwr` match will flag every developer in the room.
- **The rest of §7.5**: `CLICKFIX_COMMAND` (Win+R / Win+X / PowerShell, not Terminal), `MOTW_STRIPPED`, `LNK_IN_ARCHIVE`, `SOFTWARE_IMPERSONATION`, `DOWNLOAD_HOST_MISMATCH`, `DOUBLE_EXTENSION` (include the RTLO override char `‮`), `FAKE_BROWSER_UPDATE`, `DISABLE_ANTIVIRUS`, `TECH_SUPPORT_SCARE`, `PASSWORD_PROTECTED_ARCHIVE`, `WAREZ_CRACK`.

`DANGEROUS_EXT` alone stays LOW and stays out of `DECISIVE`. `.exe` and `.msi` are how Windows software ships.

## The rule that governs every decision here

> Every check returns hard evidence — the actual strings observed — never a vague label.

If you can't quote it, don't emit it. `evidence` is a real substring of what was on screen. This is what lets the explanation layer be safe and what makes the anti-hallucination claim true.

## Gotchas

- Adding a code to `DECISIVE` means one hit → DANGER with no corroboration. Justify each one against the control set. When in doubt, leave it out and let the ≥2-HIGH rule catch it.
- Keep the per-check `try/except` in `analyze()`. One bad regex must never take down a verdict.
- Top-3 truncation is a product decision, not a limitation. Don't raise it.
- Never `print()`. `server.py` imports you.

## Done when

- [ ] All 10 existing cases still pass, controls still SAFE with **zero** findings
- [ ] New control with real ESP tracking links → SAFE
- [ ] New control `modern-bank.com` → SAFE
- [ ] New control: clipboard holding a legitimate developer PowerShell command → **not** CRITICAL
- [ ] `tldextract` in, hardcoded TLD set out
- [ ] Every §7.5 code implemented with a passing attack fixture
- [ ] `ScreenContext` additions landed and pushed early (B is waiting)

## Suggested skills

`superpowers:test-driven-development` — this is the track where it genuinely pays: write the failing control fixture *first*, then the allowlist that makes it pass. Every check you add is one regex away from a false positive, and the control set is the only thing standing between you and flagging someone's actual bank. `everything-claude-code:python-review` before merge, since you own the contract everyone else imports.
