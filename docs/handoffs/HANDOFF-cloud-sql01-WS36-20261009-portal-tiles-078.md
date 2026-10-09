# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (tiles on My requests, 078)

**One schema step, 078 (three new tables, one nullable column on `psa.ticket`), the usual restart. Then a
preview of the starter tiles, which is applied only after Dada has seen it.**

This follows `…-20261009-schedule-edit-outlook-077.md`. 077 and 078 are independent: either can go in first, and
both can go in one window. It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for

Dada, 9 Oct 2026: *"on the my requests portal we should add in there an option like the help portal for connectwise
like choosing tiles what are your issues so that we can route to the procurement board the pmo helpdesk board so it
helps the ticketer"*.

Confirmed before building:

- A Setup page holds the tiles (Setup › Portal tiles).
- A tile can open smaller tiles. It sends the request to its board with its Type › Subtype › Item set, and asks a few
  questions.
- **Every department sees every tile.** Dada: *"every department has procurement inventory mms issues"*.
- The ten-tile starter set I proposed.
- An Item marked *needs approval* asks for it from the portal too.

The README section is *Tiles on My requests, in the reference PSA's help-portal shape*.

**What this changes for Procurement.** MEASURED by SQL01 on 6 Oct: no department is ticked for PROCUREMENT, so no ward
can reach it from the portal today; it takes mail only. Once the tiles are applied (§4), every ward can raise
*Buy something* and *Stock, a delivery or a PO* requests straight onto PROCUREMENT.

PROCUREMENT still has `notify_requester = 0` (runbook, Part 44). So those requesters get no email updates and follow
their request on the portal. Turning requester email on stays Dada's separate decision.

## 2. What runs without 078

**This head runs without 078.** MEASURED from the code: the portal asks `db.table_exists(conn, "portal_tile")`, and
without the table *My requests* shows the plain form exactly as today. With 078 but no tile, it shows the same. Wards
see a change only once tiles exist (§4).

## 3. The step: 078, then restart

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`. PSA-Notify and PSA-Calendar can stay as they are: neither touches these tables.
4. Note `SELECT COUNT(*) FROM psa.ticket`.
5. In one transaction, as sysadmin via pyodbc as for 066 to 077, run these blocks, each taken verbatim from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql` (they are all guarded, so a second run changes nothing):
   - the three `CREATE TABLE` blocks under `-- portal_tile`, `-- portal_tile_question` and `-- portal_answer`
     `(from schema/078_portal_tiles.sql)`, **in that order**;
   - the two indexes `ix_portal_tile_parent` and `ix_portal_tile_question_tile`;
   - `IF COL_LENGTH(N'psa.[ticket]', N'portal_tile_id') IS NULL`
     `ALTER TABLE psa.[ticket] ADD [portal_tile_id] INT NULL CONSTRAINT [FK_ticket_portal_tile_id] REFERENCES psa.[portal_tile]([tile_id]);`
6. Verify, inside the transaction:
   - `OBJECT_ID(N'psa.portal_tile')`, `OBJECT_ID(N'psa.portal_tile_question')` and `OBJECT_ID(N'psa.portal_answer')`
     are all non-NULL.
   - `COLUMNPROPERTY(OBJECT_ID(N'psa.portal_tile'), N'tile_id', 'IsIdentity')` is **1**, and so is the same for
     `portal_tile_question.question_id`. These are the tables' own new numbers. 072's fault was the opposite case: a
     copied key made IDENTITY.
   - `COL_LENGTH(N'psa.ticket', N'portal_tile_id')` is **4**.
   - `SELECT COUNT(*) FROM psa.ticket WHERE portal_tile_id IS NOT NULL` returns **0**.
   - `SELECT COUNT(*) FROM sys.foreign_keys WHERE name = N'FK_ticket_portal_tile_id'` returns **1**.
   - `ticket` holds the count from step 4.
   - If any check fails, roll back and hand back.
7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

Nothing changes in any scheduled task, the file store or the backup.

## 4. What is usually ticketed, then the starter tiles: preview, apply after Dada has seen both

Dada, 9 Oct 2026: *"check the ticketing for previous errors so u can have a read to what is usually ticketed"*.

MEASURED: nothing in the repo or the record breaks the tickets down by topic. There are only totals per board and per
mailbox, and the subjects are kept on the host. So the read is done where the tickets are. Run this first, under the
desk account, from `platform/psa-spine`:

