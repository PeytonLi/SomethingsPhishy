# Track D — Convex backend

**Branch:** `track/convex` · **Owns:** `convex/**` · **Read first:** [`docs/PRD.md`](../PRD.md) §6.5, §6.6, §6.7, §9 and [`README.md`](README.md)

## Mission

The reactive backend. Pure TypeScript — you touch no Python, and nothing in this track is Windows-specific.

**You are a contract owner:** Tracks E and F build against your schema and function names before you've written them. Both are fully specified in PRD §6.6 and §6.7. If you deviate from the spec, tell E and F. Otherwise they integrate cleanly on first try.

## Build

Schema is given verbatim in PRD §6.6 — five tables: `domainIntel`, `communityFlags`, `scamCorpus`, `scans`, `guardians`. Function surface is given in §6.7.

Priority order:

1. **`scans.recordScan` + `scans.guardianFeed`** — these two make the guardian demo work, and the guardian demo is the emotional beat of the pitch. Ship them first so Track F is unblocked with real data.
2. **`intel.getDomainIntel` (query) + `intel.refreshDomainIntel` (action)** — RDAP lookup against `rdap.org/domain/<d>`, cached with a TTL. Feeds `DOMAIN_VERY_NEW`, which is in `DECISIVE`.
3. **`community.reportDanger` + `getCommunityFlag`** — promote a domain at N=3 distinct reporters.
4. **`alerts.notifyGuardian`** + scheduled escalation on unacknowledged DANGER after 60s.
5. **`crons`**: nightly threat-feed refresh, hourly stale-intel expiry.
6. **P2, cut without regret:** `corpus.similarScams` vector search.

## Why Convex, in one line each (this is also the pitch)

Reactive `useQuery` means the guardian dashboard updates in under a second with no websocket code, no polling, no push infra. The intel cache turns a slow RDAP call into a cross-user latency win. The community blocklist is a real network effect — the product measurably improves with each user.

## The guardrail that matters

> Vector similarity is a **supporting signal only.** It may raise CAUTION and add a finding. It is **never** in `DECISIVE` and can never alone produce DANGER.

Letting a fuzzy signal drive verdicts destroys the low-false-positive property the whole product rests on. If you ship vector search, ship it capped at MEDIUM.

## Privacy constraints — these are schema-level, not policy-level

- `scans.findingsRedacted` holds PII-scrubbed evidence strings. Scrub emails, phone numbers, addresses, and long digit runs **before** insert, not on read.
- `textHash` is a SHA-256 of normalized text. It exists so we can dedupe without ever storing content. Never add a raw-text column to `scans`.
- **Raw clipboard text must never reach Convex.** It routinely contains passwords.
- `guardians.consentGivenAt` is required and non-optional. Guardian mode without two-sided consent is spyware, not a safety net. The protected user always sees what the guardian sees.

## Done when

- [ ] `npx convex dev` runs clean; all five tables deployed with their indexes
- [ ] `recordScan` → `guardianFeed` reflects the new row reactively (verify in the Convex dashboard before F integrates)
- [ ] RDAP lookup returns a real registration date for a known-new domain, cached on second call
- [ ] `reportDanger` promotes at exactly 3 distinct reporters, not 3 reports
- [ ] Scrubbing verified: insert a finding containing an email + phone, confirm neither survives

## Suggested skills

`everything-claude-code:database-reviewer` for schema and index review before E and F build against it — a schema change after they've integrated costs three tracks, not one. `everything-claude-code:api-design` for the function surface, since it's a contract two other tracks consume sight-unseen.
