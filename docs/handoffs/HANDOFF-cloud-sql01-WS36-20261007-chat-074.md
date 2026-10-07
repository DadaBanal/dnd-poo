# HANDOFF — Cloud Build → SQL01, WS36, 7 Oct 2026 (chat round five, 074)

**One schema step, 074 (one nullable column), then the usual restart.**

This follows `…-20261007-chat-073.md` and supersedes nothing. **If 073 is not in yet, apply 073 and then 074 in the
same stop.** 073's handoff is unchanged, and the two steps touch different columns.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

This pull also brings one code-only change from earlier today, with no step of its own. When a chat that has a ticket
ends, the rest of the conversation (everything after *Make a ticket* or *Add to a ticket*) goes on the ticket as one
Discussion note, with the files sent in that part.

---

## 1. What Dada asked for

Dada, 7 Oct: "option to close or end the chat and survey or how i did at the end". Dada confirmed each part before it was
built:

- **An end window.** *End the chat* on the desk opens a small window with an optional closing message and **Ask ‹name›
  how I did**, ticked by default. Unticked, the chat ends with no rating card for the ward.
- **"How did Lea Cruz do?"** The ward rates the operator who had the chat, by name. Each rating counts to that operator:
  per operator in Reports, and on each person's page in Setup › Members.
- **End from the banner's quick view**, beside a chat that is yours.

## 2. The step: 074, then restart

**074 must be in before PSA-Desk starts on this head.** INFERRED from the code:
- Ending a chat from the desk without asking writes `chat_session.ask_rating`. Without the column, that End fails.
- Reading is guarded, so every other page works without the column, and every chat counts as asked.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`.
4. If 073 is not applied, apply it first, per its handoff, seed included.
5. In one transaction, as you applied 066 to 073, run the statement taken verbatim from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql` under `-- … (from schema/074_chat_ending.sql)`. It is guarded:
   - `IF COL_LENGTH(N'psa.[chat_session]', N'ask_rating') IS NULL`
     `ALTER TABLE psa.[chat_session] ADD [ask_rating] INT NULL CONSTRAINT [DF_chat_session_ask_rating] DEFAULT (1);`
6. Verify, inside the transaction:
   - `COL_LENGTH(N'psa.chat_session', N'ask_rating')` is non-NULL.
   - `SELECT COUNT(*) FROM psa.chat_session WHERE ask_rating = 0` returns **0**. Existing chats are NULL, which reads as
     asked, exactly as they were.
   - `chat_session`, `chat_message` and `chat_survey` hold the same counts as before.
7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

Nothing changes in the file store, the backup or any scheduled task.

## 3. What to look for

- **The end window.** On a chat, *End the chat* opens a window with a closing message box and *Ask ‹name› how I did*,
  ticked.
  - Unticked: the ward reads the closing line and gets no rating card, and the desk's chat page says *ended without a
    rating*.
  - Ticked: the ward's card reads *How did ‹operator› do?*, with *Paki-rate po ang tulong na natanggap ninyo.*
- **The quick view.** *Live chats* shows **End** beside a chat you have. It opens that chat with the end window up.
- **Reports.** Under *Chat rating*, a table of operators: their average and how many chats were rated in the period.
- **Setup › Members.** On a chat operator's page: *Rated n / 5 by the wards over N chats*.

## 4. Evidence

| | |
|---|---|
| Unit suite | See the commit message. New: `test_chat_ends_with_or_without_asking_how_the_operator_did`. It covers: the window and its tick; End in the quick view for your own chat and the window opening on `?end=1`; ending with a closing line and without asking, so there is no card, no rating taken, and *ended without a rating*; ending with asking, so the card names the operator in Taglish, in the page and in the poll; the ward's own End and an older page's bare End both asking; a chat nobody had asking *How did we do?*; ratings counted per operator, in `metrics.desk`, in Reports' table and on the member page. Also `test_chat_the_rest_of_it_goes_on_the_ticket_when_it_ends` for the code-only change. |
| Browser checks | See the commit message. New: the ward's card names the operator; a chat started from the portal form, picked up, then ended from the quick view's End, its window opening with the tick on; unticked with a closing line, the ward reads the line and is not asked to rate. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
