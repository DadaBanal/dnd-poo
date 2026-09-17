/* =====================================================================================
   Create-WS38-ClaimsSchema-HMO-20260911-v2.sql
   WS38 — HMO + EMPLOYEE guarantor paperless trail.

   Supersedes: sql/Create-WS38-ClaimsSchema-HMO-20260911.sql
               That file FAILED the parse gate on DND-SQL01\PMC_SS, 11 Sep 2026, @Apply = 0:
               Msg 102 twice (its lines 45 and 52), Msg 208 (its line 343). Nothing was created.
               Record: docs/ws38-schema-parse-and-corrections-20260911.md
                       docs/state-20260911-sql01.md  §7, §12, §14
                       docs/continuation-prompt-ws38-hmo-20260911-v2.md  §A, §B

   Written from the cloud session, 11 Sep 2026.  NOT YET COMPILED — no SQL client there.
   The same gate applies again: run at @Apply = 0 on DND-SQL01 first and read the output.
   A clean parse is a finding, NOT permission to set @Apply = 1.

   Creates schema [claims] in PMC_Apps: the flow-type lookup, the block-reason lookup,
   the payer register, the tracker header, the append-only event log, the LOA evidence
   table, the Post A/R event table, the append-only guard, and a proof harness.

   ADDITIVE ONLY.  Creates nothing outside PMC_Apps.  Reads nothing from LIVEDB_PMC.
   No existing object is altered or dropped.

   -------------------------------------------------------------------------------------
   @Apply = 0  ->  PREVIEW.  Prints what it WOULD create and runs the proof harness
                   against whatever already exists.  Changes nothing.
   @Apply = 1  ->  CREATES.  One transaction, XACT_ABORT ON.  Rollback is in comments at
                   the bottom of this file.
   -------------------------------------------------------------------------------------

   WHAT CHANGED FROM THE SUPERSEDED FILE  (each fix is tagged [Fn] where it sits)

   [F1] RAISERROR guards: DB_NAME() hoisted into @db.  A RAISERROR substitution argument
        must be a literal or a variable; a function call is a parse error (Msg 102).  In
        the old file the two guards — and therefore the whole batch — never compiled.
        MEASURED on DND-SQL01, 11 Sep.
   [F2] Proof harness split.  Rows that read claims.* tables now run inside
        sp_executesql behind an OBJECT_ID check, so they bind at execution time.  An
        ad-hoc batch has no deferred name resolution for SELECT (Msg 208 at compile
        time, MEASURED), so the old harness could only run once the schema existed —
        the one case it was not needed for.  Rows that touch only sys.* run statically
        and always.  The AFTER row counts get the same treatment.
   [F3] SET QUOTED_IDENTIFIER ON in every batch.  claims.[Case].CaseRef is a PERSISTED
        computed column; creating it needs the option ON.  SSMS defaults ON, sqlcmd
        defaults OFF (SESSIONPROPERTY = 0, CREATE fails Msg 1934 — MEASURED).  Without
        this the file worked pasted into SSMS and failed from every automated path.
        INFERRED, NOT VERIFIED: INSERT into a table carrying a persisted computed column
        also needs the option ON, so the bridge's own connection must set it (sqlcmd -I,
        or SET QUOTED_IDENTIFIER ON per connection).  To be measured on DND-SQL01.
   [F4] DENY UPDATE, DELETE ON claims.CaseEvent in front of the trigger.  MEASURED on
        DND-SQL01: any error raised inside a trigger, THROW included, leaves the caller's
        transaction doomed (XACT_STATE() = -1; COMMIT fails 3930, then 3998).  A DENY
        refuses the write at permission-check time: error 229, XACT_STATE() = 1, appends
        still work.  The trigger stays as the backstop for principals a DENY does not
        bind (db_owner, sysadmin).  The principal is @AppPrincipal in batch 3 — NULL
        until the account the bridge connects as is established (state-20260911-sql01
        §12).  When NULL the DENY is skipped and harness row 17 reports FAIL, which is
        the truth: until then the append-only control is trigger-only.
   [F5] MAXICARE row: ConfirmedName is now NULL.  The old row set ConfirmedName with
        ConfirmedBy NULL, and harness row 12 excluded that key by name — so the one
        insurer explicitly NOT accredited was the only one that would display as
        confirmed.  The fact now lives in IsAccredited = 0 and the Note.  Row 12 has no
        exclusion.  An idempotent UPDATE (exact key) corrects the row if it already exists.
   [F6] Database guard repeated in batches 3 and 4.  RETURN leaves only the current
        batch; in the old file batches 3 and 4 ran regardless of database.
   [F7] Header prose corrected: HMO and EMPLOYEE are both IsActive = 1 (Dada, 11 Sep).
        The seed and harness row 9 were already right; the prose was stale.
   [F8] Preview no longer promises trgCaseAudit / trgApprovalAudit.  The old file printed
        them and never created them, and no harness row checked.  Still NOT written —
        see OPEN below.
   [F9] The trigger comment stated a disproven belief (that THROW leaves the caller's
        transaction healthy).  Rewritten to the measured behaviour.

   OPEN — deliberately not in this file
   - Field-level audit triggers (trgCaseAudit / trgApprovalAudit) on the payroll.AuditLog
     pattern.  Brief §6 requirement.  payroll.AuditLog's shape must be read on DND-SQL01
     first; it is not visible from where this was written.
   - @AppPrincipal.  Needs the bridge's connecting account established (an elevated look
     at the owner of the node process on port 4100).

   HMO + EMPLOYEE FIRST.  claims.FlowType is seeded with all seven candidate guarantor
   types; HMO and EMPLOYEE are IsActive = 1 (Dada ruled 11 Sep 2026).  The other five
   are present and inactive, so when the HMO office rules on the rest there is NO schema
   change — one UPDATE to IsActive and the flow opens.  That is why the lookup exists
   rather than a CHECK constraint on a string column.

   MEASURED 11 Sep 2026 on DND-SQL01\PMC_SS (docs/ws38-discovery-20260911.md):
     - approvalno is blank on 1,520 of 1,520 rows in LIVEDB_PMC.dbo.psGntrLedgers
     - 0 of 1,041 faCustomers rows carry customName / Abbrev / customID
     - account types: HMO 21 · Company 45 · Employee 687 · Officers 10 · Doctors 241 ·
       Promissory note 29 · Credit Card 4 · GOVERNMENT 2
   NOT USED, disproven 11 Sep: ApprovedAmount / CoveredAmount do not exist on any source
   table; they are CAST(NULL AS decimal(18,2)) literals inside rpt.FactHmoClaim.
   claims.Approval.ApprovedAmt / CoveredAmt are WS38's OWN capture fields.

   NO PATIENT IDENTIFIERS.  The tracker links by encounter key and account key only.
   Employee guarantors are captured by employee number, never by name in a report.
   ===================================================================================== */

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET QUOTED_IDENTIFIER ON;        -- [F3]
GO

