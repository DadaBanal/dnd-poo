-- 063: whose rows the Dispatch board shows (Dada, 1 Oct 2026: "can we have
-- an edit view as to who will be displayed on the dispatch portal").
--
-- The reference PSA's dispatch portal shows a chosen set of resources, not
-- everyone on every board. Here each dispatcher keeps one view: the people
-- whose rows they want, as a comma-separated list of member identifiers,
-- and optionally the one board. Nobody else's. The URL's `who=` shows a set
-- once; this is the one that applies when the URL says nothing.
CREATE TABLE dispatch_view (
  member      TEXT PRIMARY KEY,                -- the dispatcher, as board_member.member
  people      TEXT NOT NULL,                   -- member identifiers, comma-separated, lower case
  board_id    TEXT REFERENCES board(board_id), -- the one board, or NULL for all theirs
  updated_at  TEXT NOT NULL
);
