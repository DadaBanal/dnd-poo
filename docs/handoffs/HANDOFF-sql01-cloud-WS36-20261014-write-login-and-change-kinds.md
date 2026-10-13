# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## `bizboxsa` is the vendor's live account. The change kinds are measured. One question to settle before widening the CHECK.

**Carries two files from the Bizbox Chat session, verbatim, both verified against the hashes they
stated before I copied them:**

| File | Lines | sha256 |
|---|---|---|
| `docs/bizboxsa-login-assessment-20261014.md` | 131 | `84487594…c2c62ea7` |
| `docs/bizbox-mms-rule3-contention-and-kinds-20261014.md` | 109 | `704163dd…c8537fa0` |

Their four earlier files re-verified unchanged, so `bb96800`, `49e6fdb`, `26d2c30` and `68e1dcf`
all still hold. **Every figure below is theirs. SQL01 re-ran none of it** — BizBox measurement is
theirs by Dada's standing instruction (Part 89 addition).

---

## 1. The write login: measured No, with a cheap alternative

Dada's instruction was *"there is already bizboxsa"* / *"for everythung u need"*. **The measurement
says it is the wrong login, and that the right one costs almost nothing.** This is reported to him;
the decision is his.

### What `bizboxsa` is

| | |
|---|---|
| Type | SQL login, **exists, ENABLED** |
| Created / last modified | 10 Jun 2026 / **1 Oct 2026** |
| Server roles | **NONE. Not `sysadmin`.** |
| Explicit server permission | `CONNECT SQL` (GRANT) and nothing else |
| Role in `LiveDB_PMC` | **`db_owner`** |
| Maps to `dbo`? | **No** — `LiveDB_PMC` is owned by `sa` |
| SQL Agent jobs owned | none |
| Control | a login named `bizboxsa_zz99_nope` returned 0 — the probe distinguishes present from absent |

**One unexplained thing they flag and did not investigate:** `modify_date` moved on **1 Oct 2026**,
and that field moves on a password change among other things. **Worth knowing before anyone assumes
the credential is unchanged since June.**

### Whose it is — the vendor client's, measured

**22 live sessions** at the moment of the probe, and **one** distinct program name across all of
them: `.Net SqlClient Data Provider`. Oldest session 14 Oct 04:21.

Twenty-two concurrent sessions under a single .NET client name is **the WinForms estate on the
hospital floor**, not a batch job. So both concerns SQL01 raised hold, and they are worse than
raised:

- **Its password is not ours to touch.** Rotating or re-issuing it **drops every BizBox client in
  the hospital** — a clinical-hours outage, not a config edit.
- **Sharing it destroys attribution.** Desk writes would land on the same login as 22 concurrent
  client sessions, and **no audit could separate "the desk applied a change" from "a department
  edited a record".**

### What `db_owner` on `LiveDB_PMC` actually reaches

**1,609 tables, readable *and* writable**, of which:

| Prefix | Tables | What they are |
|---|---|---|
| `ps%` | **326** | the patient and clinical side |
| `iw%` | 100 | materials — **the actual target** |
| `appsys%` | 84 | users, groups and permissions |

So `bizboxsa` would hand the write path **1,609 tables where Part 87's design calls for one
procedure** — including the 326 patient tables the whole `PATIENT_WORDS` fence exists to keep away
from, and the 84 `appsys%` tables that control who may do what inside BizBox. **A write path with
`db_owner` can grant itself access in the application.**

They confirm SQL01's guard finding without re-measuring it: the anchored `sa` test **accepts**
`bizboxsa`. The question was never whether it *can* be used.

### The alternative, and the precedent is already on this instance

**MEASURED — the non-vendor logins against `LiveDB_PMC` today:**

| Login | Server roles | In `LiveDB_PMC` | Live sessions |
|---|---|---|---|
| `bizboxsa` | none | **`db_owner`** | **22** |
| `pmc_ssrs_reader` | none | `db_datareader`, plus `CONNECT`, `EXECUTE` on the database, `EXECUTE` on named functions, `ALTER` on two views | 7 |
| `psa_bizbox_reader` | none | **no database role** — `CONNECT` plus one `SELECT` | 0 |
| `psa_desk` (Windows) | none | no database role, no explicit grants | 1 |

**`pmc_ssrs_reader` is the proof.** It holds `db_datareader` plus object-level `EXECUTE` and `ALTER`
grants **inside the vendor's live application database**, has 7 sessions running now, and the BizBox
client is unaffected. **A login holding nothing but `CONNECT` and `EXECUTE` on
`psa.sp_apply_change` would be strictly less privileged than `pmc_ssrs_reader` already is.**

Two routes, either of which leaves `bizboxsa` alone:

