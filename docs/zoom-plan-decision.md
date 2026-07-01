# Zoom plan decision — what nodeLive actually needs

Handover note for the manager conversation. Answers: *do we need a paid Zoom
plan / Webinar license, and which one?* Backed by Zoom's own docs.

**As of July 2026.** Capabilities are confirmed against Zoom's KB/developer
docs. **Prices are approximate and change often** — verify on the live pricing
page or a sales quote before committing budget. The exact Webinars-1000 price
could not be verified (Zoom routes that tier through Sales).

---

## Bottom line

Our required feature set is: **view-only attendees at 500–1000 per class +
cloud recording + attendance Reports API.** The minimum combination that covers
all three:

> **A paid base plan (Zoom Workplace *Pro* is enough — or *Education* if we
> qualify) + the *Zoom Webinars* add-on at the 1,000-attendee tier.**

Nothing more is required. Our existing **Zoom Meeting SDK works with webinars** —
no rebuild, and **no separate Video SDK license**.

---

## The three requirements, verified

| # | Requirement | What unlocks it | Min tier | Source |
|---|-------------|-----------------|----------|--------|
| 1 | View-only attendees (500–1000) | **Zoom Webinars add-on** (1,000 tier) | paid base + add-on | KB0062404 |
| 2 | Cloud recording | any **paid** plan (not free Basic) | Pro | KB0067670 |
| 3 | Reports / Dashboard API | any **paid** plan | Pro | KB0060623 |

**1. View-only → Webinars.** A regular Zoom *Meeting* cannot force attendees
into view-only; a *Webinar* does by design (attendees can't broadcast
video/audio or screen-share unless promoted to panelist), scaling by capacity
tier up to 100k. For a 500–1000 peak we need the **1,000-attendee tier**.
→ https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062404

**2. Cloud recording** is unavailable on free Basic; **Pro is enough**.
→ https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0067670

**3. Reports API** needs a paid account. The claim that it requires
*Business-or-higher* was **refuted** during verification — **Pro unlocks it**.
(Matches our `CLAUDE.md`: Reports API is "paid-only.")
→ https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060623

---

## Why the Meeting SDK is fine (no rebuild)

The **Meeting SDK renders webinars** and follows the account's license model, so
moving to a webinar is a backend change (create a webinar instead of a meeting),
**not** a frontend rewrite. The **Video SDK** is a separate, usage-priced product
with its own custom UI — we do **not** need it.
→ https://developers.zoom.us/docs/meeting-sdk/
→ https://devforum.zoom.us/t/do-you-need-to-buy-a-videosdk-license-if-you-are-only-using-meeting-sdk/83649

## Cheaper base: Zoom for Education

If nodeLive is tied to an accredited institution, **Zoom for Education** is a
cheaper base than commercial Pro/Business and still supports the Webinars
add-on + recording + reporting.
→ https://zoom.us/pricing/education

---

## Pricing (treat as rough — verify)

Adversarial fact-checking **killed** the specific dollar figures we found, so
take these as ballpark only:

- **Pro base:** ~$13–16/user/mo.
- **Webinars 1,000 add-on:** historically low-hundreds of $/month, but the
  1,000+ tiers now typically require a **Zoom Sales quote** — no reliable public
  number.
- Live pricing: https://zoom.us/pricing · https://zoom.us/pricing/events

**Do NOT assume:** that Reports API needs Business (Pro is enough); that any
single quoted webinar price is current.

---

## Fallback if "view-only" is dropped

If students don't need to be *forced* view-only:

> **Pro/Business base + a "Large Meeting" add-on (1,000 capacity).**

Still gives cloud recording + Reports API + 1,000 concurrent — but as an
equal-participant Meeting (what we run today, where students *can* unmute/share).
**Materially cheaper** than the Webinars add-on.

---

## The decision, in one line

**Is forced view-only worth the Webinars-1000 add-on, or is a Large-Meeting
add-on (cheaper, students can unmute/share) acceptable?** Cloud recording +
attendance Reports API are covered by the paid base either way.

---

## Sources

- Meeting & webinar comparison (view-only) — https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062404
- Cloud recording availability — https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0067670
- Reporting / paid-plan requirement — https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060623
- Meeting SDK docs — https://developers.zoom.us/docs/meeting-sdk/
- Meeting SDK vs Video SDK licensing (devforum) — https://devforum.zoom.us/t/do-you-need-to-buy-a-videosdk-license-if-you-are-only-using-meeting-sdk/83649
- Zoom pricing — https://zoom.us/pricing
- Zoom Events/Webinars pricing — https://zoom.us/pricing/events
- Zoom for Education — https://zoom.us/pricing/education
