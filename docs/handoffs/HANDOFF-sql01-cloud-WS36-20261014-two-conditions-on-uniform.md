# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## What uniform actually requires: a replay refusal in the procedure, a self-explaining guard, and the grant in both databases. One proposed condition withdrawn as unbuildable.

**Read with** `HANDOFF-sql01-cloud-WS36-20261014-write-grant-measured.md` and Runbook Part 92
(`df20d9c`), which recorded Dada's decision: **`psa_desk`, uniform — one identity for reads and
writes.**

**This handoff was reviewed before sending, on Dada's instruction, and the review changed it.**
A first draft carried a condition that could not be implemented; a challenge of SQL01's own did
not survive measurement; and one open item got closed. What follows is what survived. Measurements
are the Bizbox Chat session's unless marked SQL01; controls both ways throughout.

---

## 1. A condition proposed, reviewed, and withdrawn — recorded so nobody reintroduces it

**The proposal:** because `@requested_by` and `@approved_by` are caller-supplied, `psa.sp_apply_change`
should derive the approver from the stored `ext_change` row rather than trust the parameter —
otherwise under uniform a compromised read identity could submit and self-approve in one call.

**Why it was withdrawn, two reasons, the second decisive:**

**It cannot be built.** `psa.ext_change` and `psa.ext_batch` exist **only in `PMC_PSA`** — verified
by Bizbox Chat after SQL01 raised it: `LiveDB_PMC`'s `[psa]` schema holds the five views and **no
`ext_*` tables**; `TrainingDB_HIS8` likewise. All three databases: `is_db_chaining_on = False`,
`is_trustworthy_on = False`. **The procedure runs in `LiveDB_PMC` and has no read path to the row
it was being told to trust.** Two different `[psa]` schemas in two different databases is how both
sessions missed it.

**And the threat it defended largely collapses under uniform.** The split limited what a **stolen
credential** could do. Uniform **abolishes the credential** — there is no password to steal. To
abuse the `EXECUTE` you need code execution as `psa_desk` on that host, **and at that point you are
the desk**: you can drive its own approved path, and the Python layer's correctness is moot either
way. The boundary defended against theft of a thing uniform removed.

**What stands instead — and it is already true, not a condition on the build.** The approval
control lives in the desk layer, and **SQL01 measured it as already correct**: `bizbox.py`
1034–1036 selects only `c.status = 'PENDING' AND (c.batch_id IS NULL OR b.status = 'APPROVED')`
and passes `b.approved_by` **read from the stored batch row, never from a caller.** The database
boundary is the reason it belongs there, not a deficiency. **Recorded as defence-in-depth already
satisfied.**

**Two alternatives considered and rejected**, so they are not re-proposed: a cross-database read
from the procedure to `PMC_PSA` (needs chaining or `TRUSTWORTHY` on, widens exactly what the login
exercise narrowed); and a nonce or signed payload (needs a key the desk holds and the procedure
verifies — **a shared secret, which is the exact thing uniform was taken to remove.** Trading a SQL
password for an HMAC key is not a win).

---

## 2. The replacement condition, buildable and binding: replay refusal on `change_id`

**`psa.sp_apply_change` refuses a `change_id` it has already applied, returning `ok = 0`.**

A consumed-`change_id` table in `LiveDB_PMC`, schema `psa`, **written by the procedure itself via
ownership chaining** — the same mechanism SQL01's 13 Oct run already proved in production for
reads. No secret, no cross-database read, nothing new in the trust model. **A sixth refusal in the
shape the contract already has.**

**It blocks the mundane failure rather than the exotic one:** the same approved change applied
twice by a retry, a race, a resend, or an operator re-running a batch. **At 8.5 vendor updates a
minute on `iwWareitem`, a double-applied quantity change is a realistic way to produce a wrong stock
figure** — and unlike the approval question, it is entirely inside the procedure's reach.