```
C:\PMC\Python312\python.exe -m psaspine ticket-topics "<the desk's connection>" --days 180
```

It writes nothing and prints **counts only**: never a summary, a name or a reference. MEASURED from the code
(`portal_tiles.topics`) and pinned by
`PortalTilesTest.test_ticket_topics_counts_what_was_ticketed_and_never_prints_a_summary`. It prints:

- tickets per board, and how many have a Type › Subtype › Item;
- the 25 most used Type › Subtype › Item;
- how many summaries each starter tile's words would have caught, per board;
- the same for Phone or extension and CCTV, which have no starter tile;
- how many tickets no tile's words catch.

**Paste it back whole.** It tells Dada and me whether a tile is missing (phones or CCTV, say) or one is never used,
before the tiles are applied.

Then the tiles. Run under the desk account, from `platform/psa-spine`:

```
C:\PMC\Python312\python.exe -m psaspine portal-tiles "<the desk's connection>" --actor "sql01 for dada.banal"
```

It writes nothing. It prints:

- one line for each of the nine tiles (`+ tile  Buy something  -> Procurement`);
- under each tile, its questions and its smaller tiles. Each smaller tile names the live Type › Subtype › Item it
  matched, or says `no catalogue match: the ticketer classifies it`;
- a last line, `Would add N tile(s) and M question(s). Preview only`.

The defaults are `--helpdesk IT_HELP --procurement PROCUREMENT`.

**Paste the whole preview back.** It holds tile names and catalogue names only: no person, no patient, no key.
Dada looks it over before anything is written, because the live catalogue was restructured on 2 Oct and the matches
are by name. INFERRED: some smaller tiles under *BizBox or a hospital system* will match the new Types (HIS, Pharmacy,
PhilHealth, BizBox MMS (Procurement), FMS). Where a live pair belongs to PROCUREMENT, the preview shows that tile going
to Procurement, because the catalogue's own routing wins.

When Dada says go, run the same command with `--apply` added. It ends `applied`.

- A second run adds nothing: every line reads `= … (already there …)` and the last line says `Added 0 tile(s)`.
- `SELECT COUNT(*) FROM psa.portal_tile` matches the preview's tile count.
- Setup › Audit shows `PORTAL_TILE` rows by the actor named.

## 5. What to look for

- **On the portal** (a ward PC, or any requester): *My requests* opens on **What do you need help with?**.
  - The nine tiles show, with **Something else, or not sure** last.
  - *Buy something* opens six smaller tiles. *IT equipment* opens the form: *This goes to **Procurement***, with the
    five questions.
  - Something else is the old form, routed as before.
- **The ticket.**
  - It is on the tile's board, and Type, Subtype and Item are already set.
  - The description ends with *Answers from the portal:*, and the activity says *raised from the portal tile …*.
  - `SELECT COUNT(*) FROM psa.portal_answer` goes above 0 with the first such request. Do not paste answers back:
    counts only.
- **Approvals.** A tile whose Item is marked *needs approval* in Setup › Catalogue now asks the requester's department
  approver, as the desk does. INFERRED: none of the starter Items is marked today; Dada marks them when wanted.
- **Setup › Portal tiles** (system administrators) lists them all, to rename, reorder, retire, or give a different
  Item or questions.

## 6. Evidence

| | |
|---|---|
| Unit suite | See the commit message (SQLite). New: `PortalTilesTest` (5): the starter set previews, then is added once; a ward's tile → smaller tile → form → ticket on Procurement with its pair, its answers kept and in the description, refusals kept what was typed; a retired tile and a tile with smaller tiles refused; Something else unchanged; an Item needing approval asks the department approver; Setup adds, edits, retires, and refuses a third level, an unknown Item, or no name; a store without 078 shows the plain form. |
| Browser checks | `tests/browsercheck.py`: 172 passed, 0 failed (MEASURED, this commit). New: the tiles and Something else on a phone's width with no sideways scroll; a tile opens its smaller tiles, then a form with its question; Send it lands the request on its board with its pair. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
| SQL Server | CI `psa-spine` run 78, dispatched on `1c43ac0`: green on all four jobs (Linux 3.11 and 3.14, sql-server, windows). MEASURED, 9 Oct 2026. |
| Not run here | 078 against `PMC_PSA`, and the preview against the live catalogue. |
