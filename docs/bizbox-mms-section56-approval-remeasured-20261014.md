# §5.6 approval figures, re-measured against live headers — the finding is sharper, not weaker

**Closes:** the item I flagged as *flagged-not-fixed* in
`docs/bizbox-mms-section3-flag-audit-20261014.md`. §5.6 of the brief quoted the PO approval flags
against **raw** headers of 837; the live count is 796. **Neither the brief nor the audit is edited.**

**Measured 14 Oct 2026**, `LiveDB_PMC`, read-only. Live = `deleteflag = 0 AND cancelflag = 0`.
Controls both ways. Script: `scripts/Probe-Section56Approval-20261014.py`.

## The corrected figures

| | as published (raw, of 837) | **live (of 796)** |
|---|---|---|
| `approvalflag` set / unset | 802 / 35 — 95.8% | **775 / 21 — 97.4%** |
| `approval2flag` set / unset | 762 / 75 — 91.0% | **744 / 52 — 93.5%** |
| posted **and** approved by the same person | 1 of 802 | **1 of 775** |

**Approval discipline on purchase orders is better than my raw figures implied**, not worse — most
unapproved POs turn out to be the deleted or cancelled ones, which is what you would expect, since an
unapproved PO is the kind that gets cancelled. Second-stage approval sits at 93.5% of live POs, and
**separation of preparer from approver holds on all but one live PO.**

## And the claim that actually carries §5.6, now with a working control

| Document | Live headers | Approval columns |
|---|---|---|
| Expense Requisition | 1,163 | **NONE** |
| Stock Requisition | 1,021 | **NONE** |
| Delivery / Receiving | 986 | **NONE** |
| Stock Issuance | 973 | **NONE** |
| Purchase Requisition | 605 | **NONE** |
| Purchase Order | 796 | `approvaldatetime`, `FK_ASUapproval`, `approvalflag`, `approval2datetime`, `FK_ASUapproval2`, `approval2flag` |

Controls: an impossible column pattern returned 0, and the same search finds 5 `%flag%` columns on
`iwPRinv`, so it is not blind — **the NONEs are measured absences, not a blind search.**

**So the contrast is stronger than §5.6 stated it.** The purchase order carries a full two-stage
apparatus — two distinct approver identity columns, two flags, two timestamps — and uses it on 97.4%
and 93.5% of live documents. Meanwhile **4,748 live requisition, issuance and receiving documents
have no approval field of any kind**, and those are the documents 655 and 640 people hold the screens
for.

**The conclusion is unchanged and better evidenced:** approval routing for the requisitions is not a
feature that exists and is unused — there is nowhere in the schema to record it. That remains the
natural home of the PSA desk.

Read-only throughout. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no passwords, no connection strings, no addresses or topology.*
