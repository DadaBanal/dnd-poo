# HANDOFF — SQL01 → Cloud Build, WS36, 15 Oct 2026 (design and accessibility review of `7d037f5`, measured against PMC Vitals Console; disk and efficiency of the host)

**Dada: *"do a design check on the current build and let me know what needs to be changed … disk usage and
efficiency."* Reviewed on this side under `design:design-critique` and `design:accessibility-review`, on a throwaway
desk at `7d037f5` with seeded data, in the dark (Console) theme. Where a finding says MEASURED it was read from
computed styles or the accessibility tree, not from a screenshot. Nothing on the host changed.**

## 1. What holds — measured, so you know what not to touch

| Rule in `tokens.json` / README | Measured on `/procurement` |
|---|---|
| Top bar and canvas in `chrome.deep` `#0E1520` | header `rgb(14,21,32)`, body `rgb(14,21,32)` ✓ |
| `sans` Segoe UI, `mono` Consolas | body Segoe UI; every numeric cell Consolas ✓ |
| Numeric columns `table-numeric` 13px, right-aligned | six samples, all 13px, all right ✓ |
| `page-title` 27px / 600 | h1 27px, weight 600 ✓ |
| Uppercase + letter-spacing on section labels and column headers only | section labels uppercase, 0.72px ✓ |
| No icon over 16px | 0 SVGs over 16px ✓ |
| Movement words with the code beside | *Charged CA · 3*, *Counted PC · 3*, … ✓ |
| Window list only what the mirror holds | *Last 7 days* ✓ |
| Lists are lists | Purchase Orders: no tick boxes, no bulk bar, no cells-edited bar ✓ |

## 2. Design critique

### Overall impression
The Procurement pages now read as the console they were meant to be: dark bezel, white-on-chrome readouts in mono,
cards that sit flat. The biggest remaining gap is not on these pages — it is the **first screen every user meets**,
and the pages that appear when something goes wrong.

### Usability

| Finding | Severity | Recommendation |
|---|---|---|
| **The login screen is the old desk.** Old palette, not the Vitals tokens; and its copy is the emergency path's — *"Break-glass sign in. For the on-call rota, when the WAN is down. Every use is audited."* — shown to every ordinary user. Dada: *"we can do better on the login screen."* | 🔴 Critical | Build it to the tokens like the Procurement pages. Plain *Sign in* for everyone; the break-glass wording only on the break-glass route or after a failed SSO. |
| **Error pages are outside the design system.** `/procurement` for a member without rights renders a bare `403 Forbidden` in browser-default serif with no chrome; a missing ticket renders a bare `404 Not Found`. | 🟡 Moderate | One error template in the desk's chrome: the same top bar, the sentence that is already there (*Your security role does not let you see procurement. Ask your service manager.*), and a way back. |
| **The Movements paragraph is still there** — three lines of explanation under the chips (*Every movement of stock BizBox recorded inside the window…*). Part 102: *the paragraph goes; the dated sync bar stays.* | 🟢 Minor | Remove; the chips and the window picker say it. If one sentence must stay, it is *the desk holds 10 days*, as a footnote. |
| **Two chip rows both begin with `All · 17`** — the bucket row and the code row each carry an All chip. | 🟢 Minor | One *All*; the code row filters within the chosen bucket. |
| **At 800px the primary button clips** — *+ New ticket* is cut to *+ New* by the *break-glass* label beside it. | 🟢 Minor | Let the account label truncate before the primary action does. |
| **Purchase Orders header row wraps** — TOTAL, LINES, WAITING drop to a second baseline at 800px. | 🟢 Minor | Fixed column widths or `white-space: nowrap` on the header. |

### Consistency — the measured breaks

| Element | Issue | Recommendation |
|---|---|---|
| **Blur** | MEASURED: **8 elements on `/procurement` carry `backdrop-filter` or a `blur()` filter.** The README: *"There is no glass, frosting, translucency or blur anywhere in this system, and none may be added."* Your handoff said no glass or blur; the computed styles say otherwise — most likely the chat bar / readout strip and the hover panel. | Remove every `backdrop-filter` and `filter: blur` under the Procurement body class. Depth is two flat chrome surfaces and a 1px `chrome.rule` hairline. |
| **Shadows** | MEASURED: **four distinct `box-shadow` values** — `shadow-card` (`0 2px 6px rgba(22,32,43,.10)`, correct); a 3px grape inset (the active tick, fine); **a glow `rgba(110,140,255,.45) 0 0 16px` with a white inset ring**; and **a drop `rgba(0,0,0,.22) 0 12px 32px`.** The README: *"One shadow. `shadow-card`, and only that."* | Keep `shadow-card` and the tick. Replace the glow with the grape tick or a `chrome.rule` outline; replace the 12/32 drop (the hover panel or the strip) with `chrome.elevated` + hairline. |
| **Accent misuse** | *break-glass* in the top bar is set in Ember (`accent.secondary`), which the system reserves for comparison series; the *BETTER* badge on the requisition form is Grape (`accent.primary`), which owns selection only. | *break-glass* in `status.warning`; *BETTER* in `ink.muted` text or a `surface.sunken` pill. |

