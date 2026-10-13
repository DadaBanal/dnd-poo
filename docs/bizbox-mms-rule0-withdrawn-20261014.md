# Rule 0 of the MMS design brief is withdrawn — Dada's ruling, 14 Oct 2026

**Withdraws:** Rule 0 and the §7 caption list of `docs/bizbox-mms-design-brief-20261014.md`.
**The brief is not edited** — it is committed as `bb96800`, verified byte-identical at sha256
`0b3072d1…48cd005`, and this is a separate file so that verification still holds. Read this before
§7.

**Everything else in the brief stands.** Every measurement, the §2 module map, the §3 document
chain, the §4 report usage, the whole §5 defect list, and §5.1 as corrected by
`docs/bizbox-mms-stock-truth-addendum-20261014.md`. Only Rule 0 and the caption requirement go.

---

## His ruling

Shown Rule 0 as *"same tree, same screens, same steps, same words — a department head must recognise
the screen"*, Dada said, 14 Oct 2026:

> *"no i want it built how mms functions but better"*

**Function parity, not screen parity.** The captions, grid bands, button labels, footers and screen
tree are **not binding**. The functions, the steps and the outcomes are.

---

## My error, named exactly, because it was filed under his name

Rule 0 was built on his earlier utterance of 13 Oct:

> *"it should functio nsimilar to bixbox but better"*

**The operative word is `functio` — function. It does not reach the screen layer.** I read "similar"
as similarity of appearance and derived a screen-fidelity requirement from it.

The reading being wrong is the smaller half. The larger half:

> **The brief presents Rule 0 as *"Rule 0 first, because it is his and it overrides the rest"*, and
> states *"a department head must recognise the screen"*. He never said that. I quoted him
> correctly and then wrote my own inference beside the quote as though it carried the same
> authority.**

That is the recurring failure this estate has recorded before — a correct statement plus an
uncontrolled inference reads exactly like a measured instruction once it is filed, and this one was
filed into a committed repo, in a document that opens by telling the reader not to paraphrase it.

What should have happened: Rule 0 labelled **INFERRED from "similar"**, with the alternative reading
named — that "similar" might mean function, not appearance — and the question put to him in one
line. The brief did label the withdrawn-screens history that produced the inference. It did not
label the inference.

---

## What this changes downstream

| | |
|---|---|
| **§7 Rule 0 and the caption list** | **withdrawn.** Issuing Department / Warehouse / Center / Item ID / … , the Add / Edit Mode / Delete buttons, the Total Record(s) footer, the 6 bands and 239 columns are **no longer a specification** |
| **§7 rules 1-5** | stand as relayed — and rules 1-3 remain *what not to foreclose*, not a licence to write BizBox's tables, with `PSA_BIZBOX_WRITE_ODBC` unset |
| **§7 rules 6-8** | stand. The printed document is still day-one (§4: ~21,700 runs in 60 days, top eight all document prints); still do not own the stock number alone (§3: 128,462 of 227,077 ledger rows are HIS charging); anything that is a field nobody fills still becomes a calculation (§5.3) |
| **§1 "do not re-measure the screen layer"** | **matters much less now.** The screen inventory, the 239 columns and the caption extraction existed so somebody could reproduce screens. **Nobody is reproducing screens.** Four of the five artefacts it named are unreachable from the cloud session, and that is no longer a problem |
| **The 083 Procurement screens already shipped** | stand. **BizBox captions are explicitly not to be retro-fitted to them.** This resolves the first of the two collisions in favour of the modern design already built |

### What is wanted instead of the screen layer

The **function and status inventory** — which is what §2, §3 and §5 already are, and which is
reachable. The questions to expect are *"what does this status transition actually do"* and *"what
does this save write"*, not *"what does the screen say"*.

So the measurements that now carry the weight are the ones already filed: the 14 document types with
their header and line volumes and status columns (§3), the holder distribution showing MMS is a
requisition system with a small procurement core (§2), and the seven defects that define "better"
(§5). None of those depended on Rule 0.

### Still gating estimating, unchanged and unmeasured

**The count of save paths, not the count of screens.** 133 screens was never the estimate driver.
One reflection pass over the MMS assembly under **Windows PowerShell 5.1** gives it — pwsh 7 refuses
`ReflectionOnlyLoadFrom` and returns zero. Not run.

Under function parity this measurement becomes *more* important, not less: with screen fidelity gone,
the work is entirely in reproducing what each save does, and nobody has counted them.

### A standing instruction recorded alongside this one

Dada, 14 Oct: *"use design skills and whatever skills available when building it or when u tell ws36
to build it"* — **loaded before building, not after, and which ones fired is stated.** He had the
install card rendered for `frontend-design`, which was not enabled, and is enabling it.

---

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. Relayed from peer session SQL01;
Dada's words quoted as that session recorded them. No patient identifiers, no staff names, no
addresses or topology — safe for a committed repo. Nothing built, nothing changed.*
