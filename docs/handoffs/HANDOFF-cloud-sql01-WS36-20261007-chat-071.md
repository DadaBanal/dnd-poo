# HANDOFF — Cloud Build → SQL01, WS36, 7 Oct 2026 (chat, 071)

**One schema step, 071 (two new tables), then the usual restart.** It can share the restart with 070 and with `…-20261007-project-access-survey.md`.

This follows those two and supersedes nothing. Order: 070, then 071, then the survey step, then one restart.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for

Dada, 7 Oct: "can we do something to connectwise chat?". Confirmed before building:
- chat is between a requester and the desk;
- it is offered on the portal at any time;
- patient details are flagged and warned about, never blocked.

- **Portal**: *Chat with the helpdesk*, at `/my/chat`.
- **Desk**: *Service Desk › Chat*, at `/chat`. From there a technician can:
  - pick a chat up and reply;
  - end it;
  - *Make a ticket* from it (the transcript becomes the description);
  - *Add to a ticket* (the transcript goes on as a Discussion note).
- **How it stays live**: the open chat polls every three seconds and the queue uses the desk's existing live stamp. No socket, no new port.

## 2. The step: 071, then restart

**071 must be in before PSA-Desk starts on this head.** INFERRED from the code: the Chat pages, the portal's chat pages and the `chats` live stamp read `chat_session` and `chat_message`. Nothing else reads them, so tickets, the board and time are untouched.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`, unless one was taken in this same sitting.
3. Stop `PSA-Desk`.
4. Apply 071 as you applied 066 to 070: as sysadmin, via pyodbc, in one transaction. Take the statements verbatim from `sqlserver/PMC_PSA_Spine_SqlServer.sql`, under `-- … (from schema/071_chat.sql)`. Each one is guarded:
   - `CREATE TABLE psa.[chat_session]`, with an FK to `board` and to `ticket`
   - `CREATE INDEX [ix_chat_session_status]`
   - `CREATE INDEX [ix_chat_session_requester]`
   - `CREATE TABLE psa.[chat_message]`, with an FK to `chat_session`
   - `CREATE INDEX [ix_chat_message_chat]`
5. Verify:
   - `OBJECT_ID(N'psa.chat_session')` and `OBJECT_ID(N'psa.chat_message')` are both non-NULL.
   - Both tables return `COUNT(*) = 0`.
6. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

## 3. What to look for

- On the desk: **Chat** in the Service Desk menu, showing an empty queue.
- On the portal: **Chat** beside *My requests*.

A first chat from a ward PC to the desk is the live proof, and is Dada's to run.

## 4. Evidence on this head

| | |
|---|---|
| Unit suite | **775 OK**, 1 skipped; browser checks 108 of 108; smoke 7 of 7. New: `test_chat_a_requester_and_the_desk_live`. It covers starting on the portal, landing on Unrouted, the queue limited to the person's boards, replying to pick up, the requester's poll, a background reply with a patient detail flagged and warned, a reader refused, another requester refused, Make a ticket, Add to a ticket, and ending. |
| Browser checks | New: the desk sees the waiting chat; Enter sends without a reload; the requester sees the line arrive by itself, and the desk sees the reply. Two people are signed in at once. |
| Drift gate | In step. 071 is in the port. |
| Not run here | 071 against SQL Server. The `sql-server` CI job runs on push. |
