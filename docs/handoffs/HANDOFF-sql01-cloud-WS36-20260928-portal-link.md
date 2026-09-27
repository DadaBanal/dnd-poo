# HANDOFF-sql01-cloud-WS36-20260928 — "My requests" from the Employee Portal, signed in by the portal

| Field | |
|---|---|
| To | Cloud (WS36) |
| From | SQL01 |
| Workstream | WS36 |
| Bucket | One desk door: an employee already signed in to the Employee Portal (`portal.pmcne.ph`) opens *My requests* on `help.pmcne.ph` without a second sign-in. The portal side is SQL01's, prepared and not yet deployed. |
| Read first | This file; the runbook handoff `HANDOFF-cloud-sql01-WS36-20260926-runbook.md` parts 10 and 11; `psaspine/web/__init__.py` (`_route`, `_do_login`, `_session_cookie_value`). |
| Do | Build the door below, with tests; say in the branch what the env names are. SQL01 sets them with `Set-PsaDeskEnv.ps1` and deploys the portal edit. |
| Do NOT decide | Which departments are open (Dada; until then the door is closed). Announcing the portal to wards (Dada; the DPO's §6.1 answer gates hospital-wide use). |
| Fence | Hostnames only; no patient identifier, credential, token value or internal address. Labels MEASURED / VERIFIED / INFERRED / NOT VERIFIED. |
| Done means | The door is in the branch with tests; the runbook gains its host steps; SQL01's Reply shows an employee reaching *My requests* from the Employee Portal with no second sign-in, and every refusal below producing its page. |
| Written | 2026-09-28, 07:05 +08:00 |

## Decided

Dada, verbatim, 27–28 Sep: *"can we have the help portal just be in the current payroll employee portal like
portal.pmcne.ph"*, *"u can just add the link to the portal.pmcne.ph when employees are already logged in and use
that link to make sure the user is authenticated"*, *"add ticketing or my requests"*, *"dont do it help as the
tickets may be for other departments"*, and on SQL01's design: *"go"*. The entry is called **My requests**.

## What the Employee Portal is (MEASURED 27 Sep, read-only, live files by name)

- IIS site `PMC Portal` reverse-proxies `/`, `/PMC_Portal.html` and `/api/portal/*` to the payroll bridge
  (`C:\PMC\payroll\bridge.js` 9.14.9, Node, `localhost:4100`). The same page is also served on `payroll.pmcne.ph`
  (`/PMC_Portal.html`, IIS static), and that site forwards `/api/*` to the same bridge.
- Employees sign in with their **Windows account** (AD-only mode: an LDAPS bind as `ADLogin@pmcne.ph`).
- The portal session is a random 48-hex token held in the bridge's memory (8 h sliding), kept by the page in
  `sessionStorage` and sent as header `x-pmc-portal-token`. No cookie.
- `GET /api/portal/me` (`bridge.js:4345`) with that header answers `employee.ADLogin` (lower-case
  sAMAccountName), `employee.FullName`, `employee.Department`, and `impersonated` (true for a PMO admin preview).
  With no or a dead token it refuses (401).
- `payroll.Employee.ADLogin` is set on 653 of 712 active employees; 283 of the 286 people who have used the portal
  carry it. It equals the desk's Windows identity (the lower-case sAMAccountName) and what `/my` matches on.
- The bridge listens on every interface on 4100 (firewall rule allows any remote address). A loopback call from
  the desk is therefore always possible; nothing here should rely on the bridge being unreachable from elsewhere.

## The door (to build)

`POST /sso/portal` — the portal page submits a form (top-level, new tab) with one field, `token`.

1. **Routed before the global Origin check**, like `/api/`, with its own: the `Origin` must be exactly one of a
   configured list of **https** origins (suggest `PSA_EMPLOYEE_PORTAL_ORIGINS`, e.g.
   `https://portal.pmcne.ph,https://payroll.pmcne.ph`). Unset list: the door answers 404 (off). An `http://`
   origin is refused (the token already travelled in the clear).
2. **Only on the portal host** (`config.is_portal_host`); elsewhere 404.
3. **Checks the token with the bridge, server to server:** `GET <PSA_EMPLOYEE_PORTAL_BRIDGE>/api/portal/me`
   (suggest default `http://127.0.0.1:4100`), header `x-pmc-portal-token: <token>`, timeout about 5 s. Accept only a
   200 JSON answer with `impersonated == false` and a non-empty `employee.ADLogin` matching
   `^[a-z0-9._-]{1,20}$` after lower-casing.
4. **Pilot gate:** `employee.Department` must be in a configured list (suggest
   `PSA_EMPLOYEE_PORTAL_DEPARTMENTS`, exact names as payroll holds them). Empty list: nobody passes. Dada names the
   departments; the DPO's §6.1 answer gates hospital-wide.
5. **Signs them in as the same person the Windows door would:** `User(id = ADLogin, name = FullName, email = the
   contact's if any, via = 'portal', roles = board_roles(ADLogin))`. A **browser-session cookie** (no `Max-Age`),
   host-only, `HttpOnly; SameSite=Lax; Secure`, so closing the browser ends it on a shared ward PC. Then
   `303` to `/my` (or to `next` when it is `/my` or below).
6. **Audit:** `PORTAL_SSO` (actor = the ADLogin, detail "employee portal") and `PORTAL_SSO_REFUSED` with the reason in
   words. **Never log, store or echo the token**; do not keep the bridge's answer beyond the request.
7. **Refusals** answer a plain page on the portal host, in the requester's layout, with the reason in words and a
   link *Sign in with your Windows account instead* → `/login?next=/my`:
   - no token, or the bridge says the portal session is not valid: "Your Employee Portal session has ended. Sign in
     there again, or sign in here with your Windows account." (401)
   - admin preview: "An admin preview cannot open My requests." (403)
   - no Windows username on the employee record: "Your employee record is not linked to a Windows account yet.
     Sign in here with your Windows account, or ask PMO to link it." (403)
   - department not open: "My requests is not open for your department yet." (403)
   - bridge unreachable or slow: "The Employee Portal could not be checked just now. Try again, or sign in here with
     your Windows account." (503)
8. **`GET /logout` on the portal host** must keep clearing the cookie (the portal's *Sign out* will load it as an
   image from `portal.pmcne.ph`, same-site, so the cookie is sent and the clear is accepted). Please also mark the
   cleared cookie `Secure` when `public_https`: today `_cleared_cookie()` (`__init__.py:321-327`) sends
   `psa_session=; Max-Age=0; Path=/` with no `Secure` (MEASURED 28 Sep on the loopback); IIS adds it for now.
9. **Tests:** Origin list (listed https passes, http refused, other refused, unset = 404); portal host only; bridge
   mocked for 200 / 401 / preview / no ADLogin / bad ADLogin shape / department closed / timeout; cookie attributes
   (no Max-Age, Secure, HttpOnly, SameSite=Lax); audit rows without the token; `/my` shows the tickets of the
   ADLogin; a Windows sign-in by the same person sees the same tickets.

## The portal side (SQL01's, prepared, NOT deployed)

A proposed `C:\PMC\payroll\web\PMC_Portal.html` (+41 / −3 lines against the live file, md5 of the live file
`0000ad12e5ebe76a2e71e841310fa00c`, 44,599 bytes, 9 Sep):
- menu item **My requests** before *Account*, and a **My requests** card at the top of *Home* (on a phone the menu
  shows 4 items and scrolls; measured with the portal's own CSS at 360 and 390 px; all 8 fit at 768 px and wider);
- *Open My requests* posts the session token to `https://help.pmcne.ph/sso/portal` in a new tab
  (`target=_blank`, `rel=noopener`); hidden in an admin preview;
- *Sign out* also loads `https://help.pmcne.ph/logout` before the page reloads.

No `bridge.js` change, so no bridge restart (which would drop the biometric ADMS listener on 8888 and every portal
session). The HTML is read from disk on every request, so the edit is live on the next page load on both
`portal.pmcne.ph` and `payroll.pmcne.ph`. It is deployed only after the door is in and passes on the host, with a
dated copy beside the live file (the folder's own convention) and Dada's sight of the preview.

## Reply

**Cloud, 2026-09-28. BUILT at the head this Reply arrives with; NOT VERIFIED against the real bridge from here.**

The door is `psaspine/web/sso.py`, routed as `POST /sso/portal` in `psaspine/web/__init__.py` before the desk's
Origin check and after the portal-host gate. Items 1 to 8 of "The door (to build)" are built as written, with these
readings where the spec left a choice:

- **Env names**, read by `Config.from_env`: `PSA_EMPLOYEE_PORTAL_ORIGINS` (comma list, https only; unset = 404),
  `PSA_EMPLOYEE_PORTAL_BRIDGE` (default `http://127.0.0.1:4100`), `PSA_EMPLOYEE_PORTAL_DEPARTMENTS` (comma list,
  exact names; unset or empty = nobody passes).
- **Origin:** exactly one of the listed https origins, compared as scheme + host with a default port dropped, so
  `https://PAYROLL.pmcne.ph:443` passes and `https://help.pmcne.ph` itself does not. On a refused origin the token
  never leaves for the bridge. An `http://` origin is audited as "origin not allowed (not https)".
- **Bridge:** `GET <bridge>/api/portal/me` with `x-pmc-portal-token`, `Accept: application/json`, 5 s. A non-200
  is "session has ended" (401); no answer, a timeout or non-JSON is "could not be checked" (503).
- **ADLogin:** lower-cased, then `^[a-z0-9._-]{1,20}$`; an empty or badly shaped one is the "not linked" page
  (403) and the audit row says which.
- **Department:** exact string match against the list; "not open for your department yet" (403), audited with the
  ADLogin as actor.
- **The person:** `User(id=ADLogin, name=FullName or the contact's display name, email=the contact's, via='portal',
  roles=board_roles(ADLogin))`; the contact is found as the Windows door finds it (`sam_account`, then `upn`).
  Audit `PORTAL_SSO`, detail "employee portal, contact <id>" or ", no contact row".
- **Cookie:** `psa_session` with no `Max-Age`; `HttpOnly; SameSite=Lax; Secure` by rule (the token only ever travels
  over https). `303` to `/my`, or to `next` when it is `/my` or below.
- **Item 8:** `/logout` now clears with `Secure` when `public_https`; the IIS `Secure` rewrite may go.
- **Refusal pages:** the requester's layout without a signed-in user, the reason in words, and
  `Sign in with your Windows account instead` → `/login?next=/my`. No cookie is set on a refusal.
- **Tests:** `tests/test_spine.py::EmployeePortalDoorTest`, six tests covering item 9 in full (origins listed /
  http / other / unset = 404 / wrong host = 404 / GET = 405; bridge 200 / 401 / preview / no ADLogin / bad shape /
  closed department / timeout; cookie attributes; audit rows without the token; `/my` shows the ADLogin's tickets and
  the Windows door sees the same; the Secure sign-out). The runbook's "Folded in from part 11" section has the host
  steps in order; the portal edit is deployed at its step 5, after the door passes on the host.

Not decided here: the departments (Dada), and announcing anything to a ward (Dada, after the DPO).

~~**WITHDRAWN** by SQL01 before any work, 2026-09-28. Dada, verbatim: *"just do a separate portal"*, then *"i mean u
need to add it to the portal.pmcne.ph dont it"*. Do **not** build `POST /sso/portal`. `help.pmcne.ph` stays the
staff portal on its own, with its own Windows sign-in. Nothing was added to the Employee Portal (MEASURED:
`C:\PMC\payroll\web\PMC_Portal.html` is unchanged, md5 `0000ad12e5ebe76a2e71e841310fa00c`, 44,599 bytes). The
proposed page lived only in SQL01's scratchpad and is not deployed. Still wanted from this file: item 8's small fix,
`Secure` on the cleared cookie when `public_https`.~~

**REINSTATED, 2026-09-28. The withdrawal above was SQL01's misreading; build the door as specified.** Dada, verbatim: *"so it should open directly without signing in as it has siged in already when they login to portal.pmcne.ph"*, and *"i have told you this"* (27 Sep: *"u can just add the link to the portal.pmcne.ph when employees are already logged in and use that link to make sure the user is authenticated"*). "A separate portal" means `help.pmcne.ph` stays its own site, opened from the Employee Portal's *My requests* link in a new tab, already signed in by the portal. Nothing in this spec changes. The Employee Portal is still unchanged until the door passes on the host.
