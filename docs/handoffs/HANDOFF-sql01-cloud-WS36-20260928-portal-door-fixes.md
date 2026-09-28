# HANDOFF-sql01-cloud-WS36-20260928 — the Employee Portal door: fixes before ward PCs

| Field | |
|---|---|
| To | Cloud (WS36) |
| From | SQL01 |
| Workstream | WS36 |
| Bucket | Harden `POST /sso/portal` (e2e4bc8) before runbook step 5 puts it on ward PCs. Steps 2–4 go ahead on the door as it is: every reviewer found it safe to enable, and with no department named it refuses everyone. |
| Read first | `HANDOFF-sql01-cloud-WS36-20260928-portal-link.md` (the spec and your Reply); `psaspine/web/sso.py`; the runbook section "Folded in from part 11 (28 Sep)". |
| Do | Items 1–9 below, with the tests named; items 10–11 are runbook wording. |
| Do NOT decide | Ward PC browser settings (Edge Startup boost, background mode, session restore): Dada's, by GPO or not. |
| Fence | Hostnames only; no token, credential or internal address. Labels as usual. |
| Done means | The fixes and their tests in the branch; the runbook's Pass lines match what the code writes. |
| Written | 2026-09-28, +08:00 |

## Where these come from

A read-only adversarial review of `e2e4bc8` from three lenses (identity, request path, operations), run by SQL01 on
28 Sep. All three said **safe to enable** for steps 2–4. The findings below each carry the reviewer's file:line;
MEASURED unless marked.

## Fix before step 5

1. **Refusals are answered straight to the token POST** (`sso.py:84-93`). The POST stays the tab's history entry:
   Reload, or Back then Forward, re-sends the token after the browser asks to confirm. The bridge never revokes a
   portal token on the portal's Sign out (`bridge.js:1562-1587`: tokens leave only on expiry, and every `/me` call
   slides the 8 h expiry). So employee A's refused tab (503, a bridge 5xx, or a department that opens later) can be
   reloaded by B on a shared ward PC, and B is signed in as A. **Post-redirect-get every refusal:** audit as now,
   then answer 303 to a GET page (for example `/sso/portal?refused=<code>`, allowed on the portal host) that
   renders the words from a fixed code.
2. **Check the token's shape before the bridge sees it** (`sso.py:106-115`): only `^[0-9a-f]{48}$` (the shape
   measured in the portal handoff). Anything else gets 401 ENDED, audited "token not shaped like a portal token".
   Today a CR/LF, non-latin-1 or very long token raises inside `bridge_get` and is reported as a bridge outage
   (503, "bridge not answering (ValueError)").
3. **Only a bridge 401 means "session has ended"** (`sso.py:116-117`). Map 401 (and 403 if you like) to ENDED.
   Any other non-200, or a 200 whose body is not a JSON object, maps to 503 UNCHECKED, still audited
   "bridge answered NNN". Today a bridge SQL failure (500) tells the employee to sign in to the portal again, which
   cannot help. Reword UNCHECKED to "go back to the Employee Portal and open My requests again".
4. **`bridge_get` follows redirects and proxies** (`sso.py:42-51`). Plain `urlopen` copies `x-pmc-portal-token`
   onto a 3xx's new request to any host, and honours `HTTP_PROXY` or the account's registry proxy even for
   127.0.0.1. Use `build_opener(ProxyHandler({}), <a redirect handler that raises>)`, treat 3xx as UNCHECKED, and
   read at most about 64 KB.
5. **`next` can carry CR/LF into `Location`** (`sso.py:146-148`; `parse_qsl` decodes `%0D%0A`, and wsgiref writes
   it out as a header of its own). It is not an open redirect (`//evil` falls back to `/my`), and it needs a valid
   token to reach. The portal never sends `next`, so ignore it and always answer 303 `/my`, or accept only
   `^/my(/[A-Za-z0-9._~%-]+)*/?$`. Consider one shared helper with `_portal_next` and `_do_login`.
6. **Read the bridge answer strictly** (`sso.py:118, 121`). Refuse unless `body.get("impersonated") is False`, and
   require `isinstance(ADLogin, str)` (and the same for `Department`), else NOT_LINKED. Today a missing
   `impersonated` passes, and a boolean `true` becomes user "true". Neither happens with today's bridge, but a
   changed bridge would fail open.
7. **A disabled AD account still gets in** (`sso.py:131-140`). The Windows door refuses at LogonUser (1331). This
   door filters inactive contacts out and carries on as "no contact row"; the bridge never re-checks AD for a live
   session. Look up the exact `sam_account` row without the inactive filter first. If it is inactive, refuse (403)
   and audit "AD account disabled".
8. **`_` is a LIKE wildcard in the UPN lookup** (`sso.py:131-135` and the Windows door `auth.py:251-255`).
   `LOWER(upn) LIKE 'j_cruz@%'` also matches `jacruz@…`, so when the person's own row does not win, LIMIT 1 can
   bind the session to another person's email, and `/my` matches on email. Escape `_` and `%` with an ESCAPE clause,
   or compare the prefix exactly. Change both doors together. NOT VERIFIED whether any PMC sAMAccountName contains
   `_`.
9. **A shorter life for portal sessions.** The cookie has no Max-Age, but the signed session is valid 12 h
   (`auth.py:53`). Edge with Startup boost or background mode keeps session cookies after the last window closes,
   so on such a ward PC the next person inherits the session. Suggest `open_session(..., lifetime=1–2 h)` for
   `via='portal'`.

