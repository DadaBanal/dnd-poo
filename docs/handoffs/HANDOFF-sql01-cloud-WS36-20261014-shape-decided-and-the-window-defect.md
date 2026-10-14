# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (the screen shape is decided; a window picker that cannot be satisfied; and 086 is on the host)

**One brief, held deliberately until Dada closed the screen-shape question, so you get a single instruction rather
than three in an hour that disagree. 086 is applied on `PMC_PSA`. Your `dd121eb` is merged and reviewed below.
`PSA_BIZBOX_WRITE_ODBC` stays unset.**

---

## 1. The screen shape, decided — and the provenance stated exactly

**Dada's decision: the document shape, all five BETTER items, chrome free.**

- **Keep the shape:** header pickers → the lines grid → footer totals and actions.
- **Keep all five BETTER items:** on hand per row · shortfall shown rather than silently under-served · items picked
  and never created from the screen · the approval path shown · print the slip at the same click.
- **Captions, column order and visual style are yours to set**, with the design skills.

**Two readings he did not choose, recorded so nobody reopens them:** BizBox's column set in the same order with only
the chrome modernised (that is the screen fidelity he withdrew on 14 Oct); and function only, with the screens drawn
fresh and the draft as background rather than reference.

**The provenance, because it has been load-bearing and was briefly over-stated.** His own words are four:
**"well similar not 1:!"**, answering *"does it follow this design?"* about the 13 Oct draft. Those four words settle
*similar, not 1:1* and nothing finer. **The expansion above is mine** — it was recorded as mine in the runbook at the
time under *"Read as, and acted on:"* — and **he has since confirmed it**, when the Bizbox Chat session put it to him
as a choice against the two alternatives above and he selected it. So: his ruling is the four words; the expansion is
mine; the expansion is now confirmed by his selection. **That is stronger than a paraphrase and weaker than a
sentence in his own words, and it should be cited that way, not as "Dada said".**

**One correction to the draft itself, which is measurement and not a reading of anything he said.** The 13 Oct
drawing shows a **Center picker** in the header. **There is no Centre dimension** — `FK_psDatacenter` holds a single
value across all 1,099 stock requisitions, and `psDatacenter` is a 10,508-row entity master that the stock card joins
to print patient names. **Do not build the Center picker.** "Keep the header pickers" means the pickers that exist:
**issuing department and requesting department, both warehouse FKs.**

## 2. A validation rule that would reject a third of real documents

Measured while naming the purchase requisition's issuing office: **on 205 of 639 purchase requisitions the requesting
department is the same warehouse as the issuing one** — code 1019, *Procurement, Inventory, Warehouse and Vendor
Mngt* — because Procurement requisitions its own stock.

**So a form that treats "source equals destination" as invalid rejects about a third of genuine purchase
requisitions.** Same-on-both is a normal document, not a mistake. It should save without a warning.

## 3. The Movements window picker cannot be satisfied, and it is the defect behind Dada's screenshot

He sent the Movements tab this morning. Two separate things in it, one yours and one mine.

**Mine, and the serious one.** `psaspine/web/views/procurement.py:41` offers
`WINDOWS = 7 · 30 · 90 · 183 · 365 days`. **`psa.ext_movement` physically holds 4–14 Oct — ten days, 36,465 rows.**
So **every option above 7 days returns the same rows and calls it a different period**, and "Last 12 months" is wrong
by a factor of thirty-six. Nothing on the screen says so.

The cause is mine: `psa.vw_item_ledger` is a fixed ten-day window because 14 days is 50,970 rows against the desk's
50,000 cap. **The fix is already built and is wired nowhere: `psa.fn_item_ledger(@from, @to)`** — same ten columns,
no fixed window, the desk bounding each read. `grep fn_item_ledger` across `platform/psa-spine` returns nothing.

**Either wire it or cut the list to what the data supports.** A picker offering a year over ten days of rows is worse
than a picker offering ten days, because the first one is confidently wrong.

**Also measured, so it is not a surprise later:** four rows in that mirror are **future-dated** — two on 8 Nov, two on
8 Dec, four of the six being doctype `CA`. They are BizBox's own rows, not an import artefact. `vw_item_ledger`
carries them; `fn_item_ledger` excludes them correctly with `@to = today`. They make "latest movement" read December.

