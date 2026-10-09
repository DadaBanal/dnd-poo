# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (Procurement emails its requesters; what the 104 are)

**No schema step and no restart. There are two parts, A and B. Each stops on a check if anything does not
match.**

This follows Parts 58–60. It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## What Dada asked for

Dada, 9 Oct 2026:

- On the 104 tickets no tile caught: *"yes build it"*, meaning say what those tickets are.
- *"also enabled procurement emails to requesters"*.
- *"make sure this is stupid proof"*.

What changed in the code (MEASURED, this head):

- `psaspine ticket-topics` gains one section at the end. For the tickets no tile's words caught, it shows how the
  desk classified them: Type › Subtype, or *no Type › Subtype › Item yet*. It is still counts only, never a summary,
  a name or a reference, and still writes nothing.
- Nothing else in the code changes. Procurement's emails are switched on with the desk's existing `mail-setup`
  command, previewed first. It is the same command and the same shape as PMO Helpdesk's (Part 31: 9 of 9 on).

Neither part needs PSA-Desk restarted. `ticket-topics` and `mail-setup` are command-line, and the board's email
switch is read fresh each time an email is queued.

---

## Part A — what the 104 are (read-only)

Under the desk account, from `platform/psa-spine`, as in Part 58:

```
C:\PMC\Python312\python.exe -m psaspine ticket-topics "<the desk's connection>" --days 180
```

**Check:** the output ends with a new section, `Of the N no tile's words caught, how the desk classified them`. N
should be about 104, a little more if tickets came in since.

**Paste the whole output back.** It is counts and catalogue names only.

---

## Part B — Procurement emails its requesters

### B1. Before: write these down (read-only)

- `SELECT COALESCE(notify_requester, 0) FROM psa.board WHERE board_id = N'PROCUREMENT'` gives **0**. If it is
  already 1, stop and say so.
- `SELECT COUNT(*) FROM psa.notification WHERE status = N'PENDING'`: write the number down as **P**.
- PSA-Notify's last result is **0**, and its command line still reads `-Mailbox helpdesk@pmcne.ph -SendAs
  support@pmcne.ph …`.

### B2. Preview (writes nothing)

```
C:\PMC\Python312\python.exe -m psaspine mail-setup "<the desk's connection>" --board PROCUREMENT --email-requester on --moving-emails on --actor "sql01 for dada.banal" --show
```

**Check**, line by line:

- `Procurement: email the requester on`
- `Procurement: <n> status and picked-up email(s) turned on`. n is one per Procurement status plus *picked up*.
  INFERRED from Part 38's board-compare, which counted 11 statuses: about 12.
- The `--show` listing starts `Procurement (PROCUREMENT)` / `email the requester: ON`, then each email with its
  subject and words. These are templates such as `{requester}` and `{status_text}`; no ticket appears in them.
- The last line is `PREVIEW: nothing written; re-run with --apply`.
- Re-run B1's first query: it is still **0**.

If any line differs, stop and paste the preview back.

### B3. Apply

The same command with `--apply` added. It ends `applied`.

### B4. Verify

- `notify_requester` for PROCUREMENT is now **1**.
- `SELECT COUNT(*) FROM psa.notification WHERE status = N'PENDING'` is still **P**. No email is queued about any
  ticket already there: the emails start with each ticket's next move. MEASURED in the code, and pinned by
  `PortalTilesTest.test_procurement_emails_its_requesters_from_the_next_move_and_never_for_the_backlog`.
- `SELECT COUNT(*) FROM psa.audit_event WHERE action = N'BOARD_CONFIG' AND subject_id = N'PROCUREMENT' AND detail =
  N'email the requester: on'` returns **1**.
- Running B3 a second time changes nothing (the count stays 1).

If P has grown by more than the mail that arrived in the meantime, or the switch did not flip, put it back with the
undo below and hand back.

### B5. Do not touch

- **PSA-Notify's registration.** Procurement's emails go out from its own mailbox, **helpdesk@**, because
  procurement@ is not in its `-SendAs`. MEASURED: `Send-PmcNotifications.ps1` sends from the address the requester
  wrote to only when it is `-Mailbox` or in `-SendAs`, and from `-Mailbox` otherwise. A requester's reply still lands
  on the Procurement ticket, because the subject carries its `[PMC-…]` reference.
- Adding `-SendAs procurement@pmcne.ph` stays the open item from Part 35. It needs the Graph grant on procurement@ to
  have landed first, and it is not part of this step.
- The procurement@ forwarding bridge: leave it as it is.

### Undo (only if B4 fails)

```
C:\PMC\Python312\python.exe -m psaspine mail-setup "<the desk's connection>" --board PROCUREMENT --email-requester off --moving-emails off --actor "sql01 for dada.banal" --apply
```

---

## What to look for afterwards

- The next time a Procurement ticket changes status (say, to *For Quotation*):
  - a `notification` row for that ticket goes PENDING;
  - within a minute PSA-Notify marks it SENT, from helpdesk@.
  - Hand back counts and statuses only, never the email.
- A ward raising *Buy something* on the portal gets *We have your request*, as PMO Helpdesk requesters already do.

## Evidence

| | |
|---|---|
| Unit suite | See the commit message (SQLite). New or extended in `PortalTilesTest`: `test_ticket_topics_counts_what_was_ticketed_and_never_prints_a_summary` (the new section: the unmatched by the desk's Type › Subtype, or not classified; no summary text) and `test_procurement_emails_its_requesters_from_the_next_move_and_never_for_the_backlog` (the preview changes nothing; apply flips the switch and is audited once; no email for a ticket already there; the next status change emails the requester once; a second apply changes nothing). |
| SQL Server | CI `psa-spine`, dispatched on this head. NOT VERIFIED until it reports. |
| Not run here | `mail-setup` against `PMC_PSA`, and PSA-Notify sending a Procurement email. |
