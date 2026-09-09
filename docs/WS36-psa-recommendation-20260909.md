# WS36 — PSA recommendation

**Date:** 9 September 2026 · **Workstream:** WS36 (new) · **Scope:** VARIATION
· **Entities:** PMC + JRBY-CI · **Machine:** claude.ai/code cloud (read-and-draft; no LAN, no local files)

> **Read this correction block before the paper.** The paper below is the output of a
> 14-agent discovery and design run. Three of its numbers have since been **MEASURED
> against the register by code** (`platform/psa-spine`, 21 tests) and are wrong in the
> paper. The corrections are authoritative; the paper is left otherwise unedited so the
> reasoning stays auditable.
>
> | Paper says | MEASURED | Where |
> |---|---|---|
> | "20 register rows flagged as variations" | **17** — 16 whose `contract_basis` is exactly `variation`, plus **WS34**, whose value is the literal `variation (Amendment 1)` | `python3 -m psaspine import` |
> | "eleven client-dependency notices" | **10.** 11 rows are BLOCKED, but **WS18**'s next action is Dada's own ("Dada to execute Phase 1"), so it is not a client dependency and must not receive a notice | `reports.blocked_on_client` |
> | (not stated) | 35 rows: **17 variation · 17 baseline · 1 unknown (WS17)**. 4 compound scope links. 6 data-quality findings. | same |
>
> **VERIFIED 9 Sep, and it puts a condition on the recommendation.** The paper's
> case that the incumbent stays cheapest up to ~4,000 tickets/month rests on the
> USD 24 per 100 extra tickets overage. That rate belongs to **"Leader Flex", and
> the vendor's own pricing page states it is available via **Azure Marketplace
> only** (teamswork.app/products/microsoft-teams-ticketing). PMC's admin screen
> reads plan **"Leader"**, not Leader Flex. So unless PMC's subscription is on the
> Azure Marketplace channel, **the overage cannot be bought at all** and every
> figure above 1,000 tickets/month in §2.3 and §11.1 is unavailable rather than
> merely expensive. Confirm the purchasing channel with the vendor before the
> hospital-wide volumes in this paper are quoted to anyone. The Azure Marketplace
> listing itself returned HTTP 403 and is NOT VERIFIED.
>
> **WS34 is the row that matters.** An exact-match filter on `variation` drops it, and that
> row is an entire covered entity (JRBY-CI). The importer normalises it and a test asserts
> it, so the mistake cannot recur.
>
> **The completeness critic found four BLOCKING gaps in this paper.** They are recorded in
> full at the end and are not yet resolved. The most serious: the variation mechanism does
> **not** work end to end — tickets live in the desk, variations and effort in the spine,
> and they meet only in a read-only nightly pull, so a hospital-wide uplift claim cannot be
> evidenced from ticket effort. Read §"Completeness critic" before relying on §9 or §11.
>
> **Commercial figures appear below.** They are PMC/Dada IT contract terms, not credentials
> or patient data, and this repository is private. Mirror this file into the OneDrive record
> as a dated document per the filing convention.

---

# PMC PSA — Recommendation
**WS36 · 09 September 2026 · Dada IT / Premiere Medical Center Nueva Ecija + JRBY Cancer Institute**

---

## 1. Recommendation, in three sentences

**Build the commercial spine — the agreement, the nine scope items, the Annex B variation register, notices, client dependencies and banded effort — as a small SQL schema plus a loader in a git repo, and build nothing else.** Do **not** build a ticket desk and do **not** buy one this month: the premise that drove this exercise is wrong — Kitameraki is **USD 88.50 per organisation per month with unlimited users and unlimited instances** [VERIFIED today, teamswork.app], not per-ticket-holder, so it stays cheaper than every alternative up to roughly **4,000 tickets/month** and the case for replacing it is capability, not cost. Fix the incumbent's three free defects this week, run the desk decision as a dated, testable gate at the six-monthly review with **Jira Service Management Standard** named as the successor, and spend the 60–90 hours you have on the half of a PSA that no vendor sells.

---

## 2. The arithmetic

### 2.1 What is actually being paid today

| Item | Figure | Label |
|---|---|---|
| Kitameraki plan | Leader | MEASURED (admin screen) |
| Quota | 1,000 tickets/period | MEASURED |
| Usage, period 06 Sep–05 Oct 2026 | 86 (19 ITO / 0 MOSB / 67 PCSD) | MEASURED |
| Usage, previous period | 1,133 (90 / 1 / 1,042) | MEASURED |
| Leader list price | **USD 88.50/org/month billed annually** (12,000 tickets/yr), USD 117 billed monthly (1,000/mo) | VERIFIED — https://www.teamswork.app/products/microsoft-teams-ticketing |
| Overage ("Leader Flex") | **USD 24 per 100 extra tickets** | VERIFIED, same source |
| Users | **Unlimited. Instances unlimited.** | VERIFIED, same source |

FX used throughout: **USD 1 = PHP 62.508**, **USD 1 = AUD 1.3861** [VERIFIED 08–09 Sep 2026, frankfurter.dev; corroborated PHP 62.544 at open.er-api.com]. Reprice on the day of any signature.

Contract reference denominator: **AUD 13,000/month = USD 9,379 = PHP 586,000/month**; annual AUD 156,000 = USD 112,545 = **PHP 7.03M** [MEASURED from Amendment No. 1 cl.1; execution unverified — see §12].

### 2.2 The 1,133-against-1,000 breach is partly self-inflicted

[MEASURED] On 7 Sep 2026 at 07:25:34Z `premierelab.113@gmail.com` sent one message to **both** `support@pmcne.ph` and `helpdesk@pmcne.ph`. At 07:26:07Z helpdesk@ opened **ITO-1723**; at 07:26:08Z support@ opened **PCSD-1104**. Same requester, same subject, same minute, two tickets, two acknowledgements. The same pattern recurs on 8 Sep.

[INFERRED, from ticket-key sequences] ITO 1527→1736 over 57 days ≈ 3.7/day; PCSD 905→1109 over 10 days ≈ 20/day; combined ≈ 24/day ≈ **700/month** — well *under* quota. The 1,133 figure is inflated by duplication and by an unmeasured share of the PCSD burst.

**Consequence: the business case is currently sized on a number nobody has cleaned.** Alias `support@` onto `helpdesk@` (one hour, free) and re-measure for two periods before quoting any volume to PMC. This is the single highest-value line in this document.

### 2.3 Where the incumbent's price goes, by volume (unlimited fulfillers throughout)

| Tickets/month | Annual quota use | Overage blocks | USD/yr | PHP/yr |
|---|---|---|---|---|
| 700 (post-dedup estimate) | 8,400 | 0 | **1,062** | 66,383 |
| 1,133 (measured, pre-dedup) | 13,596 | 16 | **1,446** | 90,387 |
| 2,000 (hospital-wide planning) | 24,000 | 120 | **3,942** | 246,407 |
| 2,500 | 30,000 | 180 | **5,382** | 336,418 |
| 4,000 | 48,000 | 360 | **9,702** | 606,453 |

[INFERRED — arithmetic over the VERIFIED Leader and Leader Flex rates.]

### 2.4 Where per-seat pricing breaks

Requesters are **free and unlimited on every serious candidate** [VERIFIED for Jira SM, Freshservice, HaloPSA, Zoho Desk, Kitameraki]. **100 vs 400 requesters costs USD 0 either way.** That axis of the brief is not a pricing variable. Only fulfiller seats move money.

Affordability test — a software line the board will approve. Two thresholds against the monthly ICT fee:

- **5% = USD 469/month = PHP 29,300/month**
- **10% = USD 938/month = PHP 58,600/month**

| Product | USD/seat/mo | Source | Breaks 5% at | Breaks 10% at | USD/yr @ 40 | PHP/yr @ 40 |
|---|---|---|---|---|---|---|
| **Kitameraki (per org)** | — | VERIFIED | never on seats; at **~2,500 tickets/mo** | ~4,500 tickets/mo | 3,942 @2k tkt | 246,407 |
| **Jira SM Standard** | 20 | VERIFIED, atlassian.com | **24 seats** | 46 seats | 9,600 | 600,077 |
| Freshservice Growth / Business Agent | 49 | VERIFIED | **10 seats** | 19 | 23,520 | 1,470,188 |
| HaloPSA (Asia-Pacific list, 25–49 band) | 58 | VERIFIED, usehalo.com inline PRICING object | **8 seats** | 16 | 27,840 | 1,740,223 |
| ConnectWise PSA | ~60 | NOT VERIFIED (no published price) | ~8 | ~15 | ~28,800 | ~1,800,230 |
| Syncro | 129 | VERIFIED, syncrosecure.com | **4 seats** | 7 | 61,920 | 3,870,495 |
| **Built desk (Ledger-style)** | 0 licence | — | never on licence | never | hosting only ~1,366 | ~85,388 |

**The finding:** a real per-agent PSA becomes unapprovable somewhere between **8 and 10 seats** — *below* the 10 fulfiller seats Dada has already committed to. Only Jira Service Management survives to 24 seats at 5% and 46 at 10%. Nothing else on the market clears the 40-seat end state.

### 2.5 The hidden seat cost that changes the ranking

[MEASURED] ~100 M365 accounts against ~400 staff. [MEASURED] Requesters today are shared consumer mailboxes — `premierelab.113@gmail.com`, `pharmacy_premieremedcenter@yahoo.com`, `pmc2decho@gmail.com`. [INFERRED] Roughly **30 of the 40 target departmental fulfillers are not in the ~100** and have no tenant identity.

- **Kitameraki is a Teams app.** A fulfiller needs a Teams identity, therefore an M365 licence. 30 × ~USD 6/user/mo Business Basic [NOT VERIFIED — indicative] ≈ **USD 2,160/yr = PHP 135,017**, which is *more than the Kitameraki licence itself*.
- **Jira agents need only an Atlassian account**, free to create, MFA-enforceable without an M365 licence. Zero identity cost.
- **A built desk on Entra SSO** carries the same ~30-identity cost as Kitameraki, plus MFA enrolment on personal phones supported by a 2–3 person on-site team. "A seat is an Entra group membership" is true for the licence and false for the seat.

Corrected hospital-wide comparison at 40 fulfillers, 2,000 tickets/month:

| Option | Licence USD/yr | Identity USD/yr | **Total USD/yr** | **PHP/yr** |
|---|---|---|---|---|
| Kitameraki + M365 seats | 3,942 | ~2,160 | **~6,102** | ~381,384 |
| Jira SM Standard | 9,600 | 0 | **9,600** | 600,077 |
| Built desk (hosting) | ~1,366 | ~2,160 | **~3,526** | ~220,403 |

The build's licence advantage is real but **USD 3,500–6,000/yr, not USD 26,000/yr**. At a notional AUD 150/hr, 300 hours of desk-building is AUD 45,000 to save at most AUD 4,900/yr against a contract that expires **30 June 2029 — 2.8 years away**. It does not pay back. That is the whole argument against building the desk, and it is arithmetic, not preference.

---

## 3. Target architecture

**One sentence: the desk owns the ticket; the spine owns the money; nothing commercial is ever authoritative in the desk.**

| # | Component | Runs where | Notes |
|---|---|---|---|
| 1 | **Ticket desk** | Kitameraki (SaaS), unchanged | Keep. Three instances collapse to two boards — fold "Management and Operations Service Board" (0 tickets this period, 1 last) into the Request path. |
| 2 | **`PMC_PSA` — the spine** | **Azure SQL Database, Single, Standard S0**, region **Southeast Asia (Singapore)**, in **PMC's own subscription** | Week one it runs on SQL Express / LocalDB on Dada's Melbourne machine so nothing waits on PMC provisioning. Lifted to Azure SQL at Gate 1. |
| 3 | **Identity** | Entra ID `pmcne.ph` for the ≤4 commercial users only | The spine has no hospital-facing UI, so it needs no seats. Requesters and departmental fulfillers never touch it. |
| 4 | **Commercial UI** | **SSMS + a T-SQL/Excel front end** for Phase 1; a 4-seat Power Apps canvas app only if PMC's finance approver actually needs to click Approve | Deferring the Power App removes a dependency on the on-prem gateway (WS21, open since 3 Sep). |
| 5 | **Reporting pull** | Scheduled task on **DND-SQL01**, **outbound only** over TLS to Azure SQL, read-only login in Windows Credential Manager under a dedicated service account | ~30 lines of PowerShell, a few thousand rows nightly. **No new inbound port-forward** — WS33 is closing 3389/1433/443/5432 right now. |
| 6 | **Escrow** | Nightly JSONL+CSV of every table *and the audit log* → SharePoint `ICT-Delivery-Record` on `sites/management` **and** an Azure Storage container in PMC's `pmc-backups-rg` (southeastasia) | 10-year retention. **Restore test is a gate, not a promise.** |
| 7 | **Documents** | SharePoint item IDs, never path strings | The register's `evidence` column today mixes repo-relative paths, `C:/PMC/...`, `D:\Staging\...` and a parenthetical placeholder — none resolvable [MEASURED]. |
| 8 | **Machine intake** | Watchdog on **PMC-ORTHANC01** → Kitameraki API/webhook | C-ECHO each configured AE, count arrivals/day, raise a ticket when one is quiet for a shift. |

**Backup/DR.** Azure SQL PITR 7 days included, LTR weekly ×52 + monthly ×12 (~USD 1–3/mo). Escrow is the third copy and is readable without the spine existing. If the spine is down, nothing operational stops — tickets keep flowing through the desk and mail keeps accumulating in `helpdesk@pmcne.ph`.

**Nothing in this design touches DND-HOST1** — the single Hyper-V host that also runs the only domain controller, has one 10GbE uplink and **no host-level backup** [MEASURED]. Nothing new is installed on DND-SQL01 except one scheduled outbound task.

### The irreconcilable choice I am making, and why the other loses

