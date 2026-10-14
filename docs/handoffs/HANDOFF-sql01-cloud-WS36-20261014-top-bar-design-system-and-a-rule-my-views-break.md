# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (modules on top: already yours; the house design system; and a rule in it that nine of my views break)

**Addendum to `HANDOFF-sql01-cloud-WS36-20261014-shape-decided-and-the-window-defect.md`, same day. Carries Dada's
layout instruction, three measured corrections to the 13 Oct draft, the design system you must build to, and one
finding of my own that is a conflict between his house rule and the views I built this morning.
`PSA_BIZBOX_WRITE_ODBC` stays unset.**

---

## 1. "Modules on top" — you have already built it. Do not rework it.

Dada, shown the 13 Oct Stock Requisition draft, verbatim:

> **"i want it like this modules on top to fit the build for the PSA"**

That is the whole instruction: **the module list moves off the draft's left rail onto a top bar**, so the screen fits
the desk's existing chrome.

**Checked before passing it on, and it costs you nothing:** `procurement.py:116` already carries
`# module list is the top menu` under his earlier *"the side bar should be placed on the top"*, and `d3311d6` removed
the tabs bar. **So this confirms what you shipped rather than changing it.** It applies to the *document* screens too
— the draft drew a rail; the documents take the same top bar as the lists.

Everything else in that drawing stands on his confirmed decision: the document shape, all five BETTER items, captions
and chrome yours.

## 2. Three corrections to the drawing itself — measured, and the drawing is wrong on all three

These are Bizbox Chat's corrections to their own draft, not Dada's words. **If the module bar is built from what the
PNG shows, it ships wrong badges.**

1. **The module numbers in the drawing are wrong** — it shows 02, 05, 06, 08, 11, 14. Already sent to you in full
   this morning; the short version is **Purchase Requisitions is MM03 (there is no MM05 at all)**, *11 Issuances* is
   two modules **MM07 Stock** and **MM09 Expense** (MM11 is Quantity Adjustments), and **Physical Count is MM12**
   (MM14 is Allotment and Obligations). A top bar fits more, and the procurement-side set in order is:
   **02 Items and Services · 03 Purchase Requisitions · 04 Purchase Orders · 06 Stock Requisitions · 07 Stock
   Issuances · 08 Expense Requisitions · 09 Expense Issuances · 12 Physical Counts · 20 Delivery/Receiving.**
2. **The Center picker must not be built.** No Centre dimension exists, and the column behind it points at the entity
   master that holds patient names. **The header pickers that exist are two** — *Issuing department*
   (`FK_mscWarehouseSRC`) and *Requesting department* (`FK_mscWarehouseDST`) — plus the date. The drawing shows
   *Issuing Department* and *Warehouse (from)* as separate fields, **which is one field drawn twice.**
3. **The drawing uses an emoji on the Add button.** The design system forbids it outright. **Checked in your tree:
   no emoji anywhere in `psaspine/web/` — this is a defect in the drawing, not in your code.** Keep it that way:
   inline stroke SVG at 16px, or no glyph.

## 3. The house design system — build the chrome from it, not from the draft

**PMC Vitals Console**, Dada's own and the only one on the account: `https://claude.ai/artifact/M6C4r6FT5B2CzzgWzdyNGB`
**Read `project/README.md` and `project/tokens.json`, not the rendered page.** I have read both; what follows is from
them, with two traps I measured that will bite if you work from a summary.

**What it decides for these screens:**

- **Top bar in `chrome.deep` `#0E1520`** — identical in both themes by design; the chrome is the constant.
- **`accent.primary` (Grape) owns selection and nothing else does.** The active-item mark is a **3×20px grape tick**
  appearing "in exactly two places: the rail and the cards". **For a top bar, rotating it to 20×3 under the active
  item is Bizbox Chat's reading, not the system's text** — flagged as inferred, and it is a reasonable one.
- **White `surface` cards on `canvas` `#F1F4F8`, one shadow only (`shadow-card`).** **No glass, frosting,
  translucency or blur anywhere, and none may be added.** Depth is two flat chrome surfaces 1.06:1 apart plus a 1px
  hairline.
- **Every numeric column in `mono` (Consolas), right-aligned, at `table-numeric` 13px.** This is called out as
  load-bearing: proportional digits make a column of pesos unreadable; monospaced digits line up the decimal point
  for free. **If a number sits in a column, it is mono.** That covers Quantity, Served, Unit Price, Total on every
  document grid.
