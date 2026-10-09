# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (requester and approver emails: the portal at PMC and away)

**No schema step and no restart. Nothing to do now: the new setting waits until the portal is published off the LAN,
which is Dada's decision (§3).**

This follows `…-20261009-desk-away-links.md` and adds to it; it supersedes nothing. Pull the head that carries this
file. That pull carries both changes, and the desk-links handoff's §3 still applies as written.

---

## 1. What Dada asked

After the desk links, 9 Oct 2026: *"requester and approver email links to the portal non public - do this as well"*.

## 2. What changes

- **Requester and status emails.** Under `See it here: https://help.pmcne.ph/my/PMC-…?k=…` they gain
  `Away from PMC: <portal away address>/my/PMC-…?k=…`. The HTML layout gets a plainer *Away from PMC* button beside
  *See your request*.
- **Approver emails.** Under `Decide it here: …/my/approvals` they gain `Away from PMC: <portal away address>/my/approvals`.
- **Where the address comes from:** `Send-PmcNotifications.ps1 -PortalAwayUrl` (new), else `PSA_PORTAL_AWAY_URL`.
  - It is used **only beside `-PortalUrl`**, never alone.
  - A given non-https address is refused at the start. An inherited one is quietly left out, as with the desk
    addresses, because stderr is parsed with the JSON.
- **Not set, nothing changes.** Every email is word for word as before (pinned by a test that compares the two).
- **The link the desk records** on each email (076, *which link was this person sent*) stays the one at PMC.
- **Staff emails are untouched** by this setting.

## 3. Why there is nothing to run yet

MEASURED in Part 70: `help.pmcne.net` is not published. PSA-Portal-Public is stopped, and the tunnel answers 404 for
it. A link to it today would fail. **Do not set `-PortalAwayUrl` until the portal is published.**

What publishing it needs is Dada's call, and two facts from the runbook bear on it:

- **The portal's sign-in is the AD password form**, and AD's lockout threshold is *Never* (Part 70). Published
  without a gate in front, it would take unlimited password guesses against every domain account. So it needs Access
  (or another gate) in front, as the desk has.
- **Access Free is 50 seats** (Part 70). The desk's policy is 14 people. The portal serves every ward, so INFERRED:
  far more than 50 people would sign in through it. Either the plan changes (Standard, $7 per seat per month, read by
  SQL01 on 9 Oct), or the away door is limited to a named group.

Once Dada has decided and the portal is published:

1. Add `-PortalAwayUrl https://help.pmcne.net` to the PSA-Notify task.
2. Preview the pass first, without `-Apply`.
3. One walk-through: a requester off the PMC network opens *Away from PMC* from a real update email, passes the gate,
   signs in, and lands on **that request**. Report the step that stops, if any; do not paste the email.

## 4. Evidence

| | |
|---|---|
| Unit suite | `StaffDeskLinksTest.test_the_requesters_and_approvers_emails_link_the_portal_at_pmc_and_away` checks: the requester, status and approver lines; the email minus that one line equals the email before; the HTML second button; staff emails untouched; not used without a portal address; a given http:// refused; an inherited bad one leaves every email as before; the recorded link is still the one at PMC. Full suite: see the commit message. |
| Script | `Send-PmcNotifications.ps1` parses under PowerShell 7.4 (0 errors); plain ASCII. |
| Not run here | Anything against Graph or a published portal. |
