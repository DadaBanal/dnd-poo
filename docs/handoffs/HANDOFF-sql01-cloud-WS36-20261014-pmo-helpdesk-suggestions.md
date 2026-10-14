# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (three suggestions from the PMO Helpdesk, read from their document; two are yours)

**Dada forwarded `PMO_Helpdesk_System_Improvement_Suggestions.docx` (OneDrive, 14 Oct, 2.9 MB): six annotated
screenshots of the live desk with captions, one of them in Filipino. The captions are the whole text; the images
are the live desk at `desk.pmcne.ph` under the account "Anne". Three asks. The department one is data on the host
and is answered here; the two UI ones are yours. Nothing on the host changed for this handoff.**

## 1. A pop-up image viewer with Next / Previous, instead of a new tab (Figures 1, 3, 4) — yours

The suggestion, verbatim from the caption (Filipino): *"Sana kapag ni-click ang image sa chat, magbukas ito sa
floating pop-up viewer na may Next at Previous navigation para mas madaling makita ang ibang attached images, sa
halip na automatic na magbukas sa bagong tab."* — when an image in the chat is clicked, open it in a floating pop-up
viewer with Next and Previous so the other attached images are easy to see, instead of opening a new browser tab.

Figure 4 shows today's behaviour: the image opens in a new tab. Figure 1 is their mock-up of the Next/Previous
buttons on a ticket's attached images. **Scope as they drew it:** the chat's image attachments and a ticket's
attached images, one viewer, keyboard arrows as well as buttons, Escape to close, and the filename and size the
Files card already shows. The Vitals rules apply — 16px glyphs, no blur behind the pop-up (a flat `chrome.deep`
scrim is fine), one shadow.

## 2. Attach File on the New Ticket page, before the ticket exists (Figures 5, 6) — yours

Figure 5 is `/ticket/new` as it is: Board, Source, Company, Department, Contact, Summary, type tree, the two
priority questions, Description, Owner — **no attachment field**. Figure 6 is the PMC Requests page, which has a
*Reference attachment* field, as their example of what they want. The ask: let a file be attached while raising a
ticket, not only after it exists.

One thing to carry across from how the desk already treats files: attachments on a ticket go through the Files
card's *Awaiting review / Clear / Withhold* path (Figure 2 shows "FILES · 2 · 2 TO REVIEW", a PFT scan held for
patient-information review). A file attached at creation must land in the same review state as one attached later,
never bypass it.

## 3. TB-DOTS is not in the Department list (Figure 2) — measured on the host, and it is one click

MEASURED: `psa.department` holds **52 departments, every one of them `source = 'PAYROLL'`**, loaded 28 Sep 2026 from
the payroll department list; none retired; **no row matching `%TB%` or `%DOTS%`** (control clean). `Pulmonary`
exists, which is where TB-DOTS usually sits organisationally — the PMO ticket in Figure 2 is a Pulmonary one.

So the list is payroll's, and TB-DOTS is not a payroll department. The desk already has the path for exactly this:
**Setup › Departments › add** (`departments_add`, `source = 'MANUAL'`), which writes the row and ticks it onto a
board. **Whether TB-DOTS is its own department or a service under Pulmonary is a naming decision, Dada's, so I have
not added it** — it is one click in Setup once he says, or I write the row with the same audit the screen writes.
Nothing for you to build unless he wants TB-DOTS to arrive from payroll, in which case it is a payroll-side row and
the sync brings it.

## 4. Not in the document, but the screenshots show it

Figure 2's ticket shows **"Breached by 28h"** on a P4 request with the respond target at 16h, and the resolve clock
*Paused at 3d left* while it awaits approval. Not a suggestion from them; noted because it is the first live SLA
breach I have seen on a screenshot and the respond clock is not paused by *Awaiting approval* where the resolve
clock is. Whether that is right is a rule question for Dada, not a defect report.

The document's images and extracted text are in the session record; the screenshots carry a requester's email
address and a patient-related filename, so they are **not committed**.