- **Uppercase with letter-spacing is a signal, not a style** — readout labels, section labels and table column
  headers only. Nothing else.
- **Contrast measured, never eyeballed.** `series.6` Bronze is **fill only, never text** (3.58:1). `rule` and
  `gridline` are deliberately sub-threshold and **nothing may be encoded by them alone**.
- **No icon larger than 16px anywhere.**

**Trap 1 — points against pixels.** The README gives the source spec in **points** because it was authored for Power
BI: `page-title` 20pt, `readout-figure` 30pt. `tokens.json` gives the web values in **px**: `page-title` **27px**,
`readout-figure` **40px**. **Building a web page from the pt numbers gives you a visibly undersized screen.** Use the
px from `tokens.json`; the README says so explicitly.

**Trap 2 — the accent is not one hex.** `accent.primary` is **`#6D3BD1` light and `#A98BFF` dark**, and `canvas`,
`surface`, `ink`, `ink.muted`, `rule`, `gridline` and both accents all swap by theme. **The README forbids
hard-coding a hex into a page** precisely because a literal will be wrong in one theme. Take the CSS custom
properties.

**And two of its writing rules that bear on what I hand you:**

- **"Never ship a system name to a department head."** My view columns are not labels — `TrxKey`, `WarehouseSrc`,
  `WarehouseDst`, `ItemCode`, `QtyServed` are column names. On screen they are *Issuing department*, *Requesting
  department*, *Item*, *Served*. The system notes 450 abbreviations were removed from one report in a single pass.
- **"Label every figure MEASURED or INFERRED."** Which is how this handoff is written.

## 4. The finding: a rule in his own design system that nine of my views break

**"Never filter a flag out. Deleted, cancelled and void rows are *counted and shown*, never silently excluded. A
total that quietly drops 151 deleted claims is a wrong total."**

**My document views filter `WHERE ISNULL(deleteflag, 0) = 0`.** Measured, what that hides:

| Family | Rows | Deleted, hidden | Cancelled |
|---|---|---|---|
| `iwWhreqinv` stock requisition | 1,101 | **35** | 39 |
| `iwReqinv` expense requisition | 1,232 | **28** | 32 |
| `iwPRinv` purchase requisition | 656 | **16** | 14 |
| `iwWhinv` stock issuance | 1,007 | **19** | 6 |
| `iwIssinv` expense issuance | 1,089 | **5** | 12 |
| `iwPhentinv` physical count | 104 | **5** | 7 |
| `iwPOinv` purchase order | 849 | **23** | 18 |
| `iwApinv` receiving | 1,076 | **34** | 53 |
| | | **165 total** | |

**165 documents.** The rule's own example is 151.

**Cancelled rows are fine** — the views expose `Status = 'Cancelled'`, so those are counted and shown as the rule
asks. **It is `deleteflag` that silently excludes.**

**And the mirror does not rescue it.** A row that leaves the view is kept with `present = 0` — currently 6 purchase
orders, 15 invoices, 46 PO lines, 13 stock rows — but `bizbox.py:389` appends **`AND present = 1`** to every list
query, so they are hidden from every screen. Kept for audit, shown nowhere.

**My recommendation, and it is the same shape as this morning's 404 fix: expose the flag, drop the filter.** Add
`IsDeleted` to the document views, stop filtering on it, and let the desk show a deleted document **marked** rather
than absent. That keeps the filter out of the question "does this exist" — which is exactly the mistake that produced
238 unreachable item pages — and satisfies his house rule.

**One distinction worth keeping, because it stops the fix going too far:** `present = 0` means *the row left the
view*, which covers both "BizBox flagged it deleted" and "the row vanished from the source entirely". **Only the
first should be shown and marked.** Exposing `IsDeleted` separates them; showing every `present = 0` row would
resurrect things that no longer exist anywhere.

**I have not applied this.** It changes what the live lists show — 23 deleted purchase orders and 34 deleted
receiving documents would appear — and that is a display decision on a production desk, so it is Dada's, like the
73 negative balances and the desk restart. **Flagged once, with the measurement, and left with him.**

## 5. Unchanged and still outstanding

Everything in §6 of the previous handoff: `is_active` / `is_inventory` on `ext_product` first, then `trx_key` on
`ext_purchase_order` and `ext_invoice`, the three price columns if wanted, and the twelve document mirror tables.
One port; I add every map line the day it lands.
