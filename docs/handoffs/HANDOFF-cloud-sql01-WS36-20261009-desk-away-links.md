# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (a member's email links the desk at PMC and away)

**No schema step and no PSA-Desk restart. One pull, then two arguments added to PSA-Notify (and to the Teams sender,
if one is registered).**

This answers the *For WS36* item in runbook Parts 69, 70 and 72: email links that work from outside. It supersedes
nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada chose

Asked before building, 9 Oct 2026:

- **Staff emails get both links** (Recommended): *At PMC* and *Away from PMC*. An email cannot know where it will be
  opened, so the desk does not try to choose a host per reader.
- **Portal links: not now.** Requester, status and approver emails stay on `help.pmcne.ph`. The public portal is not
  published (Part 70, *"desk only for now"*). Publishing it is a separate decision. The portal serves the whole
  hospital, so the Zero Trust Free 50-seat limit needs weighing first.

## 2. What changes

MEASURED from the code before the change: owner, resource, booked-visit and on-call-page emails carried **no link**,
only *"Open the ticket on the desk: PMC-…"*. Now they end with:

```
Open the ticket on the desk: PMC-001460
At PMC: https://desk.pmcne.ph/ticket/PMC-001460
Away from PMC: https://desk.pmcne.net/ticket/PMC-001460 (asks for the PMC sign-in code, once a day)
```

- **Where the addresses come from.** `Send-PmcNotifications.ps1 -DeskUrl` and `-DeskAwayUrl` (new), else
  `PSA_PUBLIC_URL` and `PSA_DESK_AWAY_URL`.
- **Leaving one out** leaves that line out. With neither set, every email is word for word what it is today.
- **Teams cards** (`Send-PsaTeamsNotifications.ps1 -DeskAwayUrl`, new) get *Open away from PMC* beside *Open on the
  desk*.
- **Nothing else moves.** The requester, status and approver emails are unchanged, as are the desk's accepted origins
  and LAN sign-in. The away address is only ever written into a link: the desk never reads it, so Part 69's warning
  about the origin check does not apply.
- **A deep link still lands on the ticket.** Not signed in, `/ticket/PMC-…` gets the sign-in page with the path as
  `next`, so after sign-in it opens that ticket (MEASURED from the code). INFERRED: Access returns to the same path
  after the PIN, which is its documented behaviour; the walk-through in §4 proves it.
- **Stupid-proofing.** An address given on the command line that is not `https://` is refused before anything is sent.
  One inherited from the environment that is not is quietly left out, so a stray setting can never stop the email. It
  is quiet on purpose: the senders read stderr into the JSON they parse (`2>&1`, part 28), so a warning line would
  fail every pass.

## 3. The step

1. Pull. No restart: the senders run the code fresh on each pass.
2. **Preview first**, as the desk account from `platform/psa-spine`, with your usual PSA-Notify arguments plus the two
   new ones and **without `-Apply`**:
   `… Send-PmcNotifications.ps1 <the task's arguments> -DeskUrl https://desk.pmcne.ph -DeskAwayUrl https://desk.pmcne.net`
   It sends nothing and should end as a normal pass does.
   - Confirm `https://desk.pmcne.ph` is the LAN address staff type (INFERRED from the README's example). If the LAN
     desk is reached differently, use that, https only.
3. Add the same two arguments to the PSA-Notify scheduled task's action. Change nothing else on the line.
4. If a Teams sender task exists, add `-DeskAwayUrl https://desk.pmcne.net` to it (it already takes `-DeskUrl`). If
   none is registered, skip this.

**To undo:** take the two arguments back off the task. The emails go back to exactly what they were.

## 4. What to look for

- PSA-Notify's next passes: result 0, and the same *N due: N sent, 0 failed* shape.
- **One real walk-through, by Dada or a technician:**
  1. Assign a test ticket to yourself, so an owner email is sent.
  2. In the email, the two lines are there.
  3. *At PMC* opens the ticket on the LAN.
  4. *Away from PMC*, on a phone off the PMC Wi-Fi, asks for the Access PIN, then the desk's sign-in, then opens **that
     ticket**.
  - Report which step stops, if any. Do not paste the email.
- The requester's own emails for that ticket show no desk link.

## 5. Evidence

| | |
|---|---|
| Unit suite | `StaffDeskLinksTest` (5): a member's email carries both lines and the requester's, status and approver's carry neither; with nothing set it is as before; one setting gives one line; a given non-https address is refused, and an inherited one is left out with nothing on stderr while all seven emails still go; a Teams card gets the second button only when set; both sender scripts pass `--desk-away-url` and refuse non-https. Full suite: see the commit message. |
| Scripts | Both senders parse under PowerShell 7.4 (0 errors); plain ASCII. |
| CI | See the commit that follows this one. |
| Not run here | The senders against Graph and Teams, and the walk-through through Access. |
