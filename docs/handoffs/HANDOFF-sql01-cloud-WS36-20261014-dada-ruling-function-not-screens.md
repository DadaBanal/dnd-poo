# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## DADA'S RULING: build how MMS **functions**, better. Not how its screens look.

**This overturns Rule 0 of `docs/bizbox-mms-design-brief-20261014.md`.** Read this before you build
anything from that brief. The brief's measurements all stand; its **Rule 0 does not.**

---

## 1. His words

Dada, to SQL01, **14 Oct 2026**, in response to being told Rule 0 was *"same tree, same screens,
same steps, same words — a department head must recognise the screen"*:

> *"no i want it built how mms functions but better"*

SQL01's reading, stated to him and acted on: **function parity, not screen parity.** Every function
MMS has, every step it takes, the same outcome at the end — built better. **How it looks is not the
constraint. What it does is.**

---

## 2. What this overturns

The brief's Rule 0 — written in good faith by the Bizbox Chat session — reads:

> *"Same tree, same screens, same steps, same words. … A department head opens the new screen and
> recognises it."*

and it lists the captions to reproduce (*Issuing Department, Warehouse, Center, Item ID, Item
Description, Unit, Quantity, Served Quantity, Unit Price, Total Amount, Generic Name, Expiry Date*,
buttons *Add / Edit Mode / Delete*, footers *Total Record(s)* and *Total Item*).

**That was an inference from his earlier words, and he has now corrected it.** The earlier utterance
it was built on was *"it should functio nsimilar to bixbox but better"* — and the operative word in
it is **function**. It was read as reaching the screen layer. It does not.

So:

| | |
|---|---|
| **Binding** | every MMS **function**, every **step**, the same **outcome** — and better |
| **Not binding** | the captions, the grid bands, the button labels, the footers, the screen tree |
| **Still binding from his 13 Oct instruction** | *"conforms to modern design load skills needed"* |

**The 083 Procurement screens you shipped are not in question.** Collision 1 from
`HANDOFF-sql01-cloud-WS36-20261014-mms-as-per-bizbox-but-better.md` **is closed**, and it closed in
favour of the modern design you already built. **Do not retro-fit BizBox captions onto them.** You
were told in that handoff not to re-architect them on the strength of the brief; that instruction is
now superseded by something stronger — there is nothing to retro-fit.

---

## 3. What "how MMS functions" actually obliges you to

This is the part that still binds, and it is the harder half. Function parity is not a lighter
requirement than screen parity — it is a stricter one, because a caption can be read off a form and
a behaviour cannot.

From the brief's own measurements, the functions that must exist and behave as MMS behaves:

- **The document chain, end to end.** Purchase Requisition → Purchase Order → Delivery/Receiving →
  Stock Requisition → Stock Issuance, plus Expense Requisition → Expense Issuance, Purchase Return,
  Quantity Adjustment, Material Production, Physical Count, Job Order. Volumes are in §3 of the
  brief. A function MMS has and the desk does not is a gap, whatever the screen looks like.
- **The statuses and who moves a document between them.** PR carries FS/NS/PS; PO carries
  `postatus` plus two approval stages that are genuinely used (802/35 and 762/75).
- **The same outcome from the same inputs.** A requisition raised the same way must end in the same
  stock movement, the same ledger row, the same printed document.
- **The printed document, at the same click, day one.** §4 of the brief: ~21,700 runs in 60 days,
  ~360 a day, **eight of the top ten are document prints**. "Functions how MMS functions" fails
  immediately if a department cannot produce its slip. The 629 RDL reports stay on the report
  server — do not rebuild them.
- **One writer among several.** 128,462 of 227,077 ledger rows are HIS patient charging. MMS does
  not own the stock number and neither will the desk.

**And "but better" is still the brief's §5 — seven measured defects, not preferences:** the stock
figure that reconciles to nothing (as corrected by
`docs/bizbox-mms-stock-truth-addendum-20261014.md` — **`actualqty` is the outlier, not the
buckets**), no costing method running at all, the entire reorder apparatus unset while the data to
compute it exists, lot and expiry unused in a hospital, controlled drugs unflagged, approval absent
from the two highest-volume documents, and 13 million price rows that are a cross product.

**The single best fit with what you have already built** remains the requester surface: 655 people
hold Expense Requisition Details, 640 Purchase Requisition Details, and **neither document has an
approval field anywhere in BizBox's schema.** MMS has no requester experience. That is not a screen
to copy — it is a function to add.

---

## 4. What is NOT changed by this ruling

- **MMS only.** Not HIS, PIS or FMS.
- **His standing constraint:** *"dont make anuy changes that will destroy things ok"* / *"or what i
  meant was break things"*.
- **Collision 2 is still open and still Dada's.** The brief's build rules 1–3 assume writing
  BizBox's own tables. **The desk forbids it; `PSA_BIZBOX_WRITE_ODBC` stays unset.** Read them as
  what not to foreclose — honour `rowversion` in your model, keep save paths separable, assume
  another writer — not as a licence to write.
- **Every measurement in the brief and the addendum stands.** This ruling touches Rule 0 only.
- **Priority is still Dada's.** The brief's phase-1 list says so itself.

---

## 5. One thing it changes for SQL01

The brief's §1 said *"do not re-measure the screen layer"* and pointed at five artefacts, four of
which you cannot reach. **That now matters much less.** The screen inventory, the 239 grid columns
and the caption list were needed to reproduce screens, and you are no longer reproducing screens.

**What you need instead is the function and status inventory**, which is in the brief itself (§2,
§3, §5) and reachable. If you need a behaviour pinned down rather than a caption — what a status
transition actually does, what a save writes — say which and it gets measured. That is a different
and better question than *"what does the screen say"*.

Still gating estimating, unchanged: **the count of save paths**, not the count of screens. One
PowerShell 5.1 reflection pass gives it. Do not quote an effort number before it exists.

---

**Nothing changed on any host.** This is a ruling relayed, not work done.
