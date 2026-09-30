-- 057: the small setup tables the parity check left: emails per board, the
-- survey per board, knowledge categories, company status and type,
-- auto-assign on a board, and an in/out board.
--
-- Each is its own decision in the reference PSA (ServiceEmailTemplate,
-- ServiceSurvey, KnowledgeBaseCategory, CompanyStatus / CompanyType,
-- BoardAutoAssignResource, InOutBoard) and each is small here: a table or a
-- column, a page or a tab, nothing seeded, nothing that changes an existing
-- row. A board with no template, no survey setting and no auto-assign mode
-- behaves exactly as it did yesterday.

-- The wording of the emails a board sends, per kind. No row: the desk's own
-- words. Placeholders: {ticket}, {board}, {actor}, {when}. There is no
-- {summary} and no {note}: a subject and a body leave the building (6.1).
CREATE TABLE mail_template (
  board_id    TEXT NOT NULL REFERENCES board(board_id),
  kind        TEXT NOT NULL CHECK (kind IN ('OPENED', 'UPDATED', 'CLOSED', 'ASSIGNED', 'SCHEDULED', 'APPROVAL')),
  subject     TEXT NOT NULL,
  body        TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  updated_by  TEXT NOT NULL,
  PRIMARY KEY (board_id, kind)
);

-- The survey per board: NULL is on, as it always was; the question is the
-- board's own words, else the desk's.
ALTER TABLE board ADD COLUMN survey_enabled INTEGER CHECK (survey_enabled IN (0, 1));
ALTER TABLE board ADD COLUMN survey_question TEXT;

-- Knowledge categories: a name a reader browses by; an article may have one.
CREATE TABLE kb_category (
  category_id TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0
);
ALTER TABLE kb_article ADD COLUMN category_id TEXT REFERENCES kb_category(category_id);

-- A company's status (a customer, a former customer, a prospect) and type (a
-- hospital department, a supplier, a partner): words, not rules.
CREATE TABLE company_status (
  status_id   TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE company_type (
  type_id     TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0
);
ALTER TABLE entity ADD COLUMN status_id TEXT REFERENCES company_status(status_id);
ALTER TABLE entity ADD COLUMN type_id TEXT REFERENCES company_type(type_id);

-- Auto-assign: a rule per Subtype > Item pair names the member; with no rule,
-- the board's mode: nobody (NULL or OFF), the member with the fewest open
-- tickets on the board, or the default team's leader. A ticket that arrives
-- with an owner keeps it.
ALTER TABLE board ADD COLUMN auto_assign TEXT CHECK (auto_assign IN ('OFF', 'LEAST_LOADED', 'TEAM_LEADER'));
CREATE TABLE board_auto_assign (
  board_id          TEXT NOT NULL REFERENCES board(board_id),
  catalogue_item_id TEXT NOT NULL REFERENCES catalogue_item(catalogue_item_id),
  member            TEXT NOT NULL,
  PRIMARY KEY (board_id, catalogue_item_id)
);

-- The in/out board: where each member is right now, said by themselves.
CREATE TABLE member_presence (
  member      TEXT PRIMARY KEY,
  state       TEXT NOT NULL CHECK (state IN ('IN', 'OUT', 'ON_SITE', 'REMOTE', 'LEAVE')),
  note        TEXT,
  back_at     TEXT,
  set_at      TEXT NOT NULL,
  set_by      TEXT NOT NULL
);
