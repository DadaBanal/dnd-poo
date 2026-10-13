# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## How Dada wants MMS built: as per BizBox, but better. MMS only.

**From:** SQL01, relaying the Bizbox Chat session on Dada's instruction
**To:** WS36 / Cloud Build
**Carries:** `docs/bizbox-mms-design-brief-20261014.md` — committed beside this file, verbatim,
21,509 bytes, sha256 `0b3072d1…48cd005`, byte-identical to the record copy.

**Read the brief. This covering note is only three things:** who said what and on whose authority,
**two collisions with what you have already shipped**, and what you cannot reach.

---

## 1. Why this exists

Dada, to SQL01, **14 Oct 2026**, verbatim:

> *"hey can you pls ask the claude code chat bizbox chat how i want the mms built like biBox but
> better and send it to ws36"*

So this is not SQL01's design opinion and not yours to take as mine. It is the **Bizbox Chat
session's** answer, which Dada asked for by name, relayed to you unaltered.

That session carries an earlier instruction of his that you have not seen. **His words, 13 Oct
2026 — quote it, do not restate it:**

> *"i also want you to tell it bow i want it built as per the bizbox but better mms only module"*

And his standing constraint on the same day:

> *"dont make anuy changes that will destroy things ok"* / *"or what i meant was break things"*

### Provenance, so you know what to trust (R5)

**Everything in the brief is the Bizbox Chat session's measurement, not SQL01's.** I did not re-run
one query of it. I verified exactly two things about it, both of which hold:

| What SQL01 checked | Result |
|---|---|
| The committed copy matches the record copy | **byte-identical**, sha256 equal, verified with `cmp` not by eye |
| The content fence — internal IPs, the record's denylist, personal names | **clean**: no dotted quad of any kind, no denylist term, and every name-shaped match is a screen caption (*Issuing Department*, *Served Quantity*, *Expiry Date* …) |

Their own words on contradiction, which SQL01 endorses: *"If your own measurements of these
contradict mine, mine are wrong until re-run — say so rather than averaging."* **Do not average.**

Two method traps they flag, because a session that swallowed either would report a false zero:
`isControlDrug` lives on `iwItemMedicines`, **not** `iwItems`; and the SSRS column is `ItemPath`,
**not** `ReportPath`, with `ExecutionLog3` an indexed view that **requires `SET QUOTED_IDENTIFIER ON`**
— sqlcmd does not set it and fails Msg 1934.

---

## 2. Two collisions with what you have already shipped

These are SQL01's, not theirs — they do not have sight of the desk, and you cannot see this from
the brief alone. **Neither is mine to resolve. Both are Dada's call and both are live now.**

### Collision 1 — "same screens" versus the modern design you were told to build

Rule 0 of the brief is his and it overrides the rest:

> **Same tree, same screens, same steps, same words.** A department head opens the new screen and
> recognises it. Improvements are additive.

They further record that an earlier reading was **withdrawn**: four draft screens had *"redesigned
the workflows into boards and worklists"*, and he corrected it — *"it should functio nsimilar to
bixbox but better"*.

**But on 13 Oct Dada told SQL01 the opposite-facing thing about this same build**, verbatim:

> *"make sure it has all the data it needs and it conforms to modern design load skills needed also
> tell that to the spine"*

and you shipped 083 against that — a Tasks grid, Configurations, the Procurement tab, with the
design and accessibility skills loaded, and the category dropdown reworked onto `psa.vw_lookup` so
it shows labels rather than codes.

**These are not the same instruction.** They may not even conflict — "modern design" can mean the
*rendering* (type, contrast, focus states, keyboard order, labels not codes) while "same screens"
means the *information architecture* (same tree, same captions, same step order, same footers).
That reading reconciles them and is the one SQL01 would act on.

**But it is a reading, and the last time somebody read "similar" they got it wrong and four screens
were withdrawn.** So: **do not re-architect the Procurement screens you have already shipped on the
strength of this handoff.** Build the *new* MMS screens to Rule 0, flag anything already shipped
that Rule 0 would change, and let Dada rule on it. Say which reading you are acting on, in one
line, before you build — that is his own standing rule.

### Collision 2 — the brief's build rules assume a BizBox write path the desk is forbidden

Brief rules 1–3 describe writing to BizBox's own tables: *exclusive cutover per screen* while *"the
vendor client writes these same tables until the last screen moves"*, *write paths proven on
`TrainingDB_HIS8` first*, and *honour the rowversion columns or the two clients silently overwrite
each other*.

**On the PSA desk that path does not exist and must not be built.** The standing constraint, still
in force: **the BizBox write path is not built, and `PSA_BIZBOX_WRITE_ODBC` stays unset.**
Everything the desk does against BizBox today is read-only — products, 73 warehouses, 2,166 drug
items, 4,358 non-zero stock rows, all mirrored read-only into `psa.*` views.

So rules 1–3 describe a **future** architecture, not the one you are building into. Treat them as
telling you *what not to foreclose* — honour `rowversion` in your model, keep save paths separable,
assume another writer — rather than as a licence to write. **If the MMS build genuinely needs to
write to BizBox, that is a new decision from Dada and it is not in this handoff.**

---

## 3. What you cannot reach, and what to do about it

The brief's §1 says *"do not re-measure the screen layer"* and points at five artefacts. **Four of
them live in the programme record on OneDrive. You are a cloud session and have no route to it.**

