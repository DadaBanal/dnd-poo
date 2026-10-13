# HANDOFF — Cloud Build → SQL01, WS36, 13 Oct 2026 (MMS reports on the desk, rendered by the report server, 082)

**One small schema step (082: two tables), the usual PSA-Desk restart, then three things on the host that are
yours: the Browser role for the desk's account on the reports folder, two environment values for PSA-Desk, and one
scheduled read of the folder. No report is written; the desk shows the 164 that exist.**

This answers your `HANDOFF-sql01-cloud-WS36-20261013-mms-full-drugs-reports.md` (e11d014), §6, and the message
that followed it: *"MMS reports: show them on the desk, rendered from SSRS. Don't write new reports."* It follows
`…-20261013-procurement-rights-lookups-081.md` and supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file, **once CI is green on it**.

---

## 1. What Dada chose, 13 Oct 2026

Four choices put to him, three taken as recommended:

- **Where:** a *Reports* tab inside Procurement, sixth beside Purchase orders, Receiving, Products, Vendors,
  Changes. Reports are grouped by the same three areas, so a role's *See* on an area is what shows its reports.
- **How the desk signs in to the report server:** as its own service account. No password anywhere.
- **Which reports:** **all 164, on from day one**, grouped by area with a search box. (Not the curated list.) Setup ›
  MMS reports can still retitle, move or hide one.
- **Output:** the PDF on the desk page, Excel as a download; every run logged.

Your two negative findings shaped it: nothing here needs a requisition table, and nothing here mirrors stock or
prices. Stock on hand, movements and valuations come out of the reports that already compute them.

## 2. What this head does

- **Procurement › Reports** lists the catalogue by area, with a search; each report's title is in words (the server's
  name is kept underneath on Setup, never shown to staff), its description from the server, and what it asks for.
- **A report's page** asks the server for the report's own parameters (`GetItemParameters`, for rendering, with the
  values chosen so far) and draws them: the server's lists as dropdowns, several at once where the report takes
  several, a date box, a number, yes/no, text; a box to leave a nullable one empty. A cascading dropdown refreshes
  from the server when its parent changes. The form opens on what that person ran last time, else the server's
  defaults.
- **Run and show the PDF** renders through URL access (`rs:Command=Render`, `rs:Format=PDF`) and embeds it on the
  page, with *Open in a new tab* and *Download Excel* (`EXCELOPENXML`) beside it. The bytes pass through the desk;
  the browser never talks to the report server.
- **Every run is logged** in `psa.mms_report_run`: who, which report, which values, which format, OK or the
  server's sentence, size and time. A refused sign-in or a server error is a sentence on the page, never a stack.
- **Setup › MMS reports** (a system administrator): title, area, shown, order per report; *Read the server's list
  now*. **`psaspine sync-mms-reports`** does the same read from the command line, preview unless `--apply`.
- **Nothing is written to the report server, to BizBox, or to the mirror.** MEASURED from the code: `ssrs.py` sends
  `ListChildren`, `GetItemParameters` and a render `GET`; nothing else.

## 3. The step: 082, then restart

1. Pull (once CI is green on the head).
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`. Everything else stays as it is.
4. In one transaction, as sysadmin via pyodbc as for 066 to 081, run the two `CREATE TABLE` blocks under
   `-- mms_report (from schema/082_mms_reports.sql)` and `-- mms_report_run …` from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql`, with their indexes `ux_mms_report_path`, `ix_mms_report_area`,
   `ix_mms_report_run_member`. All guarded.
5. Verify, inside the transaction: `OBJECT_ID(N'psa.mms_report')` and `OBJECT_ID(N'psa.mms_report_run')` non-NULL;
   `COLUMNPROPERTY(OBJECT_ID(N'psa.mms_report'), N'report_id', 'IsIdentity')` is **1**;
   `COL_LENGTH(N'psa.mms_report', N'path')` is **800**; both counts **0**. Control first, as in Part 77.
6. Start `PSA-Desk`: 401, down, 401. (Steps 7 to 9 below can come after; the tab says in words that the list has not
   been read yet.)

## 4. On the host: what is yours

