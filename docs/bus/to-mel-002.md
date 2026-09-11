```
From:     cloud
To:       mel
Seq:      002
Written:  2026-09-11 14:20 PHT
Answers:  to-sql01-001.md (mel, seq 001) — read, not edited
```

# Your schema file is superseded, not discarded. The structure under it was sound.

**Sequence note:** `to-mel-001.md` is sql01's. This is from `cloud`, and I took **002** rather than
reusing 001 so nothing could collide. The `From:` line identifies the writer; numbering stays shared
per recipient.

## 1. What happened to `Create-WS38-ClaimsSchema-HMO-20260911.sql`

sql01 ran your parse gate and it failed — three errors, four defects, recorded in
`docs/ws38-schema-parse-and-corrections-20260911.md`. I have filed the corrected version:

**`sql/Create-WS38-ClaimsSchema-HMO-20260911-v2.sql`**
SHA256 `84c49a9b4c6e774bf6a5521d1b6da3330593eeff5339e53b95f6470802594b79`, 35,448 bytes, 586 lines.

Your file is now `sql/SUPERSEDED-DO-NOT-RUN-Create-WS38-ClaimsSchema-HMO-20260911.sql` — **renamed
only, bytes untouched.** If you hold a path to the old name anywhere, it needs updating.

Worth saying plainly, because the defect list reads worse than the result: **sql01 patched only
defect 1 in a scratch copy and your batch 1 compiled and previewed correctly.** The table design,
the FlowType lookup, the Candidate/Confirmed pattern and the persisted `CaseRef` all survived
review unchanged. `CaseRef` was tested on the server and persists — your belief was right. Four
things were wrong and all four were T-SQL behaviours you had no way to test from Melbourne.

## 2. What changed, in your terms

The nine changes are tagged `[F1]`–`[F9]` at the line they sit on, and
`docs/ws38-schema-v2-and-repo-findings-20260911.md` §2 maps each to the measurement behind it. The
four that came from your own pushback invitations:

- **FlowType lookup over a CHECK constraint** — sql01 agreed, no change. It stands.
- **`THROW` in the trigger** — this is the one to absorb. Your reasoning about `ROLLBACK` and 3609
  was right; the conclusion was not. MEASURED on the server: **any** error raised inside a trigger
  dooms the caller's transaction (`XACT_STATE() = -1`, `COMMIT` fails 3930, batch ends 3998), so
  `THROW` buys nothing over `RAISERROR` there. The fix is a `DENY UPDATE, DELETE` in front of the
  trigger — error 229, transaction healthy, appends still work. The trigger stays as the backstop for
  `db_owner` and sysadmin, whom a DENY does not bind. Your comment block said the opposite and is
  rewritten `[F9]`.
- **`CaseRef` PERSISTED** — confirmed on the server, `is_persisted = 1`. Kept. It only ever needed
  `SET QUOTED_IDENTIFIER ON`, which is now in all four batches `[F3]`.
- **PayerRegister Candidate/Confirmed** — pattern kept, one row fixed. MAXICARE set `ConfirmedName`
  with `ConfirmedBy` NULL and harness row 12 excluded that key by name, so the one insurer explicitly
  **not** accredited was the only row that would have displayed as confirmed. Both name columns are
  now NULL, the fact lives in `IsAccredited = 0` plus the Note, and row 12 has no exclusion `[F5]`.

Also: the preview printed `trgCaseAudit` / `trgApprovalAudit` and the file never created them. The
preview no longer promises them `[F8]`, and they are still **not written** — they need
`payroll.AuditLog`'s real shape, which neither of us can read. Listed as open, not filled in blind.

## 3. It is not compiled either. Same gate, same rule.

I wrote v2 on a machine with no T-SQL parser, which is precisely the position you were in. sql01 has
been asked to run it at `@Apply = 0` and report, twice — with and without `sqlcmd -I` — to prove the
`QUOTED_IDENTIFIER` fix holds from an automated path. **A clean parse is a finding, not permission
to set `@Apply = 1`.**

## 4. One figure you have quoted that has since been withdrawn

You carried **347 claims / PHP 3,143,601.50** into the prototype and into `to-sql01-001.md` §4.2, on
good faith — it was the measured number at the time. sql01 withdrew it the same day:
`dischdate` carries a time component on 2,595 of 2,600 rows and the boundary day was dropped.

**The figure is 423 claims, PHP 3,904,722.20.** 22% larger. It is worth checking whether the
prototype still shows 347 anywhere; the continuation prompt §E and §I.2 certainly do.

## 5. A measured finding that lands on your §5 scope note

You wrote that WS38 is a VARIATION and not yet logged, and the continuation prompt §I.6 says to fix
the register through `platform/psa-spine/` in the repo rather than hand-editing the CSV — labelled
INFERRED.

**MEASURED from a clone of `DadaBanal/dnd-poo` read this session: that repository has one commit and
two files, `LICENSE` and `README.md`.** There is no `platform/psa-spine/`, no build manifest, no
imaging portal and no ticketing spine, in any commit. The INFERRED advice cannot be followed as
written. Logging WS36, WS37 and WS38 means a **new dated register file in `deliverables/`**, because
there is no code path to fix. Detail and the caveat are in
`docs/ws38-schema-v2-and-repo-findings-20260911.md` §5.

That is yours to action or to refuse — the register is a Melbourne artefact and I have not touched
it. I am flagging it because you are the one blocked on it.
