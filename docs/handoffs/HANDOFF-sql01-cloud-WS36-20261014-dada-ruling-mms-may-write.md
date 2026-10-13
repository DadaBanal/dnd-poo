# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## DADA'S RULING: the MMS build may write BizBox's tables. MMS only.

**This closes Collision 2** from `HANDOFF-sql01-cloud-WS36-20261014-mms-as-per-bizbox-but-better.md`.
Read it with the function-not-screens ruling (`590e652`), which it sits beside.

---

## 1. His words

Dada, **14 Oct 2026**, on being told the brief's build rules 1–3 assume writing BizBox's own tables
while the desk forbids it:

> *"just for this one it can right to tables as its a mms build so it should function as ome"*

SQL01's reading, stated to him and acted on: **the MMS build may write to BizBox's own MMS tables,
scoped to this build only, because an MMS that cannot write is not an MMS — it has to function as
one system.**

---

## 2. A correction SQL01 owes you, because it changes what this ruling even is

**SQL01 overstated Collision 2.** It was relayed as *"the desk forbids it and must not build it"*.
Reading `psaspine/bizbox.py` properly shows that is not what the code says.

`ProcedureWriter`'s own docstring records: **"The write path Dada chose (13 Oct 2026)"**. He had
already decided the mechanism a day before. `PSA_BIZBOX_WRITE_ODBC` being unset was a **not yet**,
not a **never** — the credential was absent, not the permission.

**So this ruling is not a reversal. It is a go on something already decided and already built.** The
practical difference matters: nobody has to design a write path, and nobody should.

---

## 3. What is already built, and must be used rather than replaced

**The desk never writes a BizBox table. It calls one procedure that does.** From
`psaspine/bizbox.py`:

```
EXEC psa.sp_apply_change @change_id, @kind, @change_kind, @ext_ref,
     @field, @new_value, @payload, @requested_by, @approved_by
```

returning one row — `ok BIT`, `message NVARCHAR(400)`, `ext_ref NVARCHAR(64)`. `ok = 1` applies it;
`message` is what BizBox says; `ext_ref` is the number BizBox gave a new record. `ok = 0` refuses it
with the message, and the caller rolls back.

**The procedure lives in BizBox, in schema `psa`, and SQL01 creates and owns it.** It checks the
change and writes BizBox's MMS tables itself, so **BizBox's own flags and rules are kept** —
which is precisely how "it should function as one" is satisfied without the desk issuing arbitrary
SQL into a live clinical database.

Four refusals are already coded and are not to be loosened:

| Guard | Behaviour |
|---|---|
| `PSA_BIZBOX_WRITE_ODBC` unset | `Refused` — nothing is pushed to BizBox |
| the write login is `sa` | `Refused` |
| the write login is the **read-only** login | `Refused` — one login for both would let a read path write |
| the procedure name is not a plain `schema.name` | `Refused` |

The transaction is explicit: `autocommit=False`, commit only on `ok = 1`, rollback on `ok = 0` or on
a procedure that answers nothing. **Leave that shape alone.**

---

## 4. What the ruling covers, and what it does not

**Covers:** BizBox's **MMS** tables, through `psa.sp_apply_change`, for this build.

**Does not cover, and nothing here grants it:**

- **HIS, PIS or FMS tables.** The ruling says *"just for this one"* and *"its a mms build"*. MMS only.
- **Patient tables or fields.** `bizbox.py`'s `PATIENT_WORDS` guard refuses any mapped view or
  column that looks like a patient record — patient, px, admission, diagnos, philhealth, phic, mrn,
  caseno and more. It is deliberately broad and **is not to be narrowed to make something fit.** A
  false refusal costs a rename on SQL01's side; a false pass puts a patient field somewhere it must
  never be.
- **Direct table writes from the desk.** The desk calls the procedure. That is the whole design.
- **sa, or the read-only login.** The write login is a login of its own, and **Dada enters its
  password himself** — SQL01 never handles it.

---

## 5. The sequence before anything touches `LiveDB_PMC`, and it is not WS36's to start

This is the first write path into BizBox that has ever existed on this estate. The brief's own
rule 2 — which **stands** — says write paths are proven on `TrainingDB_HIS8` first. So:

1. **SQL01 writes `psa.sp_apply_change`** against the contract in §3, for the MMS kinds in scope.
2. **Proven on `TrainingDB_HIS8` first**, each save path compared against what the vendor client
   itself produces, before anything is created in `LiveDB_PMC`.
3. **Dada creates the write login and enters its password**, then sets `PSA_BIZBOX_WRITE_ODBC` on
   the host. Until he does, `writer_in_force()` returns `NoWriter` and the desk pushes nothing —
   which is the correct default and needs no change.
4. **Each step previewed, gated, applied in one transaction, read back, ending in a verdict** — the
   same discipline as 079 through 084, with a control that must fail.

**Rules that survive this ruling untouched:** honour the **rowversion** columns (1,203 across the
database) or the two clients silently overwrite each other; **exclusive cutover per screen**, since
the vendor client keeps writing these same tables until the last screen moves; and **reads first on
every screen**, because the risk is entirely on writes.

And his standing constraint, which this ruling does not soften: *"dont make anuy changes that will
destroy things ok"* / *"or what i meant was break things"*.

---

## 6. One thing still open that he should hear once, and then it is his

**BizBox's contract terms on direct database writes have not been read.** Open since 13 Oct, raised
by the Bizbox Chat session in their brief's §8 and still unanswered. It does not block the work —
the procedure can be written and proven on `TrainingDB_HIS8` regardless — but it is unresolved, and
`LiveDB_PMC` is the vendor's live application database. Stated once. **His call, and he has made the
technical one.**

Recovery, for context rather than alarm: `LiveDB_PMC` is backed up — `PMC - LiveDB_PMC - FULL` at
22:00, `- DIFF` six-hourly, `- LOG` every 15 minutes. **MEASURED** previously, not re-checked today.
Note that the instance has **no SQL Agent operators, alerts or Database Mail**, so a failed backup
job tells nobody; that is worth knowing before the first live write, not after.

---

## 7. What this means for WS36 right now

**Nothing to start.** The writer already exists in the code you hold, the procedure is SQL01's to
write, and the credential is Dada's to set.

What changes for you is only this: **build rules 1–3 are no longer "what not to foreclose" — they
are live requirements.** Honour `rowversion`, keep save paths separable and per screen, and assume
the vendor client is writing the same tables beside you. And the function-parity ruling now has
teeth: with writes permitted, "the same outcome from the same inputs" means the same row in the same
BizBox table, which is what `psa.sp_apply_change` is for.

Still Dada's: **priority**. Still gating estimating: **the count of save paths**, now more than
before, because every save path is a procedure branch somebody has to write.

**Nothing changed on any host.** A ruling relayed, not work done.
