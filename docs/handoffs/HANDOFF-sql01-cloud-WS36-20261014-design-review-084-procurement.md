# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## Design review of the Procurement area as shipped in `3fb7453` — the 084 stock, movements and item cards

**Dada's ruling, 14 Oct, on where the design review happens:** *"review the design on this side"* — the
`design` plugin is in SQL01's session and not in WS36's, so the review is done here against what you
ship. This is the first one under that ruling.

**Skills that fired for this review:** `design:design-critique` and `design:accessibility-review`
(both loaded in this session; their frameworks are the structure below). `design:ux-copy` did not
fire — no copy was rewritten; the one wording finding is routed to Bizbox Chat as a vocabulary
question, not a copy decision.

**How it was reviewed:** a throwaway desk from the `3fb7453` checkout, SQLite, served on
`localhost:8086`, seeded with 6 products, 6 warehouses, 12 stock lines, 166 movements and 6 receiving
lines, signed in as a test sysadmin. **Nothing on the live desk, `PMC_PSA`, `LiveDB_PMC` or the host
was touched.** Pages reviewed: Procurement Overview, Stock on hand, Movements, Products grid, and the
item page `/procurement/product?ref=…` where the 084 cards sit. Contrast measured from computed
styles; reflow checked at 375px; keyboard focus walked.

---

## Summary

| | |
|---|---|
| **Issues found** | 7 — **1 major** (functional, same fault class as 13 Oct), 1 moderate (hierarchy), 5 minor |
| **Passes** | contrast on every measured text style, visible focus in logical order, reflow at phone width, labelled form controls on the item page |
| **What works well** | the 084 cards on the item page; the item → ticket bridge; the Overview's stock-by-warehouse bars |

---

## 1. MAJOR — movement kinds display as BizBox doctype codes, not words

**Where:** Overview "Moved in the last 7 days" chips and rows; the Movements tab chips and every row;
the item page's Movements card. Rendered as **`Ca · Ch · Dr · Ei · Pc · Ss`** and per row `Pc`, `Ch`,
`Ss`.

**Root cause, MEASURED in `psaspine/bizbox.py`:** `MOVE_WORDS` maps guessed English kinds —
`RECEIPT`, `ISSUE`, `TRANSFER_IN`, `ADJUST`, `COUNT`, `RETURN`, `CONSUME`, `SALE`, `PURCHASE` — and
**contains none of BizBox's actual doctype codes.** The brief's §3 measured the real vocabulary from
227,077 ledger rows: `CH`, `CA`, `CN`, `SS`, `PC`, `EI`, `DR`, `MP`, `QA`, `PP`, `PR`. Every real
movement misses the table and falls through to `k.capitalize()`.

**This is the 13 Oct fault again** — the category dropdown that showed numbers — in a new place:
a vocabulary guessed rather than read. The fix pattern is the same: the words come from BizBox.

**What is known from the brief's own measurements, to seed the map:**

| Code | Rows | Meaning, from the brief | Word |
|---|---|---|---|
| `CH` | 128,462 | HIS patient charging — the clinical side consuming stock | Charged |
| `SS` | 8,076 | in = out = 508,061 exactly — **transfer semantics** | Transferred |
| `PC` | 7,253 | physical count | Counted |
| `EI` | 4,363 | expense issuance | Issued |
| `DR` | 2,335 | delivery receipt | Received |
| `MP` | 315 | material production | Produced |
| `QA` | 196 | quantity adjustment | Adjusted |
| `PR` | 2 | purchase return, by document name | Returned |
| **`CA`** | 58,847 | **not stated in the brief** | — |
| **`CN`** | 17,136 | **not stated in the brief** | — |
| **`PP`** | 92 | **not stated in the brief** | — |

**`CA`, `CN` and `PP` are the second- and third-largest kinds in the ledger and nobody has named
them.** That is a BizBox question and goes to the Bizbox Chat session under the standing routing
rule, not to you. **Do not guess them.** Until they come back, the fallback should be the bare code
in a `<code>` span with a title, not a capitalised word that looks like a word.

**Function-parity note:** the ruling says where a word *is* the function the MMS term stays. These
are BizBox's internal codes, not screen words — MMS's own screens show them as document names. So
mapping them to words is correct, and the words should be MMS's document names where one exists.

---