**Spine on Azure SQL, not on DND-SQL01\PMC_SS.** The estate argument for co-location is genuinely strong: `PMC_Reporting` is a live-read star schema over `src` synonyms, so a co-located spine is *literally a synonym plus a view* — no ETL, no gateway, no new moving part [MEASURED]. That saving is real and it is worth about one day of work.

It loses to three facts. (a) DND-SQL01 runs the live BizBox HIS with a **173-finding audit open, `sa` enabled, SSRS running as Enterprise Admin and the Domain firewall profile disabled** [MEASURED]. (b) It sits on DND-HOST1, which has no host-level backup, so anything on it shares that fate — and this database *is* the contract record. (c) The exit and ownership argument only works if PMC holds the data somewhere PMC can reach without Dada IT's hands on a hospital server. One nightly outbound pull buys all three. Take the day's extra work.

---

## 4. The commercial model

This is the half no product on the market ships, and it is why the build is justified at all.

### 4.1 Instrument-versioned scope — never store a bare scope number

[MEASURED] Three instruments are in circulation with **three different clause-numbering schemes**, and Amendment No. 1 is drafted against a numbering that does not match the most complete draft:

- `Revised_Contract_DadaIT.docx` — Section 2 items 1–9; Section 4 Investment and Commercial Terms; Section 5 Out of Scope
- `Revised_Contract_DadaIT_FINAL_CLEANED.docx` v1.1 — clauses 2.1–2.10; Section 5 Commercial; Section 6 Change Control; 14.8 governing law Victoria
- Consolidated Revised 04 Jun 2026 (7pp, PMC-signed, Dada IT block blank) — cited at 2.4, 2.9, 4.2, 4.9, 5.3, 7, 10, 12

So the model is:

```
Agreement 1─* AgreementInstrument 1─* InstrumentScopeItem *─1 ScopeItem (9 fixed rows + VAR)
```

`AgreementInstrument`: `type` (AGREEMENT|AMENDMENT|CHANGE_ORDER|ANNEX), `effective_from`, `effective_to`, **`execution_status`** (DRAFT|ISSUED|SIGNED_ONE_PARTY|EXECUTED), `signatory_pmc`, `signatory_dadait`, `signed_on`, `prevails_over_id`, `sharepoint_item_id`, `sha256`, **`payment_terms_days`**, **`payment_terms_basis`** (CALENDAR|BUSINESS), **`dispute_window_days`**.

Payment terms are a per-instrument column because two values are in circulation — **15 business days** (v1.1 §5) and **7 calendar days with a 5-day dispute window** (Consolidated Revised) [both MEASURED]. Never a global constant.

**The nine baseline items, verbatim headings** [MEASURED from the executed-format source]: 1 Network Infrastructure Refresh; 2 Active Directory and Domain Services; 3 Server Virtualization (P2V) / Hyper-V and BizBox HIS; 4 Microsoft 365 Solution Deployment and Collaboration Framework; 5 Backup and Redundancy Infrastructure; 6 Strategic Oversight and Technology Planning; 7 Patient Queuing and Scheduling; 8 Document Archiving and Records Management; 9 License Strategy.

A ticket stores `scope_item_id`. The clause reference printed on any client-facing document is derived from the instrument **in force on the work date**. Nobody ever types a clause number.

### 4.2 The execution gate — with an audited override, because otherwise it gets switched off

Rule: **no Variation reaches `APPROVED`, and no `FeeLine` becomes invoiceable, against an instrument whose `execution_status ≠ EXECUTED`.** This encodes v1.1 cl.14.5 directly.

Its first output is uncomfortable and that is the point: **Amendment No. 1's signature block is blank in every readable copy** [MEASURED], and it is the sole basis for both the AUD 13,000/month currently being invoiced **and** JRBY's inclusion as a covered entity. Under Out of Scope exclusion 9, if it is unexecuted, JRBY is out of scope by default.

A control that blocks the contractor's own monthly invoice will be bypassed within one billing cycle unless it has a designed escape hatch. So: `override_reason` (mandatory free text), `override_by`, `override_at`, an `AuditEvent`, and a line on the monthly **Exception Report**. The gate never silently blocks and never silently yields.

**Sequencing consequence: get Amendment No. 1 executed BEFORE the gate goes live.** Building a self-incriminating instrument on PMC-visible infrastructure before the signature exists is the wrong order.

### 4.3 Variation as a state machine, not a flag

```
IDENTIFIED → RECORDED_IN_ANNEX_B → NOTICED → PRICED → APPROVED → BILLED
terminal: DECLINED · PAUSED_PENDING_AUTHORISATION · PERFORMED_WITHOUT_APPROVAL
```

`PERFORMED_WITHOUT_APPROVAL` is the commercially load-bearing state — Amendment No. 1 cl.4 gives best efforts *"without waiver of Dada IT's right to additional fees"* [MEASURED]. **No off-the-shelf PSA can express "we did the work and we did not waive the fee."** That single state is worth more than the ticketing module.

Fields: `variation_id`, `title`, `annex_b_category` (the four already in Annex B), `entity_id`, `state`, **`sustained_from` (distinct from `approved_on`, for retrospective pro-rating under cl.6)**, `pricing_method` (CAPACITY_UPLIFT | SEPARATE_CHARGE | PASS_THROUGH | DELIVERY_REBASELINE), `eac_percent`, `pma_amount_aud`, `notice_id`, `change_order_instrument_id`. Every transition writes an append-only `VariationEvent` with actor, timestamp, reason.

**The spine IS the Annex B register.** WS28's live action — *"start the Annex B variation register"* — is discharged by emitting Annex B in the agreement's own format, seeded with its four existing categories, of which **"Operational ticketing and facilities-adjacent work"** is already one [MEASURED]. The variation paper for hospital-wide ticketing therefore completes an argument the contract has already made rather than starting a new one.

### 4.4 Time entry — banded, at close, and monthly for open items

[MEASURED] The agreement is a **fixed monthly managed-services fee** with **no rate card, no hourly rate, no hours cap and no SLA** — grep of the full v1.1 text for "rate card", "hourly", "per hour" returns **zero hits**, and "service level" returns only three *disclaimers*.

So time entry's job here is **not** an invoice line. It is **evidence of capacity consumed**, the denominator of `PMA = BMF × EAC%`.

`TimeEntry` — all mandatory, no defaults:
`work_item_id`, `entity_id`, `site_id` (PH01|PH02|REMOTE-MEL), **`contract_basis` inherited from the work item, never set per entry** (BASELINE | VARIATION_APPROVED | VARIATION_PENDING | GOODWILL_NO_WAIVER | INTERNAL_NON_CHARGEABLE), `scope_item_id` (required iff BASELINE), `variation_id` (required iff VARIATION_*), `instrument_id` (derived from `entry_date`), `charge_method`, **`effort_band`** (LT1H | HALF_DAY | DAY | MULTI_DAY → 0.5/4/8/16 h by a versioned mapping), `after_hours`, `review_category` (one of the eleven Amendment No. 1 cl.6 categories, including *governance effort* and *vendor coordination*), **`performed_by_user_id` separate from `entered_by_user_id`**, and `authority_source_{name,role,channel,at}`.

Two corrections to what the proposals all got wrong:

1. **Band open items monthly, not only at close.** Banding at close means the 11 BLOCKED rows and long-runners like WS22 (MRI feed dead since 6 Aug) contribute **zero** effort until they close — the system structurally under-counts precisely the work that best evidences a capacity claim.
2. **`performed_by` is not optional.** [MEASURED] PCSD-1109 was closed by Thobie Dela Cruz writing *"The concern was personally handled by Sir Kevin. The faulty printer was re-cabled…"*. Without the split, all effort accrues to one PMO account and the capacity numbers are wrong.

**Capture baseline time, but do not publish it until the denominator is agreed.** Baseline hours are the denominator and you cannot compute EAC% without them — but publishing an hours record against a fixed fee with no hours cap hands PMC the argument *"AUD 13,000 buys only 70 hours?"*. Keep baseline hours internal until the AC constant is initialled (§4.5).

### 4.5 How a variation invoice is actually produced

This is where every proposal was weakest and where a generic PSA is useless. Annex B says only:

> `Pro-rated Monthly Adjustment = Base Monthly Fee × Estimated Additional Capacity Percentage`
> worked at +25% = AUD 2,875, +40% = AUD 4,600, +60% = AUD 6,900 against BMF 11,500 [MEASURED]

and — critically — **"This Annex is a supporting record only and does not amend the Agreement unless signed by authorized representatives of both parties."** [MEASURED, verbatim]

**No instrument defines the denominator.** Without one, EAC% is a self-reported numerator over a self-declared denominator computed by software written by the party being paid, and PMC's finance function rejects it in one question. So the paper must define it *before* the first uplift:

```
Available Capacity (AC)  = 160 hours per calendar month, one CIO-equivalent   ← A DECISION, not a measurement
EAC%  = round_to_nearest_5( Σ variation effort_hours in month ÷ AC )
PMA   = BMF × EAC%
```

Round-to-5 is not free precision: **5 points = AUD 650/month = AUD 7,800/year of rounding noise.** Round to the nearest 5 *downward* and say so, so the arithmetic is conservative against Dada IT and unarguable against PMC.

And the number must be corroborated by evidence PMC can check independently of Dada's own bands: ticket counts on the variation's boards, dated `Notice` records, `ClientDependency` days-outstanding, and the delivered items with dates. **The narrative is the defence; the band is only the arithmetic.**

**The October 2026 invoice, line by line** (run on the 25th for the following month — billing is monthly **in advance** [MEASURED, v1.1 §5]):

1. **Base fee** — the `FeeLine` where `effective_from ≤ period_start AND (effective_to IS NULL OR ≥ period_end)`, on an EXECUTED instrument → **AUD 13,000.00, VAT-exclusive**. *Today this line fails the gate.*
2. **Capacity uplift** — one line per `Variation` in `APPROVED` with `pricing_method = CAPACITY_UPLIFT`: `AUD 13,000 × eac_percent`. Worked example: 40 variation hours in October ÷ 160 = 25% → **AUD 3,250**.
3. **Separate charge** — **currently unusable.** No rate card exists in any instrument, so Amendment No. 1 cl.3(i) "bill the work separately" has no rate behind it. Blocked until §12 Q7 is answered.
4. **Pass-through** — at cost with the supplier invoice attached (Azure hosting; a desk subscription only if PMC declines to procure it directly).
5. **Retrospective catch-up** — where `sustained_from < approved_on`, one pro-rated line per intervening month, flagged `retrospective`, each with a recalculation-trail row. Authorised by cl.6.

Footer: subtotal AUD, "exclusive of VAT", `due_date = invoice_date + instrument.payment_terms_days` on `instrument.payment_terms_basis`, `dispute_window_days` printed from the same instrument.

**Exception report printed alongside every run:** every line the gate refused, every override and its reason, and every hour of `PERFORMED_WITHOUT_APPROVAL` work in the period. That last number is what makes the six-monthly review a negotiation rather than a plea.

### 4.6 Fee schedule, seeded

| Line | Instrument | Amount | From | To |
|---|---|---|---|---|
| Base Managed Fee | Agreement | AUD 11,500/mo | 2025-07-01 | 2026-06-30 |
| Transition uplift | Amendment No. 1 | AUD 1,000/mo | 2025-07-01 | 2026-06-30 |
| Base Managed Fee | Amendment No. 1 | AUD 13,000/mo | 2026-07-01 | 2029-06-30 |

All AUD, VAT-exclusive, billed monthly in advance, effective-dated with back-dated insertion and a recalculation trail (cl.6 permits retrospective pro-rating; cl.1(e) permits recovery of under-billed amounts) [MEASURED].

### 4.7 The other first-class commercial objects

- **`Notice`** (type PAUSE|SUSPEND|RECLASSIFY|DEPENDENCY|CURE|EXIT|MATERIAL_CHANGE, `sent_at`, from, to, subject, `instrument_id`, `delivery_channel`, `receipt_evidence`, `sharepoint_item_id`). Every commercially material right in the agreement is conditioned on **written notice**. This object alone is worth more than the ticketing module.
- **`ClientDependency`** (`raised_on`, `owner_contact_id` — a *named person*, not "PMC", `owner_department`, `scope_item_id`, `work_item_id`, `days_outstanding` computed, `notice_id`, `impact`). [MEASURED] **11 register rows are BLOCKED with a named owner and not one recorded notice against any of them.** Section 3's relief entitlement is conditioned on that notice. Dada is accruing an entitlement while destroying the evidence that activates it.
- **`Reclassification`** (old_basis, new_basis, changed_by, changed_at, reason, instrument_ref, notice_ref) — basis changes are *events*, never edits. Standing report: *"items classified VARIATION whose subject matter appears in a baseline inclusion list."* First hit: **WS22 / PACS Voyager** — the agreement's Scope of Inclusions says *"Existing support for PACS Voyager will be integrated into the scope"* while the register carries WS22 as a variation [both MEASURED]. One of those is wrong and it is worth money at the review.
- **`DecisionNote`** (`advisory_at`, `decision_at`, risk, recipients, outcome) with a hard `CHECK (advisory_at < decision_at)`. v1.1 §9 limits liability where management proceeds against advice *"to the extent such risk was clearly communicated in writing beforehand"* — a shield that only works if the writing pre-dates the decision.

### 4.8 How the PSA itself is funded

It is a **variation**, on four independent grounds [all MEASURED]: Out of Scope exclusion 3 (third-party licensing/subscriptions); exclusion 5 (custom software development); v1.1 cl.6(c) (recurring operational workstreams beyond baseline); cl.6(b) plus scope item 4's own pricing assumption of *"approximately one hundred (100) licensed users"* — 400 requesters and 40 fulfillers is 4×. And Annex B already names *"Operational ticketing and facilities-adjacent work"* as a variation category, while cl.2.10 names *"ticket handling"* as not included for additional entities.

Three separable lines, and separating them is what makes it approvable:

