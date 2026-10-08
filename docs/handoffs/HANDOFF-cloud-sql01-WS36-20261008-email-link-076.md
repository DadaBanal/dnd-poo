# HANDOFF — Cloud Build → SQL01, WS36, 8 Oct 2026 (proving the email link, and mending old ones, 076)

**One schema step, 076 (one nullable column), the usual restart, then a check that needs no mailbox.**

This answers SQL01's report after 075 (Part 53, `2e57242`) and supersedes nothing. 075's handoff stands, with its
correction note (PSA-Notify, held by disabling).

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What SQL01 found, and what Dada asked for

SQL01, 8 Oct, MEASURED on `PMC_PSA` after 075:

- 0 of 894 notifications contain the link: the sender puts it together at the moment of sending, so the database
  never held which link a person was sent.
- `PORTAL_LINK` rows: 0. Correct, since nobody has opened a request by key yet.
- PMC-000391 has no `portal_key`: it is on PROCUREMENT and its 6 notifications all predate 075. PMC-000397 and
  PMC-000398 have keys.
- The host cannot click a link in a requester's mailbox, so a link could not be proved from SQL01.

Dada, 8 Oct: "find a proper solution for this". Confirmed with Dada before building, all three:

- **Keep the link on each email** (`notification.portal_link`), written by the sender as it builds the email.
- **A check on the host, no mailbox needed**: `psaspine portal-check`.
- **Mend old links**: *Copy the requester's link* on the desk, and *Send a fresh link* on the portal's *No such
  request* page.

## 2. The step: 076, then restart

**This head runs without 076.** MEASURED from the code: the sender writes the link only when the column exists
(`db.column_exists`), and nothing else reads or writes it. So the order is not critical, but until 076 is in, no
link is kept.

1. **Disable** PSA-Notify (a stopped minute task fires again on its own trigger), so no pass runs half-pulled code.
2. Pull.
3. Take a COPY_ONLY backup of `PMC_PSA`.
4. Stop `PSA-Desk`.
5. Note `SELECT COUNT(*) FROM psa.notification`.
6. In one transaction, as you applied 066 to 075, run the statement taken verbatim from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql` under `-- … (from schema/076_notification_link.sql)`. It is guarded:
   - `IF COL_LENGTH(N'psa.[notification]', N'portal_link') IS NULL`
     `ALTER TABLE psa.[notification] ADD [portal_link] NVARCHAR(400) NULL;`
7. Verify, inside the transaction:
   - `COL_LENGTH(N'psa.notification', N'portal_link')` is non-NULL (800: 400 characters).
   - `SELECT COUNT(*) FROM psa.notification WHERE portal_link IS NOT NULL` returns **0**. Every email so far was
     sent without one kept.
   - `notification` holds the count from step 5.
   - If any check fails, roll back and hand back.
8. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.
9. **Re-enable** PSA-Notify.

Nothing changes in PSA-Notify's command line, the file store or the backup.

## 3. The check, with no mailbox

Run under the desk account, from `platform/psa-spine`, as you run `mail-why`:

```
C:\PMC\Python312\python.exe -m psaspine portal-check "<the desk's connection>" --ticket PMC-000397 --portal-url https://help.pmcne.ph
C:\PMC\Python312\python.exe -m psaspine portal-check "<the desk's connection>" --ticket PMC-000397 --person joseph.marcelo --portal-url https://help.pmcne.ph
C:\PMC\Python312\python.exe -m psaspine portal-check "<the desk's connection>" --ticket PMC-000391 --person joseph.marcelo --portal-url https://help.pmcne.ph
```

What it does (MEASURED from the code, `psaspine/portal_check.py`): it signs the person in the way the portal's doors
would (a Windows name, with their contact's address; or an address, as Entra gives it), sends the portal's own router
a GET for the request on `help.pmcne.ph`, and reports what came back. **It writes nothing.** The key a first email
would make is rolled back. A read by key is not written to the audit trail at all (it is the check, not a person), so
no `PORTAL_LINK` row appears and no number in the trail's sequence is used up. It holds a row lock on that one ticket
for the moment it runs. The session it uses is signed with a secret made for the run and never leaves the
process. `--portal-url` can be left off where `PSA_PORTAL_URL` is set.

**What to expect:**

- **PMC-000397, no `--person`** (its requester): `its email link: https://help.pmcne.ph/my/PMC-000397?k=xxxx...`,
  then `-> they see it, with or without the key.`
