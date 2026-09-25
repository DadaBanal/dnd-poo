# WS36 — Pilot test script — 25 September 2026

The first day of the pilot, as a script two or three Dada IT technicians run at
the desk with the operator beside them. Each step says what to do and what
**Pass** looks like. Tick it, or write what happened instead. The completed
copy is filed beside `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260925-pilot.md`
and is the record of the day.

Rules for the day: no patient's name or case number in any ticket, note,
file or survey — the desk flags one if it slips through, and the flag is a
finding, not a failure. Everything is on the pilot database; Kitameraki stays
the system of record.

| # | Do | Pass | ✓ / what happened |
|---|---|---|---|
| **A — signing in** | | | |
| A1 | Open the desk's address in a browser on a technician's PC. | The sign-in page. `/` without signing in shows it with a 401. | |
| A2 | Sign in with the technician's account. | The Service Board, with the technician's name top right. | |
| A3 | Press `?`. | The keyboard sheet appears; `Esc` closes it. | |
| A4 | Press `t` twice. | Dark, then light again; reload keeps the choice. | |
| **B — a ticket's life** | | | |
| B1 | `n`, then raise a ticket: summary "Pilot test: printer in the test room", source Phone, who is affected "just me", patient waiting "no". | Ticket `PMC-0000nn` opens on its board, status New, a priority the matrix computed (not typed), three SLA boxes. | |
| B2 | On the board, the new row shows a Respond chip counting down. | Green chip, e.g. `R 55m`. | |
| B3 | Add a Discussion note "Looked at it, needs toner." with 0.25 h, charged as the agreement says. | Note appears flagged Discussion; Time pod shows 0.25 h; Respond chip turns ✓ once the status moves to In Progress. | |
| B4 | Move status to In Progress from the note's *And set status*. | Status chip changes; the system line under the note says which clocks stopped. | |
| B5 | Add an Internal note. | Shaded note; it never appears on the portal (checked in section F). | |
| B6 | Add a task "Order toner" and tick it. | Tasks pod shows 1 of 1 with who ticked it. | |
| B7 | Attach a screenshot (PNG) that shows **no** patient data. | File appears *Awaiting review*; stored size smaller than received. | |
| B8 | As a second technician, open the same ticket and *Clear* the file. | Chip becomes *Cleared*; the download opens as a file, not in the page. | |
| B9 | Attach a `.exe` renamed to `.pdf`. | Refused with the sentence "programs are not kept on tickets". | |
| B10 | Drag the Files pod above Tasks; fold Commercial basis; reload. | The layout is remembered; *Reset layout* restores it. | |
| B11 | Move the ticket to Resolved, then Closed. | State Closed; the resolve clock shows Met or Missed against its target. | |
| **C — the board** | | | |
| C1 | Tick two rows, set a status in bulk. | "Updated 2 ticket(s)"; both changed. | |
| C2 | Filter to P1 and save the view as "P1s". | A chip "P1s" above the counters; it highlights when clicked. | |
| C3 | `Ctrl`+`K`, type part of a summary. | The ticket is listed from the whole desk, with its priority. | |
| C4 | `j` `j` `x` on the board. | The second row is ticked and the bulk bar appears. | |
| C5 | Switch rows to Compact and back. | Row height changes; the choice is remembered. | |
| **D — bundling** | | | |
| D1 | Raise three tickets for the same fault; on the first, attach the other two as children. | Children · 2; each child says "Child of". | |
| D2 | Close the parent. | Both children close, each with "closed with parent" in its history. | |
| D3 | Raise two more; merge the second into the first. | The second is Closed with "Merged into"; its notes appear on the first as Internal (different requesters) or Discussion (same). | |
| **E — dispatch and the day** | | | |
| E1 | Email the helpdesk mailbox "PSA pilot test: keyboard" from a PMC address. | Within a minute a ticket appears on the unrouted queue, source Email. | |
| E2 | Route it to a board with an owner. | It leaves the queue; the owner sees it under *Mine*. | |
| E3 | Reply to the intake email keeping the `[PMC-…]` subject. | The reply lands as a note on the same ticket, "customer updated" on the board. | |
| E4 | On a ticket, schedule a visit for a colleague tomorrow 10:00–11:00. | Schedule pod shows it; Dispatch › The day (tomorrow) lists it under the colleague. | |
| E5 | Try to book the same colleague 10:30–11:30 on another ticket. | Refused: "is already booked then". | |
| **F — the portal (technician's own view)** | | | |
| F1 | Open *My requests* as the technician who raised B1. | The ticket is listed; its Discussion note shows, the Internal note does not. | |
| F2 | The closed ticket shows *How did we do?* | Five stars and a box; answering once records it and the card does not return. | |
| **G — setup and rules** | | | |
| G1 | Setup › the board › *Standard notes*: add "Received, looking now". | In the note box, picking it fills the text and sets Discussion. | |
| G2 | Setup › *Workflow rules*: a rule "P1 created → notify the Service Manager", test it, switch it on; raise a P1. | The rule fires (its *What it has done*); the notification sits in the outbox (nothing is sent while requester email and notifications are off). Switch it off afterwards. | |
| G3 | Setup › *Templates*: "New starter" with three tasks; New ticket › Use template. | The ticket opens with the three tasks. | |
| **H — reports and safety** | | | |
| H1 | Open *Reports*, last 3 months. | Counters and charts with today's tickets; the CSV downloads. | |
| H2 | As a technician who is **not** on the restricted board, search for a restricted ticket's summary. | Nothing found. As a member, it is found and an audit row says so. | |
| H3 | Type a PhilHealth-shaped number into a test note. | Saved, and flagged: a data-quality finding names the shape, never the number. | |
| H4 | Run `psaspine attachments-verify` on the server. | "OK: the store is whole". | |

**Signed off by** (technician, technician, operator) · **date** · **findings carried
to the record:** …