| Line | Instrument | Amount |
|---|---|---|
| **(a) Platform + hosting** | **Pass-through, PMC procures directly in its own name** — mirroring the M365 user-licence precedent already accepted under scope item 9 | Azure SQL S0 **USD 177/yr = PHP 11,041**; desk subscription as chosen |
| **(b) Build the spine** | One-off change order, **AUD 6,500** (half a month of BMF) | Once |
| **(c) Run** | **Phase 1–2: EAC 0%.** Claimed under baseline scope item 6 *"periodic executive reporting"* — PMC pays nothing extra and Phase 1 starts this week without waiting for approval. **Phase 3 (hospital-wide): +20% = AUD 2,600/mo.** Phase 4 reviewed at the six-monthly review. | — |

Keeping (a) as PMC's own procurement is what makes PMC the licensee — the cheapest and strongest answer to the ownership problem.

**Frame the notice as a REGULATORY material change** under Section 4, an *enumerated* trigger — *"regulatory or accreditation requirements mandating major system changes or new integrations"* [MEASURED] — citing **DOH Level 3 assessment item 49, RA 10173, marked NOT COMPLIED** in PMC's own licensing pack [MEASURED, `Premiere Medical Center - Level 3 Hospital.xlsx`, form DOH-HOS-LTO-ATPI Rev.01]. That framing starts a 15-business-day negotiation clock with the agreement in full force, needs no procurement cycle, and survives a board challenge that "a better helpdesk" would not.

---

## 5. The service catalogue

### 5.1 Structure — five tables, not a per-board tree

`board → service_family → service_component → service_action`, plus a **curated junction of valid triples** (`catalogue_item`). The verb set is **shared across all boards**. ConnectWise scopes Types and SubTypes *per board* [VERIFIED via docs.connectwise.com: System > Setup Tables > Service Boards > [board] > Types tab] — at 14 hospital boards that is 14 maintenance surfaces for one tree. **A defect to avoid, not a pattern to copy.**

Each `catalogue_item` carries `default_scope_item_id`, `default_contract_basis`, `clinical_impact`, `min_priority`, `restricted`, `default_board_id`. **Defaulting scope item and contract basis from the catalogue is what lets a nurse file a ticket without ever seeing a commercial field.**

### 5.2 The ConnectWise sheet, mapped in — specific rulings

| The sheet says | Ruling | Why |
|---|---|---|
| Sheet1 vs Sheet3 disagree on families and Type axis | **Sheet3 wins on names and structure** | It correctly removes Incident/Request from the Type axis — that axis is the *board*, exactly as Sheet1's own header says |
| Sheet1 `Administration > Agreement` (dropped in Sheet3) | **RESCUE IT** | The only catalogue hook for the commercial path. Becomes the Request board's entry: *Raise a variation*, *Change to fee*, *Six-monthly review*, *Client dependency notice* |
| "On prem" and "hosted infrastucture" | **Collapse to one family, `Servers and storage`** | Identical twelve-child lists in both sheets [MEASURED]. Hosting location is an **attribute of the CI**, not a branch — SQL Server exists on DND-SQL01 and would exist again in Azure |
| `SECURITY???` with RADIUS as its only child | **Delete.** RADIUS moves under Networking | RADIUS is network access control. Create a real **restricted Security & Privacy board**: account compromise/phishing; malware; unauthorised access; data-loss/privacy incident (RA 10173); audit-finding remediation — the 173 open findings are its first backlog |
| The `im up to here` marker at IP Telephony > Handset | **Everything below is DRAFT** | PBX, IVR, Number, Voice mail, the ~20-entry Application family and Reports and Audits were never worked through. Say so in the handover; do not present a finished catalogue |
| Sheet2 (~230 entries) | **Discard entirely** | A 2020-era Ninite/Automate patch inventory — Chrome 81.0.4044.129, Firefox 75.0, Flash 32.0.0.363, Java 8u251 [MEASURED]. Contains **no** BizBox, Orthanc, SSRS, Power BI, PhilHealth eClaims, queue.pmcne.ph or AnyDesk. Applications become **CMDB items a ticket links to** — this picklist went stale by six years |
| Item column: Install/Modify/Access Controls/Decomission/Degredation/Outage/Failure ×~100 with drifting case | **Normalise to six canonical verbs + curated triples** | It is a hand-written cross-join |
| Ten misspellings: `Certifcates/SSL`, `Degredation`, `Decomission`, `Romm and equipment`, `hosted infrastucture`, `Distrubution List`, `Link unstable/dgraded`, `Differnet SLA's`, `Update agement`, `unsupport application` | **Normalise once at load, with a stable `machine_id` separate from `display_name`** | These land in `rpt.Dim*` and then on an executive's screen. WS07 already paid to remediate 450 label defects once |
| Margin note: *"outage = service failure / failure = local /hardware failure"* | **Keep and formalise: outage = a shared service or clinical service is down (Impact I1); failure = one device or one user (Impact I3)** | The single genuinely load-bearing definition in the workbook, and it is the impact axis the priority engine needs |
| Firewall items | **Extend to port-forward, DMZ, NAT** | WS33 is closing 1433/3389/443/5432 right now; those tickets exist today |
| "Should we split internal vs external users?" (asked twice) | **No** | Audience is an attribute, not a branch |

Missing entirely and must be added: **Modality/imaging, HIS/BizBox, PACS, PhilHealth, biomedical equipment, medical gas, facilities, housekeeping, dietary.** Every one is a hospital board's core content.

### 5.3 Three ticket paths, not two

The worksheet's two-board line — *"Request board = change to agreement/fee"*, *"Help board = it is broke please fix it"* — is the commercial model in one sentence and it is right. But it collapses in-baseline service requests with fee-bearing variations: its own Request list contains *"Onboard new user"*, *"New Shared Mailbox"*, *"Create security group"*, which sit squarely inside baseline items 2 and 4 [MEASURED].

1. **Incident** — restore service. Consumes the fee. No commercial event.
2. **Service Request** — in-baseline fulfilment. No fee. **Still scope-mapped.**
3. **Variation** — outside the nine items. Must create or attach to a `Variation` before it can consume effort.

**Keeping only two boards makes every new-user request look like a fee event and will destroy PMC's willingness to use the Request path at all.**

### 5.4 Priority is computed, never chosen

Impact **I1** hospital-wide or a clinical service / **I2** department or multi-user / **I3** single user. Urgency **U1** patient care stopped or a safety/regulatory exposure now / **U2** degraded, workaround exists / **U3** no care impact.

```
priority = LEAST( matrix(impact, urgency),
                  catalogue_item.min_priority,
                  CASE WHEN catalogue_item.clinical_impact = 1 THEN P2 END )
```

The requester answers **two plain questions** — *who is affected?* and *is a patient waiting?* — and never sees a priority dropdown. [VERIFIED] ConnectWise cannot do this natively: severity, impact and priority are three independent fields with no derivation, corroborated by an open product-community request for exactly this.

**Hard P1 floors no fulfiller can lower, enforced at raise *and* at close:** ward oxygen outlet, medical gas manifold, blood-bank fridge alarm, defibrillator failed self-test. Lowering below a clinical floor requires a named clinical escalation role (Nursing Supervisor / Duty Manager), a typed reason, and an `AuditEvent`. **The clinical floor list is signed off by the Chief of Hospital / Chief Nurse / Quality officer, not by Dada IT.**

### 5.5 SLA — measured, not enforced

Three clocks (respond, resolution plan, resolve), each with its **own** target, calendar and attainment percentage stated separately. The sheet's three numbers are incommensurable as written: *"response within 1 day"* is a per-ticket target, *"90% within 2 hours"* is a population percentile, *"16 hours"* has no calendar attached.

Two calendars minimum: **24×7 clinical** and **Asia/Manila business hours**. A **pause state** ("waiting on client", "waiting on vendor") that stops the resolve clock — without it, 11 of 35 register rows report as breach on day one.

**Ship all targets with `enforced = 0`.** The agreement contains no response or resolution commitment and three clauses actively disclaim creating one [MEASURED]. Turning on enforcement silently creates an obligation Dada IT is not paid for and a 2–3 person team cannot meet.

And **withdraw or contract the current auto-responder.** It publishes to the whole hospital, verbatim: *"We are planning on responding to you within the hour. For new account creation, device/networking setup, other complicated issues and requests expect a resolution within 1-2 business days"* — with no operating hours stated, against an agreement containing no such commitment [MEASURED, ITO-1724, 7 Sep 07:41Z]. Replace with a plain-language acknowledgement stating actual hours of cover and that targets are internal measures.

Dada IT's SLA covers **only** IT Help, IT Service Request and Agreement & Variation. The Agreement & Variation board gets **no resolve clock at all** — an acknowledge clock (2 business days) and a decision clock (5 business days to a priced paper).

### 5.6 The boards and who fulfils each

| Board | Named fulfiller group | Phase | Restricted |
|---|---|---|---|
| IT Help (incident) | Dada IT + on-site Windows team (Cadano, Gabelo, Asuncion) | 2 | no |
| IT Service Request (in-baseline) | same | 2 | no |
| Agreement & Variation | Dada IT / PMO (Dela Cruz, Simon) | 2 | **yes** |
| Security & Privacy | Dada IT + DPO | 2 | **yes** |
| Biomedical & Clinical Equipment | Biomedical technician, vendor-escalated | 3a | no |
| Facilities & Engineering | Facilities/Engineering supervisor | 3a | no |
| Housekeeping & Environmental Services | Housekeeping supervisor | 3a | no |
| Finance & Purchasing | Finance/Purchasing officer | 3a | no |
| HR | HR officer | 3a | partial |
| Physical Security & Safety | Security supervisor | 3b | incidents **yes** |
| Medical Records / HIMS | Medical records officer | 3b | **yes** |
| PhilHealth Claims | PHIC unit | 3b | **yes** |
| Dietary / Nutrition | Dietary supervisor | 3b | **yes** |
| Nursing / Ward Services | Nursing supervisor | 3b | **yes** |

**Rule, no exceptions: one accountable fulfiller group, one named owner, one named deputy, its own SLA. No named owner, no board.** A board with no owner is worse than no board.

Plus a default **Unrouted** queue owned by the PMO coordinator with an ageing rule that pages IT — today triage is one person (Thobie Dela Cruz) and when she is unavailable the path is a personal Teams chat to a CIO in another country [MEASURED].

**Cross-board handover is ONE ticket with a changing owner**, never two linked tickets, with `handover_at` recorded and reported as a metric. The MRI-to-PACS fault is simultaneously biomedical (the scanner) and IT (DICOM/AE title/network); two tickets each waiting on the other is exactly what produces a 25-day outage.

### 5.7 Seed the boards from the register — do not launch them empty

[MEASURED] WS24 laboratory HL7, no results since 30 Aug → Biomedical. WS22 MRI feed dead since 6 Aug, AE `AN_WP179248` → Biomedical/imaging. WS11 MB360 biometric dark since ~01:55 on 8 Sep, 545 punches loaded by hand → HR/DTR. WS04 procurement, 44 request lines never supplied → Finance & Purchasing. WS25 PhilHealth CF4 back-page defect → PhilHealth. WS10 wage distortion blocked on HR/Finance → HR.

Launching populated is the fastest credible proof the boards were needed.

### 5.8 Governance rules on the catalogue itself

No family with a single child (this alone kills `SECURITY???`). No item with zero volume after a quarter, reviewed quarterly against actual counts. **At most three clicks from a requester's start to a fileable ticket**, with the deeper tree visible only to fulfillers. Search-first filing beats tree navigation for 400 clinical staff.

---

## 6. Governance

### 6.1 The RA 10173 position, stated plainly

PMC is the **personal information controller**. Dada IT is a **processor**, operating from Melbourne. The desk vendor is a **sub-processor**. RA 10173 s.6 reaches Dada IT regardless of the agreement's Australian choice of law, and s.21 keeps PMC accountable for data transferred to third parties [VERIFIED, lawphil.net].

[VERIFIED] There is **no adequacy gate and no prior-authorisation requirement** — NPC Advisory No. 2024-01 (30 May 2024) makes model contractual clauses **voluntary** and states the NPC will not review agreements for conformity. Offshore processing is lawful **if accountability is discharged**. That removes the reflexive "must be hosted in the Philippines" objection and shifts 100% of the burden onto paperwork.

[MEASURED] **There is no Azure region in the Philippines.** Nearest are Southeast Asia (Singapore), Malaysia, Indonesia. "Keep it in-country" is not purchasable on any cloud. The honest choice is *which* foreign jurisdiction, and Singapore is defensible.

### 6.2 The gate: what must be signed before the first hospital ticket

[MEASURED] The ICT Service Agreement contains **none** of the IRR s.44 outsourcing particulars, is governed by Australian law, contains the word "escrow" **zero times**, and has **no data-return clause at all**. The promised NDA covering *"more specific confidentiality, data handling, and personnel responsibilities"* appears never to have been executed; Annex C left the data-processing addendum as an open pre-signature checklist item.

**G-a. Execute a processor annex** carrying every IRR s.44 particular: subject-matter and duration; nature and purpose; types of personal data; categories of data subjects; recipients; **proposed transfers outside the Philippines, naming Melbourne and Singapore explicitly**; and a description of privacy and security measures. Plus: processing only on PMC's documented instructions; named sub-processors with a change-notice right; personnel confidentiality; **immediate** breach notification to PMC's DPO on discovery (PMC's 72 hours starts on the *processor's* knowledge [VERIFIED, IRR s.38 / NPC Circular 16-03]); audit right; return-and-delete on termination. **Adopt ASEAN Model Contractual Clauses by reference** — voluntary, and the cheapest available demonstration of accountability at a review.

**G-b. PMC owns the tenancy.** PMC is the billing account, org admin and holder of the break-glass credential for the desk, the Azure subscription and the M365 tenant. Dada IT holds an administrator **seat**, not the account. This costs nothing on day one and is very expensive to retrofit. It converts exit from a data-recovery problem into an access-management one.

