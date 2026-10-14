# The Stock Requisition grid's money arithmetic, measured — it multiplies, it does not divide

**Supersedes** the `INFERRED` line in `docs/bizbox-mms-grid-column-map-20261014.md`, which guessed
`unitprice = price ÷ conversion` and said not to bind to it. **That guess was wrong in the opposite
direction.** The file is not edited.

**Measured 14 Oct 2026** by reflection-only disassembly of six methods on
`BizBox.MaterialsManagementSystem.CoreComponents.Details.frmStockRequisitionDetails`, under
**Windows PowerShell 5.1** via the existing `scripts/Disasm-CF4Save-20261012.ps1`.
Script: `scripts/Probe-SRGridArithmetic-20261014.ps1` (the method enumerator).

## The formulas

| Grid cell | Computed as | Stored on `iwWhreqitem`? |
|---|---|---|
| **Unit Price** (`unitprice`) | **`price` × `smallconversion`** | **no** — computed in the grid only |
| **Total Amount** (`netcost`) | **`qty` × `price` × `smallconversion`** | **yes** |
| availability check | **`warebalance` × `qty` × `smallconversion`** | `warebalance` is not on the line table |

**It is `smallconversion`, not `conversion`.** Both are bound to this grid and both are captioned
*Conversion* in the column map; the arithmetic uses the **small** one. A replacement that reaches for
`conversion` because it is the obvious name will be wrong on every item where the two differ.

## The control, stated because this is a negative

`op_Division` appears **0 times** across all six methods. `op_Multiply` appears **8 times** through
the same search. **So the division is genuinely absent rather than invisible to the method** — and
the earlier guess is dead on the data, not on preference.

Decimal arithmetic in .NET is an **operator call**, not an IL opcode: my first pass searched for
`div` and `mul` and found **zero of each**, which read as "no arithmetic here" and was a method
artefact. `Decimal::op_Multiply` is what to search for. **That near-miss is the reusable lesson.**

## Two consequences for the build

1. **`netcost` on the line table is a stored computed value.** The grid computes
   `qty × price × smallconversion` and the save persists it. **A replacement must compute it the same
   way or the stored totals drift from the lines they describe** — and nothing in the schema would
   catch that, because both sides are just numbers.
2. **"Unit Price" is price per *converted* unit, not per smallest unit.** Multiplying by
   `smallconversion` scales *up* from the stored `price`. A reader seeing the caption and expecting a
   price-per-smallest-unit has it backwards, and so did I.

## Method note worth keeping

Passing several method names to the disassembler from bash as `"a","b"` sends **one** token `a,b`,
which matches no method and returns an **empty listing** — indistinguishable from "these methods are
empty". It produced 0 lines on the first attempt. **One method per call**, or build a real array.
Same family as the day's other quoting traps.

## Not established

Whether `unitprice` is also written anywhere on save. It is a column on the client-side
`dtItemRepository` DataTable and is made writable on form load
(`dtItemRepository.Columns["unitprice"].ReadOnly = false`), but `InsertItemsToIwWhreqitem` is only 77
bytes of IL and delegates to `<InsertItemsToIwWhreqitem>b__2f` (361 bytes), **which I did not
disassemble.** The save path is where a stored `unitprice` would appear if one existed; the table has
no such column, so the expected answer is no, but it is **not measured**.

Read-only throughout. No BizBox code executed — reflection-only. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology.*
