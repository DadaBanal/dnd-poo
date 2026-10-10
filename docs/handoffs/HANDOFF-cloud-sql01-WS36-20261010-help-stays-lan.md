# HANDOFF — Cloud Build → SQL01, WS36, 10 Oct 2026 (decision: the requester portal stays on the LAN)

**A decision for the record, with nothing to run. It supersedes §3 of
`HANDOFF-cloud-sql01-WS36-20261009-portal-away-links.md`, which said "set `-PortalAwayUrl` once the portal is
published". The portal will not be published.**

## The decision

Dada, 10 Oct 2026: *"they should just be available on the internal lan the help."*

- `help.pmcne.ph`, the requester portal, stays **LAN-only**.
- Do **not** publish `help.pmcne.net`. PSA-Portal-Public stays stopped with auto-start off, and the tunnel keeps
  answering 404 for that name (Part 70).
- Do **not** set `-PortalAwayUrl` or `PSA_PORTAL_AWAY_URL` on PSA-Notify. Requester, status and approver emails keep
  the one LAN link, word for word as today.
- Staff are unchanged: `desk.pmcne.net` behind Access, and the *At PMC* and *Away from PMC* links in staff emails
  (applied by Dada, Part 76).

## Why (agreed with Dada before recording)

- The portal serves every ward. Through Access Free's 50 seats, that means hitting the limit or paying per seat.
- The portal signs people in with their domain password, and AD's lockout threshold is *Never* (Part 70). A
  misconfigured gate would expose every domain account to guessing.
- Ward staff raise requests from PMC PCs. The people who work away are the technicians, and they already have the desk.
- If this is ever revisited: Entra sign-in on the gate first (parked for the week of 12 Oct, Part 73), then the portal.

## State, MEASURED 10 Oct 2026 from outside PMC (Cloudflare DNS over HTTPS)

| Name | Public DNS |
|---|---|
| `help.pmcne.net` | NXDOMAIN (does not exist) |
| `help.pmcne.ph` | NXDOMAIN |
| `desk.pmcne.net` | resolves; `GET /` → 302 to `pmcne.cloudflareaccess.com` (the gate) |

The `-PortalAwayUrl` code stays in place, unused. Removing it would change the sender for no gain, and the README row
now says to leave it unset.