**G-c. PIA on file and an NPC data-processing-system registration entry.** PMC crosses NPC Circular 2022-04's thresholds on both counts (250+ persons; sensitive personal information of 1,000+ individuals). Carry `pia_on_file` and `npc_registered` as **fields on the PSA's own CI record**, so the state is auditable rather than remembered.

**G-d. The DPO's written determination on foreign processing.** Open in the record since at least 7 September. Ask this week, in writing.

**G-e. Amend PMC's privacy manual in the same board paper.** [MEASURED] `49. PMC DPA POLICY.pdf` is written around **"Comlogik Hospital Information System"** while the live HIS is BizBox HIS 8 (8.26.15.47); it contains **no breach-notification timeline at all**, no NPC registration section, no processor section beyond one line, and **no IT/service-desk row in its departmental scope list**. Adding the service desk, the 72-hour clock, a processor section naming Dada IT and the vendor, and ticket retention is **billable inside baseline scope item 6** (*"Support in ensuring compliance with the Data Privacy Act and DOH/PhilHealth IT standards"*) — one of the very few PSA-adjacent activities unambiguously inside the nine items, and therefore **free to PMC**. It is also the strongest single argument for approving the variation.

### 6.3 Patient data in tickets — already happening

[MEASURED, 9 Sep 2026 06:57Z] A message to `helpdesk@pmcne.ph` from the external consumer mailbox `premieremedicalcenterdots@gmail.com`, titled *"REQUEST TO EDIT CHARGE DATE"*, carrying a **named patient and a PhilHealth case number** in the body. This is a live control problem today, on the same address as printer faults.

Six controls, all mandatory:

1. **One named, maskable `patient_reference` field.** Identifiers **never** in the subject line — subject lines propagate into Teams cards and email notifications.
2. **Default-restrict all inbound mail to a triage queue.** Do **not** rely on a regex PHI classifier as the boundary between a housekeeping supervisor and a patient name — a false negative is a 72-hour NPC clock. Pattern matching may *escalate*; only a human release moves a ticket to a departmental board. This is the one place where the extra friction is unarguably worth it.
3. **Erasure resolves to redaction, not deletion.** IRR s.34 erasure grounds are conditional and are overridden where retention rests on another legal ground (DOH RDS, a PhilHealth claim hold). "Erase" = redact the payload, retain ticket id, timestamps, actors and state transitions, write a logged DPO-performed redaction event. **Any product whose only privacy tool is "delete the ticket" is disqualified.**
4. **Restricted-board notifications carry subject and reference only, never the body.**
5. **`PrivacyIncident`** with a mandatory `discovered_at`, a computed 72-hour NPC deadline modelled as a **legal deadline** not a service target, a DPO-only queue invisible to the fulfiller seats, and the 5-day full-report artefact attached.
6. **Least privilege by default.** Departmental fulfillers see only their own queue. Cross-department read is an explicit grant, never a role default. A flat 40-seat agent model with global read is a proportionality failure under s.18(c) before it is a security one.

**The escrow/erasure conflict, resolved.** Two of the three proposals put the nightly escrow into an Azure blob container with an **immutability policy** — and you cannot redact an immutable blob. That creates an undeletable third copy of PHI and makes the PIA unsignable. **Resolution: two escrow tiers.** The **audit-log tier** (actor, timestamp, object, field, state transition — *no free text, no ticket body*) gets the 10-year immutability lock. The **content tier** (ticket bodies, notes, attachments) gets 10-year *retention with versioning*, no immutability lock, and a documented redaction procedure that propagates to all versions and logs itself. Redaction remains possible; the audit trail remains tamper-evident.

### 6.4 Audit trail

Every core table is a SQL Server **system-versioned temporal table** — per-field before/after history with no application code to forget. On top, an append-only application `AuditEvent` log records what temporal tables cannot: reads of restricted records, exports, redactions, priority overrides below a clinical floor, execution-gate overrides, and every variation state transition.

**Named accounts only.** [MEASURED] The shared account `encoder@premieremedicalcenter.net` ("PhilHealth Encoder") is commenting on tickets today, which destroys attribution, effort data and audit simultaneously. Shared mailboxes remain valid **requester** channels; they can never hold a fulfiller seat.

**Prerequisite: fix NTP and the single-DC time source (open in WS12).** A 72-hour breach clock, an SLA clock and a DOH corrective-maintenance log are each only as defensible as the clock behind them.

One trail, four audiences: NPC, DOH/HFSRB, the PMC board, the six-monthly contract review.

### 6.5 Retention

[VERIFIED] DOH Department Circular No. 2021-0226 (31 May 2021): **in-patient health records 10 years; out-patient 7 years after last consultation.** [MEASURED] PMC's own board policy: *"No box or record may be destroyed solely because the earliest disposal review date has arrived"*, and before disposal *"Compliance/DPO must confirm no privacy, legal, regulatory, complaint, or investigation hold"*, with a disposal log carrying batch number, retention basis, method, approver, witness and certificate.

Per-board `RetentionPolicy`, **minimum 10 years** for any board that can touch a patient or a medical device — not a vendor's default. `LegalHold` blocks purge and survives export. Disposal emits a log in exactly the shape the board policy specifies.

**That board policy is currently UNAPPROVED** — blank effective date, seven blank signature lines [MEASURED]. Ticket retention has no defensible basis until it is signed. Put it in the same board paper; it is a cheap win.

**Kitameraki's retention controls are NOT VERIFIED.** Its vendor-side horizon is therefore the working surface, and the **spine plus the PMC-controlled escrow is the retention system of record at 10 years.** State that plainly in the PIA rather than claiming a control you have not tested.

### 6.6 Medical devices are DOH-inspectable evidence

[MEASURED] HFSRB tool item 11 requires a *"PREVENTIVE AND CORRECTIVE MAINTENANCE LOGBOOK"*; item 15 requires *"Records of preventive and corrective maintenance and plan for replacement"*; item 16 requires *"For outsourced service: MOA/Contract"*. DOH AO 2012-0012 requires a calibration/PM/repair programme and a contingency plan for equipment breakdown.

**The 25-day MRI outage that produced no ticket was also a gap in a DOH-inspectable maintenance record.** Every medical-device ticket must be exportable as a per-asset corrective-maintenance log over a multi-year window. That is a hard export requirement and it disqualifies any product whose reporting cannot slice tickets by asset over years.

### 6.7 Exit

[MEASURED] The agreement gives PMC only a *"non-exclusive internal-use right"* to deliverables (v1.1 §11); *"Significant exit or transition assistance beyond a reasonable handover shall be separately chargeable"* (§13); a **six-month exit fee** — **AUD 78,000** at the current rate — on a fixed 48-month term ending **30 June 2029**, non-renewing by default with a 90-day renegotiation window opening 1 April 2029.

The variation annex must add: PMC named licensee and tenant owner; **ticket, time, agreement and CMDB data declared PMC property**; a scheduled export in a documented open format to PMC-controlled storage as a **contractual deliverable**; return-and-delete on termination; **and a PSA/desk term that does not outlast 30 June 2029**, with the spine warning on any subscription whose renewal or exit date falls outside it.

**And one thing that must move in the opposite direction.** [MEASURED] Dada IT's Australian client archives — The Lumery, Southgate Trust CBRE, Butler Market Gardens — sit inside PMC's tenant in `sites/management-Management`. A PSA sold as a PMC-owned two-entity record while three unrelated Australian clients sit in the hospital's tenancy is indefensible at audit. Schedule that removal before Phase 3.

---

## 7. Migration

### 7.1 Off the CSV register — now

[MEASURED] The CSV holds **35 rows, WS01–WS35**. `docs/programme-register-and-plan-2026-09-08.md` §2 renders **34** and omits WS35; three separate places in the record say "34 rows"; WS35 sits physically out of id order between WS15 and WS16. [MEASURED] On 8 Sep at 12:57 two machines saved `PMC_START_HERE.md` and `docs/_INDEX.md` from different copies and OneDrive kept the later one — **a day of notes lost, no conflict copy.**

That drift and that loss are the whole argument for a database. Load all 13 columns losslessly:

| CSV column | Lands as |
|---|---|
| `id` | `WorkItem.reference` — **`WS01`…`WS35` kept verbatim.** No second taxonomy; the SharePoint `Workstream` column keeps working |
| `entity` | `Entity` link. `PMC+JRBY` → **two rows**, not a string. `Dada IT` → DADA-IT-INTERNAL. `UNCLASSIFIED` is a real state (WS17) |
| `scope_item` | `WorkItemScopeItem` many-to-many with `relation`: `2->8` → SEQUENCE; `3+5` → BOTH; `4/8` and `1/2` → EITHER with `is_primary`. `VAR`, `JRBY`, `?` → sentinels. **Nothing flattened** |
| `contract_basis` | Enum. `variation (Amendment 1)` splits into basis + `instrument_id` |
| `status` | `status` + `substatus` — `DONE (filed; execution unverified)` → `DONE` / `filed; execution unverified`, so DONE stays machine-countable |
| `blocked_on` | A `ClientDependency` per BLOCKED row, with the **named person** parsed out (*"Chief Pharmacist (Ms. Abad), question 18"*) and `notice_given = 0` |
| `next_action` | Split on the pipe-and-timestamp pattern into dated `WorkItemNote` rows — WS07's cell is **~4,000 characters with at least six timestamped entries**. **The raw original is retained verbatim as note zero**; anything unsplittable is flagged `needs_split` and counted |
| `last_activity` | `datetime2`. `unknown` (WS31, WS32) → NULL **plus a DataQuality row** — never dropped, never guessed |
| `evidence` | Semicolon-split, each resolved to a SharePoint item ID. Unresolvable strings (`C:/PMC/PowerBI/dev/build`, `D:\Staging\...`, `(to be collected via Graph/Entra)`) land in `DocumentUnresolved` with the raw text |

Structural facts recovered that the CSV cannot express: **WS35's parent is WS15**; **WS22 and WS23 are one imaging programme**.

**Cutover discipline: one week of dual-running, then the CSV write path is deleted** and `PMC_Workstream_Register_YYYYMMDD.csv` becomes a generated export filed on the Friday programme block. **If the hand-edited CSV survives past that week, the spine has lost.** That is a gate, and it is the failure mode that kills the whole thing.

### 7.2 Off Kitameraki — pre-positioned, not executed

We are **keeping** the desk, so this is an archive exercise, not a migration. But do it **now**, because vendor cooperation cannot be assumed:

[MEASURED] WS08 records a Kitameraki outage diagnosed as **vendor-side, with a support email drafted and never sent.** A vendor in an unacknowledged dispute is a vendor who may not help with an export later. **Send that email this week** — PMC's board may reasonably ask why the incumbent was never held to its SLA before a replacement was contemplated.

1. **PMC's own administrator runs the export**, using credentials PMC already holds. **No agent in this run — including me — asks for, records, quotes or uses any API key.**
2. Export all three instances to CSV + JSON with attachments, verify **20 sampled tickets field-by-field against the UI** (including one with attachments and one with a long internal thread), and file into SharePoint `ICT-Delivery-Record` as DocType=Evidence, Sensitivity=Restricted, retention 10 years. Record the verification as dated evidence.
3. **The real archive is the mailbox, not the tool.** [MEASURED] `helpdesk@pmcne.ph` holds **3,210 messages back to 16 Oct 2024**, and every ticket generated email. Apply a **Purview 10-year retention policy to `helpdesk@` and `support@` this week.** That, not Kitameraki, is PMC's durable record — and it means a total vendor export failure still leaves PMC holding two years of the actual correspondence, keyed by the `ITO-`/`PCSD-` reference in the subject line.

**What is lost, and I will not pretend otherwise.** Internal comments and private notes; attachment fidelity; workflow, automation and custom-field configuration; SLA clock history and first-response timestamps; per-ticket assignee history; and — whenever the desk eventually changes — the `ITO-`/`PCSD-` numbering sequences. Every future ticket carries a `legacy_ref` so an inspector can still resolve an old citation, but the sequences end. SLA history is the least painful loss: it measured a promise that was never contracted.

---

## 8. Reporting

**Feed the existing model. Never build a second one.**

[MEASURED] `PMC_Reporting` on `DND-SQL01\PMC_SS` is a live-read star schema: `src` synonyms over `LIVEDB_PMC`, `rpt.Dim*`/`rpt.Fact*` views on top, a nightly SQL Agent job *"PMC Reporting - Nightly Stock Snapshot"* at 23:30, feeding a published **46-page** Power BI report (semantic model `9af7856e`, report `5162c395`, workspace "PMC Analytics", PPU 25 seats assigned 8 Sep).

[MEASURED] **The decisive fact:** `Generate-PowerBI-Model-TMDL-20260907.sql` is read-only and *"prints the Power BI semantic model (tables typed from sys.columns, relationships, ~100 DAX measures, Entity RLS roles) as a TMDL script"* — and *"the model is generated from whatever rpt.\* views exist when it runs."*

**Mechanism.** Nightly scheduled task on DND-SQL01, outbound over TLS to Azure SQL, incremental by `rowversion`, MERGE into a `psa.*` staging schema in `PMC_Reporting`, then `rpt.*` views over it, added as **step 3 of the existing 23:30 job**. No new job, no new schedule, no new gateway, no new inbound port.

**Views added:** `rpt.DimAgreement`, `rpt.DimInstrument`, `rpt.DimScopeItem`, `rpt.DimVariation`, `rpt.DimEntity`, `rpt.DimSite`, `rpt.DimBoard`, `rpt.DimCatalogue`, `rpt.DimConfiguration`, `rpt.DimWorkstream`, `rpt.DimContact`; `rpt.FactWorkItem`, `rpt.FactWorkItemState` (one row per transition — this is what makes ageing, handover time and SLA attainment computable), `rpt.FactEffort`, `rpt.FactVariationLine`, `rpt.FactClientDependency`, `rpt.FactNotice`, `rpt.DataQualitySummaryPSA`. Built in the existing `rpt.usp_BuildSimpleDim` one-paste idiom and registered in `rpt.BuildLog` / `rpt.BuildManifest`.

