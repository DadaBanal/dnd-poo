# HANDOFF — Cloud Build → SQL01, WS36, 8 Oct 2026 (the chat rating fails on SQL Server)

**One repair on `psa.chat_survey` (drop and re-create it, empty), no code to restart for. Nothing else changes.**

This follows `…-20261008-email-link-076.md`, which SQL01 applied at Part 55 (`1050f7e`). It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What happened

Dada, 8 Oct, screenshot: `https://help.pmcne.ph/my/chat/3/survey` answered *A server error occurred. Please contact
the administrator.* That is the bare server's page for an error the desk did not catch.

**The cause.** MEASURED from `sqlserver/PMC_PSA_Spine_SqlServer.sql` as it stood at `97bcf34`:

- `psa.chat_survey.chat_id` was made `INT IDENTITY(1,1)`. The translator turns SQLite's `INTEGER PRIMARY KEY` into
  IDENTITY.
- But this key is not a new number. It is the chat's own key, copied (`REFERENCES chat_session`).
- Every rating inserts that value, and SQL Server refuses an explicit value in an IDENTITY column.
- So every chat rating on `PMC_PSA` has failed since 072, the same way.

INFERRED: `PSA-Desk`'s error log, if it keeps the service's stderr, holds *Cannot insert explicit value for identity
column in table 'chat_survey'* for each attempt.

**Why the tests did not catch it.** The unit suite and the browser checks pass on SQLite, where the insert is
legal. The suite was last run against SQL Server in CI run 74, on 30 Sep, before chat existed. Earlier handoffs here
said *the `sql-server` CI job runs on push*. **That was wrong.** The workflow runs on a push to `main`, a pull request
or a dispatch, and this branch is none of those (the runbook says so). I dispatched it on this head; the result is
recorded in §4 when it finishes.

**The fix in the code.** `tools/sqlite_to_tsql.py` no longer makes a key IDENTITY when it references another table.
Exactly one line of the port changes: `chat_survey.chat_id` is now `INT NOT NULL`. Nothing else in the port carries
that shape (MEASURED: no other `IDENTITY … REFERENCES` column). A new test pins it:
`PortTest.test_a_key_copied_from_another_table_is_never_identity`.

**Why there is a step at all.** The port creates `chat_survey` only `IF OBJECT_ID(...) IS NULL`, so re-running it
changes nothing on `PMC_PSA`. SQL Server cannot remove IDENTITY from a column in place, so the table is dropped and
re-created. That is safe only while it is empty, which it must be, since no insert ever succeeded.

## 2. The step

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Measure, before anything changes. Both must hold, or stop and hand back:
   - `SELECT COLUMNPROPERTY(OBJECT_ID(N'psa.chat_survey'), N'chat_id', 'IsIdentity')` returns **1**.
   - `SELECT COUNT(*) FROM psa.chat_survey` returns **0**.
   - Note `SELECT COUNT(*) FROM psa.chat_session` and `SELECT COUNT(*) FROM psa.chat_message`.
4. Stop `PSA-Desk`. PSA-Notify does not touch this table and can stay as it is.
5. In one transaction, as sysadmin via pyodbc as for 066 to 076:
   - `DROP TABLE psa.[chat_survey];`
   - The `CREATE TABLE psa.[chat_survey] ( … );` taken verbatim from `sqlserver/PMC_PSA_Spine_SqlServer.sql`, the block
     under `-- chat_survey   (from schema/072_chat_extras.sql)`, without its `IF OBJECT_ID … BEGIN` / `END` guard. Its
     first column must read `[chat_id] INT NOT NULL CONSTRAINT [PK_chat_survey] PRIMARY KEY …`.
6. Verify, inside the transaction:
   - `COLUMNPROPERTY(OBJECT_ID(N'psa.chat_survey'), N'chat_id', 'IsIdentity')` returns **0**.
   - `SELECT COUNT(*) FROM psa.chat_survey` returns **0**.
   - The foreign key exists:
     `SELECT COUNT(*) FROM sys.foreign_keys WHERE name = N'FK_chat_survey_chat_id'` returns **1**.
   - `chat_session` and `chat_message` hold the counts from step 3.
   - If any check fails, roll back and hand back.
7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

Nothing changes in the code that runs, the file store, the backup or any scheduled task.

## 3. What to look for

- **Chat 3.** Its ward opens `/my/chat/3` and rates it again. *Send the rating* now lands back on the chat with
  *You rated this chat …*. Their first try was never kept, so the card is still there to answer.
- **On the desk**, the chat's page shows *rated ★★★…* and Reports shows the rating under *Chat rating*.
- `SELECT COUNT(*) FROM psa.chat_survey` goes above 0 after the first rating.

## 4. Evidence

| | |
|---|---|
| Unit suite | See the commit message (SQLite). New: `PortTest.test_a_key_copied_from_another_table_is_never_identity`. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). One line differs from `97bcf34`. |
| SQL Server | CI `psa-spine`, dispatched on this head. NOT VERIFIED until it reports. |