7. **The account PSA-Desk runs under** (you know which; the desk does not): on the report server, give it the
   **Browser** role on `/BizBox MMS Reports` (Report Manager › the folder › Security, or `rs.exe`). Browser is enough:
   list, read parameters, render. Not Content Manager. **Pass:** as that account,
   `http://dnd-sql01/ReportServer?/BizBox MMS Reports` lists the folder and one report renders to PDF in the browser.
8. **Two values in PSA-Desk's environment** (the service's, as `PSA_BIZBOX_ODBC` is for the hourly read):
   - `PSA_SSRS_URL=http://dnd-sql01/ReportServer`
   - `PSA_SSRS_FOLDER=/BizBox MMS Reports` (this is the default, so it may be left out)
   Restart PSA-Desk after setting them.
9. **How the desk signs in.** On Windows the desk uses the system's own HTTP stack (`WinHttpRequest` through
   `pywin32`) with the process identity, so the service account's Windows sign-in reaches the report server with no
   password anywhere. **Check `C:\PMC\Python312\python.exe -c "import win32com.client"` succeeds as the desk
   account.** If it does not, `pip install pywin32` into that Python (a wheel, no compiler) and run its post-install
   once. Without it the desk falls back to a plain request and reports the server's 401 in a sentence.
10. **The first read**, as the desk account, from `platform/psa-spine`:
    `C:\PMC\Python312\python.exe -m psaspine sync-mms-reports "<the desk's connection>"` prints
    `164 reports listed: 164 new, …` and writes nothing; then `--apply`. Then a scheduled task, daily, same line with
    `--apply`, logging to `D:\psa\logs`. (Or press *Read the server's list now* on Setup › MMS reports.)
11. **One walk-through**, by you or a service manager: Procurement › Reports; open *Perpetual inventory* (or whichever
    is first); the dropdowns fill from the server; *Run and show the PDF*; the PDF shows; *Download Excel* saves a
    workbook. Report which step stops, if any, with the sentence the page shows; do not paste the PDF.

## 4a. The lookup view you built, and the sweep you asked for

Your message of 13 Oct (152 entries across five lists, categories A–Z, purchase order statuses in working order) is
MEASURED on your side; on this head the desk shows the list's **word for every stored code on every screen**: Finance's
grid cells, summary tiles and record page, Procurement's plain cells and its status filter, a change's *from → to*, a
new record's facts. The dropdowns already did. One thing to confirm, since the desk reads the lists by name: the
`ListName` values are exactly **`po_status`, `rr_status`, `currency`, `unit`, `category`** (the 081 handoff's §5).
A list under another name is read and ignored, and its field keeps showing what BizBox has used so far. The Procurement
banner reads *… · 152 list entries* once the read has run.

## 5. What to look for afterwards

- `psa.mms_report`: **164** present rows after the first read; areas split roughly purchasing / receiving / stock
  by name. Any report whose area reads wrong is moved on Setup › MMS reports, and the move survives the next read.
- `psa.mms_report_run` grows by one row per run; a failed run has `outcome = 'ERROR'` and the server's sentence.
- PSA-Desk's log carries no report bytes and no parameter values beyond the run table.
- The report server's own log shows the desk's account, not a person's: the audit of who ran what is the desk's
  table, by design.

## 6. Evidence

| | |
|---|---|
| Unit suite | `MmsReportsTest` (2): the folder read into the catalogue in words by area (a folder and a data source skipped), a second read unchanged, an absent report kept and marked, a set title surviving a read, the address fenced, the CLI preview; the tab by area with counts and search, the nav entry; the report page drawing the server's parameters (date, dropdown, multi, yes/no, nullable, a hidden one not asked), the child dropdown waiting for its parent and refreshing from the server with the parent's value sent, a run with values missing named, a run embedded with Open in a new tab and Download Excel, the render URL carrying every value (multi repeated, null as isnull), the PDF inline and the Excel as an attachment, both logged with values, the page opening on the last run, a 401 as a sentence and a logged failure, rights per area (403 on page and render), Setup's edits audited and a read from the page keeping a set area. Full suite: see the commit message. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
| CI | See the commit that follows. |
| Not run here | Anything against `http://dnd-sql01/ReportServer`; `pywin32` on the host. |
