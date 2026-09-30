-- 054: the source of a change on the audit trail, and the indexes a reader needs
--
-- Setup > Audit reads audit_event, which every change has written since 003.
-- What it could not say is WHERE a change came from: the desk, the portal, the
-- API, the mail pickup, the rules runner, or a command on the host. The
-- reference PSA's audit entry carries a source (Member / API / Workflow /
-- Portal / EmailConnector ...); this adds the same, stamped by the entry point
-- and never by the engine that made the change. Rows from before this step
-- read as unknown, which is the truth.

ALTER TABLE audit_event ADD COLUMN source TEXT;

CREATE INDEX ix_audit_event_when ON audit_event (occurred_at);
CREATE INDEX ix_audit_event_actor ON audit_event (actor);
CREATE INDEX ix_audit_event_subject ON audit_event (subject_kind, subject_id);
