# Dada's direction on the app, verbatim — with provenance, and one gap

**For:** the WS36 / PSA desk build. Requested by SQL01 on 14 Oct 2026 so WS36 builds to his words
rather than to a paraphrase.

**Why provenance matters here and is not pedantry.** My own `Rule 0` was withdrawn on 14 Oct because
I quoted him correctly and then wrote my inference beside the quote as though it carried the same
authority. **So this note separates what he said to this session from what reached me through
SQL01, and names the one piece I hold only as a paraphrase.** Nothing below is a synthesis; where I
describe what a quote settles, that is marked as my reading.

---

## A. Said directly to this session

| His words | Date |
|---|---|
| *"not the db i mean if we reuse the same db but build a better app for HIS PIS MMS AND FMS"* | 13 Oct |
| *"can you give me a proposal and a draft image what would it look like"* | 13 Oct |
| *"and whats the advantaghe"*, then **"the advantage should be checked properly not just assumed"** | 13 Oct |
| *"i mean do a sample run thorugh on all the main apps HIS PIS MMS AND FMS"* | 13 Oct |
| **"this does not include all functions we are looking for 1 : 1 but better copy"** | 13 Oct |
| **"it should functio nsimilar to bixbox but better"** | 13 Oct |
| **"i also want you to tell it bow i want it built as per the bizbox but better mms only module"** | 14 Oct |
| **"dont make anuy changes that will destroy things ok"**, then *"or what i meant was break things"* | 13 Oct |
| *"Still yours, once: the 73 negative stock balances on the live Stock on hand tab — show, flag, or floor at zero."* | 14 Oct |

## B. Reached me through SQL01 as his words — I did not hear these directly

Carried here because WS36 is building to them. **SQL01 is the source for the wording, not me.**

| His words, as SQL01 recorded them | What SQL01 said it settled |
|---|---|
| **"no i want it built how mms functions but better"** | function parity, not screen parity; withdrew `Rule 0` |
| *"conforms to modern design load skills needed"* | the 083 screens' rendering |
| *"use design skills and whatever skills available when building it or when u tell ws36 to build it"* | skills loaded before building, and named |
| *"if the procedure is too complicated simplify it to many checks isnt good at all it can be secured and simplified properly"* | three mechanisms, four controls |
| *"just for this one it can right to tables as its a mms build so it should function as ome"* | MMS build may write BizBox's own MMS tables |
| *"psa desk make it uniform"*, then *"ok psa desk it is if its vetter"* | one identity for read and write |
| *"there is already bizboxsa"*, then *"ask bizbox chat"* | routed the login question to this session |

## C. The gap — and it is load-bearing for the screens being built now

**I do not hold his words for the ruling that the MMS document screens follow the 13 Oct Stock
Requisition draft.** That reached me as SQL01's description:

> *"the MMS document screens are built similar to your 13 Oct Stock Requisition draft — the document
> shape with the BETTER items on it — not 1:1"*

That is a **paraphrase, not a quote.** It is also the ruling that currently governs how the
document screens are drawn, so it is the one most worth having in his own words. **SQL01 should
supply his quote, or we should treat the screen shape as unconfirmed.** This is precisely the shape
of the `Rule 0` error, caught before it is built on rather than after.

## D. What the quotes settle, and what they do not — my reading, marked as such

**Settled by his own words:**
- **Scope:** the same database, a better application. *"reuse the same db but build a better app"*.
- **Fidelity:** **function parity, not screen parity** — *"how mms functions but better"*, and the
  earlier *"functio nsimilar"*, whose operative word is **function**. The captions, grid bands,
  button labels and screen tree are **not** binding. *(This is the correction that killed `Rule 0`.)*
- **Breadth:** **1:1 on function** — *"all functions we are looking for 1 : 1 but better copy"* —
  so the whole product's functions, not the 26% slice PMC currently holds.
- **This build:** **MMS only** — *"mms only module"*.
- **Evidence:** **no asserted advantages** — *"the advantage should be checked properly not just
  assumed"*. Seven claimed advantages were checked against the live system on 13 Oct; two were
  withdrawn and two narrowed.
- **Restraint:** *"dont make anuy changes that will destroy things"*.
- **Simplicity over thoroughness:** *"to many checks isnt good at all it can be secured and
  simplified properly"*. **Worth repeating to WS36 as a standing constraint, not a one-off** — it
  was said about a procedure, and it applies to every mechanism added since.

**Not settled, and nobody should infer it:**
- **Which screens, in what order.** He has not sequenced the MMS screens. *(He sets priority.)*
- **The screen shape** — see §C.
- **Whether the show / flag / floor decision on the 73 negative balances is made.** He asked for it
  once and has the document; **it is open.**
- **Any deadline.** The Procurement and Pharmacy worksheet carries `[date to be set]` for that
  reason.

---

## E. `iwPRinv` FROM / TO — settled, and the convention is reversed between the two forms

SQL01 inferred the roles from the distinct-value profile and asked for a measurement.

**MEASURED from the client's own control names** on `frmPurchaseRequisitionDetails`:

| Control | So the column means |
|---|---|
| `cboRequestingDeptFROM_ValueChanged` / `_AfterDropDown` | **`FK_mscWarehouseFROM` = REQUESTING** |
| `cboIssuingDeptTO_ValueChanged` / `_AfterDropDown` | **`FK_mscWarehouseTO` = ISSUING** |

Also present: `get_WarehouseIdFROM`, `get_WarehouseIdTO`, `FillWarehouseData`.

**Confirmed against the data, measured independently:** on 655 purchase requisitions,
`FK_mscWarehouseFROM` is filled on all 655 with **29 distinct** values; `FK_mscWarehouseTO` filled on
all 655 with **1 distinct**. Many departments request, one office issues.

> **The trap: `SRC`/`DST` and `FROM`/`TO` are semantically REVERSED between the two forms.**
> Stock requisition: `cboIssuingDeptSRC`, `cboRequestingDeptDST` — **SRC = issuing, DST = requesting**.
> Purchase requisition: `cboRequestingDeptFROM`, `cboIssuingDeptTO` — **FROM = requesting, TO = issuing**.
> So `SRC` pairs with `TO`, and `DST` pairs with `FROM`. Carrying the stock-requisition convention
> across would invert both ends.

**On SQL01's two decisions:**
- `vw_purchase_req.WarehouseDst = FROM` as the **requesting** department — **correct**, and their
  distinct-value inference was right.
- `WarehouseSrc = null`, on the grounds that a purchase requisition has no issuing warehouse —
  **not correct.** The issuing warehouse **is** `FK_mscWarehouseTO`. It is **constant**, because one
  procurement office issues all of them, but it exists and is populated on every row. **Set
  `WarehouseSrc = FK_mscWarehouseTO`.** A constant is not an absence — and treating it as one is the
  same error class as `FK_mscBranches` being dismissed before its single value was measured.

## Not established

- His verbatim wording for the screen-shape ruling (§C).
- Whether `FK_mscWarehouseTO`'s single value is the Procurement office specifically. **Not read** —
  it needs one join to `mscWarehouse` and nobody asked.

Read-only throughout. Reflection-only disassembly; no BizBox code executed. Nothing written.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology.*
