# HANDOFF — Cloud Build → SQL01, WS36, 5 Oct 2026

**One job: restart PSA-Desk onto the new head. There is no schema step.**

Supersedes nothing. Adds to `HANDOFF-cloud-sql01-WS36-20261002-mail-window-and-schema.md`
and the 3 Oct 065 handoff, both of which still stand. Your Part 33 is read and nothing in
it is reopened.

Branch `claude/psa-ticketing-build`, head **b388977** (merge of my `17cae9f` onto your
`784e016`). Pull before reading anything below.

---

## 1. What changed, and why it is code only

Dada, with a live ticket open, sent a screenshot of an intake note reading:

```
[Speaker phone with solid fill]
The Teams phone on Ward 3 is not ringing...
[cid:image004.jpg@01DD5349.6A321CD0]
Portal <https://portal.pmcne.ph/x> Portal
https://portal.pmcne.ph/x
```

**MEASURED cause.** An Outlook message carries two bodies — `text/html`, which the sender
composed, and `text/plain`, which Outlook generates from it. `intake.body_of` kept only
the second. Everything odd in that screenshot is the shape of the generated fallback: an
icon becomes its own alt text, an inline image becomes its `cid:` reference, and a link is
written twice (once as its label, once as its address). Nothing was broken; the desk was
showing the wrong one of the two bodies the mail arrived with.

**Fixed:** intake now keeps the HTML part and the ticket shows it, through
`richtext.clean` — the one 064 gate a technician's own note already goes through.
`ticket_event.body_format` is `'HTML'` on the `INTAKE` and `INTAKE_REPLY` events that came
in that way.

**`body_format` is the column you applied in 064 on 2 Oct** (`psa.ticket_event`,
NVARCHAR(32) NULL, your Part 31 step 1, COL_LENGTH 64 measured after). Nothing new is
needed, in either schema copy. `tools/sqlite_to_tsql.py --check` is green on this head, so
the drift gate agrees there is no DDL here.

## 2. The step

Exactly your sitting-1 restart, with the schema half left out:

1. Pull the branch to the desk's checkout.
2. Stop `PSA-Desk`.
3. Start `PSA-Desk`.
4. `:8085` should answer 401, go down, and answer 401 again inside a couple of seconds.

**No backup is required for this one** — nothing writes DDL and no row is rewritten. Take
one anyway if that is the local habit; it costs nothing and it keeps the road identical.

**Mail does not need to be re-run.** Tickets already in the database keep the plain text
they were stored with and read exactly as they do now; the change applies to mail that
arrives after the restart. If Dada wants the 3 Oct–5 Oct window re-rendered as HTML that
is a re-import question and a separate decision — **do not** do it off this handoff.

## 3. What to expect to see afterwards, and what must never appear

A ward's next email on a ticket should read as the sender wrote it — bold where they used
bold, a list where they used a list, one link per link, a signature whose lines are apart.

What the gate refuses, which is the part that matters on a clinical desk:

| | |
|---|---|
| Script, style block, event handler, iframe, `javascript:` link | **Never written.** The gate writes a new document out of its own allow-lists rather than editing the one it read, so these are not removed — they never get as far as the database. |
| Every image, inline or remote | **`<img>` is not on the lists**, so no tracking pixel can phone home and no remote image can tell a sender that a clinician opened the ticket and when. A file the mail attached is still kept on the ticket, through the PHI review it always went through. Showing it *inside* the note is **not built** — see §5. |
| Word's and Outlook's `mso` markup, `<o:p>`, conditional comments | Unwrapped or dropped; the words are kept. |

**If any of the following appears on a ticket after the restart, stop and tell me — it
would mean the gate is not in the path:** a visible `<` tag read out as words, a
`[cid:...]` reference, an image loading from outside PMC, or the same link printed twice.

## 4. The PHI fence, restated for this change

- The scan reads **the words of both bodies**, because a patient reference can sit in the
  HTML and not in the fallback (a link's own text, a table cell). `phi.scan` gives at most
  one finding per rule per field, so one name present in both parts is still **one** row
  on Setup › Data quality, not two. Expect no change in flag volume from this.
- A flagged intake note behaves as it did: recorded, visible, and the requester email
  carries the portal words rather than the note.

## 5. Open, and not mine to decide

1. **Inline images are not shown.** A screenshot pasted into an email is kept as a file on
   the ticket but the note shows a gap where it sat. Resolving `cid:` to the stored
   attachment needs a `content_id` on `attachment` (a schema step) and an `<img>` allowed
   with a `src` that can only be this desk's own `/ticket/<id>/file/<n>` — never a scheme,
   never a host. I have **not** built it. It is the obvious next ask and it is a real
   schema change, so it waits for Dada.
2. **Re-rendering mail already imported** (§2) — Dada's call, not an operational step.

## 6. Evidence on this head

| | |
|---|---|
| Unit suite | **736 OK**, 1 skipped (SQLite). 11 new tests, all in `RichEmailTest`, built on a message in the shape Outlook actually sends: `multipart/related` around `multipart/alternative`, a `<style>` block, two `cid:` images, a layout table, a `<script>` and a remote 1×1 pixel. |
| Browser checks | **30 of 30** in a real Chromium (`tests/browsercheck.py`, five of them new): the page shows bold rather than the word `<b>`; no tag or `cid:` is read out as words; the link is a link, written once; **zero** `img` elements exist in the note; and a `<script>` carried in the email **did not run** (asserted by evaluating `!window.BROKE_IN` in the page). |
| Drift gate | `tools/sqlite_to_tsql.py --check` — in step. |
| Smoke | 7 of 7. |
| Not run here | Nothing. There is no host-only step in this change. |

## 7. Two older defects fixed in the same commit

Both were already wrong for desk-written rich notes from 064 onward; keeping the HTML of
email would have made them common. Neither needs anything on the host.

1. A board row's 90-character preview of the last note spent all 90 characters on that
   note's opening tags. It now previews the words.
2. Merging a duplicate ticket carried a rich note across as plain text, so it read as its
   own markup on the ticket it was merged into. `body_format` now travels with it.

## 8. One test was a time bomb, for the record

`MailCutoverTest.test_the_desk_says_whether_mail_is_becoming_tickets_at_all` pinned its
fixture mail to a fixed date and left `intake.health`'s window to the real clock, so it
passed in the week it was written and started failing on 4 Oct. It is **not** a regression
from this change. `intake.health` now takes an `at` (defaulting to now, which is what the
host wants), and the CLI assertion widens its `--days` to reach the fixture. Worth
knowing in case you see it red on an older checkout.

---

## Reply

Please reply as **Part 34** in
`docs/handoffs/HANDOFF-cloud-sql01-WS36-20260926-runbook.md`, with the head you restarted
onto, the `:8085` 401 → down → 401 timing, and anything from §3's "must never appear" list
that did appear.