**Yours, and already fixed in the tree.** The chips Dada saw were raw doctype codes — `Ch · Ca · Cn · Ss · Ei · Dr ·
Mp · Pp · Qa`. **`dd121eb` fixes this**: `MOVE_WORDS` carries the words and `BUCKETS` carries Receipts / Issuances /
Transfers. He was looking at **undeployed code** (§5). One thing survives the fix, though: **`CH` and `CA` both map to
"Charged"**, so a per-code chip row still shows the same word twice — 20,857 and 8,742. Merge them into one
*Charged · 29,599* with the codes beside it, or show the bucket and let the codes live underneath.

And for the default view: **patient charges are 32,520 of 36,465 rows — 89% of a Procurement screen.** The buckets
make that filterable; consider what the page leads with.

## 4. `vw_purchase_req`'s warehouses were wrong and are corrected — with a trap you need

Part 105 set `WarehouseSrc` to NULL on purchase requisitions, reasoning that `FK_mscWarehouseTO` held one distinct
value and carried nothing. **Wrong — a constant is not an absence.** Corrected on both databases:

```
vw_purchase_req.WarehouseSrc = FK_mscWarehouseTO    (issuing)
vw_purchase_req.WarehouseDst = FK_mscWarehouseFROM  (requesting)
```

**The trap, because it inverts both ends if you carry one form's convention across:**

| Document | Client's controls | So |
|---|---|---|
| Stock requisition | `cboIssuingDeptSRC` · `cboRequestingDeptDST` | **SRC = issuing, DST = requesting** |
| Purchase requisition | `cboRequestingDeptFROM` · `cboIssuingDeptTO` | **FROM = requesting, TO = issuing** |

**SRC pairs with TO; DST pairs with FROM.** The two forms use opposite conventions and nothing in the schema says so.
In the twelve views you are given uniform `WarehouseSrc` = issuing and `WarehouseDst` = requesting throughout, so you
never have to hold this — it is recorded for whoever reads the source tables directly.

## 5. 086 is applied — and your new code is not deployed, which is what Dada is seeing

**086 applied on `PMC_PSA`, verdict PASS**, from the port unretyped, COPY_ONLY backup first
(`PMC_PSA_COPYONLY_pre086_20261014-131812.bak`). `psa.member_module_grant` exists, **is empty** so nobody gains or
loses a page today, PK `(member, module)`, the level CHECK on, **exactly one table added and none changed, 161 → 162**,
verdict on a fresh connection.

**But `PSA-Desk` has been running since 08:54.** The working tree under it now holds `dd121eb` after my rebase, and a
running process does not pick that up. **So the live desk is still serving the screens he rejected this morning while
their replacements sit in the tree.** I have not restarted it on my own initiative: it is a visible production change
in working hours and his standing *"dont make anuy changes that will destroy things"* covers it. **The decision is
with him**, and I checked first that it is safe — your new code references none of the mirror columns still
outstanding (`trx_key`, `is_active`, `is_inventory`) nor the twelve new views, so 086 was its only requirement.

## 6. One port, everything I still owe the mirror

In this order, because the first one is visible to him today:

1. **`is_active BIT` and `is_inventory BIT` on `ext_product`** — the Items list grew from 5,506 to 8,572 when I
   removed the filter that was causing the 404s, and these two let you filter it back to active inventory items while
   the page still resolves for everything.
2. `trx_key NVARCHAR(20) NULL` on `ext_purchase_order` and `ext_invoice` — the slip key.
3. `conversion`, `purc_price`, `last_purc_price` on `ext_product`, if you want them on the form.
4. The twelve mirror tables for the document views, one uniform pattern twelve times.

**I add every map line the day it lands** and prove them on an hourly read.

## 7. A standing constraint, not a one-off

Dada's *"to many checks isnt good at all it can be secured and simplified properly"* was said about a procedure. It
applies to **every mechanism added since**. It is why the 404 fix removed a filter rather than adding a condition, and
it is worth holding against the rights model, the validation rules and anything added to the write path.
