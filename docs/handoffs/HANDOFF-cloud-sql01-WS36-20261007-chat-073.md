# HANDOFF — Cloud Build → SQL01, WS36, 7 Oct 2026 (chat round four, 073)

**One schema step, 073 (two nullable columns), a two-line seed in the same transaction, then the usual restart.**

This follows `…-20261007-chat-072.md`, which SQL01 applied at Part 51. It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

The round before this one ("round three": chats named by their person, the quick view, the bigger banner and the Taglish
*Paalala*) changed code only and needs no step. It comes with this pull.

---

## 1. What Dada asked for

Dada, 7 Oct: "change the chat beep to a more audible one", "if the chat is converted into a ticket can it be that the
operators time be recorded", and "a chat operator member access atm make sure only PMO Helpdesk members can use the
chat". Dada confirmed each one before it was built:

- **A louder ring.** A phone-style ring in place of the soft chime, again every 30 seconds while a chat waits.
- **The operator's time, pre-filled for them to confirm.** On *Make a ticket* (or *Add to a ticket*), the ticket opens
  with its time entry window up. Start is the operator's pick-up, End is now, and the notes say *Chat with ‹name› · chat
  N*. Nothing is booked until they press Save.
- **Chat operators.** *Chat operator* is a tick on the member record (Setup › Members). Only someone who works a board
  that takes chats can be ticked. A board takes chats by a tick on its Setup page, and **only PMO Helpdesk takes them
  for now**. The banner, the queue, picking up, replying and making a ticket are for ticked members only. Wards chat
  only with boards that take chats.

## 2. The step: 073, the seed, then restart

**073 must be in before PSA-Desk starts on this head.** INFERRED from the code: every desk page reads
`member.chat_operator` to decide whether to draw the chat banner and the Chat menu item, and the portal reads
`board.takes_chats`.

**Why the seed.** Without it, chat goes dark after the restart. The columns arrive empty: nobody would be an operator and
no board would take chats. The seed keeps today's behaviour: PMO Helpdesk takes chats, and everyone who works it
(`WORK` or `ADMIN`) is ticked. Dada then unticks anyone who should not answer.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`.
4. Measure, before anything changes:
   - `SELECT board_id FROM psa.board WHERE display_name = N'PMO Helpdesk'` must return **exactly one row**. Note its
     `board_id`. If it returns none or several, stop and hand back.
   - The number of distinct members with `WORK` or `ADMIN` on that board, and how many of them have no `psa.member`
     row.
5. In one transaction, as you applied 066 to 072:
   - The two statements taken verbatim from `sqlserver/PMC_PSA_Spine_SqlServer.sql` under
     `-- … (from schema/073_chat_operators.sql)`. Each is guarded with `IF COL_LENGTH(...) IS NULL`:
     - `ALTER TABLE psa.[member] ADD [chat_operator] INT NULL CONSTRAINT [DF_member_chat_operator] DEFAULT (0);`
     - `ALTER TABLE psa.[board] ADD [takes_chats] INT NULL CONSTRAINT [DF_board_takes_chats] DEFAULT (0);`
   - The seed, with the `board_id` from step 4 in place of `@b`:
     ```sql
     UPDATE psa.board SET takes_chats = 1 WHERE board_id = @b;
     INSERT INTO psa.[member] (member, created_at, created_by, updated_at, updated_by)
       SELECT DISTINCT bm.member, CONVERT(nvarchar(19), SYSDATETIME(), 120), N'SQL01 073',
                       CONVERT(nvarchar(19), SYSDATETIME(), 120), N'SQL01 073'
       FROM psa.board_member bm
       WHERE bm.board_id = @b AND bm.access IN (N'WORK', N'ADMIN')
         AND NOT EXISTS (SELECT 1 FROM psa.[member] m WHERE LOWER(m.member) = LOWER(bm.member));
     UPDATE psa.[member] SET chat_operator = 1
       WHERE LOWER(member) IN (SELECT LOWER(bm.member) FROM psa.board_member bm
                               WHERE bm.board_id = @b AND bm.access IN (N'WORK', N'ADMIN'));
     ```
     The `INSERT` only gives a record to someone the desk already knows from the board, as Setup › Members does when a
     sysadmin saves one. It writes no name, so the page still shows the AD contact's.
6. Verify, inside the transaction:
   - `COL_LENGTH` is non-NULL for both columns.
   - `SELECT COUNT(*) FROM psa.board WHERE takes_chats = 1` returns **1**.
   - `SELECT COUNT(*) FROM psa.[member] WHERE chat_operator = 1` equals the number measured in step 4.
   - `chat_session`, `chat_message` and `board` hold the same counts as before.
   - If any check fails, roll back and hand back.
7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

Nothing changes in the file store, the backup or any scheduled task.

## 3. What to look for

- **Setup › Boards › PMO Helpdesk** has *Takes chats from the portal* ticked. No other board does.
- **Setup › Members**, on a person who works PMO Helpdesk: *Chat operator: Yes*, with **Untick**. On someone who does not
  work it, *Make chat operator* is refused, with the board named.
- **A member who is not ticked** sees no *Chat* in the Service Desk menu and no banner. `/chat` answers 403 with what to
  ask for, and a chat's page answers 404.
- **The ring.** With a chat waiting, an operator's desk page rings: louder, two bursts, twice. It rings again about
  every 30 seconds until someone picks the chat up. Only one of the person's open tabs rings. The 🔔 mutes it, and ✕
  hides the banner and stops the ring until a new chat comes in. A browser plays sound only after someone has clicked
  once on the page.
- **Make a ticket** (or *Add to a ticket*) lands on the ticket with the time entry window open: Start at the pick-up,
  End at now, notes *Chat with ‹name› · chat N*. **Save** books it like any other time entry, to the desk's quarter
  hour. **Cancel** throws the clock away.
- **The portal's Chat** offers PMO Helpdesk only, whatever the ward's department.

## 4. Evidence

| | |
|---|---|
| Unit suite | See the commit message. New: `test_chat_operators_answer_and_their_time_waits_on_the_ticket`. It covers: no chat board, no operators and the 403 before anything is set; the tick refused without a chat board and to a reader; ticked by a sysadmin only, and audited; the portal refusing a board that does not take chats; a worker without the tick getting no menu, banner, JSON, page or reply; the ring's pieces in the script; *Make a ticket* opening the ticket on a stopped clock from pick-up to now, with nothing booked until Save; Save booking it; *Add to a ticket* starting from the operator's first line; and the untick. The three earlier chat tests now run with IT Help taking chats and alice ticked. |
| Browser checks | See the commit message. New: a waiting chat rings, and not again on the next page within 30 seconds; *Make a ticket* opens the ticket's time entry window with Start, End and the chat already filled in. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
