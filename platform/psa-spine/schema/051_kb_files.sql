-- 051 — files on a knowledge article: a screenshot of the setting, the
-- vendor's PDF, the exported config.
--
-- 039's article is Markdown text. A fix is often a picture: where the switch
-- is, what the dialog looks like. So an article takes files, kept the way a
-- ticket's are (027: sniffed by their own bytes, compressed, hashed, every
-- one reviewed for patient information before a requester sees it) in a
-- store of their own beside the attachment store, and the article's text
-- shows them with ![caption](file:N). Nothing here changes an article's
-- words; a file removed leaves its row and the audit.
PRAGMA foreign_keys = ON;

CREATE TABLE kb_file (
  file_id        INTEGER PRIMARY KEY,
  article_id     TEXT NOT NULL REFERENCES kb_article(article_id),
  filename       TEXT NOT NULL,
  caption        TEXT,
  media_type     TEXT NOT NULL,
  size_received  INTEGER NOT NULL CHECK (size_received > 0),
  size_stored    INTEGER NOT NULL CHECK (size_stored > 0),
  sha256         TEXT NOT NULL,
  encoding       TEXT NOT NULL CHECK (encoding IN ('IDENTITY', 'GZIP')),
  treatment      TEXT NOT NULL,
  uploaded_by    TEXT NOT NULL,
  uploaded_at    TEXT NOT NULL,
  review_status  TEXT NOT NULL DEFAULT 'PENDING'
                   CHECK (review_status IN ('PENDING', 'CLEARED', 'WITHHELD')),
  reviewed_by    TEXT,
  reviewed_at    TEXT,
  removed_at     TEXT,
  removed_by     TEXT,
  CHECK ((review_status = 'PENDING') = (reviewed_by IS NULL))
);
CREATE INDEX ix_kb_file_article ON kb_file (article_id);
