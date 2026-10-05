# HANDOFF — Cloud Build → SQL01, WS36, 5 Oct 2026 (second today)

**One job: restart PSA-Desk onto the new head. No schema step, no backup needed.**

Adds to `HANDOFF-cloud-sql01-WS36-20261005-email-html.md`, which you ran as Part 34.
Nothing in that is reopened. Your Parts 34–37 (the gate check, procurement@, the 403
`-KeepOnForbidden` fix) are read and merged.

Branch `claude/psa-ticketing-build`, head **b16f7e5** (my `f0f5860` merged onto your
`11d6496`). Pull before reading anything below.

---

## 1. What changed

Two asks from Dada in one line. Both are code only.

**Nine forms asked for a ticket number typed from memory** — link a related ticket, attach
a child, make this a child of, merge into, the board's two bulk fields, put a ticket on a
project, and the two ways of booking a visit. They are now one control: a text input with
a `datalist` the browser fills from `/search.json` as you type. The search behind it widened
from three fields (number, summary, requester) to every field a person would search by,
**including the words of a ticket's notes**.

**A project's plan could not be corrected.** A phase could be added and marked done and
that was all, so a typo in a phase name, a predecessor set the wrong way round, or a ticket
on the wrong project were permanent. All of it is now editable, and anything carrying no
work can be removed. Work is still never deleted: a phase with tickets or booked hours is
kept and offers Done; a project that got going is cancelled, not deleted.

## 2. The step

Your sitting-1 restart with the schema half left out, exactly as this morning:

1. Pull the branch to the desk's checkout.
2. Stop `PSA-Desk`.
3. Start `PSA-Desk`.
4. `:8085` should answer 401, go down, and answer 401 again inside a couple of seconds.

**No DDL and no row is rewritten**, so no backup is required; take one if that is the local
habit. `tools/sqlite_to_tsql.py --check` is green on this head.

## 3. One thing worth your eye, because it is a query cost

The ticket search now has a clause that **cannot use an index**: it matches the words of
`ticket_event.detail` for notes. On the pilot's ~275 tickets that is nothing. It is the one
part of this change whose cost grows with the desk, and it runs on every keystroke-ish
(debounced 140 ms) in a picker.

If you see `/search.json` getting slow on the host as the ticket count climbs, that clause
is why, and the fix is a full-text index rather than a `LIKE` — tell me and I will do it.
I have **not** pre-emptively added one: it would be a schema step on a guess, and the
measurement that would justify it can only be taken there.

`LIMIT` is 8 rows, and the restricted-board audit is unchanged (one row per board per
search, with the count), so nothing about who may see what moved.

## 4. What to expect to see

- Every field that names another ticket is a search box. Typing a word from a summary, a
  ward, a person, a company, a status — or a word from one of its notes — fills the
  dropdown. A ticket is **never** offered to itself.
- A project's phases each have **Edit**, **↑ ↓**, and either **Remove** or, where it
  carries work, text saying what is holding it (`kept: 2 ticket(s) are on it`).
- Each "waits on" is a chip with a **×**.
- A project with phases, tickets or a BizBox record shows no Remove button and says it
  would be cancelled instead.

**If a picker's dropdown stays empty when you type two or more characters**, that is worth
reporting: it means the fetch is not reaching `/search.json`, and the field falls back to
being a plain number box (which is what it was before today, so nothing breaks — it just
stops helping).

## 5. Evidence on this head

| | |
|---|---|
| Unit suite | **740 OK**, 1 skipped. 4 new tests. |
| Browser checks | **43 of 43** in real Chromium (`tests/browsercheck.py`, 13 new). These matter here because a `datalist` is filled by a fetch: they prove a word existing only inside a note fills the dropdown, that the option says it was found in a note, that the ticket you are on is never offered, and that a tag name (`noopener`) fills it with nothing. On the project side they drive the real rename and the real predecessor removal. |
| Drift gate | In step. |
| Smoke | 7 of 7. |
| Not run here | Nothing; there is no host-only step. |

## 6. Open, not mine to decide

1. **The full-text index** in §3, which waits on a measurement only the host can take.
2. Still open from this morning: **inline images from email** (needs a `content_id` column
   on `attachment`), and whether mail already imported gets re-rendered as HTML.

---

## Reply

Please reply as the next Part in
`docs/handoffs/HANDOFF-cloud-sql01-WS36-20260926-runbook.md`, with the head you restarted
onto, the `:8085` timing, and anything from §4's last paragraph if a picker came up empty.