One correction of my own in this area: **the system has no rule against gradients** (Dada, 15 Oct: *"there is no flat
accent no gradient rule"*). MEASURED: 0 gradient buttons on the Procurement pages anyway. What it forbids is blur,
glass, translucency and a second shadow — and those are the two breaks above.

### What works well
- The Overview reads at a glance: six readouts, the warehouse bars in `accent.primary`, the movement ledger with the
  word first and the code second.
- The stock requisition form is the draft's shape with every BETTER item on it — on hand at source per row, *Unit
  price (BizBox purchase price) · at save*, eight rows, nothing created from the screen — and labelled honestly.
- The ticket page's respond/resolve readouts (*Met in 25m · Met in 2h 45m*) are exactly the console's vitals idea.

## 3. Accessibility audit — WCAG 2.1 AA

**Issues found: 6 | Critical: 1 | Major: 2 | Minor: 3**

| # | Issue | Criterion | Severity | Recommendation |
|---|---|---|---|---|
| 1 | **Login fields have no accessible name** — both render as unnamed `textbox` in the accessibility tree. | 3.3.2 Labels, 4.1.2 Name/Role/Value | 🔴 Critical | `<label for>` on both, or `aria-label`. This is the first form every user meets. |
| 2 | **Stock requisition: the three required header pickers are unnamed** — MEASURED: 29 controls, 25 with an accessible name; the 4 without are `warehouse_src`, `warehouse_dst`, `doc_date` and the global search. The visible labels exist but are not associated. | 3.3.2, 4.1.2 | 🟡 Major | `label[for]` → the select/input `id`. The 25 line controls are named — same treatment. |
| 3 | **Global search box unnamed** (placeholder only: *Go to a page, open PMC-000123, or search this board…*). | 3.3.2 | 🟢 Minor | `aria-label="Search"`. |
| 4 | **Four controls under 24px** on the requisition form. | 2.5.5 (AAA) / 2.5.8 (2.2 AA) | 🟢 Minor | 24px minimum hit area; advisory under 2.1 AA. |
| 5 | **Error pages have no landmarks and no chrome** (see §2). | 1.3.1 | 🟡 Major | The one error template fixes both. |
| 6 | **Contrast** — not re-measured here: every pairing in `tokens.json` carries a measured ratio and the pages use the tokens (MEASURED). The one pairing to confirm is the *BETTER* badge's grape on its own fill, which is not a listed pairing. | 1.4.3 | 🟢 Minor | Use a listed pairing. |

**Keyboard and structure, measured:** a `:focus-visible` rule exists in the CSS ✓; `<main>`, `<nav>`, `<header>`
landmarks present ✓; `lang="en"` ✓; page titles distinct per page ✓; 0 images, so no alt gaps on these pages.

### Priority fixes
1. **The login screen** — design and the two unnamed fields in one change; it is the first impression and the first
   WCAG failure.
2. **Blur and the two extra shadows** — the only measured breaks of the house rules on the rebuilt pages.
3. **Name the three required pickers** on every document form (the same template serves six kinds).
4. The error template; then the four minors.

## 4. Disk and efficiency on the host — measured 15 Oct

| | |
|---|---|
| Drives | C: 926.6 GB free · D: 832.3 GB free · T: 3.6 TB free. Nothing is near a limit. |
| `PMC_PSA` | **200 MB data, 136 MB log, SIMPLE recovery.** Largest table `ext_movement` 19 MB / 36,097 rows. Small and fine. |
| The hourly read | touches **88,008 mirror rows** per run across 22 objects; last run exit 0. Not a load worth optimising on this instance. |
| `D:\Backups` | 51.2 GB in 39,305 files. **Of that, my COPY_ONLY backups: 13 files, 4.95 GB** — seven taken on 13–14 Oct, one per schema step, 28–137 MB each. The pre-083/084/085 ones (130 MB class) are superseded by every later one. |
| `D:\psa` (attachments, map, backups of the map) | 530 files, 280 MB. |
| **Dead rows I left in the mirror** | MEASURED: **2,396 header rows with `present = 0`** across the six document mirrors — the DocNo-keyed rows from the first 087 read, every one a short numeric key that will never return (stock_req 253, expense_req 264, purchase_req 643, stock_issuance 520, expense_issuance 636, physical_count 80). Control: 0 on the line tables, keyed by `LineID` from the start. The desk hides them (`present = 1` on every list) but they are carried on every read. |

**Two housekeeping items, both deletes, so both are Dada's word:** (a) purge the 2,396 dead header rows — one
`DELETE … WHERE present = 0 AND LEN(ext_ref) <= 4` per table, gated; (b) delete the eight superseded COPY_ONLY
backups from 13–14 Oct and keep `pre088` — recovers about 1 GB. Neither is urgent; D: has 832 GB free.

## 5. Skills

Rendered to Dada as an install card: **frontend-design** (Anthropic — the one he said *"enable them"* to on 14 Oct;
still off), **Axe Accessibility** (Deque — scan → remediate → verify with keyboard tests; measured contrast, which is
the system's own rule), and **ux-ui-audit**. The `design` plugin's critique and accessibility skills are enabled here
and were used for this review. In your cloud session, per your §6 of 14 Oct, only `artifact-design` fires.

The throwaway desk is stopped. Screenshots are in the session record; none committed.