**One control that must fail, added to the verifier:** as `psa_desk`,
`HAS_PERMS_BY_NAME` for `DELETE` on the consumed-ids table **must return 0.** `psa_desk` will hold
`SELECT ON SCHEMA::psa` and can therefore read the table — harmless — but holds no DML and must not
be able to clear it.

**For WS36:** `change_id` is the spine's key and it is now load-bearing on the BizBox side too.
**It must be unique and never reused across the life of the desk.** If anything in the spine could
mint the same `change_id` twice — a reset, a reseed, a restore — the replay guard is defeated from
your side. Say so if that is possible today.

---

## 3. The guard: inverted, with a docstring and a refusal that explains itself

The separation guard in `write_odbc_string()` passes silently under uniform — it only fires when
both strings carry an explicit `uid=`, and trusted auth carries none. **Decided:**

- **Invert it.** Refuse any write string carrying an explicit `uid=` at all. That enforces the
  Trusted-Connection-only decision, **it can fail**, and it fires on exactly the mistake uniform
  newly makes possible — someone reintroducing a SQL login for the write path and quietly undoing
  the one benefit the decision was taken for.
- **No override.** An override is a second thing that can be set wrongly, and this estate's own
  record is the argument: `Watch-PMCBridge`'s `.trn` guard read *"if not null AND stale"*, so
  absence meant silence, and it never fired once in its life while the `.bak` side cried wolf for
  17 days. An override nobody audits is the same class of thing.
- **The docstring says the host-move case requires changing this guard deliberately.**
  `DND-SQL01\psa_desk` is a local account and does not travel; the remedy on a host move is a domain
  account — **and not a SQL login as a drop-in**, because this guard refuses it by design.
- **The refusal message carries the remedy**, because a docstring is read at authoring time and
  this guard will fire at 2am on a host move: *the write path is Windows-authenticated by decision
  of 14 Oct 2026; if the desk has moved host, this guard is the thing to change, deliberately.*
  **A guard that explains itself at the moment it fires is the opposite of the silent-pass failure.**

**Also corrected, before anyone cites it:** `ApplicationIntent=ReadOnly`, which `odbc_string()`
appends to every read string, is a **routing hint for availability-group replicas, not a
permission.** It does not prevent a write and is not residual separation.

---

## 4. The grant goes in both databases, and the Training owners are now measured

**SQL01's first reading — one database user — was incomplete and would have failed at the proving
step.** `psa_bizbox_reader` is mapped in **two** databases (all 13 online databases walked):

| Database | User | Roles | Grants |
|---|---|---|---|
| `LiveDB_PMC` | `psa_bizbox_reader` | none | `CONNECT`; **`SELECT ON SCHEMA::psa`** |
| **`TrainingDB_HIS8`** | `psa_bizbox_reader` | none | `CONNECT`; **`SELECT ON SCHEMA::psa`** — identical |
| the other 11 | — | — | no mapped user |

**Build rule 2 proves every write path on `TrainingDB_HIS8` first.** A `LiveDB_PMC`-only grant would
lose the proving step's read path the moment the reader retires — failing exactly when the procedure
was being proven.

```sql
-- LiveDB_PMC
CREATE USER [psa_desk] FOR LOGIN [DND-SQL01\psa_desk] WITH DEFAULT_SCHEMA = psa;
GRANT SELECT  ON SCHEMA::psa                 TO [psa_desk];
GRANT EXECUTE ON OBJECT::psa.sp_apply_change TO [psa_desk];

-- TrainingDB_HIS8
CREATE USER [psa_desk] FOR LOGIN [DND-SQL01\psa_desk] WITH DEFAULT_SCHEMA = psa;
GRANT SELECT  ON SCHEMA::psa                 TO [psa_desk];
GRANT EXECUTE ON OBJECT::psa.sp_apply_change TO [psa_desk];   -- once it exists there
```

`CREATE USER` carries `CONNECT`; add `GRANT CONNECT` only if revoked. **`SELECT` at SCHEMA level and
`EXECUTE` at OBJECT level is intentional** — schema level matches exactly what the reader has, so
nothing is lost; object level keeps a future procedure in `[psa]` from silently becoming executable.

