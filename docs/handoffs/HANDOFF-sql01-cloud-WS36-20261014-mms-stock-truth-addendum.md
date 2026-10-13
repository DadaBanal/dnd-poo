# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## Addendum to the MMS brief: `actualqty` is the outlier, not the buckets. And the answer to their one question.

**Supersedes nothing.** It **corrects §5.1** of
`docs/bizbox-mms-design-brief-20261014.md`, which stands otherwise and is **unedited** — still
sha256 `0b3072d1…48cd005`, re-verified in this commit, so `bb96800` holds.

**From:** SQL01, relaying the Bizbox Chat session
**Carries:** `docs/bizbox-mms-stock-truth-addendum-20261014.md` — theirs, verbatim, 133 lines,
sha256 `f8bb3d72…915111`, which **matches the hash they stated before I copied it**.

---

## 1. What they corrected, in their own framing

Their §5.1 told you to compute the stock position from the ledger **without having proved the
ledger can produce one.** They then measured that gap, and it reversed the direction of the defect.

Three candidate figures exist per item+warehouse pair: stored `iwWareitem.actualqty`; the bucket
arithmetic on the same row; and `SUM(qtyin) − SUM(qtyout)` from `iwItemLedger` grouped by
`FK_iwItems` + `FK_mscWarehouse`. Across **5,681 pairs** where any of the three is non-zero:

| Agreement | Pairs | Share |
|---|---|---|
| ledger == buckets | 4,458 | **78.5%** |
| `actualqty` == buckets | 1,750 | 30.8% |
| `actualqty` == ledger | 1,893 | 33.3% |
| all three agree | 1,711 | 30.1% |
| none agree | 1,002 | 17.6% |

**The ledger and the buckets are two broadly consistent views of the same history. The stored
`actualqty` — the number every BizBox screen shows — agrees with neither about two thirds of the
time.** And it is not one correctable offset: on the eight largest stock rows the ledger and buckets
agree exactly while `actualqty` does not, and the direction varies — one item stored higher than its
history supports, another lower.

Three explanations they ruled out, each measured: **cancelled rows** (610 of 227,084; they summed
the table both counting and excluding them and every figure above is identical to the digit),
**staleness** (of 4,351 stock-holding pairs with history, **zero** last moved over a year ago), and
**no history to compare against** (only **7** stock-holding pairs have no ledger row at all).

### What they say they got wrong, under their own name, and it matters for how you read §5.1

- **The direction.** §5.1 framed the buckets as the figure liable to drift. Wrong — the buckets
  track the ledger 78.5% of the time; `actualqty` is what departs from both.
- **The denominators are not comparable and nobody should line them up.** §5.1's *2,617 of 4,358
  (60.1%)* counts `iwWareitem` **rows holding stock**. The addendum's *5,681* counts
  **item+warehouse pairs where any of the three is non-zero**, which also catches pairs with ledger
  movement but no stored stock. Neither figure is wrong; they answer different questions. **Do not
  quote one against the other.**
- **§5.1's instruction stands and is now evidenced rather than asserted:** one derived position
  computed from the ledger, never a maintained bucket that can drift from it.

---

## 2. Their one question, answered — and the answer is "none of the three"

They asked which figure the 084 stock view reads, and said plainly that they cannot see 084: no
local checkout on this host and the GitHub routes here are unauthenticated. **That is cannot-see,
not not-there**, and they were right to refuse to assert. The check belonged to whoever can read the
schema. **SQL01 can, and did.**

**MEASURED, 14 Oct 2026, with controls both ways:**

| Probe | Result |
|---|---|
| `psa.vw_stock_on_hand` | **absent** |
| `psa.vw_item_ledger` | **absent** |
| `psa.vw_receiving_line` | **absent** |
| `D:\psa\bizbox-map.json` objects wired today | `invoice`, `lookup`, `po_line`, `product`, `purchase_order` |
| `stock` / `movement` / `rr_line` in that map | **not wired** |
| control, must be absent — `psa.vw_zzz_nope` | absent ✔ |
| control, must exist — `psa.vw_lookup` | EXISTS ✔ |
| control, must exist — `dbo.iwWareitem` | EXISTS ✔ |

**So 084 reads nothing yet.** WS36 built the containers — `ext_stock`, `ext_movement`,
`ext_rr_line` — and the sample map names `psa.vw_stock_on_hand`, `psa.vw_item_ledger` and
`psa.vw_receiving_line` as their sources. **Those three views are SQL01's to build and do not
exist.** The map is unwired, so no desk page is showing a stock number from any of the three.

**The choice of figure is therefore unmade, and it lands on SQL01, not on WS36.** Their addendum
arrived before anything was baked in, which is the whole value of it.

### It also needs no change to what WS36 shipped

`ext_stock` takes `quantity`, `unit_cost`, `as_of`; `ext_movement` takes `qty_in`, `qty_out`,
`balance`, `unit_cost`. A ledger-derived position fills all of those from one source —
`iwItemLedger` carries `lotno`, `expdate` and `purcprice` **on the row**, which is why the ledger
route is strictly better than the other two: it is correct by construction *and* it is the only one
of the three that can also carry lot, expiry and cost, answering the brief's §5.2, §5.3 and §5.4
gaps from one place instead of three.

**SQL01's intent, for Dada's go, not WS36's:** build `psa.vw_stock_on_hand` off the ledger, not off
`actualqty`. Creating a view is additive and read-only. **Wiring it into the map is the moment the
desk starts showing it to Procurement**, so the wiring waits on Dada's word, not on this handoff.

---

## 3. The trap, which SQL01 inherits when it builds these views

Worth carrying because it produces a confident wrong answer rather than an error.

Their first run picked the ledger's warehouse key **by pattern-matching column names and matched
`FK_mscBranches` before `FK_mscWarehouse`.** Joining branch against warehouse matched nothing, every
ledger net came back `0.00`, and the output read as a clean, alarming **"0.0% agreement"** — entirely
a method artefact. **The tell was that every ledger value was exactly zero, which is not what
disagreement looks like.**

`iwItemLedger` carries **both** `FK_mscBranches` and `FK_mscWarehouse`; the warehouse key is the
second. **Name the column; never match a pattern.** They caught it themselves and the 0% figure
never left their session.

---

## 4. Nothing else changes

- The brief is **unedited** and still governs. Rule 0 — same tree, same screens, same steps, same
  words — is untouched by this.
- **Both collisions from the 14 Oct handoff remain open and remain Dada's**, and Bizbox Chat has
  explicitly declined to resolve either: they confirm the "modern design as rendering vs Rule 0 as
  information architecture" reading is a reasonable *reading* with nothing measured that settles it,
  and they confirm SQL01's relay of build rules 1–3 as *what not to foreclose* rather than a licence
  to write.
- **This addendum needs no write either.** The ledger derivation is a read.
  `PSA_BIZBOX_WRITE_ODBC` stays unset.

**Changed on any host: nothing.** Read-only throughout, both sessions. They hold
`scripts/Measure-BizBoxMMS-9_truth-20261014.py` and `-10_threeway-20261014.py`, each ending in a
control that must fail, and state they are running nothing further in MMS.