Then **re-run the TMDL generator**. The 46-page report gains every PSA table with **zero hand modelling**, and the Entity RLS roles it already generates cover PMC/JRBY separation automatically (WS34).

**The joins that only exist because the data reaches this model:**
- `FactWorkItem` → `DimDate` → `FactMidnightCensus`: housekeeping terminal-clean turnaround against bed occupancy — **78.4% of 125 DOH-licensed beds in August, 11 of 35 nights above 125** [MEASURED]. The housekeeping board pays for itself in a measure PMC has already built.
- `FactWorkItem` → `DimConfiguration` → imaging exam counts: modality downtime against studies not performed.
- `FactEffort` → `DimScopeItem`: effort inside the fixed fee vs effort attributable to variations — the EAC% denominator.

**What this avoids.** [MEASURED] The SaaS-only pattern is already designed, written and never run (`docs/powerbi-internal-dashboard-2026-09-03.md`, WS08 **BUILT-NOT-RUN**), and its own design note states why it is expensive: *"The API returns 'now', not history. Connect directly and you can never chart last month, because last month was never stored anywhere."* Since we are keeping Kitameraki, **that collector must finally be run** — it is the ticket-volume feed. But it feeds `stg.Kitameraki*` alongside `psa.*`; it is not a second model.

**Honest dependency, do not oversell.** [MEASURED 8 Sep] There is **no on-premises data gateway**; PowerShell Gallery is blocked; the published report shows data because it was published from Desktop, not because a refresh runs. The gateway needs **one user sign-in** (`Add-DataGatewayCluster` requires a user credential) and **two portal clicks**. Until then, PSA reporting is **manual-refresh only.** Say that; do not promise a live dashboard in week one.

**Reporting rules inherited, non-negotiable.** Never exclude data: rows with missing entity, missing scope item, `last_activity = unknown` or a contradictory CI field are **flagged and counted**, never filtered. Stable machine ids with separate display names so the ten catalogue misspellings can be fixed without orphaning `rpt.Dim*` members.

**The six-monthly review pack is generated, not written.** It emits, as counts at a date, all **eleven** things Amendment No. 1 cl.6 names — supported entities, user counts, sites, systems, software, projects, integrations, governance effort, vendor coordination workload, compliance requirements, additional/legacy work — grouped by scope item, with delivered items and dates, evidence resolved to SharePoint URLs, open risks, outstanding client dependencies with days-outstanding and notice status, the Annex B variations section with `PMA = BMF × EAC%` worked, and the data-utilisation count. **This is the acceptance test that separates a PSA from a helpdesk.** It replaces `Build-EvidencePack.py`, which is a skeleton that does not yet exist — so nothing is lost by moving it into the spine.

---

## 9. Phased plan with gates

A gate is a fact, not a date. Nothing that costs money happens before Gate 1.

### Phase 0 — this week, days 1–5. USD 0. No procurement, no approval, no dependency on PMC.

The genuinely Dada-controlled items, in order:

1. **Alias `support@pmcne.ph` onto `helpdesk@pmcne.ph`.** One hour. Kills the measured double-creation.
2. **Rewrite the auto-responder** — withdraw the uncontracted "within the hour" promise, state actual hours of cover.
3. **Apply 10-year Purview retention** to both mailboxes.
4. **Send the WS08 Kitameraki support email.**
5. **Write the eleven client-dependency notices by hand**, from the CSV, and send them. This needs no code, no database and no platform. Section 3's relief entitlement is conditioned on written notice and there is not one recorded against any of the 11 BLOCKED rows.
6. **Write the instrument exception memo by hand** — one page saying that AUD 13,000/month and JRBY's status as a covered entity both rest on a blank signature block.
7. **Create the repo** `platform/psa-spine/` and start the schema (§10).

Then the items that leave your hands:

8. **Issue the variation notice in writing**, framed as a **regulatory** material change under Section 4 citing DOH assessment item 49 NOT COMPLIED. This starts the 15-business-day negotiation clock *in parallel with everything else*, with the agreement in full force meanwhile.
9. **Write to the DPO** with the foreign-processor question and the draft s.44 annex.
10. **Ask PMC three questions in writing**: is Amendment No. 1 executed and on what date; which instrument is operative; will PMC hold the tenancy in its own name.

**Gate 0 →** single intake proven for three consecutive days with zero duplicates; auto-responder replaced; eleven notices sent and receipted; exception memo issued; repo created.

*Note honestly: items 8–10 inherit the estate's measured latency. 11 of 35 rows are BLOCKED on PMC and Lane C exists as a whole operating lane precisely because PMC does not answer quickly. Items 1–7 are this week; 8–10 are issued this week and answered when they are answered.*

### Phase 1 — weeks 2–4. The commercial spine. Dada only, no seats, no hosting decision.

Schema, importer, three generators (§10). Runs on SQL Express locally, then lifts to Azure SQL S0 in PMC's subscription. Time entry starts here, banded, on Dada alone — **if it does not stick for one person for three weeks it will not stick for forty.**

**Gate 1 →** all 35 rows imported losslessly with zero data-quality rows silently dropped; the Annex B register reconciles line-for-line with the CSV's 20 `contract_basis = variation` rows; the six-monthly review pack names all nine scope items and lists the 11 dependencies with days outstanding; **three weeks of unbroken banded effort capture.** Spine lifted to Azure SQL. **If PMC declines the variation, the programme stops here** — and what has been built is still valuable, because the register, the variation evidence and the review pack are baseline obligations under items 6 and 8 anyway.

### Phase 2 — weeks 5–8. Prove or disprove the incumbent. USD 0 in new licences.

Configure Kitameraki against **four acceptance tests**, all pass/fail:

1. **Machine intake.** The modality watchdog on PMC-ORTHANC01 raises a **real ticket** against the GE 1.5T (serial 179248) when `AN_WP179248` is quiet for a shift, via Kitameraki's API/webhook. *Add a heartbeat on the watchdog itself, or the thing that detects silence will go silent silently.*
2. **Commercial fields.** `scope_item`, `contract_basis`, `entity` and `variation_id` exist as custom fields, default from the catalogue, and come out through the API into `stg.Kitameraki*`.
3. **Restricted board.** A departmental fulfiller is **provably unable** to read a ticket on the restricted instance — proven by test, recorded in the PIA. This is the one I genuinely doubt.
4. **Reporting.** `rpt.FactWorkItem` appears in the regenerated Power BI model with no hand modelling; ticket counts match the desk within 1% for three consecutive nights.

Also in Phase 2: fold the "Management and Operations Service Board" instance (0 tickets this period, 1 last) into the Request path; run the collector that has been BUILT-NOT-RUN since 3 September; install the gateway; fix NTP (WS12); **retire the CSV write path.**

**Gate 2 →** four tests pass, or a written note saying which failed and why. **Gate 2 is the desk decision gate** — see §9.1. Register CSV is a generated export.

### Phase 3a — weeks 9–14, only on variation approval. Non-PHI departments.

Facilities & Engineering, Biomedical, Housekeeping, Finance & Purchasing, HR. Seeded on day one from the register's open rows. Seats to 10, then 25.

**Per-board gate, no exceptions:** a named owner, a named deputy, a completed **two-hour induction** covering four actions only (accept, note, reassign, close with a resolution sentence) and **one privacy rule** — *if a ticket names a patient, reassign it to the restricted board and stop reading* — a retention policy set, and the restricted flag set.

**Gate 3a →** a management instruction from Mr. Yang or the department heads that after a stated date, **work is accepted only through the service desk**, with a named emergency exception ticketed retrospectively. Without that instruction the desk is a fourth channel and adoption is the largest risk in the plan.

### Phase 3b — weeks 15–22, hard-gated on governance. PHI-bearing boards.

Medical Records, PhilHealth Claims, Dietary, Nursing, Security incidents. Seats to 40.

**Gate 3b →** s.44 processor annex **EXECUTED**; DPO written determination received; PIA complete; NPC registration entry filed; restricted-board isolation proven by test; Dada IT's Australian client archives out of PMC's tenant. **These boards ship on a governance schedule, not a technical one.**

### Month 6 — first generated evidence pack, and the desk decision reviewed with real numbers.

### 9.1 The desk decision, made in advance so it is not made under pressure

**Migrate off Kitameraki to Jira Service Management Standard when any one of these is true:**

- (a) Post-de-duplication volume exceeds **3,500 tickets/month** sustained for two periods — at ~3,960/month Kitameraki crosses Jira at 40 seats [INFERRED from VERIFIED rates];
- (b) a second vendor-side outage occurs **after** a properly escalated support case;
- (c) any of the four Phase-2 acceptance tests fails and the vendor will not remedy it in writing within one period;
- (d) the count of departmental fulfillers who would need a **new M365 licence** to use a Teams-native desk exceeds 25 — at ~USD 6/user/month that overtakes the licence saving.