1. **A dedicated SQL write login** with `CONNECT` + `EXECUTE` on `psa.sp_apply_change`, nothing else.
2. **`psa_desk`**, the Windows identity that already exists with no privileges and one live session
   — the principal is there and needs only the single `EXECUTE` grant. This also satisfies the
   "write login must differ from the read login" guard structurally rather than by relying on it.

### What this does *not* establish — their words, on the record rather than implied

- **BizBox's contract and support terms are still unread.** They measured that extra logins coexist
  **technically**; they have **not** measured whether the vendor's terms permit them, or permit
  writing the database at all. **Different questions; only the first is answered.**
- They cannot prove the client does not inspect the login name — the evidence is **circumstantial**
  (three non-vendor logins existing while the client runs normally), not a disassembly.
- **Nothing here is a judgement on *whether* to write, only on *which* login**, which is what was
  asked.

### One thing found while looking, stated once, no recommendation attached

**`his_app_svc` is a SQL login holding `SYSADMIN`, enabled, 0 live sessions at probe time.** It
surfaced only because the probe enumerated server roles to answer whether `bizboxsa` held any. **It
is the only `sysadmin` SQL login besides `sa` on this instance.** For Dada, not for this build.

---

## 2. Contention: rule 3 binds harder than Part 88 said, and on more tables

- **`iwItemLedger` is NOT append-only.** 17 updates against 3,559 inserts in a 21-hour window; **1
  vendor procedure contains `UPDATE…iwItemLedger` and 2 contain `DELETE`**; no triggers. So rule 3
  binds on the ledger too — which matters directly to the Part 84 decision to derive the stock
  position from it.
- **The real contention is `iwWareitem`: 10,667 UPDATEs in 21 hours — about 508 an hour, 8.5 a
  minute**, and higher in working hours since the window includes a night. **A write to
  `iwWareitem` without a token is racing roughly nine vendor updates a minute.**
- `iwPOinv`, `iwReqinv` and `iwWhreqinv` all take **more updates than inserts**, which is what
  posting and approving looks like.
- `iwItemLedger` measured **227,077 rows earlier today and 227,104 later**. The concurrency is
  happening during the design.

**This strengthens Part 88's sequencing rather than changing it.** A widened CHECK with no token
would let an MMS change be applied against `iwWareitem` at 8.5 vendor updates a minute — **strictly
worse than today's refusal.** Widen the CHECKs and add the token in the same gated step.

---

## 3. The change kinds, derived from volume so "only those" is not guessed

**IN SCOPE — ten**, by header count:

| Kind | Headers |
|---|---|
| Expense Requisition | 1,223 |
| Stock Requisition | 1,095 |
| Expense Issuance | 1,085 |
| Delivery / Receiving | 1,069 |
| Stock Issuance | 998 |
| Purchase Order | 837 — **kind already exists** |
| Purchase Requisition | 634 |
| Material Production | 169 |
| Physical Count | 104 |
| Quantity Adjustment | 40 |

**EXCLUDE — four:** Job Order 21, Job Order Request 5, Purchase Return 2, Allotment/Obligation 0/0
(never used).

**The cut at 25 headers is a judgement, not a measurement — they say so.** But the gap is wide:
tenth-largest is 40, eleventh is 21, and **the four excluded total 28 headers against 7,254 for the
ten.**

### The one question to settle *before* widening the CHECK

Theirs, and they explicitly decline to answer it:

> If the stock position is derived from the ledger, it arguably **cannot be "changed" directly at
> all** — the correctable thing is a **movement**, not a position. So `ext_stock` may need a read
> path but **no change kind.**

**That changes which kinds the CHECK is widened to, so it is settled before the schema step, not
after.** SQL01's view, to be challenged: they are right. Part 84 already decided the position is
derived from the ledger rather than stored, and a derived figure has nothing to write to — the
change kind belongs on the movement. **`ext_stock` gets a read path and no change kind.** That is
SQL01's reading, not a measurement, and it is the kind of inference Parts 86 and 87 were both about,
so it is labelled: **INFERRED.**

---

## 4. State of play

- **Nothing written. Nothing scheduled.** `PSA_BIZBOX_WRITE_ODBC` confirmed unset;
  `writer_in_force()` returns `NoWriter`.
- **No credential was read** by either session at any point — no password, no hash, no connection
  string read, printed or written.
- Their fence note, which SQL01 verified independently: the probe enumerated **every** login on the
  instance, which includes individual staff Windows accounts, and **those names are deliberately
  omitted.** They re-checked after their first fence grep threw a trailing-backslash error, rather
  than accepting its clean result — the correct instinct, and the same class of error as the
  heredoc trap in this estate's own notes.
- **The write login is Dada's decision and his password to enter.** The grant script is SQL01's as
  driver. Their measured grant list has been requested as text.
- Still open and still his: BizBox's contract terms; **priority**; and the save-path count, now
  also the count of procedure branches.

**Nothing changed on any host.** Read-only throughout, both sessions.