- **PMC-000397 as joseph.marcelo** (someone it is not raised by; if it is his, use any other Windows name):
  - the plain link `-> 404 Not Found  not theirs by any address the desk holds`
  - `(the email link) -> 200 OK  opens by the link`
  - a wrong key `-> 404 Not Found  (as it must)`
- **PMC-000391 as joseph.marcelo**: `(no key yet: none of its emails was sent with one ...)`, then the email link
  `-> 200 OK`. That proves the key route works for it. The key shown is only for the check: none is kept.
- The last line is always `Nothing was written: every change this check made was rolled back.` Afterwards,
  `SELECT portal_key FROM psa.ticket WHERE work_item_id = N'PMC-000391'` is still NULL, and `PORTAL_LINK` rows are
  still 0.

**Keys in what you paste back.** A whole key opens that request to anyone signed in. `portal-check` prints four
characters of it and then `...`. Paste its output as it is. Do not paste a key read from the database.

**What the check does not prove** (INFERRED): the path from a ward PC to `help.pmcne.ph` (DNS, IIS, TLS). The 401 in
step 8 proves the desk answers. A browser on the hospital network proves the rest.

## 4. After the next requester email

Once PSA-Notify has sent a requester email (any status change or Discussion note on a board that emails requesters):

- `SELECT COUNT(*) FROM psa.notification WHERE portal_link IS NOT NULL` is above 0.
- `portal-check` on that ticket lists it: `#n SENT <when>: https://help.pmcne.ph/my/PMC-nnnnnn?k=xxxx...  (this ticket's key)`.
  `NOT this ticket's key` there would be a defect: hand back.

## 5. What Dada and the desk will see

- **PMC-000391 and every request whose emails went before 075.** Two ways to mend the link:
  - **On the desk.** On the ticket, under *Contact*, **Copy the requester's link** copies the link the emails now
    carry, to paste into a reply. It is shown to anyone who works the ticket's board. The first press makes the
    ticket's key if it has none. Each press is in Setup › Audit as `PORTAL_LINK_COPIED`.
  - **On the portal.** The *No such request* page now offers **Send a fresh link to the address this request came
    from**. The link goes only to the ticket's own requester, never to the person asking. At most one is sent an hour
    per request. None is sent while another requester email is waiting to go, since that one carries the link. None
    is sent on a board that does not email its requesters. The page says the same thing whether or not the request
    exists, so asking teaches nothing. Each ask is in Setup › Audit as `PORTAL_LINK_REQUEST`, with what happened. When
    one is queued, the ticket's activity says so and names who asked.
- `who-sees` now uses the portal's own rule (with 075's own-domain match), so it cannot disagree with the portal.

## 6. Evidence

| | |
|---|---|
| Unit suite | See the commit message. New in `PortalIdentityTest`: `test_the_link_each_email_carried_is_kept_on_it` (kept for the requester's email as it went; none on a dry run, without a portal address, or for an approver's email; a store without 076 sends the same email and writes nothing), `test_the_host_proves_a_link_without_a_mailbox` (the four answers and why; no key kept and no audit row written; the requester by default; the kept link with its key cut to four characters, never whole; refusals), `test_the_desk_hands_a_technician_the_requesters_link` (no button or link without a portal address, or for a reader; the JSON and the no-script page carry the same key; audited; the link opens the request on the portal), `test_a_fresh_link_goes_only_to_the_address_the_request_came_from` (offered for any reference; the same page whether the request exists; one email to the requester with the keyed link; not again within the hour; each ask audited). `test_the_desk_can_say_why_in_one_command` now also covers the own-domain match. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
| Not run here | 076 and `portal-check` against SQL Server. The `sql-server` CI job runs on push. |
