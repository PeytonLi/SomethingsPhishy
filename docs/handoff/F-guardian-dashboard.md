# Track F — Guardian dashboard

**Branch:** `track/dashboard` · **Owns:** `dashboard/**` · **Read first:** [`docs/PRD.md`](../PRD.md) §6.5(1), §6.6, §15.5, §9.4 and [`README.md`](README.md)

## Mission

React + Convex. When a DANGER verdict fires on Margaret's PC, Dan's dashboard updates in under a second — no websocket code, no polling, no push infrastructure, just `useQuery` on `scans:guardianFeed`.

This is the emotional beat of the pitch. The line it has to earn: *"The reason elder fraud works is isolation. This breaks the isolation in under two seconds."*

## Build

1. `useQuery(api.scans.guardianFeed, { guardianUserId })` — reactive, that's the whole mechanism.
2. A feed of scan cards: verdict badge, relative time ("40 seconds ago"), the finding titles, the domain.
3. Acknowledge button → `scans:acknowledge` mutation. Cancels the 60 s escalation.
4. Live counters: "targeted 4 times this month."
5. If time allows: precision/recall from the `scans` table, so the demo can show eval results live.

## Don't wait for Track D

The schema is specified verbatim in PRD §6.6. Build against it with seeded rows. D is shipping `recordScan` + `guardianFeed` first specifically to unblock you.

## Design

This gets projected. Optimize for **legibility from across a room**, not density. One glance should answer: is something wrong right now, and how bad?

Verdict colors carry meaning, so they can't be the only channel — pair each with its glyph (⛔ / ⚠️ / ✅) and a text label. Some judges are colorblind, and projectors mangle reds.

## The framing that keeps this from being creepy

Guardian mode is a **two-sided consented safety net**, not monitoring. `consentGivenAt` is required in the schema. The protected user always sees exactly what the guardian sees — build that view too, even if it's a single read-only screen. Without it this is spyware with a nice UI, and a judge will say so.

Show finding titles and the domain. Never render raw page text, email bodies, or clipboard contents — they never leave the user's machine, so they aren't in the table at all.

## Done when

- [ ] Two windows side by side: a `recordScan` in one appears in the other in <2 s, unprompted
- [ ] Acknowledge round-trips and visibly clears the alert
- [ ] Legible on a projector from 15 feet
- [ ] Empty state doesn't look broken (it's what judges see first)
- [ ] The protected user's own view exists

## Suggested skills

`frontend-design` — this is the one screen anyone actually *sees*, and generic dashboard styling will undercut a pitch about protecting a real person. `/browse` to verify the live-update behavior end to end rather than trusting it renders.
