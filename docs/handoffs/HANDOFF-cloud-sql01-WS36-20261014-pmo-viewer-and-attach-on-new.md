# HANDOFF — Cloud Build → SQL01, WS36, 14 Oct 2026 (the PMO Helpdesk's two UI asks, built)

**Answers `HANDOFF-sql01-cloud-WS36-20261014-pmo-helpdesk-suggestions.md` §1 and §2. No schema step, nothing on the
host changes beyond the code; a restart picks it up. `PSA_BIZBOX_WRITE_ODBC` stays unset. Suite: `851 tests, OK (skipped=2), 474 s, on this exact tree`.**

## 1. The pop-up viewer, with Previous and Next (Figures 1, 3, 4)

- **One viewer for a ticket's files and the chat's pictures.** A chat picture no longer opens a new tab: it opens in
  the page's viewer, as a ticket's files already did. Without script the link still opens the file.
- **Previous and Next**, and the left and right arrow keys, step through every viewable file on the page in page
  order, wrapping at the ends; a single file shows no arrows. **Escape** closes, as does a click outside.
- The bar shows the **name, the size and the place in the list** ("· 12 KB · 1 of 2"), with Download and Open in a
  tab kept.
- Design rules: 16px glyphs (the desk's own left and right arrows), a flat `chrome.deep` scrim with no blur and no
  see-through, one shadow (`shadow-card`).
- MEASURED in a browser on a ticket with two pictures: opens on the first ("1 of 2"), Next shows the second, the
  right arrow wraps to the first, the left arrow back to the second, Escape closes, no new tab opened.

## 2. Attach File on New Ticket (Figures 5, 6)

- `/ticket/new` has an **Attach files** field (several at once). The files go through the **same call as the Files
  card's Attach** (`attachments.add`, source `DESK`), so they land **PENDING**, "Awaiting review", exactly as a file
  attached later; nothing bypasses the review.
- The ticket and its files are written in **one transaction**. A file the desk refuses (a program, a zip, a script,
  over 10 MB) is named in the message and the ticket stands, as on the PMC Requests portal; the person attaches it
  again from the Files card if they want it.
- If the form comes back with an error, it says the files must be chosen again (a browser does not keep them).

## 3. Not built, as you said

- **TB-DOTS:** a Setup › Departments click, Dada's naming decision.
- **The respond clock and Awaiting approval (§4):** a rule question for Dada; nothing changed.
- **`sp_apply_change` STOCK_REQ on Training:** noted — `PK_TRXNO` from `mscSeriesNo` TRK, `FK_ASUPost` 0, refusing on
  `FK_ASUReg` until Dada names the BizBox user. Nothing on the desk depends on either until the write is switched on.

## 4. Evidence

- MEASURED: `test_new_ticket_takes_files_into_the_same_review_and_the_viewer_steps_through_them`, and the browser
  run above. The suite, `851 tests, OK (skipped=2), 474 s, on this exact tree`.
