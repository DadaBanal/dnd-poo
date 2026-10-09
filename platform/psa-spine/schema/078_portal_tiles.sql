-- 078: tiles on the requester portal, in the reference PSA's help-portal shape.
--
-- Dada, 9 Oct 2026: "on the my requests portal we should add in there an option
-- like the help portal for connectwise like choosing tiles what are your issues
-- so that we can route to the procurement board the pmo helpdesk board so it
-- helps the ticketer". Confirmed before building:
--   * the tiles are set up on a Setup page, not fixed in the code;
--   * a tile may open a row of smaller tiles (one level), and a tile sends the
--     request to its board with its Type, Subtype and Item already chosen;
--   * a tile may ask a few questions, kept per question for the desk;
--   * every department sees every tile ("every department has procurement
--     inventory mms issues"), so a tile's board does not need a department tick;
--   * a request whose Item needs approval (049) asks for it, as the desk does.
-- A sub-tile with no board or no Item takes its parent's.
CREATE TABLE portal_tile (
  tile_id           INTEGER PRIMARY KEY,
  parent_id         INTEGER REFERENCES portal_tile(tile_id),
  label             TEXT NOT NULL,
  hint              TEXT,
  icon              TEXT,
  board_id          TEXT REFERENCES board(board_id),
  catalogue_item_id TEXT REFERENCES catalogue_item(catalogue_item_id),
  sort_order        INTEGER NOT NULL DEFAULT 0,
  inactive          INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1))
);
CREATE INDEX ix_portal_tile_parent ON portal_tile (parent_id);

-- A question a tile asks. A parent tile's questions are asked for each of its
-- sub-tiles as well, before the sub-tile's own.
CREATE TABLE portal_tile_question (
  question_id INTEGER PRIMARY KEY,
  tile_id     INTEGER NOT NULL REFERENCES portal_tile(tile_id),
  label       TEXT NOT NULL,
  field_type  TEXT NOT NULL DEFAULT 'TEXT'
              CHECK (field_type IN ('TEXT', 'PARAGRAPH', 'NUMBER', 'DATE', 'CHECKBOX')),
  required    INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0,
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1))
);
CREATE INDEX ix_portal_tile_question_tile ON portal_tile_question (tile_id);

-- What the requester answered, one row per question, with the question's words
-- as they were asked (a question renamed later does not rewrite an answer).
CREATE TABLE portal_answer (
  work_item_id TEXT NOT NULL REFERENCES ticket(work_item_id),
  question_id  INTEGER NOT NULL REFERENCES portal_tile_question(question_id),
  label        TEXT NOT NULL,
  value        TEXT,
  PRIMARY KEY (work_item_id, question_id)
);

-- Which tile a request came in by, for the desk and for reports.
ALTER TABLE ticket ADD COLUMN portal_tile_id INTEGER REFERENCES portal_tile(tile_id);
