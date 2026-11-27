# R-30 Five-person "normie test" plan

Overnight 2, 2026-11-15. Plan only; nothing has been run.

**The answer.** Before the private beta, five people who have never owned an EV each do four short tasks on the prototype over a free video call, thinking aloud, 30 minutes each. We record two things per task: did they finish without help, and which word or screen stopped them. Every term that stops two or more people gets a new label or tooltip before launch. Cost: €0. Menno's time: about 4 hours (recruiting, 5 calls, a 30-minute write-up). The tasks come from spec §4 "Test with normies" and the bidirectional spec's normie check; Trip fit and the Variant finder are added because they are the newest and most jargon-heavy flows.

## 1. Who

- 5 adults who don't drive an EV and haven't researched one in depth. At least 2 who would actually consider a used car in the next 2 years.
- Mix: at least 1 aged 55+, at least 1 on a phone only, at least 2 testing in Dutch (the rest in English). Optional: 1 in French, as Menno lives in France.
- Not: EV owners, developers, people from the project, or anyone who has seen the mock-ups.
- 🟡 Five is the usual small-sample rule of thumb for spotting the biggest problems; it is not enough to measure success rates. Treat the numbers as signals, not statistics.

## 2. Recruiting for free

| Route | How | Notes |
|---|---|---|
| Friends of friends | Ask 3–4 people to forward a short message (below) to someone who fits | Fastest. Exclude close friends: they are too kind |
| Local Facebook / WhatsApp groups (village, expat, Dutch-in-France) | Post the message once | Ask the group admin first |
| Family | One person at most | Useful for the 55+ slot |
| Owner forums | **Not for this test.** Owners aren't normies; save them for the private beta (launch-plan.md) | |

Thank-you: a personal thank-you and an early look at the site. No money, so no payment or tax admin.

**Recruiting message (EN; NL below).** Menno sends it himself; draft only.

> I'm building a free website that helps people choose a used electric car. I'm looking for 5 people who have *never* owned an electric car to try it for 30 minutes on a video call. No preparation, no right or wrong answers: I'm testing the website, not you. Interested? Reply with a day and time that suits you.

> Ik bouw een gratis website die mensen helpt een tweedehands elektrische auto te kiezen. Ik zoek 5 mensen die *nog nooit* een elektrische auto hebben gehad, om hem 30 minuten via een videogesprek uit te proberen. Je hoeft niets voor te bereiden en er zijn geen foute antwoorden: ik test de website, niet jou. Zin? Stuur me een dag en tijd die je uitkomt.

## 3. Setup

- **Tool:** Jitsi Meet or Google Meet (free, screen share, no account needed for the tester on Jitsi). The tester shares their own screen so we see their real device and browser.
- **Recording:** only with spoken consent at the start, saved locally, deleted after the write-up (R-04 privacy: no personal data kept beyond need). Without consent, take notes only.
- **Build:** the prototype on a public preview URL, seeded with real-looking data. Set the country to the tester's own and the detail level to **Simple** (the default).
- **Observer:** Menno alone is fine. If a second person can join, they take notes and stay silent.

## 4. Script (≈30 minutes)

**Intro (3 min).** "Thanks for helping. I'm testing the website, not you. If something is confusing, that's the website's fault and exactly what I need to know. Please think out loud: say what you're looking for, what you expect, and what surprises you. I won't help during the tasks, so I can see where the site needs to explain more. You can stop at any time. Is it OK if I record the screen and audio? I'll delete it after I've written my notes."

**Warm-up (2 min).** "Before you click anything: what do you think this site is for?" Then: "Have a quick look around for 30 seconds and tell me what you see."

**Task 1 — Find (6 min).** "You have about €15,000 to spend. You'd like an electric car that can still do 250 km on one charge in winter. Find one or two that fit." Done when: they name a car and can point to where the site shows the winter range.

**Task 2 — Compare (6 min).** "Pick two of those cars and find out which one charges faster on a road trip." Done when: they use Compare (or two model pages) and give an answer plus the reason.

**Task 3 — Understand (4 min).** "One of the cars has an 'LFP' battery. What does that mean for you as an owner?" Done when: they find the tooltip or learn page and say something like "I can charge it to 100 % every day" in their own words.

**Task 4 — Pick one of these (6 min), rotate across testers:**
- 4a Trip fit: "You live in [tester's town] and drive to [a city ~200 km away] at Christmas. Will this car make it without stopping?"
- 4b Variant finder: "You see an ad for a [model] from 2021. How do you find out whether it has a heat pump?"
- 4c Bidirectional (spec check): "Between a used VW ID.3 58 kWh and an ID.4 77 kWh, which one can power a house in Germany, and what extra box would you need?"

**Wrap-up (3 min).**
1. "On a scale of 1 to 7, how easy was this overall?"
2. "Which word or part confused you the most?"
3. "Would you use this when buying a car? Why or why not?"
4. "Anything you expected to find and didn't?"

The script in Dutch is a WS3 task (all six languages live in content/), so it isn't drafted here.

## 5. What we measure

Per tester and task, one row:

| Field | Values |
|---|---|
| tester_id | P1–P5 (no names) |
| device | desktop / phone, browser |
| language | en / nl / fr |
| task | T1, T2, T3, T4a/b/c |
| result | done unaided · done with a hint · gave up |
| time_s | rough seconds to done |
| stuck_on | exact word, label or screen where they paused >10 s or asked |
| expected | what they said they expected instead |
| quote | one short quote, no personal details |

After all five: the **stuck list** — each term or screen with the number of testers who got stuck on it.

## 6. Decision rule

- Stuck for 2+ testers → change the label, tooltip or layout before launch (a WS2 or WS3 task, glossary edit first).
- Stuck for 1 tester → log it; fix it if the fix is a glossary text change.
- Any task with 2+ "gave up" → the flow needs a redesign; send it to the coordinator's INBOX (`workstreams/WS0/INBOX.md`) for UX.
- Retest the changed terms with 2 new people (15 minutes each).

## 7. When

After the Explore, model page, Compare and glossary tooltips work on a preview URL with real seed data; before the private beta in launch-plan.md. Trip fit and the Variant finder join task 4 only once they have a working preview, otherwise rotate in 4c.

## Sources

- Spec §4 "Simple by default, nerdy on demand", the normie test line (docs/spec/master-spec-v2.md, read 2026-11-15).
- docs/spec/bidirectional-and-connectors.md, normie test line for ID.3 vs ID.4 (read 2026-11-15).
- docs/growth/launch-plan.md, private beta row (read 2026-11-15).
- research/R-04-privacy-gdpr.md for recording and data-minimisation rules.
- 🔴 No outside usability source was cited: the fetch of a usability-research article was blocked tonight, so the "five testers" rule is stated as a rule of thumb, not as a sourced figure.
