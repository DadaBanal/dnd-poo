# WS36 — Pilot test script — 27 September 2026

**Supersedes `docs/WS36-pilot-test-script-20260925.md`** (SQL01 sitting 2, part 9,
checked it against the code and found three steps that could not pass as written:
B3 booked a quarter hour the bands do not hold, H3 expected a scan the desk did not
run on a technician's note, and E1 needs the mail task that waits on the Graph
registration). This copy fixes those, names the two addresses the desk now has,
and adds the portal's own steps. The 25 September file is kept as written.

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
| A1 | Open `https://desk.pmcne.ph` (no port) in a browser on a technician's PC. | The sign-in page, no certificate warning, "your Windows account" first. `/` without signing in shows it with a 401; `http://` redirects to `https://`. | |
| A2 | Sign in with the technician's account. | The Service Board, with the technician's name top right. | |
| A3 | Press `?`. | The keyboard sheet appears; `Esc` closes it. | |
| A4 | Press `t` twice. | Dark, then light again; reload keeps the choice. | |
| **B — a ticket's life** | | | |
| B1 | `n`, then raise a ticket: summary "Pilot test: printer in the test room", source Phone, who is affected "just me", patient waiting "no". | Ticket `PMC-0000nn` opens on its board, status New, a priority the matrix computed (not typed), three SLA boxes. | |
| B2 | On the board, the new row shows a Respond chip counting down. | Green chip, e.g. `R 55m`. | |
| B3 | Add a Discussion note "Looked at it, needs toner." with **0.5 h** (the smallest band; effort is banded 0.5 / 2 / 4 / 8 / 20), charged as the agreement says. | Note appears flagged Discussion; Time pod shows 0.5 h; Respond chip turns ✓ once the status moves to In Progress. | |
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
| E1 | **Only once `PSA-MailPickup` is running** (it waits on the mail handoff's Graph registration; until then write "not yet" here and skip E3). Email the helpdesk mailbox "PSA pilot test: keyboard" from a PMC address. | Within a minute a ticket appears on the unrouted queue, source Email. | |
| E2 | Route it to a board with an owner. | It leaves the queue; the owner sees it under *Mine*. | |
| E3 | Reply to the intake email keeping the `[PMC-…]` subject. | The reply lands as a note on the same ticket, "customer updated" on the board. | |
| E4 | On a ticket, schedule a visit for a colleague tomorrow 10:00–11:00. | Schedule pod shows it; Dispatch › The day (tomorrow) lists it under the colleague. | |
| E5 | Try to book the same colleague 10:30–11:30 on another ticket. | Refused: "is already booked then". | |
| **F — the portal (technician's own view)** | | | |
| F1 | Open *My requests* as the technician who raised B1. | The ticket is listed; its Discussion note shows, the Internal note does not. | |
| F2 | The closed ticket shows *How did we do?* | Five stars and a box; answering once records it and the card does not return. | |
| F3 | On a ward PC, as a staff member who is on **no** board, open `https://help.pmcne.ph`. | Straight to the sign-in page, then to *Your requests* with only that entry in the menu: no Service Board, no Dispatch, no ⌘K, no New ticket button. | |
| F4 | Same person, type `https://help.pmcne.ph/dispatch` and `https://help.pmcne.ph/admin`. | 404, not a sign-in page and not a board. | |
| F5 | Same person, raise a request from the portal's form with a screenshot. | It appears on the unrouted queue on the desk, source Portal; the person sees it under *Your requests*. | |
| F6 | A technician opens `https://help.pmcne.ph/my`. | The requester's layout, even for them; the desk's own address still shows the whole desk. | |
| **G — setup and rules** | | | |
| G1 | Setup › the board › *Standard notes*: add "Received, looking now". | In the note box, picking it fills the text and sets Discussion. | |
| G2 | Setup › *Workflow rules*: a rule "P1 created → notify the Service Manager", test it, switch it on; raise a P1. | The rule fires (its *What it has done*); the notification sits in the outbox (nothing is sent while requester email and notifications are off). Switch it off afterwards. | |
| G3 | Setup › *Templates*: "New starter" with three tasks; New ticket › Use template. | The ticket opens with the three tasks. | |
| **H — reports and safety** | | | |
| H1 | Open *Reports*, last 3 months. | Counters and charts with today's tickets; the CSV downloads. | |
| H2 | As a technician who is **not** on the restricted board, search for a restricted ticket's summary. | Nothing found. As a member, it is found and an audit row says so. | |
| H3 | Type a PhilHealth-shaped number into a test note on the desk. | Saved, and flagged: a data-quality finding names the shape, never the number (the desk scans a technician's note the same way it scans a requester's words). | |
| H4 | Run `psaspine attachments-verify` on the server. | "OK: the store is whole". | |

**Signed off by** (technician, technician, operator) · **date** · **findings carried
to the record:** …
