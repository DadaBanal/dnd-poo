-- 049 — request approvals: a manager says yes before the desk does the work.
--
-- A new user account, an access change, a licence: the desk should not do it
-- on the requester's word alone. The reference PSA has no approval step for
-- a service ticket (its approvals are for changes); a hospital needs one. So:
-- a department names its approver (Setup › Departments); a catalogue pair can
-- require approval; a technician can ask for one by hand. An approval request
-- parks the ticket in the board's "Awaiting approval" status (a waiting
-- status: the resolve clock pauses), emails the approver, and shows on the
-- approver's portal under Approvals. Their decision, with a reason, goes on
-- the ticket as a note the requester can read, and the ticket comes back to
-- the status it was in. Decisions are appended, never edited.
PRAGMA foreign_keys = ON;

ALTER TABLE department ADD COLUMN approver TEXT;                     -- an email at the hospital
ALTER TABLE catalogue_item ADD COLUMN needs_approval INTEGER DEFAULT 0
  CHECK (needs_approval IN (0, 1));

CREATE TABLE approval (
  approval_id      INTEGER PRIMARY KEY,
  work_item_id     TEXT NOT NULL REFERENCES ticket(work_item_id),
  approver         TEXT NOT NULL,                                    -- email, lower case
  requested_at     TEXT NOT NULL,
  requested_by     TEXT NOT NULL,
  reason           TEXT,
  status           TEXT NOT NULL DEFAULT 'PENDING'
                     CHECK (status IN ('PENDING', 'APPROVED', 'DECLINED', 'WITHDRAWN')),
  decided_at       TEXT,
  decided_by       TEXT,
  note             TEXT,
  return_status_id TEXT REFERENCES board_status(board_status_id)     -- where the ticket goes back to
);
CREATE INDEX ix_approval_ticket ON approval (work_item_id);
CREATE INDEX ix_approval_approver ON approval (approver, status);
