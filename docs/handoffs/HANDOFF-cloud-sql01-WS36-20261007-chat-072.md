# HANDOFF — Cloud Build → SQL01, WS36, 7 Oct 2026 (chat round two, 072)

**One schema step, 072 (three new tables and one nullable column), then the usual restart.**

This follows `…-20261007-chat-071.md`, which SQL01 applied at Part 50. It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for

Dada, 7 Oct: "a banner ... moving from right to left ... and a sound or a chime", "reactions and emojis", "attachments", "a survey at the end". Dada confirmed each one before it was built.

- **The banner**, on every desk page. Waiting chats scroll right to left, with a chime and a bell to switch the chime off.
- **Reactions**: 👍 ❤️ 😄 😮 🙏 ✅, plus an emoji picker in the message box.
- **Pictures and files** in chat. A ward's file waits for the desk to clear or withhold it, as ticket files do.
- **A rating**: one to five stars when a chat ends, shown in Reports beside Satisfaction.
- **"Please wait"**. Dada asked for it: "a message ... before a ticket gets picked up like please wait ... similar to support chats".
  - The moment a chat starts, the desk's welcome line appears in it.
  - The ward sees its place in the queue, kept current, until someone joins.
  - Each board writes its own welcome on its Setup page (`board.chat_welcome`).

## 2. The step: 072, then restart

**072 must be in before PSA-Desk starts on this head.** INFERRED from the code: two things read the new tables.

- **Every desk page.** Its banner polls `/chat/waiting.json`, and the chat pages and Reports read the new tables.
- **The attachment store's integrity check and purge.** They read `chat_file` when it exists, so chat files are counted as live.

Without 072, the chat pages and Reports would fail.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`.
4. Apply 072 as you applied 066 to 071: as sysadmin, via pyodbc, in one transaction, with the statements taken verbatim from `sqlserver/PMC_PSA_Spine_SqlServer.sql` under `-- … (from schema/072_chat_extras.sql)`. Each one is guarded:
   - `CREATE TABLE psa.[chat_reaction]`, with primary key (message_id, member, emoji) and FK to `chat_message`
   - `CREATE TABLE psa.[chat_file]`, with FKs to `chat_session` and `chat_message`
   - `CREATE INDEX [ix_chat_file_chat]`
   - `CREATE TABLE psa.[chat_survey]`, with FK to `chat_session`
   - `IF COL_LENGTH(N'psa.[board]', N'chat_welcome') IS NULL ALTER TABLE … ADD [chat_welcome] NVARCHAR(400) NULL`
5. Verify:
   - `OBJECT_ID` is non-NULL for all three tables.
   - All three tables return `COUNT(*) = 0`.
   - `COL_LENGTH(N'psa.board', N'chat_welcome')` is non-NULL, and `SELECT COUNT(*) FROM psa.board WHERE chat_welcome IS NOT NULL` returns **0**. Every board reads the desk's words until someone writes its own.
   - `chat_session` and `chat_message` hold the same counts as before.
6. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

**The file store.** Chat files go into the same folder as ticket files (`PSA_ATTACHMENT_DIR`). Nothing changes in the folder's set-up, backup or retention task. MEASURED from the code: `attachments-verify` now counts chat files as live, and a purge keeps their bytes.

## 3. What to look for

- **The banner.** With a chat waiting, a strip under the menu scrolls its subject right to left. A hover holds it still. The 🔔 switches the chime off or on.
- **Chime.** The browser plays it only after someone has clicked once on the page.
- **In a chat:**
  - ☺+ on a line adds a reaction;
  - 😊 opens the emoji set;
  - the paperclip sends a picture or file;
  - a screenshot pasted into the box is sent as well.
- **On the desk:** a ward's picture shows with **Clear** and **Withhold**.
- **The rating.** When a chat ends, the ward sees *How did we do?*. Reports then shows **Chat rating**.
- **"Please wait".** A new chat shows the welcome line and *you are number 1 in the queue*. When a technician replies, *… has joined the chat* appears.

## 4. Evidence on this head

| | |
|---|---|
| Unit suite | MEASURED: last full run 776 tests OK (1 skipped), before the please-wait line and the scroll fix; after them the modules suite ran 18 OK. The final full run was not completed, at Dada's request. New: `test_chat_banner_reactions_files_and_a_rating_at_the_end`. It covers the banner on desk pages only, and `waiting.json` for the person's boards only. It covers reactions toggled, counted and limited to the set. On files: PENDING, viewable by the desk and the sender, refused to a stranger, never an orphan to the store check, withheld then hidden from the ward, the desk's cleared at once, and carried onto the ticket with their review. On the rating: refused while the chat runs, kept once, shown on the desk page, the queue and Reports. |
| Browser checks | MEASURED: last full run 119 passed, 1 failed (the size check, card 200 → 252 px). The fix (banner drawn by the server; the pod scroll-hold no longer undoes the browser's own anchoring) was checked by a probe only: card stays at 200 px. NOT VERIFIED by a full browser run. New: the banner shows and moves right to left, with its bell. A reaction lands and reaches the ward unprompted. The emoji button inserts. A ward picture shows on the desk with Clear and Withhold. Ending the chat asks for the rating, and the rating is kept. |
| Drift gate | In step. 072 is in the port. |
| Not run here | 072 against SQL Server. The `sql-server` CI job runs on push. |