/* =====================================================================================
   BATCH 2 — guards, preview, apply
   ===================================================================================== */
SET QUOTED_IDENTIFIER ON;        -- [F3] SET options are per batch in some clients; restate after every GO

DECLARE @Apply bit = 0;          -- <<<<<<  SET TO 1 AND RE-RUN TO CREATE  <<<<<<
DECLARE @db   sysname = DB_NAME();   -- [F1] RAISERROR needs a variable, not a function call

/* ---------------------------------------------------------------------------------
   GUARD 1 — right database.  This script must never run anywhere but PMC_Apps.
   --------------------------------------------------------------------------------- */
IF @db <> N'PMC_Apps'
BEGIN
    RAISERROR(N'ABORT: this script runs only in PMC_Apps. Current database is %s.', 16, 1, @db);
    RETURN;
END;

/* GUARD 2 — never the live HIS database, belt and braces. */
IF @db IN (N'LIVEDB_PMC', N'PMC', N'PHILHEALTH', N'PMC_HR')
BEGIN
    RAISERROR(N'ABORT: refusing to run against %s.', 16, 1, @db);
    RETURN;
END;

PRINT N'================================================================';
PRINT N'WS38 claims schema v2 — ' + CASE WHEN @Apply = 1 THEN N'APPLY' ELSE N'PREVIEW (no changes)' END;
PRINT N'Database : ' + @db;
PRINT N'Server   : ' + @@SERVERNAME;
PRINT N'Run at   : ' + CONVERT(nvarchar(19), SYSDATETIME(), 120);
PRINT N'QUOTED_IDENTIFIER in this session : ' + CONVERT(nvarchar(1), SESSIONPROPERTY('QUOTED_IDENTIFIER'));
PRINT N'================================================================';
PRINT N'';

/* ---------------------------------------------------------------------------------
   BEFORE — what exists right now
   --------------------------------------------------------------------------------- */
PRINT N'--- BEFORE ---';
SELECT  N'schema claims'                       AS [Object],
        CASE WHEN EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'claims')
             THEN N'EXISTS' ELSE N'absent' END AS [State];

