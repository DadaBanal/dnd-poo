# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (mail pickup: a crash can no longer stop email-to-ticket)

**No schema step. One pull, then the usual PSA-Desk restart for the came-from badges. The pickup change takes effect
on the next minute pass, with no restart.**

This follows `…-20261009-numbering-identity-cache.md`. It supersedes nothing. SQL01 held this pull at `c1c25d6`
because CI 82 and 83 were red; that hold is answered in §5.

**Status: applied.** SQL01, `edae965`: run 85 green, so the pull went in at `1637d4b` and PSA-Desk restarted (401,
down, 401). The first pickup passes on this code were all result 0, each link had a `.prev` beside it, and there
were no NUL bytes anywhere (MEASURED by SQL01, 9 Oct 2026). This file was written alongside that and arrived after
it. It is the record of what changed, and §4 is what to keep watching; nothing in §3 is still to do.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. Why

MEASURED by SQL01, 9 Oct 2026: the unclean shutdown at 13:10 (event 6008) left all three pickups' delta links in
`D:\psa\mail-state\` as NUL bytes. Every pass then failed with *Invalid URI*, and no email became a ticket from about
12:26 until the repair (`Repair-PsaMailPickup.ps1 -ResetDelta -Apply`). Dada asked for it to be made *stupid proof*.

## 2. What changes (`671dcd9`, tests `118deb4` and `1637d4b`)

`scripts/Invoke-PmcMailPickup.ps1`:

- **Saving.** A delta link is first written to `inbox-deltalink-<slug>.txt.tmp` and forced to disk (WriteThrough).
  It is then swapped in, and the link before it is kept as `inbox-deltalink-<slug>.txt.prev`. A crash leaves either the
  old link or the new one, never half a file.
- **Reading.** A link that is not a Graph link (NUL bytes, empty, cut short) is set aside as `….bad-<time>` and never
  deleted. The pass then carries on from `.prev`. If `.prev` is bad too, it reads from two hours before the last good
  save. It never reads later than `-Since`, and never more than 14 days back. Imports are keyed by Message-ID, so the
  overlap imports nothing twice.
- **Preview** (no `-Apply`) moves and renames nothing.
- **410 (link expired).** The pass forgets the link and its `.prev`, then reads from the last good save instead of
  from now, so nothing that arrived in between is skipped.

`scripts/Repair-PsaMailPickup.ps1 -ResetDelta -Apply` now forgets `.prev` as well, so the reset window is what gets read.

## 3. The step

1. Pull. The minute tasks (PSA-MailPickup and the per-mailbox pickups) run from this tree, so the next pass uses the
   new script. Nothing in any scheduled task's command line changes.
2. Restart `PSA-Desk` for the came-from badges in colour and on Compact (`86c51e7`, code only). Expect `:8085` to
   answer 401, go down, then answer 401 again.

## 4. What to look for

- **Each pickup's next pass** logs result 0 and the usual *N new message(s)* line.
- **In `D:\psa\mail-state\`**, after a pass that saved a link:
  - `inbox-deltalink-<slug>.txt` is a single line starting `https://graph.microsoft.com/`;
  - `inbox-deltalink-<slug>.txt.prev` exists beside it from the second save on;
  - no `.tmp` is left behind.
  - Do not paste the links back: they are bearer state. Their size and first 30 characters are enough.
- **There should be no `.bad-*` file.** If one appears, the log line beside it names the cause. Hand back with that line
  and the file's size, not its contents.
- **Mail still arrives.** Send one test mail to each of the three mailboxes, and each becomes a ticket within a couple
  of minutes.

If a pass fails after the pull, go back with `git checkout c1c25d6 -- platform/psa-spine/scripts/Invoke-PmcMailPickup.ps1`
and hand back with the log line. The old script reads the same `inbox-deltalink-<slug>.txt` and ignores `.prev`.

## 5. Evidence

| | |
|---|---|
| Why 82 and 83 were red | Three source-text tests were pinned to the wording `671dcd9` replaced. I pushed it without the full suite. Run 84 then failed on Windows only, because a new check assumed LF line endings. Both are fixed, and the pickup itself did not change in either fix. |
| Unit suite | 804 tests OK (SQLite, Linux), 1 skipped. MEASURED, 9 Oct 2026. |
| Pickup functions | `tests/ps/delta-link-check.ps1`, 14 PASS, 0 FAIL: the script parses, then 13 checks on its own functions, lifted from the shipped script: first run; save, read back, `.prev` kept, no `.tmp` left; a NUL-filled file (the 6008 case) is not a link; preview carries on from `.prev` and moves nothing; with `-Apply` it carries on from `.prev` and sets the bad file aside; both lost, reads from two hours before the last save, never later than `-Since`, never more than 14 days back; the next good save reads normally. Passes under PowerShell 7.4 here and under 5.1 on the Windows CI job. |
| CI | `psa-spine` run 85, dispatched on `1637d4b`: green on all four jobs (Linux 3.11 and 3.14, sql-server, windows). MEASURED, 9 Oct 2026. |
| Not run here | The script against Graph and the live mailboxes. |

## Not ours, but noted for Dada

The 13:10 restart was unclean (event 6008). It cost the ticket numbers (IDENTITY cache, now off) and the mail links
(this file). Why the host went down uncleanly is worth a look of its own.
