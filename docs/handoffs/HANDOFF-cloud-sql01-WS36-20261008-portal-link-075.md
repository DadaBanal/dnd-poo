# HANDOFF — Cloud Build → SQL01, WS36, 8 Oct 2026 (the portal's email link, 075)

**One schema step, 075 (one nullable column), then the usual restart. Apply 073 and 074 first if they are not in.**

> **Correction, 8 Oct 2026 (after SQL01 Part 53, `2e57242`).** This handoff names an `outbox-send` task. No task or
> command by that name exists: it was my error. The thing that builds and sends requester email is **PSA-Notify**
> (`scripts/Send-PmcNotifications.ps1`, which calls `psaspine outbox-pending --portal-url …` and then
> `psaspine outbox-mark`), and that is what SQL01 correctly held. SQL01 also corrected the method: a minute-task that
> is only *stopped* fires again on its own trigger, so holding it means **disabling** it, then re-enabling it after.
> Read "the `outbox-send` task" below as "PSA-Notify, disabled". MEASURED from the code: `outbox.pending` commits at the
> end of every pass that is not `--dry-run` (`psaspine/outbox.py`), so the key an email carries is the key the ticket
> keeps. The steps below are otherwise as they were applied.

This follows `…-20261007-chat-074.md` and supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for

Dada, 8 Oct: "when users click on the see my requests it goes to a 404". MEASURED from the screenshot:
`https://help.pmcne.ph/my/PMC-000391` answered *404 … You are signed in as joseph.marcelo*. The portal shows a
request only to the addresses it can prove are the person's; Joseph signed in by his Windows name and the request was
raised from an email address no contact row tied to that name.

Confirmed with Dada before building:

- **The "See your request" link carries the ticket's own key** (`?k=…`). Whoever holds the email opens that one
  request on the portal once signed in, whatever address they signed in with. A read by key is audited (`PORTAL_LINK`).
- **A Windows sign-in name also matches that name on the hospital's own mail domains** (`joseph.marcelo` ↔
  `joseph.marcelo@pmcne.ph`). The domains are read from the AD contacts and member records already in the database.

## 2. The step: 075, then restart

**075 must be in before PSA-Desk starts on this head.** INFERRED from the code: the sender makes the key the first
time it builds a requester email after this pull, and writes `ticket.portal_key`; without the column, `outbox-send`
fails on the first requester email.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk` and the `outbox-send` task (do not let a send run between the pull and the step).
4. If 073 or 074 is not applied, apply them first, per their handoffs.
5. In one transaction, as before, run the statement taken verbatim from `sqlserver/PMC_PSA_Spine_SqlServer.sql`
   under `-- … (from schema/075_portal_key.sql)`. It is guarded:
   - `IF COL_LENGTH(N'psa.[ticket]', N'portal_key') IS NULL`
     `ALTER TABLE psa.[ticket] ADD [portal_key] NVARCHAR(64) NULL;`
6. Verify, inside the transaction: `COL_LENGTH(N'psa.ticket', N'portal_key')` is non-NULL, and
   `SELECT COUNT(*) FROM psa.ticket WHERE portal_key IS NOT NULL` returns **0**. `ticket` holds the same count as before.
7. Start `PSA-Desk` and the `outbox-send` task. Expect `:8085` to answer 401, go down, then answer 401 again.

Nothing changes in the mail task's command line, the file store or the backup.

## 3. What to look for

- **The next requester email** has *See your request* pointing at `https://help.pmcne.ph/my/PMC-nnnnnn?k=…`, and the
  same link in the plain text under *See it here*. Emails sent before this pull still carry the plain link; those
  requests open by the own-domain match, or the requester asks the desk.
- **Joseph's case.** Signed in as `joseph.marcelo`, `/my/PMC-000391` opens, and *Your requests* lists it, provided it
  was raised from `joseph.marcelo@<a domain the staff are on>`. If it was raised from a shared mailbox, the key in
  the next email about it opens it.
- **Setup › Audit** shows a `PORTAL_LINK` row for every request opened by key, with the address or name that used it.
- A wrong or missing key on somebody else's request still answers the 404 with the signed-in name.

## 4. Evidence

| | |
|---|---|
| Unit suite | See the commit message. New in `PortalIdentityTest`: `test_the_email_link_opens_the_request_for_whoever_holds_the_email` (the key is stable; a wrong key 404s; the right one opens the request to another person, is audited, and the page's form and the reply's redirect carry it; a reply without it 404s; the email's text and HTML carry it) and `test_a_windows_sign_in_is_its_name_on_the_hospitals_own_domains` (joseph.marcelo opens and lists a request from joseph.marcelo@pmcne.ph; jose.marcelo does not; a gmail address never matches). |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
