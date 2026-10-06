# HANDOFF — Cloud Build → SQL01, WS36, 6 Oct 2026

**One schema step (066, one nullable column), then a PSA-Desk restart. Two reads after it.**

Supersedes nothing. Adds to both 5 Oct handoffs (`…-20261005-email-html.md`,
`…-20261005-pickers-and-projects.md`), which still stand; §5.1 of the email one ("inline
images are not shown … waits for Dada") is the thing this builds, on Dada's ask today.

Branch `claude/psa-ticketing-build`: the code is commit **50bfd04** and the commit that
carries this file (a fix to the frame's height, a dark-mode border rule, the docs and the
6 Oct guide). Pull the head before reading anything below.

---

## 1. What Dada reported, and what was wrong

Dada, with two screenshots of live tickets: replies *"look like these"*, *"emails are not
rendering properly on the ticket viewer"*, *"images are not rendering on the ticket"*, the
Procurement board *"does not look like the PMO helpdesk board"*, and *"menu and navigations
when ethel is logged in looks like the old one"*. Then: *"add a way to sort messages by
earliest first then to the newest on tickets"*.

| Report | Cause | Evidence |
|---|---|---|
| Every Outlook line a blank line apart; signature run flat | Outlook writes each line as its own `<p class=MsoNormal>` and zeroes its margin in a `<style>` block, which the gate rightly drops; the desk's own `p` margin then spaced every line. The note profile also unwraps tables. | MEASURED, reproduced in a test from a real Outlook reply's shape |
| The whole quoted thread at full length under each reply | Nothing folded it | MEASURED (screenshot) |
| Pictures missing | Intake kept the picture as a file but not the Content-ID the HTML calls it by, so the note could never find it again (your §5.1 of 5 Oct) | MEASURED in code |
| Ethel sees "the old menu" | The Entra door used the account's **object GUID** as the desk identity. It matches no `board_member` row, so the desk sees a person on no board and draws the three-link **requester** shell, with `/` sent to My requests. The Windows door uses `ethel.luciano`. | INFERRED from the code path and reproduced in a test; **§4 asks you to MEASURE which door she uses** |
| Procurement "does not look like" PMO Helpdesk | Not known. A board set up by hand usually lacks a calendar, SLA targets and ticket types, and that changes the board's columns and clocks. | NOT VERIFIED; **§5 is the read that measures it** |

**Fixed, in 50bfd04 and the commit after it:**

- **An email is drawn in a sandboxed frame**: `<iframe sandbox="allow-popups
  allow-popups-to-escape-sandbox allow-same-origin" srcdoc=…>` and **never** `allow-scripts`,
  under its own CSP (`default-src 'none'; img-src 'self'; …`). It goes through an email
  profile of the same `richtext` gate first (tables, divs and a short allow-list of inline
  CSS kept, **no colour, no background**, `img` only by `cid:`). Layered the way
  [Close](https://making.close.com/posts/rendering-untrusted-html-email-safely) and
  [AgentMail](https://engineering.agentmail.to/blog/rendering-email-safely-preventing-phishing-attacks)
  render untrusted mail. **No new dependency** on the host.
- **The quoted thread folds** under *Earlier messages in this email*, opened with a click.
- **Applied when a note is drawn, not only at intake**, so the tickets in Dada's screenshots
  read properly on the next page load with no re-import and no row changed.
- **066 `attachment.content_id`**: intake records each picture's Content-ID and the note
  shows it where it was pasted, from the desk only. The desk shows any image not WITHHELD and
  not purged; the portal only what it already shows a requester.
- **Entra maps to the member** by the member's email, then the sign-in's local part — the
  Windows door's rule. The GUID stays in the audit detail.
- **Oldest first / Newest first** on the Activity card, remembered per browser (cookie
  `psa_order`, Path `/ticket`).
- **Requester emails** carry a rich note as cleaned HTML (it went out as its own markup),
  reply only, PHI gate on the words first.
- **`board-compare`**: a read-only CLI that prints how two boards are set up differently.

## 2. The step

The sitting-1 road, as on 2 and 3 Oct. **066 must be in before PSA-Desk starts on this head**
— the new code names `attachment.content_id` when it stores an email's file and when it draws
a ticket that has one, so a desk started first would refuse mail with attachments and could
not draw those tickets (INFERRED from the code; not run against a database without the
column).

1. Pull the branch to the desk's checkout.
2. COPY_ONLY backup of `PMC_PSA`.
3. Preview: `.\Invoke-PsaSpine.ps1 -SchemaPreview` — expect **one** addition, the column.
4. **Stop `PSA-Desk`.**
5. Apply 066 by the method recorded on this host on 2 Oct (sysadmin via pyodbc), or
   `-SchemaApply` if `psa_desk` holds ALTER. The whole of it:

       IF COL_LENGTH(N'psa.[attachment]', N'content_id') IS NULL
       ALTER TABLE psa.[attachment] ADD [content_id] NVARCHAR(400) NULL;

   Guarded, so a re-run adds nothing. No existing row changes; every file already stored
   keeps `content_id` NULL.
6. Verify: `SELECT COL_LENGTH(N'psa.attachment', N'content_id');` → **800**.
7. `init`, then **start `PSA-Desk`**. `:8085` answers 401, goes down, answers 401 again.

## 3. What to expect afterwards, and what must never appear

**Expect:** an email on a ticket reads as it did in Outlook — lines a line apart, the
signature as its table, the earlier messages folded under a pill reading *Earlier messages
in this email*. The **Oldest first** link sits at the right of the Activity tabs. A
**new** email with a pasted screenshot shows the picture in place.

**Pictures in mail imported before the restart will not appear inside the note.** The file
is on the ticket's Files card as before, but the Content-ID was never recorded, so there is
nothing to tie it to its place. Recovering them would mean re-importing that mail — a
separate decision for Dada, **not** an operational step off this handoff.

**Stop and tell me if any of these appears** — each would mean a layer is not in the path:

- a tag read out as words, a `[cid:…]` reference, or a link printed twice;
- an email's lines a blank line apart;
- any picture whose address is not this desk's own `/ticket/…/file/…`;
- in the browser's developer tools on a ticket, an `iframe.mail` whose `sandbox` contains
  `allow-scripts`.

## 4. Read 1 — which door Ethel uses (MEASURE, writes nothing)

Before the restart, so the old behaviour is on record:

    SELECT TOP (20) occurred_at, actor, action, subject_kind, subject_id
    FROM psa.audit_event
    WHERE action IN (N'ENTRA_LOGIN', N'WINDOWS_LOGIN', N'LOCAL_LOGIN')
      AND (actor LIKE N'ethel%' OR subject_id LIKE N'ethel%')
    ORDER BY occurred_at DESC;

    SELECT board_id, member, access FROM psa.board_member WHERE member LIKE N'ethel%';

- **If her rows are `ENTRA_LOGIN` with a GUID as `actor`**, the cause above is MEASURED. After
  the restart her next `ENTRA_LOGIN` row's `actor` should read `ethel.luciano`, and she
  should land on the board with the full menu. Ask her to sign out and back in once.
- **If her rows are `WINDOWS_LOGIN` with `actor = ethel.luciano`** and she still saw the
  requester layout, my inference is wrong. Send me those rows and the `board_member` rows and
  I will look again; do not change her membership to make it fit.

Report hostnames and identifiers only, as always. No GUIDs from that table in the reply,
please — say "a GUID" or "the identifier".

## 5. Read 2 — Procurement against PMO Helpdesk (MEASURE, writes nothing)

    .\Invoke-PsaSpine.ps1 -Spine "board-compare IT_HELP PROCUREMENT"

It prints the board settings that differ (calendar, kind, owner, live, requester emails,
survey, default work role and type, …), each part of the set-up whose count differs
(statuses, SLA targets, ticket types, members, teams, addresses, per-status emails, standard
notes, templates, workflow and auto-assign rules, departments, on-call shifts), statuses on
only one side, and what each holds. Plain SELECTs; it reads the same on SQL Server as in the
tests. Paste its output back. **Do not fix anything it shows**: what Procurement should have
(its own SLA numbers, its calendar, which ticket types it takes) is Dada's to say, and the
owner/deputy gap you recorded on 1 Oct may be part of the answer.

## 6. One decision for Dada, carried here, not acted on

A signature reading *"Junior Philhealth Associate"* trips `PHI_PHILHEALTH_MENTION`, so every
requester email that quotes that person's reply goes out as the portal wording instead of
its text (MEASURED in a test built on the shape of the reply in Dada's screenshot). The rule
is doing what it was written to do. Whether a job title should count is the record's call,
not this code's. Nothing changed; it is listed so it is not mistaken for a fault.

## 7. Evidence on this head

| | |
|---|---|
| Unit suite | **751 OK**, 1 skipped (SQLite). New: `EmailOnTheTicketTest` (9), `TicketOrderTest`, an Entra test that a member signing in with Microsoft is on her boards; 066 is exercised by the inline-picture tests (shown on the desk, withheld, a logo not kept). The Entra test that used to assert `actor = oid-alice` was pinning the bug and now asserts the member. |
| Browser checks | **60 of 60** in a real Chromium (`tests/browsercheck.py`). For the frame: it exists; no `allow-scripts`; height equals the email's and **still does 1.5 s later** (a fit that crept 120 px/s was caught and fixed before this push); a `<script>` carried in the email never ran; lines 21–22 px apart; the signature has its cells; the pasted picture loads from `/ticket/…/file/1`; the fold starts closed, opening it grows the frame and closing it gives the room back; dark mode reaches inside; **nothing fetched from outside the desk**; and the order toggle reverses and is remembered. |
| Drift gate | `tools/sqlite_to_tsql.py --check` — in step; the port carries the guarded ALTER above. |
| Smoke | 7 of 7. |
| Not run here | 066 against SQL Server — the `sql-server` CI job runs it on push; I have no route to `DND-SQL01\PMC_SS`. Ward PCs' Edge is Chromium, so the browser checks should hold there (INFERRED, NOT VERIFIED on a ward PC). |

One note for whoever reads a console on the desk: a *"Blocked script execution in
'about:srcdoc'"* error appears only when an automation tool reaches into the frame — that is
the sandbox refusing the tool, as it should. A person clicking produces none (MEASURED).
