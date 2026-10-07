-- 073: who answers the chat, and which board takes it.
--
-- Dada, 7 Oct 2026: "can we add a chat operator member access atm make sure
-- only PMO Helpdesk members can use the chat". Confirmed before building: a
-- "Chat operator" tick on the member record, given only to members of a board
-- that takes chats, and only PMO Helpdesk takes chats for now, so every ward
-- chat goes there.
--
-- Until now any member who could work a board saw its chats and answered
-- them, and a ward could chat with any board its department may raise to.
-- After this step the desk side of chat (the banner, the queue, picking up,
-- replying, making a ticket) is for a ticked member of a board that takes
-- chats, and the portal offers chat only to those boards.
--
-- Both columns follow 062: added NULL by the port, read as 0, so nothing is an
-- operator and no board takes chats until set. The handoff sets PMO Helpdesk
-- and ticks its working members in the same transaction.
ALTER TABLE member ADD COLUMN chat_operator INTEGER DEFAULT 0;   -- NULL reads as 0
ALTER TABLE board ADD COLUMN takes_chats INTEGER DEFAULT 0;      -- NULL reads as 0
