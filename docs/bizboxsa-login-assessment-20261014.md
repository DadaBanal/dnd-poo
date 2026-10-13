# `bizboxsa` — what it is, and why it is not the desk's write login

**Answers:** the four questions routed from Dada via peer session SQL01 on 14 Oct 2026 —
*"there is already bizboxsa"*, then *"ask bizbox chat"*.

**Measured 14 Oct 2026**, `DND-SQL01\PMC_SS`, read-only, controls passed. Security **metadata only**:
no password, no hash and no connection string was read, printed or written at any point.
Scripts: `scripts/Probe-BizboxsaLogin-20261014.py`, `scripts/Probe-LoginPrecedent-20261014.py`.

**The short answer: it exists, it is the vendor client's own live service account, it is not
sysadmin — but it is `db_owner` on `LiveDB_PMC`, which reaches 1,609 tables including the clinical
ones. It is not appropriate as the desk's write login, and a suitable one can be added, because three
non-vendor logins already coexist with the BizBox client on this instance.**

---

## 1. What it is

| | MEASURED |
|---|---|
| Exists | **yes** — `SQL_LOGIN` |
| Enabled | **yes** (`is_disabled = False`) |
| Created / last modified | **10 Jun 2026** / **1 Oct 2026** |
| Default database | `LiveDB_PMC` |
| Server roles | **none** |
| Explicit server permissions | **`CONNECT SQL` (GRANT)** — and nothing else |
| **Is it sysadmin** | **No.** |
| Role in `LiveDB_PMC` | **`db_owner`** |
| Maps to `dbo` | **no** — `LiveDB_PMC` is owned by `sa` |
| SQL Agent jobs owned | **none** |
| Control | a login named `bizboxsa_zz99_nope` returned 0 rows, so the probe can tell present from absent |

**The one unexplained thing:** the login was **modified on 1 Oct 2026**. `modify_date` moves on a
password change among other things. Not investigated, and worth knowing before anyone assumes the
credential is unchanged since June.

## 2. Whose account it is — the vendor client's, measured

| | MEASURED, at the moment of the probe |
|---|---|
| Live sessions as `bizboxsa` | **22** |
| Distinct program names across them | **1** |
| That program name | **`.Net SqlClient Data Provider`** |
| Oldest session login time | 14 Oct 2026 04:21 |

**`bizboxsa` is how the BizBox client authenticates.** Twenty-two concurrent sessions under a single
.NET client program name is the WinForms estate on the floor, not a batch job.

**Two consequences, both of which SQL01 anticipated and both of which hold:**

- **Its password is not ours to touch.** Rotating or re-issuing it drops every BizBox client in the
  hospital. Any change to this login is a clinical-hours outage, not a configuration edit.
- **Sharing it destroys attribution.** Desk writes would arrive on the same login as 22 concurrent
  vendor-client sessions, and no audit — `appsysUsers`, a trace, or the `tstamp` trail — could
  separate "the desk applied a change" from "a department edited a record".

## 3. Is it appropriate as the desk's write login? **No.**

Part 87's design, which is Dada's own choice of 13 Oct, says the write login *"may do nothing but
`EXECUTE`"* `psa.sp_apply_change`. `db_owner` is the opposite end of that scale.

**What `db_owner` on `LiveDB_PMC` reaches, MEASURED:**

| | |
|---|---|
| Tables it can read **and write** | **1,609** |
| of which `ps%` — the patient and clinical side | **326** |
| of which `iw%` — materials, the actual target | **100** |
| of which `appsys%` — users, groups and permissions | **84** |

So using `bizboxsa` would give the write path **1,609 tables** when the design calls for one
procedure. That includes the 326 `ps%` tables the `PATIENT_WORDS` fence exists to keep away from, and
the 84 `appsys%` tables that control who can do what in BizBox — a write path with `db_owner` can
grant itself access inside the application.

**It is also strictly unnecessary**, which is what makes the answer easy: `EXECUTE` on one procedure
is a smaller grant than `db_owner` by any measure, and §4 shows it is available.

**Note on the code-side guard, since it is relevant and is SQL01's measurement, not mine:**
`write_odbc_string()`'s `sa` test is anchored to the exact login `sa`, so **`bizboxsa` passes it** —
it is not caught by name. The guard would accept this login. The question was never whether it
*can* be used.

## 4. The alternative, and the precedent already on this instance

**Yes — and extra logins demonstrably coexist with the BizBox client here.** MEASURED, the
non-vendor logins against `LiveDB_PMC` today:

| Login | Server roles | `LiveDB_PMC` role | Explicit grants | Live sessions |
|---|---|---|---|---|
| `bizboxsa` | none | **`db_owner`** | `CONNECT` | **22** |
| `pmc_ssrs_reader` | none | `db_datareader` | `CONNECT`, `EXECUTE` on the database, `EXECUTE` on named functions, `ALTER` on two views | 7 |
| `psa_bizbox_reader` | none | **none** | `CONNECT`, one `SELECT` | 0 |
| `psa_desk` (Windows) | none | **none** | **none** | 1 |

**`pmc_ssrs_reader` is the proof.** It holds `db_datareader` plus object-level `EXECUTE` and `ALTER`
grants in the vendor's live application database, it has 7 sessions running now, and the BizBox
client is unaffected. A new login holding nothing but `CONNECT` and `EXECUTE` on
`psa.sp_apply_change` would be **strictly less privileged than `pmc_ssrs_reader` already is**.

So the recommendation, in one line: **add a dedicated write login with `CONNECT` plus `EXECUTE` on
`psa.sp_apply_change` and nothing else, and leave `bizboxsa` alone.** `psa_desk` already exists as a
Windows login with no privileges and one live session, so if a Windows identity is preferred over a
SQL one, the principal is already there and only needs the single `EXECUTE` grant.

### What this does **not** establish

- **BizBox's contract and support terms are still unread.** §8 of the brief has been open since
  13 Oct. I have measured that extra logins coexist **technically**; I have not measured whether the
  vendor's terms permit them, or permit writing the database at all. Those are different questions
  and only the first is answered here.
- **I cannot prove the client does not inspect the login name.** The evidence is circumstantial but
  strong: three non-vendor logins exist and the client runs normally. Not a disassembly.
- Nothing here is a judgement on **whether** to write — only on **which login**, which is what was
  asked.

## 5. One thing found while looking, stated once

**`his_app_svc` is a SQL login holding `sysadmin`**, enabled, with 0 live sessions at the time of the
probe. It was not part of the question; it surfaced because the probe enumerated server roles to
answer whether `bizboxsa` held any. Recording it because it is the only `sysadmin` SQL login besides
`sa` on this instance. No recommendation attached.

---

Read-only throughout. Nothing built, nothing changed, no credential read or written. The instance's
Windows logins include individual staff accounts; **those names are deliberately omitted here**
because this file goes into a committed repo.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no passwords, no connection strings, no addresses or topology.*