| Artefact | Reachable by WS36? |
|---|---|
| `docs/bizbox-mms-design-brief-20261014.md` | **yes** — committed beside this file |
| `deliverables/PMC_OwnApp_1to1_Inventory_20261013.xlsx` (22 modules, 137 submodules, 133 screens, holders per function) | **no** |
| `docs/bizbox-ui-inventory-MMS-20261013.txt` (`frmStockRequisitionDetails`, 239 grid columns over 6 bands, real captions) | **no** |
| `deliverables/PMC_OwnApp_Proposal_v2-1_20261013.pdf`, `PMC_OwnApp_1to1_MMS_20261013.png` | **no** |
| `docs/bizbox-clone-question-20261013.md` | **no** |

**The captions you need for Rule 0 are in the brief itself**, §7, so you are not blocked on the
screen you will build first: *Issuing Department, Warehouse, Center, Item ID, Item Description,
Unit, Quantity, Served Quantity, Unit Price, Total Amount, Generic Name, Expiry Date*, buttons *Add
/ Edit Mode / Delete*, footers *Total Record(s)* and *Total Item*.

**For anything beyond that screen, ask and it gets measured — do not guess a caption.** Say which
artefact or which screen and SQL01 or Bizbox Chat will extract it. Reflection over the assemblies
**requires Windows PowerShell 5.1**; pwsh 7 refuses `ReflectionOnlyLoadFrom` (SYSLIB0018) and
returns zero windows, which reads as *"no forms found"* — a false negative, not a fact.

---

## 4. The four things in the brief that most change your build

Not a summary — read the brief. These are the ones that change *architecture* rather than backlog.

1. **MMS does not own the stock number.** 128,462 of 227,077 `iwItemLedger` rows are doctype `CH`
   — HIS patient charging. The clinical side is the **majority writer of stock movement** and MMS
   does not control it. Anything that owns a stock position must be correct while another system
   writes behind it.
2. **The printed document is the product, not a report feature.** ~21,700 MMS report runs in 60
   days, ~360/day, and **eight of the top ten are `MMS_ADHOC_*` document prints.** Analysis is under
   5%. Every document screen needs a print a department will accept **in place of** today's slip, at
   the same click, day one. The 629 RDL reports stay on the report server — **do not rebuild them.**
3. **The requester surface is the high-volume product and BizBox has none.** 655 people hold
   Expense Requisition Details, 640 Purchase Requisition Details — and **neither document has an
   approval field anywhere in the schema.** PO has two stages and uses them; expense and purchase
   requisitions approve on paper or not at all. That is the natural home of the PSA desk and it is
   the strongest fit between the brief and what you have already built.
4. **A field nobody fills should have been a calculation.** Twelve reorder and critical-level fields
   are zero across every item. Both inputs already exist: 227,077 ledger rows for consumption, and
   the receipt-to-PO chain is **complete — 2,250 of 2,250 receipt lines carry `FK_iwPOitem`** — so
   actual lead time is measurable on every line. Compute it. (`iwPOinv.deliverdate` is populated on
   **0 of 837** POs, so vendor lateness against a promise is *not* derivable until that field is
   captured — capture it on the new PO screen.)

The other three defects — no costing method anywhere (`avgcost > 0` on **0** of 5,443 items), lot
and expiry **completely unused in a hospital** (six lot tables at 0 rows, 2,008 medicine items
including chemo, expiry tracked on paper), controlled drugs **not flagged** (`isControlDrug = 1` on
0 of 2,167, the one with a regulatory edge) — plus 13,042,176 price rows that are a cross product
at 1,523× the item master. All in §5 of the brief with their controls.

---

## 5. Priority

**Dada sets priority. Not SQL01, not Bizbox Chat, and not you.** The brief's §7 phase-1 list is
explicitly *"what the numbers point at, for him to order"* and says so itself. Take it as evidence
for a conversation with him, not as a backlog you may start.

The brief's own deliberate exclusions, which SQL01 agrees are well-founded: Asset Management (18
submodules, a sub-product in itself), the ~69 submodules nobody holds, the six modules with zero
holders, and the 629 RDL reports.

---

## 6. Open, and one of them gates estimating

From the brief's §8, unchanged and not SQL01's to close:

- **How many MMS screens actually write.** 133 screens is not the estimate driver; the **count of
  save paths** is. One reflection pass over the MMS assembly under PowerShell 5.1 gives it. **This
  is the first measurement before anyone sizes effort** — do not quote a number before it exists.
- **BizBox's contract terms** on direct database writes and on reverse-engineering the assemblies.
  Open since 13 Oct. Either could change the answer, and this compounds Collision 2.
- **Whether the vendor has a web client or an API on its own roadmap.**
- **Whether the disabled SQL Agent job `PMC - MMS Movement Column Alignment` is the vendor's own
  fix** for the stock reconciliation defect, and why it is disabled. Its steps have not been read.
  INFERRED from the name only — not confirmed with the vendor.

---

## 7. State of play

| | |
|---|---|
| Changed on any host | **nothing.** Read-only throughout, both sessions |
| Who holds the BizBox measurement | **Bizbox Chat**, which also holds `scripts/Measure-BizBoxMMS-*-20261014.py` (7 files) and states it is writing nothing further in MMS |
| Who holds this handoff | SQL01 |
| Who builds | **WS36.** One driver per cycle — SQL01 is not building MMS |
| Still with Dada | both collisions in §2, priority in §5, and whether BizBox writes are ever permitted |

SQL01 ran no BizBox probes for this, deliberately, so nothing here collides with Bizbox Chat's
measurement.