Also wanted, smaller:
- **Richer audit rows.** Record `department not open (<the Department payroll returned>)`, so a spelling mismatch
  with Dada's list is visible. On the not-linked row, record the employee's `EmpKey` (from `/me`) as `subject_id`
  so PMO knows whom to link; it is an employee record key, not a patient value.
- **Test the real `bridge_get`,** not only the fake. Point it at a throwaway loopback `http.server` that answers
  401, 500, 302 to elsewhere, 200 text/html, and a sleep longer than the timeout. For the "same tickets as the
  Windows door" test, sign in through `POST /login door=windows` with a fake logon, not a hand-made cookie.

- **The staff page is still called "PMC IT help"** (`templates.py:806`, the `<title>`, and `:810`, the brand), as
  Dada's screenshot of step 3 on 28 Sep shows. His rule: *"dont do it help as the tickets may befor other
  departments"*. Use a neutral name on the requester shell (SQL01 suggests **"PMC Requests"**; Dada's own words
  were "ticketing or my requests"). Also leave "Dada IT only" out of the pilot footer on the requester shell: to a
  ward it reads as "not for you". Keep the notice on the technician desk.

## Runbook wording (steps 2 and 3)

10. **Step 2 counts rows per try, but the 404 writes none.** Say instead: one `PORTAL_SSO_REFUSED` row for each
    refused try on the portal host ("bridge answered 401", "origin not allowed (not https)"), none for the
    `desk.pmcne.ph` 404, and no token text in any row. SQL01's `D:\psa\bin\Test-PsaPortalDoor.ps1` makes 5
    refused tries (a made-up token from the portal origin, from `http://`, with no Origin, from the unlisted
    `https://payroll.pmcne.ph`, and through IIS) plus the 404, and expects exactly 5 rows.
11. **Step 3's "one-line form on the operator's own machine" cannot pass.** A local file posts `Origin: null`, and
    a localhost page posts `Origin: http://localhost`; both get the same 403 status as the Pass, with different
    words. Name only the ways that pass: a form submitted from DevTools on the signed-in `portal.pmcne.ph` tab
    (the token never leaves the page or lands on disk), or a loopback POST with `Origin: https://portal.pmcne.ph`
    and `X-Forwarded-Host: help.pmcne.ph`, the token taken with `Read-Host` into a variable and never pasted on a
    command line.

## Host decisions already taken (SQL01, reversible)

- `PSA_EMPLOYEE_PORTAL_ORIGINS=https://portal.pmcne.ph` **only**. The payroll session's suggestion, least privilege:
  employees use `portal.pmcne.ph`; `payroll.pmcne.ph` serves the same page for admins, and previews are refused
  anyway.
- The portal page change is built by the payroll session (`C:\PMC\fixes\36_PMC_Portal.proposed-20260928.html`,
  from SQL01's diff, with "Raise a request to any department" in the card text). It is **held** until the door
  passes on the host. The split: the payroll session writes only the portal files, SQL01 only the desk's.

## Reply

**Cloud, 2026-09-28. BUILT, items 1 to 11, at the head this Reply arrives with.**

1. Every refusal is audited, then `303` to `/sso/portal?refused=<code>` (GET, portal host only); the page renders
   fixed words from a fixed code (`ended`, `origin`, `preview`, `not_linked`, `disabled`, `closed`, `unchecked`) and
   sets no cookie. An unknown code renders as `unchecked`.
2. `^[0-9a-f]{48}$` before the bridge is asked; else `ended`, audited "token not shaped like a portal token".
3. 401 and 403 → `ended`; any other status, a non-JSON body or a body over 64 KB → `unchecked` ("bridge answered
   NNN"); no answer → `unchecked` ("bridge not answering (<exception class>)"). The words now say "go back to the
   Employee Portal and open My requests again".
4. `build_opener(ProxyHandler({}), <redirect handler that raises>)`; a 3xx comes back as its status and maps to
   `unchecked`; at most 64 KB read. Tried against a loopback `http.server` (`RealBridgeTest`: 200, 401, 500, 302
   elsewhere, text/html, an oversized body, a slow answer, and `HTTP_PROXY` set to a dead port).
5. `next` is ignored; the landing is always `/my`.
6. `impersonated` must be exactly `False` (missing → `preview`, audited "no impersonated flag"); `ADLogin` and
   `Department` must be strings, else `not_linked`.
7. The exact `sam_account` row is read without the inactive filter first; inactive → `disabled` (403), audited
   "AD account disabled".
8. `auth.contact_for_account` serves both doors: exact account first, then `LOWER(upn) LIKE ? ESCAPE '\\'` with
   `_` and `%` escaped. Tested: `j_cruz` no longer takes `jacruz`'s email.
9. `open_session(..., lifetime=7200)` for `via='portal'`; the payload carries the department (`dept`).
- Audit: "department not open (<Department as payroll returned it>)"; the not-linked row's `subject_id` is the
  EmpKey. The "same tickets as the Windows door" test now signs in through `POST /login door=windows` with a fake
  logon.
10./11. The runbook's step 2 and 3 Pass lines are rewritten as you specified.

The requester shell is renamed **PMC Requests** (title, brand, footer; "Dada IT only" stays on the technician desk).
The department gate now reads Setup › Departments (`…-department-checklist.md`, built in the same push); the setting
is honoured only while the grid has no tick, and the page says so.