Jira SM is the named successor because [VERIFIED today]: free forever for 3 agents with unlimited unlicensed customers; USD 20/agent/month Standard; **data residency available on Standard** with **Singapore and Sydney** both selectable; Assets included in Standard at 5,000 objects (PMC's estate is ~600). Agents need only an Atlassian account, so it carries **no M365 identity cost**.

Because the catalogue, the CMDB master, the commercial spine and the reporting are all **built and portable**, that migration changes **one ingest adapter** and nothing else. **That portability is the entire justification for building the spine.**

---

## 10. What to build FIRST in the git repo this week

**`platform/psa-spine/`** — the commercial spine as a versioned, tested SQL schema plus a loader.

Not a ticket UI. Not the Kitameraki connector. The thing that is useful whether or not any desk is ever bought, and that discharges an open action.

```
platform/psa-spine/
  db/migrations/
    0001_instruments_and_scope.sql      -- Agreement, AgreementInstrument (execution_status,
                                        --   payment_terms_days/basis, dispute_window_days),
                                        --   ScopeItem (9 + VAR), InstrumentScopeItem (clause_ref),
                                        --   ScopeItemInclusion, Entity, Site
    0002_fee_lines.sql                  -- effective-dated, retrospective insert, recalc trail
    0003_variations_and_notices.sql     -- Variation (9 states, CHECK-constrained),
                                        --   VariationEvent (append-only), Notice,
                                        --   ClientDependency, Reclassification,
                                        --   DecisionNote CHECK(advisory_at < decision_at)
    0004_work_items_and_scope_links.sql -- WorkItem (+parent_id, substatus, authority_source_*),
                                        --   WorkItemScopeItem (many-to-many, relation, is_primary),
                                        --   WorkItemNote (append-only)
    0005_effort.sql                     -- TimeEntry, bands, performed_by ≠ entered_by,
                                        --   CapacityDeclaration (the EAC denominator)
    0006_documents_and_quality.sql      -- Document (SharePoint item id, Superseded state),
                                        --   DocumentUnresolved, DataQuality, LegalHold
    0007_temporal_and_audit.sql         -- system-versioned temporal on every core table + AuditEvent
  db/seed/
    scope_items.csv                     -- the nine, verbatim headings
    instruments.csv                     -- 4 instruments, each with its REAL execution_status
    instrument_scope_items.csv          -- all three clause-numbering schemes
    fee_lines.csv                       -- 11,500 @2025-07-01; +1,000 to 2026-06-30; 13,000 @2026-07-01
    annex_b_categories.csv              -- the four existing categories
  tools/
    Import-WorkstreamRegister.ps1       -- all 35 rows, all 13 columns, lossless
    Build-AnnexB.ps1                    -- the register, in the agreement's own format
    New-DependencyNotice.ps1            -- one dated written notice per BLOCKED row
    Build-EvidencePack.ps1              -- the six-monthly pack (week 3)
  db/views/010_rpt_views.sql            -- synonyms + rpt.Dim*/rpt.Fact* in PMC_Reporting
  tests/                                -- see acceptance below
  .github/workflows/ci.yml              -- tests + schema-drift check
docs/WS36-psa-commercial-spine-20260909.md
```

**The four artefacts it produces, all from data:**

1. **`PMC_AnnexB_Variation_Register_20260916.md/pdf`** — in the agreement's own Annex B format, seeded with the four existing categories and back-filled from the **20 register rows already flagged as variations and never billed as one**. This discharges WS28's live action, open since the register was written.
2. **`PMC_Client_Dependency_Notices_20260916/`** — eleven dated written notices, one per BLOCKED row, each naming the person, the scope item, the days outstanding and the impact. **Fastest money in the whole programme.**
3. **`PMC_Instrument_Exception_Report_20260916.md`** — every fee line and variation resting on a non-EXECUTED instrument. First output: AUD 13,000/month and JRBY both rest on a blank signature block.
4. **`PMC_Variation_Paper_PSA_20260916.md`** — the three separable lines, the EAC% with its denominator shown and offered for initialling, the data-ownership and exit annex, and the RA 10173 processing schedule.

**Acceptance tests for the week:** 35 rows in → 35 work items out (not 34); no variation reaches APPROVED against a non-EXECUTED instrument; every work item has ≥1 scope-item link or an explicit `?` that is **counted, never filtered**; compound values `2->8`, `3+5`, `1/2`, `4/8` survive as two links each; all eleven cl.6 counts resolve to a number; **no row is silently dropped by any transform**; the Annex B output reconciles line-for-line with the CSV's variation rows.

**Repository fence honoured:** no patient identifiers, no keys or tokens, no internal IP addresses, no network topology. `NetworkAddress` and CI address data are **loaded at runtime from a data file held outside git** (SharePoint or the database); the repo carries the schema and the loader only.

**Sequencing note that respects the base rate:** items 5 and 6 of Phase 0 — the eleven notices and the exception memo — are produced **by hand, in a text editor, on days 1–2**, before the schema exists. The schema is so they never have to be produced by hand again. Do not let the code become a reason the notices do not go out this week.

---

## 11. Cost at 10, 25 and 40 fulfiller seats

FX **USD 1 = PHP 62.508** [VERIFIED 08–09 Sep 2026]. Requesters at 100 and at 400 add **USD 0.00** to every line below.

### 11.1 The recommendation — spine + Kitameraki

| | 10 seats | 25 seats | 40 seats |
|---|---|---|---|
| Desk licence (Kitameraki Leader, annual) | USD 1,062 | USD 1,062 | USD 1,062 |
| Ticket overage @ 2,000/mo | — | USD 2,880 | USD 2,880 |
| Azure SQL S0 (spine) | USD 177 | USD 177 | USD 177 |
| M365 identities for new fulfillers [NOT VERIFIED, ~USD 72/yr each] | ~USD 0 | ~USD 1,080 (15) | ~USD 2,160 (30) |
| **Total USD/yr** | **~1,239** | **~5,199** | **~6,279** |
| **Total PHP/yr** | **~77,447** | **~325,000** | **~392,507** |
| **% of ICT contract (PHP 7.03M/yr)** | **1.1%** | **4.6%** | **5.6%** |

### 11.2 The named successor — spine + Jira SM Standard

| | 10 seats | 25 seats | 40 seats |
|---|---|---|---|
| Jira SM Standard @ USD 20/agent/mo | USD 2,400 | USD 6,000 | USD 9,600 |
| Azure SQL S0 (spine) | USD 177 | USD 177 | USD 177 |
| Identity | USD 0 | USD 0 | USD 0 |
| **Total USD/yr** | **2,577** | **6,177** | **9,777** |
| **Total PHP/yr** | **161,083** | **386,111** | **611,140** |
| **% of ICT contract** | **2.3%** | **5.5%** | **8.7%** |

### 11.3 The rejected options, at 40 seats

| Option | USD/yr | PHP/yr | % of ICT contract | Stops being viable at |
|---|---|---|---|---|
| **Kitameraki + spine** | ~6,279 | ~392,507 | 5.6% | **~2,500 tickets/mo** (5%) / ~4,500 (10%); never on seats |
| **Jira SM Standard + spine** | 9,777 | 611,140 | 8.7% | **24 seats** (5%) / **46 seats** (10%) |
| Build the desk too (Ledger) | ~3,526 licence+identity, **plus ~300–460 build hours** | ~220,403 | 3.1% | never on licence; **fails on payback and on bus factor** |
| Freshservice Growth | 23,520 | 1,470,188 | 20.9% | **10 seats** |
| HaloPSA (APAC list) | 27,840 | 1,740,223 | 24.7% | **8 seats**, plus mandatory unquoted onboarding |
| ConnectWise PSA [NOT VERIFIED] | ~28,800 | ~1,800,230 | ~25.6% | ~8 seats; **ineligible without a written quote** |
| Syncro | 61,920 | 3,870,495 | 55.0% | **4 seats** |

**Build cost of the spine:** **60–90 hours** [INFERRED] across Phases 0–2 — schema, importer, three generators, `rpt.*` views. No web UI, no authentication, no intake, no pen test, no hosting migration. That is the honest reason this estimate is credible where a 460-hour desk build is not: it is SQL and PowerShell in the one-paste idiom the record already uses, by the person who wrote the register.

Priced to PMC as a one-off change order of **AUD 6,500** (half a month of BMF) — the only defensible number, because **no rate card exists in any instrument**.

**Run uplift:** Phase 1–2 **EAC 0%** (claimed under baseline scope item 6). Phase 3 **+20% = AUD 2,600/month**. State plainly to the board: at the 40-seat end state the software is ~USD 520/month and the human capacity to run it is ~USD 1,876/month. **Anyone arguing about the licence line is arguing about a fifth of the cost.**

---

## 12. Decisions only Dada or PMC can make

| # | Decision | My recommended answer |
|---|---|---|
| **1** | **Is Amendment No. 1 executed, and on what date?** Its signature block is blank in every readable copy, and it is the sole basis for both AUD 13,000/month and JRBY's inclusion. | **Get it signed this week, before anything else.** If it is unexecuted, Out of Scope exclusion 9 puts JRBY out of scope by default and PMC has been invoiced at a rate with no instrument behind it. This is a paper-only, zero-cost fix worth more than any software in this document. |
| **2** | **Which instrument is operative** — the 04 Jun 2026 Consolidated Revised (PMC-signed, Dada IT block blank), the v1.1 FINAL_CLEANED counter-offer, or the original? | **The Consolidated Revised**, and countersign it. Every scope-item citation depends on the answer, and it is the only one with a signature on it. Someone must open that PDF and confirm its Section 2 headings — I could not extract its text. |
| **3** | **What is the six-monthly review anchor date?** cl.6 says "every six months" and names no start. | **1 January and 1 July**, counting from the 1 July 2025 service commencement. Confirm in writing; the whole evidence-pack cadence hangs on it. |
| **4** | **What is the EAC% denominator?** No instrument defines one. | **AC = 160 hours per calendar month, one CIO-equivalent**, stated in the variation paper and **initialled by PMC before the first uplift invoice**. Round EAC% to the nearest 5 points *downward*. Without an agreed denominator every uplift is an assertion and PMC's finance function rejects it in one question. |
| **5** | **Does PMC hold the tenancy?** Azure subscription, M365 tenant, desk subscription, GitHub organisation. | **Yes, all four, in PMC's name, with PMC holding the break-glass credential and Dada IT holding administrator seats.** Costs nothing on day one, is very expensive to retrofit, and it is the only thing that makes a PMC-funded, Dada-operated PSA defensible to a board. |
| **6** | **Is the PSA baseline or a variation?** | **A variation**, on four grounds, and Annex B already names *"Operational ticketing and facilities-adjacent work"* as a category. But claim **Phase 1–2 under baseline scope item 6** ("periodic executive reporting") at EAC 0% — that is what lets the spine start this week without waiting for approval. Are you prepared to say so in writing? |
| **7** | **Is there a rate card?** None exists. Amendment No. 1 cl.3(i) "bill the work separately" has no rate behind it. | **Agree one now, in the same paper** — a single blended day rate is enough. Until then `pricing_method = SEPARATE_CHARGE` is unusable and only CAPACITY_UPLIFT works. |
| **8** | **What EAC% do you claim for hospital-wide ticketing?** Annex B's illustrations against 11,500 are 25% / 40% / 60%. | **+20% for Phase 3 (AUD 2,600/month)**, reviewed at the six-monthly review. Only Dada can set this; it is the paper's headline number. |
| **9** | **Which departments have actually agreed to fulfil their own tickets, and who is the named owner and deputy for each?** | **Facilities, Biomedical and Housekeeping first.** Those three decide whether this is a hospital PSA or an IT helpdesk with extra menus. **No board opens without a named owner and deputy whose manager has agreed the duty in writing.** |
| **10** | **Will Mr. Yang instruct the hospital that after a stated date work is accepted only through the service desk?** | **Ask for it explicitly as a condition of variation approval**, with a named emergency exception ticketed retrospectively. Without it, the desk is a fourth channel and adoption is the largest risk in the programme. |
| **11** | **Will the DPO accept a foreign-processor disclosure**, and will Ms. Ma. Elma F. Yango remain DPO while also serving as MIS Head? | **Ask in writing this week.** RA 10173 has no adequacy gate, so the answer is very likely yes with the s.44 annex in place. But phase the five PHI-bearing boards last regardless, so Phases 1–3a ship without waiting. The DPO independence question (NPC Advisory 2017-01) is PMC's to answer, not yours. |
| **12** | **Is PACS Voyager baseline or variation?** The agreement's Scope of Inclusions says it will be integrated into scope; the register carries WS22 as a variation. | **Resolve it in one direction before the H2 review**, with a `Reclassification` event and a written notice. It changes the review numbers either way, and leaving it ambiguous costs you the argument. |
| **13** | **Should ticket data live on DND-SQL01 or Azure SQL?** | **Azure SQL, southeastasia, PMC's subscription.** See §3 for why the cheaper co-location loses. |
| **14** | **WS17 — is DND-PH01-HOST1 / NCLHSQLSERVER PMC, JRBY or a third client?** | **Answer it before the review pack runs**, or it pollutes the "supported entities" and "sites" counts in the very report the variation is priced on. |
| **15** | **Will Purchasing accept the PSA as system of record** for `ACQUIRED AND MACHINE INVENTORY 2025.xlsx`? | **Get it agreed as a Phase-3 gate, not an assumption**, or the spreadsheet forks again within a quarter. |
| **16** | **Who carries the P1 clock at 03:00?** [MEASURED] Saturday 5 and Sunday 6 September produced **zero** messages. | **Either PMC names a first responder per shift with a five-condition "call the CIO when" list, or the published SLA states honestly that after-hours P1 cover does not exist and is not contracted.** A 15-minute 24×7 response is not deliverable by one remote CIO in Melbourne. |

---

## 13. What could not be verified

**Plainly, and without filling the gaps:**

- **The Consolidated Revised PDF (04 Jun 2026) could not be read.** Item `01NIB62P7C33DVXRW5WFGYI65ZEESVZDEX` returned empty on three attempts including paginated. Its clause text reaches this paper only second-hand through the 2 September working note. **Someone must open it and confirm its Section 2 headings and clause numbers** before any variation cites a clause number.
- **No instrument's execution status is confirmed.** Amendment No. 1's signature block is blank in every readable copy; v1.1's names Danilo Yang and Leo Christopher Banal with blank signature and date lines; the Consolidated Revised is signed for PMC only. Amendment No. 2 is marked "Draft Version" and is the only instrument contemplating after-hours charges — **so the desk must not offer an after-hours rate**, though it should flag after-hours work as review evidence.
- **No executed NDA or data-processing addendum was found.** Annex C left it as an open pre-signature checklist item. I found no executed copy in the drive.
- **Kitameraki's restricted-instance permission model is NOT VERIFIED.** The admin screens show tabs for Instances and User Permission, which *suggests* per-instance access control, but whether a departmental fulfiller can be provably excluded from a PHI-bearing instance has not been tested. **Phase 2 acceptance test 3 exists precisely to settle this.**
- **Kitameraki's data retention controls and export fidelity are NOT VERIFIED.** The WS08 collector design reads header-level fields only (`id`, `status`, `priority`, `department`, `category`, `assignee`, `firstResponseOn`). Whether the API returns full note threads, internal comments and attachments is unknown, and attachments are the part most likely to be lost.
- **Jira Service Management's rate table was not read from Atlassian's own page in a form I could quote line-by-line.** The USD 20/agent/month Standard and USD 0 Free-for-3-agents figures are VERIFIED from atlassian.com; the Assets-included-in-Standard change (5 Feb 2026, 5,000 objects) is from a **vendor-adjacent secondary source**, and if Assets turns out to be Premium-only for the object types a medical-device CMDB needs, the seat rate roughly triples and the successor recommendation changes.
- **Microsoft 365 per-user pricing for the ~30 new fulfiller identities is NOT VERIFIED.** The ~USD 6/user/month Business Basic figure is indicative. **The count itself is INFERRED** — nobody has counted how many of the 40 target departmental fulfillers already hold one of the ~100 M365 accounts. **Count them; it is a one-hour Graph query and it moves USD 2,160/year.**
- **The 60–90 hour build estimate is INFERRED and is made by the person who will do the work.** The record's own base rate argues against optimism: the Power BI collector was fully designed on 3 September and never run; the gateway has been one user sign-in and two portal clicks away since 3 September; `Build-EvidencePack.py` does not exist; the Kitameraki support email was drafted and never sent; WS28's variation register has been open for months. **BUILT-NOT-RUN is a status in active use in this register.** The scope was cut to SQL and PowerShell with no UI precisely so that base rate has less to bite on — but if week two ends with no imported register, stop and reduce scope to `Build-AnnexB.ps1` and `New-DependencyNotice.ps1` alone.
- **The post-de-duplication ticket volume is unknown.** The 700/month figure is INFERRED from ticket-key sequences on the assumption that each key is a contiguous per-instance sequence. **Everything in §11 that depends on ticket volume is provisional until two clean periods have been measured.**
- **ConnectWise PSA, Autotask PSA and Kaseya BMS publish no price.** Every figure in circulation is a third-party estimate. They are **ineligible for comparison** until each produces a written quote at 10, 25 and 40 seats naming the modules included and the onboarding fee. Do not let a blog estimate compete against a verified rate card — in either direction.
- **Odoo's Philippine regional pricelist could not be confirmed.** odoo.com served US pricing regardless of `country_id`, pricelist parameters and an `en-PH` Accept-Language header. If the reported ~USD 8.95/user/month PH list is real, Odoo at 40 seats is ~USD 4,296/year and would deserve a second look — but Odoo Helpdesk is Enterprise-only, so "One App Free" cannot be the ticketing system.
- **Whether Purchasing's asset register is complete, and whether the VIOLA mammograph (2011) and the QuantumCam gamma camera (2016) emit DICOM at all**, remains open — it decides whether they are CIs with a feed to monitor or CIs with a manual workflow.
- **The employment status of Kevin C. Cadano, Jomar G. Gabelo and John Kenneth Asuncion is NOT VERIFIED.** Their directory job title is "Support Staff" on `pmcne.ph`, which is INFERRED to mean PMC employment — but it decides who can be rostered on call, whose seat PMC pays for, and whose time is billable against a variation.

---

# Completeness critic
**Verdict.** This is a strong, unusually honest paper on the commercial half of the problem — the instrument-versioning, the execution gate, the variation state machine, the Notice and ClientDependency objects, and the refusal to let an undefined denominator into an uplift invoice are all better than anything a vendor ships. But it is not a PSA, and it does not admit that it isn't. It is a contract-and-variation ledger placed alongside a helpdesk whose fitness was never assessed, with procurement, opportunities, knowledge base, companies/contacts, CMDB and invoicing simply absent and no deferred-scope register saying so.

Three structural failures matter more than everything else. (1) The variation mechanism does NOT work end to end. Tickets live in Kitameraki, variations and effort live in Azure SQL, and the only place they meet is the reporting warehouse on DND-SQL01 — read-only, after the fact. No Request ticket can create or attach to a Variation, and TimeEntry.work_item_id can only reference the 35 spine workstreams, not the 700–2,000 tickets/month. So the Phase 3 +20% EAC claim for hospital-wide ticketing can never be evidenced from ticket effort; it can only be asserted, which is precisely the failure the paper says it is curing. (2) What §10 builds is not what §5, §6.6 and §8 design: no Configuration/CMDB table, no catalogue tables, no Contact table, no Board table, no Invoice table — yet §6.6 promises a DOH-inspectable per-asset maintenance export, §4.5 walks through an invoice run, and §8 promises rpt.DimConfiguration/DimCatalogue/DimContact/DimBoard over sources that do not exist. (3) The whole §5 catalogue, computed-priority, clinical-floor, pause-state, per-board-SLA and one-ticket-id-across-handover design has no home: Kitameraki was never tested against it, Phase 2's four acceptance tests touch none of it, and the paper's own MEASURED evidence (separate ITO-/PCSD- sequences on separate instances) contradicts cross-board handover on one ticket id.

Two arithmetic problems then undercut the headline. The migration trigger of 3,500 tickets/month is inconsistent with the paper's own M365 identity cost (real crossover ~3,200), and trigger (d) is already true at the 40-seat end state by the paper's own inference — so the gate fires on day one. And the entire "incumbent stays cheap to 4,000 tickets/month" case rests on Leader Flex overage that the brief itself says is Azure-Marketplace-subscription-only, which nobody confirmed PMC can buy, with quota-exhaustion behaviour unverified in a clinical setting.

On labelling: mostly exemplary, with two lapses that matter — "20 register rows flagged as variations" is asserted MEASURED against a source enumeration of 17 and is the reconciliation target of an acceptance test; and Jira's data residency on Standard is asserted VERIFIED without a URL while §13 concedes the adjacent Assets claim is secondary.

On multi-client reality: assumed away. This is a PMC ledger. Dada IT's actual services business (the Australian clients, the unclassified NCLH/WS17 client) still has no PSA, and putting Dada IT's own commercial spine — including a DADA-IT-INTERNAL entity — inside PMC's Azure subscription repeats exactly the contamination §6.7 demands be undone.

What bites in month six: the first review arrives with the "keep baseline hours internal" strategy colliding head-on with cl.6's obligation to report governance effort and vendor coordination; the execution gate having printed six months of overrides or six months of stopped invoicing if Amendment No. 1 is still unsigned; and — if nothing changes on the editing surface — a CSV that never died.

## Gaps, in priority order

### [BLOCKING] The variation mechanism breaks between the ticket and the billable line. There is no transactional path from a Kitameraki ticket to a spine Variation or TimeEntry.

**Why it matters.** §5.3 requires a Request ticket to create or attach to a Variation before it can consume effort, and §4.4 makes TimeEntry.work_item_id mandatory. But the desk is SaaS in one place and the spine is Azure SQL in another; the only described integration is desk -> collector -> stg.Kitameraki* on DND-SQL01, and spine -> nightly push -> psa.* on DND-SQL01. They meet only in the reporting warehouse, read-only, after the fact. So no ticket can attach to a Variation, no effort can be banded against a ticket, and TimeEntry.work_item_id can only point at the 35 spine workstreams, not at the 700-2,000 tickets/month. The Phase 3 claim of +20% EAC (AUD 2,600/month, AUD 31,200/year) for hospital-wide ticketing therefore has no evidentiary basis at all - it is exactly the unevidenced assertion §4.5 says PMC's finance function will reject in one question. The paper's own best sentence, 'the narrative is the defence; the band is only the arithmetic', is unbuildable as drawn.

**What to do.** Either (a) add a bi-directional adapter to Phase 2 scope - spine issues a variation_id, the desk carries it as a custom field, and a scheduled job pulls closed tickets back into spine WorkItem/TimeEntry rows so effort bands against tickets and not only workstreams - and make that a fifth Phase 2 acceptance test; or (b) state plainly that in Phases 1-2 EAC% is computed from workstream effort only, that departmental ticket effort is out of scope for the capacity claim, and remove the Phase 3 +20% from the paper until the adapter exists. Do not price an uplift on a data path that has not been built.

### [BLOCKING] The build plan in §10 omits the CMDB, the catalogue, contacts, boards and invoices - all of which other sections treat as delivered.

**Why it matters.** Migrations 0001-0007 cover instruments, fees, variations, work items, effort, documents and audit. There is no Configuration/CI table, so §6.6's hard DOH requirement (per-asset preventive/corrective maintenance export against HFSRB items 11/15/16, worked example the GE 1.5T serial 179248) cannot be met and governance requirement R7 is silently dropped. There is no catalogue table, so the whole of §5 - four levels, curated triples, default_scope_item_id, clinical_impact, min_priority - has nowhere to live. There is no Contact table, yet ClientDependency.owner_contact_id references one and the estate lens explicitly demands a named person rather than 'PMC'. There is no Invoice or InvoiceLine table, yet §4.1 stores payment_terms_days, payment_terms_basis and dispute_window_days and §4.5 walks through a monthly invoice run with due dates and a dispute window - so the system can price but cannot invoice, chase or record a dispute. And §8 promises rpt.DimConfiguration, rpt.DimCatalogue, rpt.DimContact and rpt.DimBoard over source tables that do not exist, so the reporting acceptance test cannot pass.

**What to do.** Either add 0008_contacts_and_configurations.sql, 0009_catalogue.sql and 0010_invoices.sql to Phase 1 and re-estimate honestly (this is where 60-90 hours becomes 120-150), or cut §5, §6.6 and the four orphan rpt views into a named Phase 4 with its own gate - and say in §13 that CMDB, catalogue and invoicing are deliberately deferred, so nobody reads §6.6 as a commitment made to a DOH inspector.

### [BLOCKING] Kitameraki's capability was never assessed against the design §5 spends pages building, and Phase 2's acceptance tests do not test any of it.

**Why it matters.** The recommendation is to KEEP the incumbent, so every §5 requirement must be satisfiable in it or abandoned. Nobody investigated whether Kitameraki supports computed priority from impact x urgency; per-item hard P1 floors enforced at raise and at close; a clinical_impact floor overridable only by a named role; three separate SLA clocks with two calendars; a pause state that stops the resolve clock; per-board SLA ownership; a four-level catalogue whose defaults flow into custom fields; owner and deputy per queue; or the three-path Incident/Service Request/Variation model. Worse, the paper's own MEASURED evidence - separate ITO- and PCSD- key sequences on separate instances - contradicts the stated hard requirement of ONE ticket id across a cross-board handover, which is the specific control the paper says prevents another 25-day MRI outage. Phase 2's four tests cover machine intake, custom fields, restricted-board isolation and reporting; none touches priority, SLA, pause, handover or the catalogue.

**What to do.** Before Phase 2, run a one-page capability matrix against the incumbent's admin screens (no API keys required) covering those nine items, and add at least three acceptance tests: computed priority with a hard P1 floor; a pause state that demonstrably stops a resolve clock; and a cross-instance reassignment that preserves one reference. Where the product cannot do it, say so and either descope the design or name the failure as migration trigger (c) in §9.1.

### [BLOCKING] The 'incumbent stays cheapest to ~4,000 tickets/month' case rests on Leader Flex overage that is Azure-Marketplace-subscription-only, and nobody checked PMC's purchasing channel or what happens at quota exhaustion.

**Why it matters.** The brief states Leader Flex is sold by Azure Marketplace subscription only. Every figure in §2.3 and §11.1 above 1,000 tickets/month - the 2,000/month planning case, the USD 6,279 and PHP 392,507 totals at 40 seats, the 5.6%-of-contract line, and the ~3,960-ticket crossover that sets the migration trigger - assumes overage is purchasable. If PMC's subscription is direct or via a reseller, overage cannot be bought and the 1,000/period quota is a hard cap; the previous period already hit 1,133. Behaviour at exhaustion is unverified: if creation blocks, a hospital-wide desk stops accepting tickets partway through a period at exactly the moment adoption succeeds, which is a clinical-safety event, not a billing event.

**What to do.** Make this a Phase 0 item this week: confirm in writing from the vendor (a) the current subscription channel, (b) whether Leader Flex can attach to it, (c) what happens on the 1,001st ticket. If overage is not purchasable or creation blocks, the recommendation to keep the incumbent through hospital-wide rollout collapses and Jira SM Standard becomes the Phase 3 platform rather than a successor - reprice §11 before the variation paper is issued.

### [HIGH] '20 register rows flagged as variations' is presented as MEASURED and used as an acceptance-test reconciliation target; the source enumeration lists 17. The BLOCKED count appears as both 11 and 12 and is asserted as 11.

**Why it matters.** The §10 acceptance test is 'the Annex B output reconciles line-for-line with the CSV's 20 contract_basis = variation rows'. The enumerated variation rows are WS02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 22, 23, 24, 25, 27, 34, 35 - seventeen. A test written against a number that cannot occur will either be quietly relaxed or will block the first deliverable, and the first client-facing artefact, a back-filled variation register going to PMC, would carry a count PMC can disprove from the CSV it already holds. The same exposure applies to the dependency notices: one lens says 12 of 34 rows are BLOCKED, another names 11. A notice pack that omits a blocked row forfeits the Section 3 relief entitlement on that row permanently.

**What to do.** Recount both from the CSV before anything is generated, publish the row ids in the paper rather than a bare count, and rewrite the acceptance test as 'reconciles line-for-line with the enumerated variation rows' with the list attached. Relabel every count that was not directly recounted as INFERRED.

### [HIGH] The §9.1 migration triggers contradict the paper's own identity-cost arithmetic, and trigger (d) is already satisfied at the 40-seat end state.

**Why it matters.** Trigger (a) sets migration at 3,500 tickets/month, justified by a ~3,960/month crossover computed on licence cost alone. But §2.5 and §11.1 add ~USD 2,160/year of M365 identities to the Kitameraki option because it is Teams-native; including that, the crossover against Jira at 40 seats falls to roughly 3,200 tickets/month - below the stated trigger, so the trigger fires late by its own logic. Trigger (d) says migrate when the count of departmental fulfillers needing a new M365 licence exceeds 25, and the paper's own INFERRED figure is that ~30 of the 40 do. So the decision gate is already satisfied at the end state the plan is driving toward, which makes 'keep the incumbent through Phase 3' self-defeating and risks paying to roll out fourteen boards twice.

**What to do.** Recompute the crossover on total cost of ownership including identity and restate trigger (a) at ~3,200. Either delete trigger (d) or convert it into a Phase 3a gate: run the one-hour Graph query that counts the overlap between the 40 target fulfillers and the ~100 M365 accounts BEFORE Phase 3 opens, and if the answer exceeds 25, migrate first rather than rolling out twice.

### [HIGH] The execution gate has no fallback if Amendment No. 1 is never executed, and it will print a self-incriminating exception report on PMC-visible infrastructure every month.

**Why it matters.** The gate refuses to make a fee line invoiceable against a non-EXECUTED instrument. Amendment No. 1 - the sole basis for AUD 13,000/month and for JRBY being a covered entity - has a blank signature block in every readable copy. The only mitigation offered is 'get it signed this week', against a counterparty with a MEASURED record of not answering: eleven rows BLOCKED on PMC and an entire operating lane devoted to waiting. If it is not signed, the choices are to override the gate monthly, producing a dated PMC-readable record that Dada IT knowingly invoiced without an instrument - materially worse than never having built the gate - or to stop invoicing. This is the sharpest month-six bite: six overrides and six exception reports meet the first six-monthly review.

**What to do.** Add an explicit fallback branch. If Amendment No. 1 is not executed by a named date: (i) keep the gate but hold the exception report internal-only and off PMC-controlled storage until execution; (ii) issue a written notice under Section 4 / cl.14.5 recording that invoicing continues on the parties' course of dealing pending signature; (iii) escalate the signature as a board item in the same paper as the variation. Take advice on whether an override record helps or harms before the first override is written.

### [HIGH] Multi-client reality was assumed away. This is a PMC ledger, not a PSA for Dada IT's services business, and hosting Dada IT's commercial spine in PMC's tenancy repeats the exact contamination §6.7 says must be undone.

**Why it matters.** The ask is a platform to run the services business. §7.1 maps entity 'Dada IT' to a DADA-IT-INTERNAL row and §12 decision 5 puts the Azure subscription, the M365 tenant, the desk subscription AND the GitHub organisation in PMC's name. So Dada IT's own contract, fee, effort and variation records - and the unresolved WS17/NCLH client - would sit inside a database PMC owns and holds the break-glass credential for. That is precisely the pattern §6.7 condemns when it requires The Lumery, Southgate Trust CBRE and Butler Market Gardens to leave sites/management-Management. It is also a live commercial exposure: PMC would hold Dada IT's capacity denominator and internal effort data inside a system PMC controls, during a negotiation about that same denominator.

**What to do.** Split it explicitly. PMC-scope data (agreement, scope items, variations, notices, dependencies, PMC/JRBY work items and effort) lives in the PMC-owned tenancy; Dada IT's business-wide PSA, if still wanted, is a separate instance in Dada IT's own subscription sharing the schema and not the data. Remove DADA-IT-INTERNAL from the PMC instance. State in the paper that this exercise does not deliver a PSA for the Australian clients, and that WS17/NCLH cannot be modelled until decision 14 is answered.

### [HIGH] The EAC% denominator ignores who performs the work; a one-CIO-equivalent denominator is never reconciled with delivery by 2-3 on-site staff and 40 departmental fulfillers.

**Why it matters.** AC = 160 hours/month, 'one CIO-equivalent', is offered for PMC to initial. But the MEASURED operating reality is that resolutions are typed by a PMO officer describing work done by on-site Support Staff whose employment status is NOT VERIFIED, and Phase 3 adds 40 departmental fulfillers. If PMC-employed staff hours land in TimeEntry with contract_basis = VARIATION_*, EAC% inflates on PMC's own labour and PMC will say so in one sentence. If they are excluded, numerator and denominator measure different populations. The paper introduces performed_by but never states the rule governing which performed_by values count toward the capacity claim - so the single number the variation paper is priced on is undefined at hospital scale.

**What to do.** State the rule in the variation paper: only hours performed by named Dada IT personnel count toward the EAC numerator; PMC-employed fulfiller effort is recorded for the cl.6 review counts and excluded from capacity, with the exclusion visible on the exception report. Resolve the employment status of Cadano, Gabelo and Asuncion first, because it determines the list.

### [HIGH] 'Keep baseline hours internal' collides with the cl.6 six-monthly review pack, which the paper itself makes the acceptance test.

**Why it matters.** §4.4 says capture baseline time but do not publish it, to avoid PMC asking 'AUD 13,000 buys only 70 hours?'. But §8 and §10 make the review pack emit all eleven cl.6 categories as counts at a date, and two of them - governance effort and vendor coordination workload - are effort measures. You cannot report those without disclosing effort, and once effort is disclosed by category the baseline total is one subtraction away. The strategy and the acceptance test cannot both hold, and the collision lands precisely at the first review in month six, in front of PMC's finance function, with no prepared position.

**What to do.** Choose now. Either report effort openly from day one and prepare the answer to the hours question (a fixed fee buys availability and outcomes, not hours; here is the delivered-items list per scope item), or report the cl.6 effort categories as ordinal load indicators rather than hours and state that in the pack's methodology note. Do not discover this in the review.

### [HIGH] The funding logic self-contradicts: exclusion 5 (custom software development) is used to prove the PSA is a variation, then Phase 1-2 is claimed under baseline scope item 6, and the build is separately charged as an AUD 6,500 change order.

**Why it matters.** §4.8 lists custom software development as ground two for variation status - and the spine IS custom software development. Claiming its run under baseline item 6 while charging its build as a change order invites the obvious counter: if it is baseline reporting, the build is inside the fixed fee; if it is a variation, stop claiming item 6. The paper also states no rate card exists so SEPARATE_CHARGE is unusable, and then prices a separate charge. PMC's finance function only has to pull one of these threads to reopen the entire variation, including the Phase 3 uplift that depends on it.

**What to do.** Adopt one consistent story. The cleanest: the spine is delivery instrumentation for baseline items 6 and 8, built at Dada IT's own cost and risk, EAC 0%, no change order - which is also what makes the ASAP start defensible without waiting for approval. Charge only the hospital-wide rollout (Phase 3) as the variation. That removes the AUD 6,500 line, removes the rate-card problem, and removes PMC's strongest objection.

### [HIGH] Requester identity at 400 was never solved. About 300 hospital staff have no M365 account, and the current answer is the shared consumer Gmail/Yahoo mailboxes that are also the measured PHI leak vector.

**Why it matters.** The paper solves fulfiller identity (30 x ~USD 6/month) and then says requesters are free everywhere, so 400 requesters cost USD 0. That is true of licence and false of identity: the incumbent is a Teams app, roughly 100 of ~400 staff hold a tenant identity, and the MEASURED intake today is premierelab.113@gmail.com, pharmacy_premieremedcenter@yahoo.com and the rest - including the message carrying a named patient and a PhilHealth case number. Opening ticketing hospital-wide over shared consumer mailboxes scales the RA 10173 exposure rather than containing it, and destroys attribution at the requester end just as shared accounts do at the fulfiller end. Nobody investigated the two channels the brief names and PMC already owns: the RDS farm publishing RemoteApps on PMC-HIS8-Collection, and queue.pmcne.ph.

**What to do.** Add a requester-identity section with three costed options: (a) M365 F-tier or Business Basic for the remaining ~300, priced - it likely dwarfs every software line in §11 and may be the real decision; (b) a web or RemoteApp intake form on the existing RDS farm requiring only a hospital login; (c) keep shared mailboxes with a hard triage rule and accept the attribution loss. Decide before Phase 3a, because it determines both the PHI control and the true cost.

### [MEDIUM] Four discovery-brief requirements were dropped without acknowledgement: the Lane A-D / owner-of-next-action board, change and blackout windows, the on-call rota and escalation object, and per-audience notification templates with an internal/customer-visible note split.

**Why it matters.** The estate lens states the programme is sectioned by who has to act, not by scope, and that a board groupable only by queue or priority fights the operating model - the spine has no Lane and no owner-of-next-action grouping. The same lens requires scheduled change windows tied to a configuration with a Monday blackout on DND-SQL01 during the live payroll parallel run; nothing in the schema or plan carries one, so the only control protecting the live HIS during the Tuesday/Thursday paste cadence is absent from a design that adds a nightly job step to that very instance. The operating-model lens explicitly requires an on-call/rota object and an escalation path that does not terminate in a personal Teams message to a CIO in another country; the paper raises this as decision 16 and models nothing. The working agreement's four audience registers and the internal-versus-customer-visible note split appear nowhere.

**What to do.** Add Lane as a derived attribute on WorkItem (from status, blocked_on and next_action_by) so the default board matches how the programme is actually run; add a ChangeWindow object with a blackout calendar keyed to configuration items; add Rota and EscalationPath even if Phase 1 seeds them with 'no after-hours cover contracted', which is at least an honest record; add a note visibility flag and per-audience notification templates before any hospital-wide notification goes out.

### [MEDIUM] Whole PSA modules are absent with no deferred-scope register: procurement, opportunities, knowledge base, companies/contacts, and the asset-register handover.

**Why it matters.** The ask names them explicitly, and they are not theoretical here. Procurement: WS04 is live with 44 request lines never supplied, Finance and Purchasing is a Phase 3a board, and decision 15 asks Purchasing to accept the PSA as system of record for ACQUIRED AND MACHINE INVENTORY 2025.xlsx while offering no target schema for it to land in. The knowledge base is ~155 dated markdown documents mentioned once, in passing, inside a catalogue ruling. Without a stated deferral, both PMC and Dada will read the paper as delivering a PSA and discover in month three that purchase requests, the asset register and the knowledge base still live in spreadsheets and OneDrive - the fragmentation the exercise exists to end, and the answer to 'did it quietly shrink back into a helpdesk' is yes unless the shrinkage is declared.

**What to do.** Add a short deferred-scope table naming each missing module, the phase it is deferred to, and what carries it meanwhile. Move the asset-register schema into Phase 3a as a precondition of decision 15 rather than an assumption, and state whether the 155 docs become KB articles or remain SharePoint documents linked from work items.

### [MEDIUM] The cost model is soft in five places, and the affordability thresholds that generate the headline seat-cliff finding are invented and unlabelled.

**Why it matters.** Phase 0 is presented as USD 0 with no dependency on PMC, but item 3 applies 10-year Purview retention to two mailboxes - long-term retention depends on the M365 SKU, which §13 admits is unverified, and may require a tenant-wide licence uplift. There is no legal cost anywhere for drafting an IRR s.44 processor annex and adopting ASEAN MCCs for a hospital, no PIA cost, and no labour cost for standing up fourteen boards or inducting 40 fulfillers (two hours each is 80 hours of hospital staff time plus a trainer). VAT at 12% and possible Philippine withholding on cross-border payments to an Australian contractor are absent, yet §11 reports percentages of contract to one decimal place. In §11.1 the ticket-overage row appears at 25 and 40 seats but not at 10, making volume a function of seat count - the wrong axis, and it flatters the 10-seat column. And the 5% / 10%-of-monthly-fee affordability thresholds, which generate the central finding that per-agent PSAs die between 8 and 10 seats, are stated with no label and no source while doing the heaviest analytical lifting in the paper.

**What to do.** Label the thresholds INFERRED and say what they are a proxy for. Split volume out of the seat table. Verify the M365 SKU before promising Purview retention this week. Add ranged lines for legal review, PIA, board setup and fulfiller induction, and a footnote on VAT and withholding so the percentages are not read as landed cost.

### [MEDIUM] The successor recommendation rests on two Jira Service Management properties that are not verified to the standard the paper applies elsewhere.

**Why it matters.** §9.1 asserts as VERIFIED that data residency is available on Standard with Singapore and Sydney selectable, and that Assets is included in Standard at 5,000 objects - while §13 admits the Assets figure comes from a vendor-adjacent secondary source and that the rate table was not read line by line. Residency is the governance load-bearing property (it is what makes the successor defensible under RA 10173 without a larger annex) and Assets is what would carry the medical-device CMDB that §6.6 makes a DOH requirement. If residency is Premium-only the successor's cost roughly triples; if Assets is Premium-only for the object types a device CMDB needs, the same. Either outcome changes the named successor, and both are one page-read away.

**What to do.** Read and cite both from Atlassian's own pricing and data-residency pages with URLs before the paper is issued. If either cannot be confirmed, downgrade the successor to NOT VERIFIED and name a second candidate, so §9.1's trigger list does not point at a single unconfirmed product.

### [MEDIUM] No data-subject rights workflow, no position on employee data in the HR board, and no examination of whether the liability cap covers an NPC fine.

**Why it matters.** Governance handles erasure well - redaction plus a logged event - but RA 10173 also confers rights of access, correction, objection and portability with response obligations. A hospital-wide desk holding patient references and, via the HR board, payslip and DTR data will receive such requests, and there is no intake type, no clock and no owner for them. The HR board is marked only 'partial' restricted, yet payslip discrepancies and biometric punch records are employee sensitive personal information with a different lawful basis and a different retention schedule from DOH's clinical one. And the paper quotes the NPC penalty range (0.25-3% of gross income, capped PHP 5 million) without ever asking whether v1.1 §9's limitation of liability covers it or who bears it - the first question Dada IT's own risk position should raise about operating a hospital-wide system.

**What to do.** Add a DataSubjectRequest type with a statutory clock and a DPO owner alongside PrivacyIncident; give the HR board its own retention policy and full restriction rather than 'partial'; and add one line to the variation paper allocating regulatory-fine risk between controller and processor, with advice taken before signature.

### [MEDIUM] The spine has no editing surface, so the CSV-retirement gate - the paper's own stated make-or-break - is set up to fail.

**Why it matters.** §7.1 says that if the hand-edited CSV survives past one week of dual-running, the spine has lost. But §3 defers the Power App and offers 'SSMS + a T-SQL/Excel front end' for Phase 1, which means updating status, next actions and the ~4,000-character WS07-style note stream for 35 workstreams by hand-writing SQL from Melbourne - strictly worse ergonomics than the CSV it replaces. The record's base rate is explicit and unforgiving: the Power BI collector was designed and never run, the gateway has been two clicks away since 3 September, Build-EvidencePack.py does not exist, the Kitameraki support email was drafted and never sent, and BUILT-NOT-RUN is a live status in the register. This is the precise mechanism by which the recommendation becomes shelfware, and the paper acknowledges the base rate without addressing this instance of it.

**What to do.** Put a minimal write surface in Phase 1, not Phase 3 - an Excel-linked table or a 60-line PowerShell CLI covering the four daily operations (add note, change status, set next action, band effort). Make 'ten work items updated without opening SSMS' an explicit Gate 1 criterion alongside three weeks of unbroken effort capture.

### [LOW] The non-linear pricing families the brief specifically demanded be investigated do not appear in the rejected-options table with reasons, including Power Platform, which the brief named twice.

**Why it matters.** The brief asked which platforms do NOT charge linearly per fulfiller and named four families, including an explicit instruction to price Power Apps per-app versus per-user and Dataverse versus Dataverse for Teams at 40 makers, since PMC already owns M365 and every licensed user is already in Teams. §11.3 lists Kitameraki, Jira, a build, Freshservice, HaloPSA, ConnectWise and Syncro. Power Platform, self-hosted open source, Zoho Desk light agents, SuperOps per-endpoint, Desk365 and Tikit are all absent, so a reader cannot see that the non-linear families were weighed or why each lost. The recommendation happens to land on a per-organisation product, which satisfies the spirit - but the paper does not show its working on the question it was asked, and that is exactly what a board challenge will probe.

**What to do.** Add four rows to §11.3 with a one-line rejection each: Power Platform (per-app SKU withdrawn to new customers Jan 2026; Premium USD 20/user at 40 equals Jira, plus a premium SQL connector floor and no ticketing out of the box); self-hosted open source (no Linux host, no Linux experience, worsens R14); Zoho Desk light agents (unverified whether a light seat can own and resolve); SuperOps per-endpoint (PSA module inclusion unconfirmed, endpoint count unknown).

### [LOW] Two unlabelled overclaims weaken the evidence discipline that is otherwise the paper's main asset.

**Why it matters.** §3 states 'Nothing in this design touches DND-HOST1' and then, two sentences later, 'nothing new is installed on DND-SQL01 except one scheduled outbound task' - DND-SQL01 is a guest on DND-HOST1, so the design adds a scheduled task, a service account and an outbound path on the very host the sentence disclaims. Separately, §8 adds the reporting views as step 3 of the existing 23:30 nightly job, a change to a live job on the HIS instance under a 173-finding audit, described as though it were free. In a document whose authority comes from MEASURED/INFERRED labelling, unlabelled overclaims are the lines a hostile reader will quote back.

**What to do.** Rewrite as 'no new workload is placed on DND-HOST1 beyond one scheduled outbound task inside the existing DND-SQL01 guest', and treat the 23:30 job change as a change request with a rollback, executed in a Tuesday or Thursday paste window, not as a footnote.
