# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (a question: the PMC systems on the portal)

**Read-only. Nothing is written, applied or restarted. Answers only, before anything is built.**

This follows Part 60 (the portal tiles are live). It supersedes nothing.

## Why

Thobie Dela Cruz, 9 Oct, on the portal's *Can't log in, or a password* tile (screenshot via Dada): *"I cannot log in
to PMC Portal or PMC Payroll"*. Dada: *"also include the other pmc one things"*, and then *"please ask sql01 … so u
can have a proper decision"*.

The live catalogue has the in-house suite as one Type, **Premiere One**: Queue, Payroll, Analytics, Imaging, HomeBase
and PSA Desk (runbook Part 32, from `PMC_PremiereOne_Systems_20260930.html`). None of the nine tiles names it. Its
Payroll is reached only as a smaller tile under *BizBox or a hospital system* (Part 59).

Before I build anything, I need four facts from the host and the record.

## The questions

Run these as `psa_desk`, as for `ticket-topics`. They are SELECTs only.

**Q1. The Premiere One tree as it stands.** Paste the rows. They hold catalogue names only.

```sql
SELECT f.display_name AS type, c.display_name AS subtype, a.display_name AS item,
       i.default_board_id, i.is_draft, c.is_draft AS subtype_retired
  FROM psa.catalogue_item i
  JOIN psa.service_component c ON c.component_id = i.component_id
  JOIN psa.service_family f ON f.family_id = c.family_id
  JOIN psa.service_action a ON a.action_id = i.action_id
 WHERE f.display_name LIKE N'%Premiere%'
 ORDER BY c.display_name, a.display_name;
```

**Q2. Which system is which.** From the record (`PMC_PremiereOne_Systems_20260930.html`, or wherever it says), give
one line per Premiere One system: its name, what staff use it for, and its hostname. Hostnames only, never an
address.

- Specifically: which one is **PMC Portal**, the `portal.pmcne.ph` staff sign in to, where *My requests* is linked
  (Part 14)?
- Which one is **PMC Payroll**?
- Are those two the same system, or two systems?

**Q3. How much each gets ticketed.** Counts only.

```sql
SELECT c.display_name AS subtype, a.display_name AS item, COUNT(*) AS n
  FROM psa.ticket t
  JOIN psa.catalogue_item i ON i.catalogue_item_id = t.catalogue_item_id
  JOIN psa.service_component c ON c.component_id = i.component_id
  JOIN psa.service_family f ON f.family_id = c.family_id
  JOIN psa.service_action a ON a.action_id = i.action_id
 WHERE f.display_name LIKE N'%Premiere%' AND t.opened_at >= DATEADD(day, -180, SYSDATETIME())
 GROUP BY c.display_name, a.display_name
 ORDER BY COUNT(*) DESC;
```

**Q4. The two tiles as they stand.** These are the tile labels and the pair each one lands on.

```sql
SELECT p.label AS tile, t.label AS smaller_tile, t.board_id, t.catalogue_item_id, t.inactive
  FROM psa.portal_tile t JOIN psa.portal_tile p ON p.tile_id = t.parent_id
 WHERE p.label IN (N'Can''t log in, or a password', N'BizBox or a hospital system')
 ORDER BY p.label, t.sort_order;
```

If Part A of `…-20261009-procurement-email-topics.md` has run by then, its new last section names how the desk
classified the 104 untiled tickets. Any Premiere One line in it belongs with Q3.

## What happens next

When the answers are back, I put the options to Dada with the numbers. The likely options are:

- a smaller tile *"I cannot log in to PMC Portal or PMC Payroll"* (plus the other PMC systems) under *Can't log in*;
- a top tile *PMC systems (Premiere One)*;
- or both.

Whatever Dada picks is added the same way the starter set was: `portal-tiles` previews, adds only what is missing,
and never changes a tile that is there.