SELECT  t.name AS [ExistingClaimsTable],
        (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS [Cols]
FROM    sys.tables t
JOIN    sys.schemas s ON s.schema_id = t.schema_id
WHERE   s.name = N'claims'
ORDER BY t.name;

PRINT N'';

IF @Apply = 0
BEGIN
    PRINT N'PREVIEW ONLY. Nothing was created.';
    PRINT N'Objects this script would create in [claims]:';
    PRINT N'   FlowType      (lookup, 7 rows seeded, HMO and EMPLOYEE active)';
    PRINT N'   BlockReason   (lookup, 6 rows seeded)';
    PRINT N'   PayerRegister (Candidate* / Confirmed* pattern, 21 HMO accounts + 1 not-accredited marker seeded)';
    PRINT N'   [Case]        (tracker header)';
    PRINT N'   CaseEvent     (append-only; UPDATE and DELETE refused by DENY, backstopped by trigger)';
    PRINT N'   Approval      (LOA evidence)';
    PRINT N'   PostAR        (the Post A/R event)';
    PRINT N'   + trgCaseEventNoChange append-only backstop trigger';
    PRINT N'   + DENY UPDATE, DELETE ON CaseEvent to @AppPrincipal (skipped while @AppPrincipal is NULL)';
    PRINT N'   NOT in this file: trgCaseAudit / trgApprovalAudit field-level audit triggers (open item)';   -- [F8]
    PRINT N'';
    PRINT N'>>> To create: change @Apply to 1 at the top of this batch AND in batch 3, then re-run. <<<';
    PRINT N'';
END;

/* =================================================================================
   APPLY
   ================================================================================= */
IF @Apply = 1
BEGIN
    BEGIN TRAN;

    IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'claims')
        EXEC(N'CREATE SCHEMA [claims] AUTHORIZATION [dbo];');

    /* ---- lookup: flow type.  HMO and EMPLOYEE active, the rest present and inactive ---- */
    IF OBJECT_ID(N'claims.FlowType') IS NULL
    EXEC(N'
        CREATE TABLE claims.FlowType (
            FlowCode      varchar(20)   NOT NULL CONSTRAINT PK_claims_FlowType PRIMARY KEY,
            FlowName      nvarchar(80)  NOT NULL,
            IsActive      bit           NOT NULL CONSTRAINT DF_claims_FlowType_Active DEFAULT (0),
            SortOrder     int           NOT NULL CONSTRAINT DF_claims_FlowType_Sort   DEFAULT (99),
            Note          nvarchar(200) NULL,
            UpdatedAt     datetime2(0)  NOT NULL CONSTRAINT DF_claims_FlowType_Upd    DEFAULT (SYSDATETIME())
        );');

    /* [F7] HMO and EMPLOYEE active (Dada, 11 Sep 2026). The other five wait on the HMO office ruling. */
    INSERT claims.FlowType (FlowCode, FlowName, IsActive, SortOrder, Note)
    SELECT v.FlowCode, v.FlowName, v.IsActive, v.SortOrder, v.Note
    FROM (VALUES
        ('HMO',       N'HMO / Insurer',        CONVERT(bit,1), 1, N'21 insurer accounts. Live first.'),
        ('COMPANY',   N'Company / Corporate',  CONVERT(bit,0), 2, N'45 company accounts. Awaiting ruling.'),
        ('PHIC',      N'PhilHealth',           CONVERT(bit,0), 3, N'Statutory 60-day clock. Awaiting ruling.'),
        ('DOCTOR',    N'Doctor guarantor',     CONVERT(bit,0), 4, N'241 doctor accounts. Awaiting ruling.'),
        ('EMPLOYEE',  N'Employee / Officer',   CONVERT(bit,1), 5, N'687 employee + 10 officer. ACTIVE: Dada ruled 11 Sep 2026 that employee guarantors ship with HMO.'),
        ('PROMNOTE',  N'Promissory note',      CONVERT(bit,0), 6, N'29 accounts MEASURED 11 Sep. NOT in the original five flows.'),
        ('CREDITCARD',N'Credit card acquirer', CONVERT(bit,0), 7, N'4 accounts MEASURED 11 Sep. NOT in the original five flows.')
    ) v (FlowCode, FlowName, IsActive, SortOrder, Note)
    WHERE NOT EXISTS (SELECT 1 FROM claims.FlowType f WHERE f.FlowCode = v.FlowCode);

    /* ---- lookup: block reason ---- */
    IF OBJECT_ID(N'claims.BlockReason') IS NULL
    EXEC(N'
        CREATE TABLE claims.BlockReason (
            ReasonCode  varchar(20)   NOT NULL CONSTRAINT PK_claims_BlockReason PRIMARY KEY,
            ReasonText  nvarchar(160) NOT NULL,
            SortOrder   int           NOT NULL CONSTRAINT DF_claims_BlockReason_Sort DEFAULT (99)
        );');

    INSERT claims.BlockReason (ReasonCode, ReasonText, SortOrder)
    SELECT v.ReasonCode, v.ReasonText, v.SortOrder
    FROM (VALUES
        ('NOTPAID',   N'Account reads "Not Yet Paid"',                1),
        ('NOPOSTAR',  N'No one authorised present to Post A/R',       2),
        ('NOAPPROVAL',N'Guarantor approval not yet obtained',         3),
        ('NOTRECORDED',N'Approval obtained but not recorded in BizBox',4),
        ('NOINVOICE', N'Invoice not raised',                          5),
        ('OTHER',     N'Other',                                       9)
    ) v (ReasonCode, ReasonText, SortOrder)
    WHERE NOT EXISTS (SELECT 1 FROM claims.BlockReason b WHERE b.ReasonCode = v.ReasonCode);

    /* ---- payer register: the answer to "0 of 1,041 accounts carry a name" ----
       Candidate* holds the PROPOSAL (accredited list, matched in order).
       Confirmed* holds what a human has actually confirmed.
       Nothing INFERRED is ever displayed: the app reads ConfirmedName, which is NULL
       until the HMO office types it. Follows rpt.HmoNameMap exactly.              */
    IF OBJECT_ID(N'claims.PayerRegister') IS NULL
    EXEC(N'
        CREATE TABLE claims.PayerRegister (
            PayerKey        varchar(20)   NOT NULL CONSTRAINT PK_claims_PayerRegister PRIMARY KEY,
            FlowCode        varchar(20)   NOT NULL,
            CandidateName   nvarchar(120) NULL,
            ConfirmedName   nvarchar(120) NULL,
            ConfirmedBy     nvarchar(80)  NULL,
            ConfirmedAt     datetime2(0)  NULL,
            IsAccredited    bit           NULL,
            InvoiceCount    int           NULL,
            OpenValue       decimal(18,2) NULL,
            Note            nvarchar(200) NULL,
            UpdatedAt       datetime2(0)  NOT NULL CONSTRAINT DF_claims_PayerRegister_Upd DEFAULT (SYSDATETIME()),
            CONSTRAINT FK_claims_PayerRegister_Flow FOREIGN KEY (FlowCode)
                REFERENCES claims.FlowType (FlowCode)
        );');

    /* 21 HMO accounts, MEASURED from PMC_Payer_Name_Confirmation_20260909.xlsx.
       CandidateName is the in-order match against the 24 Feb 2026 accredited list.
       It is a PROPOSAL. ConfirmedName stays NULL until a human confirms it.        */
    INSERT claims.PayerRegister (PayerKey, FlowCode, CandidateName, IsAccredited, InvoiceCount, OpenValue, Note)
    SELECT v.k, 'HMO', v.n, v.acc, v.inv, v.val,
           N'Candidate matched in order against the 24 Feb 2026 accredited list. PROPOSAL, not a fact.'
    FROM (VALUES
        ('06260012', N'INTELLICARE',          CONVERT(bit,1), 246, CONVERT(decimal(18,2),1486573.18)),
        ('06260011', N'INSULAR HEALTHCARE',   CONVERT(bit,1), 153, CONVERT(decimal(18,2),1001457.68)),
        ('06260015', N'MEDICARD',             CONVERT(bit,1), 126, CONVERT(decimal(18,2),425855.22)),
        ('06260018', N'PHILHEALTHCARE',       CONVERT(bit,1),  98, CONVERT(decimal(18,2),853919.61)),
        ('06260019', N'VALUECARE',            CONVERT(bit,1),  84, CONVERT(decimal(18,2),286329.24)),
        ('06260002', N'AVEGA',                CONVERT(bit,1),  72, CONVERT(decimal(18,2),370274.03)),
        ('06260013', N'KAISER',               CONVERT(bit,1),  36, CONVERT(decimal(18,2),226943.14)),
        ('06260004', N'COCOLIFE',             CONVERT(bit,1),  24, CONVERT(decimal(18,2),69807.24)),
        ('06260007', N'ETIQA',                CONVERT(bit,1),  18, CONVERT(decimal(18,2),80887.14)),
        ('06260009', N'GENERALI PHILIPPINES', CONVERT(bit,1),  16, CONVERT(decimal(18,2),49700.00)),
        ('06260014', N'MEDASIA',              CONVERT(bit,1),  16, CONVERT(decimal(18,2),205869.60)),
        ('06260008', N'FORTUNELIFE',          CONVERT(bit,1),  13, CONVERT(decimal(18,2),24496.00)),
        ('06260001', N'AMAPHIL',              CONVERT(bit,1),  12, CONVERT(decimal(18,2),169390.01)),
        ('06260020', N'SUNLIFE',              CONVERT(bit,1),   9, CONVERT(decimal(18,2),14520.00)),
        ('06260005', N'EASTWEST',             CONVERT(bit,1),   6, CONVERT(decimal(18,2),79040.00)),
        ('06260010', N'HMI',                  CONVERT(bit,1),   3, CONVERT(decimal(18,2),62600.00)),
        ('06260017', N'MEDOCARE',             CONVERT(bit,1),   2, CONVERT(decimal(18,2),32532.94)),
        ('06260003', N'BENLIFE',              CONVERT(bit,1),   1, CONVERT(decimal(18,2),5392.00)),
        ('06260006', N'EMA GLOBAL',           CONVERT(bit,1),   0, CONVERT(decimal(18,2),0.00)),
        ('06260016', N'MEDILINK',             CONVERT(bit,1),   0, CONVERT(decimal(18,2),0.00)),
        ('08260067', NULL,                    NULL,             3, CONVERT(decimal(18,2),6670.00))
    ) v (k, n, acc, inv, val)
    WHERE NOT EXISTS (SELECT 1 FROM claims.PayerRegister p WHERE p.PayerKey = v.k);

    /* 08260067 opened during the August cutover, after the accredited list -> no candidate. */
    UPDATE claims.PayerRegister
       SET Note = N'Opened during the Aug 2026 cutover, after the 24 Feb accredited list. No candidate name exists.'
     WHERE PayerKey = '08260067' AND CandidateName IS NULL;

    /* [F5] MAXICARE is explicitly NOT accredited — recorded so nobody re-adds it.
       ConfirmedName stays NULL: nothing unconfirmed is ever presentable, this row included.
       The fact lives in IsAccredited = 0 and the Note.                                   */
    INSERT claims.PayerRegister (PayerKey, FlowCode, CandidateName, ConfirmedName, IsAccredited, Note)
    SELECT 'NOTACCRED-MAXICARE', 'HMO', NULL, NULL, CONVERT(bit,0),
           N'MAXICARE. Explicitly NOT accredited (HMO Relations Supervisor, 24 Feb 2026). Not a payable account.'
    WHERE NOT EXISTS (SELECT 1 FROM claims.PayerRegister p WHERE p.PayerKey = 'NOTACCRED-MAXICARE');

    /* [F5] idempotent correction, exact key: if the row was ever seeded the old way, clear it. */
    UPDATE claims.PayerRegister
       SET ConfirmedName = NULL,
           Note = N'MAXICARE. Explicitly NOT accredited (HMO Relations Supervisor, 24 Feb 2026). Not a payable account.'
     WHERE PayerKey = 'NOTACCRED-MAXICARE' AND ConfirmedName IS NOT NULL AND ConfirmedBy IS NULL;

    /* ---- the tracker header ---- */
    IF OBJECT_ID(N'claims.Case') IS NULL
    EXEC(N'
        CREATE TABLE claims.[Case] (
            CaseId         int IDENTITY(1,1) NOT NULL CONSTRAINT PK_claims_Case PRIMARY KEY,
            CaseRef        as (CONCAT(''WS38-'', RIGHT(CONCAT(''000000'', CaseId), 6))) PERSISTED,
            EncounterKey   varchar(30)   NOT NULL,
            PatientAcctKey varchar(30)   NOT NULL,
            Department     nvarchar(60)  NOT NULL,
            Service        nvarchar(160) NOT NULL,
            FlowCode       varchar(20)   NOT NULL,
            ReasonCode     varchar(20)   NOT NULL,
            Status         varchar(20)   NOT NULL CONSTRAINT DF_claims_Case_Status DEFAULT (''Open''),
            Owner          nvarchar(80)  NOT NULL,
            BackupOwner    nvarchar(80)  NULL,
            WordTemplateUsed bit         NOT NULL CONSTRAINT DF_claims_Case_Word DEFAULT (0),
            BackEncoded    bit           NOT NULL CONSTRAINT DF_claims_Case_Enc  DEFAULT (0),
            ResultReadyAt  datetime2(0)  NULL,
            OpenedAt       datetime2(0)  NOT NULL CONSTRAINT DF_claims_Case_Opened DEFAULT (SYSDATETIME()),
            BlockedAt      datetime2(0)  NULL,
            DueAt          datetime2(0)  NULL,
            ReleasedAt     datetime2(0)  NULL,
            ClosedAt       datetime2(0)  NULL,
            CONSTRAINT FK_claims_Case_Flow   FOREIGN KEY (FlowCode)   REFERENCES claims.FlowType    (FlowCode),
            CONSTRAINT FK_claims_Case_Reason FOREIGN KEY (ReasonCode) REFERENCES claims.BlockReason (ReasonCode),
            CONSTRAINT CK_claims_Case_Status CHECK (Status IN
                (''Open'',''Blocked'',''ReadyForRelease'',''Released'',''Reconciled'',''Escalated'',''Cancelled''))
        );');

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_claims_Case_Open' AND object_id = OBJECT_ID(N'claims.Case'))
        EXEC(N'CREATE INDEX IX_claims_Case_Open ON claims.[Case] (Status, DueAt) INCLUDE (Owner, Department, FlowCode);');
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_claims_Case_Encounter' AND object_id = OBJECT_ID(N'claims.Case'))
        EXEC(N'CREATE INDEX IX_claims_Case_Encounter ON claims.[Case] (EncounterKey);');

    /* ---- append-only event log ---- */
    IF OBJECT_ID(N'claims.CaseEvent') IS NULL
    EXEC(N'
        CREATE TABLE claims.CaseEvent (
            EventId     bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_claims_CaseEvent PRIMARY KEY,
            CaseId      int          NOT NULL,
            FromStatus  varchar(20)  NULL,
            ToStatus    varchar(20)  NOT NULL,
            Note        nvarchar(400) NULL,
            ActedBy     nvarchar(80) NOT NULL,
            ActedAt     datetime2(0) NOT NULL CONSTRAINT DF_claims_CaseEvent_At DEFAULT (SYSDATETIME()),
            CONSTRAINT FK_claims_CaseEvent_Case FOREIGN KEY (CaseId) REFERENCES claims.[Case] (CaseId)
        );');

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_claims_CaseEvent_Case' AND object_id = OBJECT_ID(N'claims.CaseEvent'))
        EXEC(N'CREATE INDEX IX_claims_CaseEvent_Case ON claims.CaseEvent (CaseId, EventId);');

    /* ---- LOA / approval evidence.  HMO fields are first-class; other flows reuse. ---- */
    IF OBJECT_ID(N'claims.Approval') IS NULL
    EXEC(N'
        CREATE TABLE claims.Approval (
            ApprovalId    int IDENTITY(1,1) NOT NULL CONSTRAINT PK_claims_Approval PRIMARY KEY,
            CaseId        int           NOT NULL,
            PayerKey      varchar(20)   NULL,
            ApprovalNo    varchar(60)   NULL,
            ApprovedAmt   decimal(18,2) NULL,
            CoveredAmt    decimal(18,2) NULL,
            CoPayAmt      decimal(18,2) NULL,
            ValidUntil    date          NULL,
            ObtainedBy    nvarchar(80)  NOT NULL,
            AfterHours    bit           NOT NULL CONSTRAINT DF_claims_Approval_AH DEFAULT (0),
            AttachRef     nvarchar(200) NULL,
            RecordedAt    datetime2(0)  NOT NULL CONSTRAINT DF_claims_Approval_At DEFAULT (SYSDATETIME()),
            CONSTRAINT FK_claims_Approval_Case  FOREIGN KEY (CaseId)   REFERENCES claims.[Case] (CaseId),
            CONSTRAINT FK_claims_Approval_Payer FOREIGN KEY (PayerKey) REFERENCES claims.PayerRegister (PayerKey),
            CONSTRAINT CK_claims_Approval_Amt   CHECK (ApprovedAmt IS NULL OR ApprovedAmt >= 0)
        );');

    /* ---- the Post A/R event ---- */
    IF OBJECT_ID(N'claims.PostAR') IS NULL
    EXEC(N'
        CREATE TABLE claims.PostAR (
            PostARId    int IDENTITY(1,1) NOT NULL CONSTRAINT PK_claims_PostAR PRIMARY KEY,
            CaseId      int          NOT NULL,
            PerformedBy nvarchar(80) NOT NULL,
            InvoiceNo   varchar(40)  NULL,
            PerformedAt datetime2(0) NOT NULL CONSTRAINT DF_claims_PostAR_At DEFAULT (SYSDATETIME()),
            CONSTRAINT FK_claims_PostAR_Case FOREIGN KEY (CaseId) REFERENCES claims.[Case] (CaseId)
        );');

    COMMIT;
    PRINT N'Tables created / already present. Committed.';
END;
GO

/* =====================================================================================
   BATCH 3 — append-only control on CaseEvent.  Separate batch: triggers need their own.
   This is the control that makes the audit trail survive an argument.
   ===================================================================================== */
SET QUOTED_IDENTIFIER ON;        -- [F3]

DECLARE @Apply        bit     = 0;     -- <<<<<<  MUST MATCH THE VALUE IN BATCH 2  <<<<<<
DECLARE @AppPrincipal sysname = NULL;  -- <<<<<<  [F4] the database user the bridge connects as.
                                       --         NULL = not yet established -> DENY is SKIPPED and
                                       --         harness row 17 reports FAIL. Set it once known.  <<<<<<
DECLARE @db           sysname = DB_NAME();

/* [F6] same guard as batch 2 — RETURN only left that batch. */
IF @db <> N'PMC_Apps' OR @db IN (N'LIVEDB_PMC', N'PMC', N'PHILHEALTH', N'PMC_HR')
BEGIN
    RAISERROR(N'ABORT (batch 3): refusing to run against %s.', 16, 1, @db);
    RETURN;
END;

IF @Apply = 1 AND OBJECT_ID(N'claims.CaseEvent') IS NOT NULL
   AND OBJECT_ID(N'claims.trgCaseEventNoChange') IS NULL
BEGIN
    /* [F9] BACKSTOP ONLY.  MEASURED on DND-SQL01 (state-20260911-sql01 §12): an error raised
       inside a trigger — THROW or RAISERROR, it makes no difference — leaves the caller's
       transaction doomed (XACT_STATE() = -1); a following COMMIT fails with 3930 and the batch
       ends with 3998.  So this trigger cannot give the bridge one clean error.  What it does
       give is a guarantee that no principal, db_owner and sysadmin included, can silently
       change or remove an event.  The clean-error path is the DENY below, which binds the
       application principal at permission-check time (error 229, XACT_STATE() = 1).       */
    EXEC(N'
    CREATE TRIGGER claims.trgCaseEventNoChange
    ON claims.CaseEvent
    INSTEAD OF UPDATE, DELETE
    AS
    BEGIN
        SET NOCOUNT ON;
        THROW 50038, N''claims.CaseEvent is append-only. UPDATE and DELETE are not permitted.'', 1;
    END;');
    PRINT N'Created claims.trgCaseEventNoChange (append-only backstop).';
END;

/* [F4] the DENY in front of the trigger */
IF @Apply = 1 AND OBJECT_ID(N'claims.CaseEvent') IS NOT NULL
BEGIN
    IF @AppPrincipal IS NULL
        PRINT N'DENY UPDATE, DELETE ON claims.CaseEvent SKIPPED: @AppPrincipal is NULL. '
            + N'Append-only control is trigger-only until the bridge account is established.';
    ELSE IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @AppPrincipal)
        PRINT N'DENY SKIPPED: principal ' + @AppPrincipal + N' does not exist in ' + @db + N'. Create the user first.';
    ELSE
    BEGIN
        DECLARE @deny nvarchar(400) = N'DENY UPDATE, DELETE ON claims.CaseEvent TO ' + QUOTENAME(@AppPrincipal) + N';';
        EXEC sys.sp_executesql @deny;
        PRINT N'Applied: ' + @deny;
    END;
END;
GO

/* =====================================================================================
   BATCH 4 — PROOF HARNESS.  Read-only.  Prints a FAIL row for anything that is not true.
   Part 1 touches only sys.* and runs on any database state.
   Part 2 reads the claims tables and runs only once they exist.  [F2]
   ===================================================================================== */
SET QUOTED_IDENTIFIER ON;        -- [F3]

DECLARE @db sysname = DB_NAME();
IF @db <> N'PMC_Apps' OR @db IN (N'LIVEDB_PMC', N'PMC', N'PHILHEALTH', N'PMC_HR')   -- [F6]
BEGIN
    RAISERROR(N'ABORT (batch 4): refusing to run against %s.', 16, 1, @db);
    RETURN;
END;

PRINT N'';
PRINT N'--- PROOF HARNESS, part 1: catalogue checks (always run) ---';

;WITH chk AS (
    SELECT 1 AS Seq, N'schema [claims] exists' AS [Check],
           CASE WHEN EXISTS (SELECT 1 FROM sys.schemas WHERE name=N'claims') THEN N'PASS' ELSE N'FAIL' END AS Result
    UNION ALL SELECT 2, N'claims.FlowType exists',
           CASE WHEN OBJECT_ID(N'claims.FlowType') IS NOT NULL THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 3, N'claims.PayerRegister exists',
           CASE WHEN OBJECT_ID(N'claims.PayerRegister') IS NOT NULL THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 4, N'claims.Case exists',
           CASE WHEN OBJECT_ID(N'claims.Case') IS NOT NULL THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 5, N'claims.CaseEvent exists',
           CASE WHEN OBJECT_ID(N'claims.CaseEvent') IS NOT NULL THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 6, N'claims.Approval exists',
           CASE WHEN OBJECT_ID(N'claims.Approval') IS NOT NULL THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 7, N'claims.PostAR exists',
           CASE WHEN OBJECT_ID(N'claims.PostAR') IS NOT NULL THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 8, N'CaseEvent append-only backstop trigger present',
           CASE WHEN OBJECT_ID(N'claims.trgCaseEventNoChange') IS NOT NULL THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 16, N'nothing was created outside PMC_Apps',
           CASE WHEN @db = N'PMC_Apps' THEN N'PASS' ELSE N'FAIL' END
    UNION ALL SELECT 17, N'DENY UPDATE and DELETE on claims.CaseEvent present for some principal',   -- [F4]
           CASE WHEN OBJECT_ID(N'claims.CaseEvent') IS NULL THEN N'n/a'
                WHEN (SELECT COUNT(DISTINCT permission_name) FROM sys.database_permissions
                      WHERE class = 1 AND major_id = OBJECT_ID(N'claims.CaseEvent') AND minor_id = 0
                        AND state = 'D' AND permission_name IN (N'UPDATE', N'DELETE')) = 2
                THEN N'PASS' ELSE N'FAIL - trigger-only; set @AppPrincipal in batch 3' END
    UNION ALL SELECT 18, N'CaseRef persisted computed column present on claims.Case',   -- [F3]
           CASE WHEN OBJECT_ID(N'claims.Case') IS NULL THEN N'n/a'
                WHEN EXISTS (SELECT 1 FROM sys.computed_columns
                             WHERE object_id = OBJECT_ID(N'claims.Case') AND name = N'CaseRef' AND is_persisted = 1)
                THEN N'PASS' ELSE N'FAIL' END
)
SELECT Seq AS [#], [Check], Result FROM chk ORDER BY Seq;

PRINT N'';
PRINT N'--- PROOF HARNESS, part 2: content checks (need the tables) ---';

IF  OBJECT_ID(N'claims.FlowType')      IS NOT NULL
AND OBJECT_ID(N'claims.PayerRegister') IS NOT NULL
AND OBJECT_ID(N'claims.Case')          IS NOT NULL
AND OBJECT_ID(N'claims.PostAR')        IS NOT NULL
BEGIN
    /* [F2] dynamic so it binds at execution time, after the OBJECT_ID test above has passed. */
    DECLARE @h nvarchar(max) = N'
    ;WITH chk AS (
        SELECT 9 AS Seq, N''exactly two flows active: HMO and EMPLOYEE (Dada, 11 Sep)'' AS [Check],
               CASE WHEN (SELECT COUNT(*) FROM claims.FlowType WHERE IsActive = 1) = 2
                     AND NOT EXISTS (SELECT 1 FROM claims.FlowType
                                     WHERE IsActive = 1 AND FlowCode NOT IN (''HMO'',''EMPLOYEE''))
                    THEN N''PASS'' ELSE N''FAIL'' END AS Result
        UNION ALL SELECT 10, N''all 7 candidate flow types are present'',
               CASE WHEN (SELECT COUNT(*) FROM claims.FlowType) = 7 THEN N''PASS'' ELSE N''FAIL'' END
        UNION ALL SELECT 11, N''21 HMO payer accounts seeded'',
               CASE WHEN (SELECT COUNT(*) FROM claims.PayerRegister
                          WHERE FlowCode = ''HMO'' AND PayerKey <> ''NOTACCRED-MAXICARE'') = 21
                    THEN N''PASS'' ELSE N''FAIL'' END
        UNION ALL SELECT 12, N''no INFERRED name is presentable (ConfirmedName NULL wherever ConfirmedBy is NULL, no exclusions)'',
               CASE WHEN NOT EXISTS (SELECT 1 FROM claims.PayerRegister
                                     WHERE ConfirmedName IS NOT NULL AND ConfirmedBy IS NULL)
                    THEN N''PASS'' ELSE N''FAIL'' END
        UNION ALL SELECT 13, N''MAXICARE recorded as NOT accredited, with no presentable name'',
               CASE WHEN EXISTS (SELECT 1 FROM claims.PayerRegister
                                 WHERE PayerKey = ''NOTACCRED-MAXICARE'' AND IsAccredited = 0
                                   AND ConfirmedName IS NULL AND CandidateName IS NULL)
                    THEN N''PASS'' ELSE N''FAIL'' END
        UNION ALL SELECT 14, N''every Released case has a PostAR row'',
               CASE WHEN NOT EXISTS (SELECT 1 FROM claims.[Case] c
                                     WHERE c.Status IN (''Released'',''Reconciled'')
                                       AND NOT EXISTS (SELECT 1 FROM claims.PostAR p WHERE p.CaseId = c.CaseId))
                    THEN N''PASS'' ELSE N''FAIL'' END
        UNION ALL SELECT 15, N''no case sits on an inactive flow'',
               CASE WHEN NOT EXISTS (SELECT 1 FROM claims.[Case] c
                                     JOIN claims.FlowType f ON f.FlowCode = c.FlowCode
                                     WHERE f.IsActive = 0)
                    THEN N''PASS'' ELSE N''FAIL'' END
    )
    SELECT Seq AS [#], [Check], Result FROM chk ORDER BY Seq;';
    EXEC sys.sp_executesql @h;
END
ELSE
    PRINT N'SKIPPED: claims tables absent, so rows 9-15 cannot bind. Expected on a first run at @Apply = 0.';

PRINT N'';
PRINT N'--- AFTER: objects in [claims] ---';
SELECT  o.type_desc AS [Type], s.name + N'.' + o.name AS [Object]
FROM    sys.objects o
JOIN    sys.schemas s ON s.schema_id = o.schema_id
WHERE   s.name = N'claims'
ORDER BY o.type_desc, o.name;

IF  OBJECT_ID(N'claims.FlowType')      IS NOT NULL
AND OBJECT_ID(N'claims.BlockReason')   IS NOT NULL
AND OBJECT_ID(N'claims.PayerRegister') IS NOT NULL
    EXEC sys.sp_executesql N'
        SELECT COUNT(*) AS [RowCount], N''claims.FlowType'' AS [Table] FROM claims.FlowType
        UNION ALL SELECT COUNT(*), N''claims.BlockReason''   FROM claims.BlockReason
        UNION ALL SELECT COUNT(*), N''claims.PayerRegister'' FROM claims.PayerRegister;';   -- [F2]
ELSE
    PRINT N'Row counts skipped: lookup tables absent.';
GO

/* =====================================================================================
   ROLLBACK — paste this block to undo everything this script created.
   Drop order matters: children before parents.
   Safe to run only while claims.Case is empty. If cases exist, STOP and decide.

   USE [PMC_Apps];
   GO
   -- only if a DENY was applied (batch 3, @AppPrincipal set); dropping the table removes it anyway:
   -- REVOKE UPDATE, DELETE ON claims.CaseEvent FROM [<AppPrincipal>];
   IF OBJECT_ID(N'claims.trgCaseEventNoChange') IS NOT NULL DROP TRIGGER claims.trgCaseEventNoChange;
   IF OBJECT_ID(N'claims.PostAR')        IS NOT NULL DROP TABLE claims.PostAR;
   IF OBJECT_ID(N'claims.Approval')      IS NOT NULL DROP TABLE claims.Approval;
   IF OBJECT_ID(N'claims.CaseEvent')     IS NOT NULL DROP TABLE claims.CaseEvent;
   IF OBJECT_ID(N'claims.Case')          IS NOT NULL DROP TABLE claims.[Case];
   IF OBJECT_ID(N'claims.PayerRegister') IS NOT NULL DROP TABLE claims.PayerRegister;
   IF OBJECT_ID(N'claims.BlockReason')   IS NOT NULL DROP TABLE claims.BlockReason;
   IF OBJECT_ID(N'claims.FlowType')      IS NOT NULL DROP TABLE claims.FlowType;
   IF EXISTS (SELECT 1 FROM sys.schemas WHERE name=N'claims') DROP SCHEMA [claims];
   GO
   ===================================================================================== */
