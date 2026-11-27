# EV Shortlist — brand and design decisions (owner: UX/design chat)

> Migrated from the former claude.ai Project doc `claude/brand-design-decisions.md` on 26 Nov 2026 (Decision 089). This repo file (`docs/design/brand-design-decisions.md`) and `docs/design/` are the source of truth from now on; the historical `claude.ai` artifact links below are not reachable from Antigravity.

Other chats: read this, don't edit it. Send requests to the coordinator's INBOX (`workstreams/WS0/INBOX.md`) for UX.

**Design system (source of truth in repo):** mirrored for builders at https://github.com/zkMenno/EV-Shortlist/tree/main/docs/design (start with `docs/design/SOURCE.md`; historical Claude artifact https://claude.ai/artifact/EiqvMW5NcFgxFq6c5YHuPP). Class prefix `evs-`.
**Design board (historical visual companion: logo sheet, elements, icons, textures, illustrations, phone + desktop mockups):** https://claude.ai/artifact/7oaYaK26i6xQBogFuuctMp. It installs the system's tokens; the system and the board link to each other. When one changes, update the other (Menno, 2026-11-15).
**Architecture design file (historical system map, data model, tech board):** https://claude.ai/artifact/9wDnjtwg7iFcFtfSAoATKH

## Solarpunk x EV round: Menno's picks (2026-11-15)
- **Illustration direction: B + C combined.** C's layered hills and a winding road that narrows into the distance (it echoes the tick-V logo), drawn in B's picture-book ink line. Menno liked all three directions (A Play mat, B Picture-book map, C Paper cutout).
- **Home headline: "Used EVs got good."**
- **Colour: rich greens on the home hero only, soft pale tints everywhere else.**
- **Illustration kit approved and rolled in (design system v6, board artboard "Illustrations: solarpunk").** Village and **city** scenes (Menno asked for a solarpunk city next to the village/rural one): village by default, city for visitors who answer "city" in the profile picker or on kerbside-charging pages. 21 elements incl. house with solar roof, wallbox, public and lamp-post chargers, turbine, solar field, trees, EV, EV van, tram, bike, apartments with roof gardens, row houses, road pieces. Every asset has day and night versions.
- **Night drive: deep green hills** (Menno's pick over blue-green).
- 10 illustration-only colour tokens: hill-1..3 (soft), hill-rich-1..3, leaf, forest, solar-gold (#F0BE45, a deeper sunflower, not orange), solar-panel. Never text or states.
- Home hero: "Used EVs got good." + step 1 of 3 (country), rich village scene with a small taped shortlist note. No numbers inside illustrations.
- Renders: https://github.com/zkMenno/EV-Shortlist/tree/main/docs/design/explorations/solarpunk-r1 · SVGs: docs/design/assets/Illustrations/

## Brief for this round (Menno, 2026-11-15)
- Go more solarpunk. The site should evoke optimism: used EVs are now genuinely good at an approachable price (not super cheap yet, but within reach). Menno's "350–500 km for €10–12k (e.g. a used Kia Niro EV)" was an illustration of that feeling, not a slogan to print. The design and copy carry the mood; any specific price or range shown on the site still comes from our data. Charging is nothing to worry about any more. The solarpunk future is being realised and you can be part of it; this is a tool that helps accelerate the EV transition.
- Inspiration: classic kids' play mats with roads; road-trip vibes with nature; exploring in silence without polluting, on electricity, even from your own roof solar.
- Tone: Solarpunk x EV — optimistic, future-forward, sensible, sustainable, but approachable for people who don't care about sustainability or tech.

## Name and brand
- Working title **EV Shortlist** (repo Decision 018). Tagline: **"Compare EVs. Make your shortlist."**
- **Working logo (Menno, 2026-11-15, iterate once the name is final):** "EV" in one sky-blue shape, the V a tick that winds and narrows like a road towards a sunflower sun; "Shortlist" in Bitter ExtraBold, ink. Tick weight = the Bitter card he picked (stem 19 units). App icon: EV + tick on an ink tile with generous padding (logo within the middle 55%).
- Logo history (rejected): tick-road mark; tomato EV road-sign plate with road out of the t; traffic sign with tick-V; Overpass and 10+ other fonts; retro decal, 70s poster, sticker, bouncy, marker, deco; number plate, Type 2 face, pin-tick, list-to-road. Liked: V as a tick, the winding/perspective tick, the traffic-sign idea. Disliked: orange, Overpass, anything generic. Still "generic but fine for now". Logo round 2 once the name is final, from Menno's references.

## Decided (Menno)
- Audience 30–70, first-time buyers plus EV veterans. Legibility first, colour-blind safe.
- Positioning: approachable, rooted in reality; honest monthly cost vs petrol; solarpunk optimism turned up (this round).
- Visual direction: road trip / holiday map; texture and illustrations in the margins; data stays clean.
- Voice: knowledgeable neighbour. Themes: light ("Day trip") and dark ("Night drive").
- Palette Ink and sky (no orange): ink #16233A, sky #3B78AE, action #2F679C, sunflower #FFD166, tint #E8F1F9, link #2B5F91, danger berry #A1224A; meadow/sea + the illustration tokens above for illustrations only.
- Type: Bitter (logo, headings), Atkinson Hyperlegible (reading, numbers), Patrick Hand (notes only). Self-hosted OFL.
- **Breathing room rule:** backgrounds, tiles, chips and buttons never touch or crowd their text (≥ half the cap height of padding; icon logo within the middle 55%).
- More texture: paper grain, contours, map grid, land hatching, halftone sun, folds, route divider (v5).
- Range-as-route signature feature (brief in WS2 INBOX; Decisions 012/013 respected).

## Decided by the UX chat (reversible)
- One shortlist (no favourites/hearts), up to 12 cars; ShortlistTray replaces the compare tray; Compare takes up to 4. Sent to WS0 to log.
- Components: Logo, Hero, ShortlistButton, ShortlistTray, ShortlistNote, Header, Button, Chip, LegendTooltip, DetailSwitch, CarCard, ExploreTable, RangeRoute, Field, SourceList, EmptyState, Texture. Asset groups: Logo, Symbols (35 icons), Textures, Illustrations (48 SVGs).

## Next (UX chat)
1. Variant finder: the "differences only" highlight for Compare (only that ships at launch, Decision 051); clue box and finder later.
2. Visual audit of EV-media logos when Chrome is available.
3. Logo round 2 once the name is final.