**Closed on review:** the Training owners were flagged unmeasured. **Now measured: `[psa]` owned by
`dbo`, `[dbo]` owned by `dbo`, same owner** — ownership chaining works there too and the proving
step behaves as live.

**Not to be granted:** no database role of any kind — **not `db_datareader` even though the identity
now reads**, because schema `SELECT` on `[psa]` is the whole read surface and `db_datareader` opens
all 1,609 tables; no table or view DML; not `EXECUTE ON SCHEMA::psa`; no `ALTER`, `CONTROL` or
`VIEW DEFINITION`; nothing at server level; `bizboxsa` untouched.

**Chaining is proven in production, not inferred.** SQL01's 13 Oct run had `psa_bizbox_reader`
reading **152 rows** through `psa.vw_lookup` while still refused `dbo.iwItems` — the mechanism
exercised, not read off metadata. Same mechanism the procedure and the replay table rely on.

---

## 5. Is `psa_bizbox_reader` unused? CANNOT TELL — and SQL01's challenge to that did not survive

**Clean, each measured:** no Agent job step names it; no Agent proxies on the instance; no linked
servers; the one server credential is the Azure blob backup URL; **0** SSRS catalog definitions
contain the login name — with a positive control, 1,279 items contain `"DataSet"`.

**The one unknown:** `/Data Sources/BIZBOXHS8` stores a credential — `CredentialRetrieval = 2`,
a stored `UserName`, encrypted, **not decoded.**

**SQL01 challenged the `2 = Store` reading** on the documented SOAP enum (Prompt=0, Store=1,
**Integrated=2**, None=3 — VERIFIED, learn.microsoft.com), then **measured the catalog instead of
arguing:** across all 1,200 rows, value `1` = 1,197 with nothing stored; value `3` = 2 with nothing
stored; value `2` = **exactly one, with both a username and a password stored.** **Stored
credentials exist under `2` and under no other value — so in this catalog `2` is Store, the table
does not use the SOAP numbering, and the challenge is withdrawn.** IS-NULL checks only.

**And there is no durable record of any successful login on this instance:** audit level =
**failure** (`xp_loginconfig`; `SERVERPROPERTY` has no `AuditLevel`), no server audits, the stock four
Extended Events sessions none of which capture logon, default trace likewise, uptime 21 hours. **The
0-sessions figure is a point-in-time sample with no history behind it.**

**What would settle it:** open `/Data Sources/BIZBOXHS8` in Report Manager and **read the stored
username off the screen** — the UI shows it and hides only the password. Ten seconds, no query, no
change, no credential handled. **Dada's.** Otherwise: **leave the login exactly where it is.** Nothing
is retired in this step regardless.

---

## 6. State of play, and the order

**Nothing run. Nothing scheduled. Code untouched.** `PSA_BIZBOX_WRITE_ODBC` unset;
`writer_in_force()` returns `NoWriter`. No credential read, no encrypted value decoded. `bizboxsa`
untouched and staying untouched.

**Order:** invert the guard with docstring and self-explaining refusal → write `psa.sp_apply_change`
**with the replay refusal and its consumed-ids table** → create the user and grant **in both
databases** → verify, as `psa_desk` under `EXECUTE AS` … `REVERT`: `SELECT` on a `psa` view = 1,
`EXECUTE` on the procedure = 1; **must fail**: `UPDATE` on `dbo.iwWareitem`, `INSERT` on
`dbo.iwItemLedger`, **`UPDATE` on `dbo.appsysUserSubmodules`**, `SELECT` on a `ps%` table, **`DELETE`
on the consumed-ids table** — all 0, any 1 voids the run → execute once with a payload a coded
refusal must reject, confirm `ok = 0` and no commit → prove on `TrainingDB_HIS8`.

Still Dada's: **priority**, the Report Manager check, whether the reader ever retires. Still open:
`bizboxsa`'s `modify_date`, `his_app_svc`, BizBox's contract terms, the save-path count.
