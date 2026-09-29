-- 039 — the knowledge base, in the reference PSA's shape.
--
-- An article is a title and a body (Markdown), for the desk (INTERNAL) or for
-- requesters too (REQUESTER), in DRAFT, PUBLISHED or RETIRED. It may belong to
-- a board and to a Subtype › Item pair, which is how a ticket finds it. Every
-- save keeps the words it replaced (kb_revision), so an article is never
-- silently rewritten. A ticket that an article helped to resolve is linked,
-- and the count is how the desk learns which articles earn their keep.
-- Patient details are not refused (Dada, 28 Sep 2026); they are flagged on save
-- like every other free text, for the author to tidy.
PRAGMA foreign_keys = ON;

CREATE TABLE kb_article (
  article_id        TEXT PRIMARY KEY,                   -- 'KB-0001'
  title             TEXT NOT NULL,
  body              TEXT NOT NULL,
  audience          TEXT NOT NULL DEFAULT 'INTERNAL' CHECK (audience IN ('INTERNAL', 'REQUESTER')),
  status            TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PUBLISHED', 'RETIRED')),
  board_id          TEXT REFERENCES board(board_id),
  catalogue_item_id TEXT REFERENCES catalogue_item(catalogue_item_id),
  version           INTEGER NOT NULL DEFAULT 1,
  uses              INTEGER NOT NULL DEFAULT 0,
  created_at        TEXT NOT NULL,
  created_by        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  updated_by        TEXT NOT NULL
);

CREATE TABLE kb_revision (
  article_id  TEXT NOT NULL REFERENCES kb_article(article_id),
  version     INTEGER NOT NULL,
  title       TEXT NOT NULL,
  body        TEXT NOT NULL,
  saved_at    TEXT NOT NULL,
  saved_by    TEXT NOT NULL,
  PRIMARY KEY (article_id, version)
);

CREATE TABLE kb_ticket (
  article_id    TEXT NOT NULL REFERENCES kb_article(article_id),
  work_item_id  TEXT NOT NULL REFERENCES ticket(work_item_id),
  linked_at     TEXT NOT NULL,
  linked_by     TEXT NOT NULL,
  PRIMARY KEY (article_id, work_item_id)
);