## 2. MODERATE — the same four-line paragraph opens every Procurement tab

The instruction block (*"Everything here is read from BizBox… Nothing in BizBox changes until it is
approved and sent."*) renders above the tab bar on **every** tab. At the desk's pane height the tab
row sits at the fold; at 375px the paragraph is a full screen before any control appears.

**First impression** on any tab is the same paragraph the user just read on the previous one. The
information is right and should exist once.

**Recommendation:** show it on the Overview only, or collapse it to one line with a *"How changes
work"* disclosure. The green *"Read from BizBox 2026-10-14 09:00"* bar is the status that should sit
at the top of every tab; the paragraph is not.

---

## 3–7. MINOR

| # | Finding | Where | WCAG / principle | Fix |
|---|---|---|---|---|
| 3 | Tile accessible name concatenates number and caption: **"0purchase orders · 0 this month"** — `div.n` and `div.l` with no separator, so a screen reader reads "zero-purchase orders" | Overview, six tiles | 4.1.2 Name | a space, or `aria-label` on the `<a>` |
| 4 | Products grid: every row is a full edit form — two `<select>`s and two inputs per row, header-only label association, so a screen reader announces every option list on every row | Products tab | 3.3.2 Labels, 1.3.1 | `aria-labelledby` from the header cell + the item code per control; or edit-on-click so the grid reads as a table until a row is opened. **The edit-cells-in-a-row design is deliberate and stands; this is the accessible-name layer on it** |
| 5 | Money has no currency anywhere — `734,778.50`, `453,600.00` | Overview, Stock, item card | clarity | `₱` or `PHP` once per column caption; this is a PHP estate and Finance will read it against BizBox |
| 6 | "As of" repeated on every stock row when every row carries the same value | Stock tab, item card | visual noise | lift to the table caption when uniform; keep per row only when rows differ |
| 7 | "Remarks" column always rendered, empty on every row in the window | Movements tab | visual noise | hide the column when no row in the result carries a remark |

---

## Colour contrast — PASS

Measured from computed styles on the Procurement pages, dark theme:

| Element | Foreground | Size / weight | Ratio | Required | |
|---|---|---|---|---|---|
| body and `.muted` text | `rgb(176,184,201)` | 14px / 400 | **10.55:1** | 4.5:1 | ✅ |
| table headers `th` | `rgb(127,136,155)` | 12px / 600 | **5.90:1** | 4.5:1 | ✅ |
| table cells `td` | `rgb(238,241,248)` | 12px / 400 | **18.57:1** | 4.5:1 | ✅ |
| tabs and links | `rgb(255,255,255)` | 13.5–14px / 500–600 | **21.00:1** | 4.5:1 | ✅ |

## Keyboard — PASS

Eight presses of Tab from the item page walked the header controls in document order and the focus
ring was visible on the text-size button. No trap. Form controls on the item page carry visible
labels (Item, Name, Category, Unit, Unit cost, Why).

## Reflow at 375px — PASS

`scrollWidth` 375 = viewport, no horizontal page scroll; tables sit in `.tablewrap` with
`overflow-x: auto` and scroll within. Tab chips wrap. (Finding 2 is worst here: the paragraph fills
the first screen.)

---

## What works well

- **The 084 cards on the item page are right.** Stock on hand per warehouse with a total row,
  Movements last 30 days with in/out/balance, and *"Raise a ticket about this item"* pre-filled with
  the item — that link is the MMS → PSA bridge the whole build is for, and it is one click.
- **The Overview's stock-by-warehouse bars** give the shape of the estate at a glance, and each is a
  link into the filtered Stock tab.
- **The green sync bar** is the right status element — one line, dated, on every tab.
- **The three-way filter on Movements** (window · warehouse · item code) is the right three.

---

## Priority

1. **Finding 1** — functional, user-facing, same class as the 13 Oct fault. Map the eight known codes
   now; route `CA`/`CN`/`PP` to Bizbox Chat; fall back to a code span, not a fake word.
2. **Finding 2** — one change, every tab improves.
3. Findings 3–7 as a sweep.

**Nothing on the host changed.** The throwaway desk is stopped and its database is in the scratchpad,
not the repo. `3fb7453` is pulled; 085 is not applied; `PSA_BIZBOX_WRITE_ODBC` unset.
