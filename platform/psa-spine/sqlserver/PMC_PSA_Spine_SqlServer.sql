/*==============================================================================
  PMC / Dada IT -- PSA spine, SQL Server schema
  Target: DND-SQL01\PMC_SS, database PMC_SS, schema [psa]

  GENERATED FILE -- DO NOT EDIT.
      source:     platform/psa-spine/schema/*.sql   (SQLite, the one source)
      translator: platform/psa-spine/tools/sqlite_to_tsql.py
      decisions:  platform/psa-spine/tools/tsql-decisions.json
      regenerate: python3 tools/sqlite_to_tsql.py --write
      drift gate: python3 tools/sqlite_to_tsql.py --check   (CI runs this)

  An edit made here is lost on the next regeneration and, worse, is invisible in
  the SQLite copy that the importer and the reports actually run against. Change
  schema/*.sql and regenerate.

  ---------------------------------------------------------------------------
  HOW TO RUN IT

      sqlcmd -S "DND-SQL01\PMC_SS" -d PMC_SS -i PMC_PSA_Spine_SqlServer.sql

  IT PREVIEWS BY DEFAULT. @Apply is 0 below and nothing is created until you set
  it to 1. That is the discipline this programme uses for anything that touches a
  live database.

      @Apply         0 = print the plan and change nothing. 1 = create.
      @AllowExisting 0 = refuse if anything already exists in [psa] (the default:
                     this script is not meant to run twice). 1 = create only what
                     is missing, which makes a re-run idempotent.

  The whole apply runs in one transaction with a verify gate at the end: if the
  object counts do not match what this script intended to create, it rolls the
  transaction back and throws. A partial schema is worse than none.

  ROLLBACK is at the foot of this file, commented out, in dependency order.

  ---------------------------------------------------------------------------
  WHAT THIS SCRIPT IS NOT

  It creates structure only. It seeds no data, no fee amount, no board owner and
  no signed clinical floor -- those are decisions with names attached and the
  schema refuses to hold them until somebody with the authority makes them.

  NOT VERIFIED: this script has never been executed. It was generated in an
  environment with no network route to DND-SQL01\PMC_SS. Run it with @Apply = 0
  first and read the plan.
==============================================================================*/

SET NOCOUNT ON;

-- XACT_ABORT means a failure anywhere in the apply below takes the whole
-- transaction with it rather than leaving half a schema behind.
SET XACT_ABORT ON;

DECLARE @Apply         BIT = 0;      -- <<<< set to 1 to make changes
DECLARE @AllowExisting BIT = 0;      -- <<<< set to 1 to fill in what is missing

DECLARE @Schema        SYSNAME = N'psa';
DECLARE @DbName        SYSNAME = DB_NAME();   -- RAISERROR takes variables, not calls
DECLARE @Existing      INT;
DECLARE @Tables        INT;
DECLARE @Triggers      INT;
DECLARE @Indexes       INT;

/*------------------------------------------------------------------ preflight */

IF @DbName <> N'PMC_SS'
BEGIN
    RAISERROR(N'Refusing: connected to database [%s], expected [PMC_SS] on DND-SQL01\PMC_SS. Nothing was changed.',
              16, 1, @DbName);
    RETURN;
END;

SELECT @Existing = COUNT(*)
  FROM sys.objects o
  JOIN sys.schemas s ON s.schema_id = o.schema_id
 WHERE s.name = @Schema AND o.type IN ('U', 'TR');

IF @Existing > 0 AND @AllowExisting = 0
BEGIN
    RAISERROR(N'Refusing: schema [%s] already holds %d objects. This script is not meant to run twice. Set @AllowExisting = 1 to create only what is missing.',
              16, 1, @Schema, @Existing);
    RETURN;
END;

/*-------------------------------------------------------------------- preview */

IF @Apply = 0
BEGIN
    PRINT N'PREVIEW ONLY. Nothing has been changed.';
    PRINT N'';
    PRINT N'Would create schema [psa] and the following, in this order:';
    PRINT N'    psa.entity';
    PRINT N'    psa.site';
    PRINT N'    psa.instrument';
    PRINT N'    psa.scope_item';
    PRINT N'    psa.instrument_scope_item';
    PRINT N'    psa.fee_line';
    PRINT N'    psa.variation';
    PRINT N'    psa.variation_event';
    PRINT N'    psa.notice';
    PRINT N'    psa.client_dependency';
    PRINT N'    psa.reclassification';
    PRINT N'    psa.decision_note';
    PRINT N'    psa.work_item';
    PRINT N'    psa.work_item_scope_item';
    PRINT N'    psa.work_item_note';
    PRINT N'    psa.work_item_evidence';
    PRINT N'    psa.time_entry';
    PRINT N'    psa.capacity_declaration';
    PRINT N'    psa.document';
    PRINT N'    psa.data_quality';
    PRINT N'    psa.audit_event';
    PRINT N'    psa.import_run';
    PRINT N'    psa.board';
    PRINT N'    psa.service_family';
    PRINT N'    psa.service_component';
    PRINT N'    psa.service_action';
    PRINT N'    psa.catalogue_item';
    PRINT N'    psa.clinical_floor';
    PRINT N'    psa.sla_target';
    PRINT N'    psa.ticket';
    PRINT N'    psa.ticket_event';
    PRINT N'    psa.ticket_handover';
    PRINT N'    psa.priority_override';
    PRINT N'    psa.board_status';
    PRINT N'    psa.board_role';
    PRINT N'    psa.board_team';
    PRINT N'    psa.board_member';
    PRINT N'    psa.holiday_list';
    PRINT N'    psa.holiday';
    PRINT N'    psa.calendar';
    PRINT N'    psa.ticket_clock';
    PRINT N'    psa.ticket_clock_pause';
    PRINT N'    psa.workflow';
    PRINT N'    psa.workflow_event';
    PRINT N'    psa.workflow_trigger';
    PRINT N'    psa.workflow_condition';
    PRINT N'    psa.workflow_action';
    PRINT N'    psa.workflow_run';
    PRINT N'    psa.oncall_slot';
    PRINT N'    psa.loop_reply';
    PRINT N'    psa.ticket_numbering';
    PRINT N'    psa.ticket_number';
    PRINT N'    psa.intake_message';
    PRINT N'    psa.ix_fee_line_effective';
    PRINT N'    psa.ix_time_entry_period';
    PRINT N'    psa.ix_workflow_run_event';
    PRINT N'    psa.ix_oncall_active';
    PRINT N'    psa.ix_intake_thread';
    PRINT N'    psa.ix_intake_ticket';
    PRINT N'    psa.time_entry_requires_a_variation';
    PRINT N'    psa.ticket_close_requires_a_variation';
    PRINT N'    psa.patient_reference_needs_a_restricted_board';
    PRINT N'    psa.patient_reference_stays_on_a_restricted_board';
    PRINT N'';
    PRINT N'  53 tables, 6 indexes, 4 triggers.';
    PRINT N'  Existing objects in [psa] right now: ' + CAST(@Existing AS NVARCHAR(10)) + N'.';
    PRINT N'';
    PRINT N'Re-run with @Apply = 1 to create them.';
    RETURN;
END;

/*---------------------------------------------------------------------- apply */
--
-- CREATE SCHEMA and CREATE TRIGGER must each be the first statement in their
-- batch, so those two go through sp_executesql. That keeps the whole file one
-- batch, which is what lets @Apply and the verify gate at the foot still be in
-- scope down there. Tables and indexes carry no such rule and are written plainly.

BEGIN TRANSACTION;

IF SCHEMA_ID(@Schema) IS NULL
    EXEC sp_executesql N'CREATE SCHEMA psa';


-- --------------------------------------------------------------------------
-- entity   (from schema/001_core.sql)
-- ---------------------------------------------------------------- entities
IF OBJECT_ID(N'psa.[entity]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[entity] (
    -- 'PMC', 'JRBY-CI', 'DADA-IT', 'UNCLASSIFIED'
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_entity] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,

    -- covered by an executed instrument?
    [is_covered] INT NOT NULL CONSTRAINT [DF_entity_is_covered] DEFAULT (0) CONSTRAINT [CK_entity_01] CHECK (is_covered IN (0, 1)),
    [note] NVARCHAR(MAX) NULL
);
END;

-- --------------------------------------------------------------------------
-- site   (from schema/001_core.sql)
IF OBJECT_ID(N'psa.[site]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[site] (
    -- 'PH01', 'PH02', 'REMOTE-MEL'
    [site_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_site] PRIMARY KEY,
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_site_entity_id] REFERENCES psa.[entity]([entity_id]),
    [name] NVARCHAR(400) NOT NULL
);
END;

-- --------------------------------------------------------------------------
-- instrument   (from schema/001_core.sql)
-- ---------------------------------------------------- agreement instruments
--
-- Three instruments are in circulation with three different clause-numbering
-- schemes, so a bare clause number is never stored against work. The clause
-- printed on a client-facing document is derived from whichever instrument was
-- in force on the work date.
IF OBJECT_ID(N'psa.[instrument]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[instrument] (
    [instrument_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_instrument] PRIMARY KEY,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_instrument_01] CHECK (kind IN ('AGREEMENT','AMENDMENT','CHANGE_ORDER','ANNEX')),
    [title] NVARCHAR(400) NOT NULL,

    -- ISO date; NULL = not yet in force
    [effective_from] NVARCHAR(32) NULL,
    [effective_to] NVARCHAR(32) NULL,

    -- The execution gate turns on this column. DRAFT and SIGNED_ONE_PARTY are not
    -- a basis for invoicing; see fee_line and variation.
    [execution_status] NVARCHAR(32) NOT NULL CONSTRAINT [CK_instrument_02] CHECK (execution_status IN ('DRAFT','ISSUED','SIGNED_ONE_PARTY','EXECUTED')),
    [signatory_pmc] NVARCHAR(200) NULL,
    [signatory_dadait] NVARCHAR(200) NULL,
    [signed_on] NVARCHAR(32) NULL,
    [prevails_over] NVARCHAR(64) NULL CONSTRAINT [FK_instrument_prevails_over] REFERENCES psa.[instrument]([instrument_id]),

    -- Payment terms are per-instrument because two values are in circulation.
    [payment_terms_days] INT NULL,
    [payment_terms_basis] NVARCHAR(32) NULL CONSTRAINT [CK_instrument_03] CHECK (payment_terms_basis IN ('CALENDAR','BUSINESS')),
    [dispute_window_days] INT NULL,

    -- SharePoint item id, never a path string
    [source_ref] NVARCHAR(400) NULL,
    [source_sha256] NVARCHAR(64) NULL,
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [effective_from_parsed] AS (CASE WHEN [effective_from] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_from], 112) WHEN [effective_from] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_from], 23) END),
    [effective_to_parsed] AS (CASE WHEN [effective_to] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_to], 112) WHEN [effective_to] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_to], 23) END),
    [signed_on_parsed] AS (CASE WHEN [signed_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [signed_on], 112) WHEN [signed_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [signed_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- scope_item   (from schema/001_core.sql)
-- The nine baseline items, plus VAR for everything outside them.
IF OBJECT_ID(N'psa.[scope_item]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[scope_item] (
    -- '1'..'9', 'VAR'
    [scope_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_scope_item] PRIMARY KEY,
    [heading] NVARCHAR(400) NOT NULL,
    [is_baseline] INT NOT NULL CONSTRAINT [CK_scope_item_01] CHECK (is_baseline IN (0, 1))
);
END;

-- --------------------------------------------------------------------------
-- instrument_scope_item   (from schema/001_core.sql)
-- The same scope item is cited differently in each instrument.
IF OBJECT_ID(N'psa.[instrument_scope_item]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[instrument_scope_item] (
    [instrument_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_instrument_scope_item_instrument_id] REFERENCES psa.[instrument]([instrument_id]),
    [scope_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_instrument_scope_item_scope_item_id] REFERENCES psa.[scope_item]([scope_item_id]),

    -- e.g. 'Section 2 item 3', 'cl.2.3'
    [clause_ref] NVARCHAR(400) NULL,
    CONSTRAINT [PK_instrument_scope_item] PRIMARY KEY ([instrument_id], [scope_item_id])
);
END;

-- --------------------------------------------------------------------------
-- fee_line   (from schema/001_core.sql)
-- ------------------------------------------------------------- fee schedule
--
-- Effective-dated so a retrospective, pro-rated adjustment is an insert with a
-- recalculation trail, not an edit. Amounts are NOT seeded in this repository —
-- they are commercial figures and load from a data file held outside git.
IF OBJECT_ID(N'psa.[fee_line]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[fee_line] (
    [fee_line_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_fee_line] PRIMARY KEY,
    [instrument_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_fee_line_instrument_id] REFERENCES psa.[instrument]([instrument_id]),
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_fee_line_entity_id] REFERENCES psa.[entity]([entity_id]),
    [description] NVARCHAR(400) NOT NULL,
    [amount] DECIMAL(19,4) NOT NULL,
    [currency] NVARCHAR(32) NOT NULL,
    [period] NVARCHAR(32) NOT NULL CONSTRAINT [CK_fee_line_01] CHECK (period IN ('MONTHLY','ONE_OFF','ANNUAL')),
    [effective_from] NVARCHAR(32) NOT NULL,
    [effective_to] NVARCHAR(32) NULL,
    [basis] NVARCHAR(32) NOT NULL CONSTRAINT [CK_fee_line_02] CHECK (basis IN ('BASELINE_FEE','CAPACITY_UPLIFT','SEPARATE_CHARGE','PASS_THROUGH')),

    -- set iff basis <> 'BASELINE_FEE'
    [variation_id] NVARCHAR(64) NULL,
    [recalc_of] INT NULL CONSTRAINT [FK_fee_line_recalc_of] REFERENCES psa.[fee_line]([fee_line_id]),
    [entered_on] NVARCHAR(32) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [effective_from_parsed] AS (CASE WHEN [effective_from] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_from], 112) WHEN [effective_from] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_from], 23) END),
    [effective_to_parsed] AS (CASE WHEN [effective_to] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_to], 112) WHEN [effective_to] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_to], 23) END),
    [entered_on_parsed] AS (CASE WHEN [entered_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [entered_on], 112) WHEN [entered_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [entered_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- variation   (from schema/002_commercial.sql)
-- --------------------------------------------------------------- variations
--
-- A variation is a state machine, not a boolean. PERFORMED_WITHOUT_APPROVAL is
-- the commercially load-bearing state: work done on best efforts without waiver
-- of the right to additional fees. Off-the-shelf PSAs cannot express it, which
-- is why unbilled variation work currently disappears.
IF OBJECT_ID(N'psa.[variation]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[variation] (
    -- 'VAR-0001'
    [variation_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_variation] PRIMARY KEY,
    [title] NVARCHAR(400) NOT NULL,
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_variation_entity_id] REFERENCES psa.[entity]([entity_id]),

    -- an Annex B category
    [category] NVARCHAR(400) NOT NULL,
    [state] NVARCHAR(32) NOT NULL CONSTRAINT [CK_variation_01] CHECK (state IN ( 'IDENTIFIED','RECORDED_IN_ANNEX_B','NOTICED','PRICED','APPROVED','BILLED', 'DECLINED','PAUSED_PENDING_AUTHORISATION','PERFORMED_WITHOUT_APPROVAL')),
    [pricing_method] NVARCHAR(32) NULL CONSTRAINT [CK_variation_02] CHECK (pricing_method IN ('CAPACITY_UPLIFT','SEPARATE_CHARGE','PASS_THROUGH','DELIVERY_REBASELINE')),

    -- sustained_from is distinct from approved_on so a retrospective pro-rated
    -- adjustment can be evidenced from the date the load actually started.
    [sustained_from] NVARCHAR(32) NULL,
    [approved_on] NVARCHAR(32) NULL,

    -- effort-as-capacity %, the uplift numerator basis
    [eac_percent] DECIMAL(9,4) NULL,
    [instrument_id] NVARCHAR(64) NULL CONSTRAINT [FK_variation_instrument_id] REFERENCES psa.[instrument]([instrument_id]),
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [sustained_from_parsed] AS (CASE WHEN [sustained_from] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [sustained_from], 112) WHEN [sustained_from] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [sustained_from], 23) END),
    [approved_on_parsed] AS (CASE WHEN [approved_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [approved_on], 112) WHEN [approved_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [approved_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- variation_event   (from schema/002_commercial.sql)
-- Append-only. A variation's history is evidence; it is never edited in place.
IF OBJECT_ID(N'psa.[variation_event]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[variation_event] (
    [event_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_variation_event] PRIMARY KEY,
    [variation_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_variation_event_variation_id] REFERENCES psa.[variation]([variation_id]),
    [from_state] NVARCHAR(32) NULL,
    [to_state] NVARCHAR(32) NOT NULL,
    [occurred_on] NVARCHAR(32) NOT NULL,
    [actor] NVARCHAR(200) NULL,
    [reason] NVARCHAR(MAX) NULL,
    [evidence_ref] NVARCHAR(400) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [occurred_on_parsed] AS (CASE WHEN [occurred_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [occurred_on], 112) WHEN [occurred_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [occurred_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- notice   (from schema/002_commercial.sql)
-- ------------------------------------------------------------------ notices
--
-- Every commercially useful right in the agreement — pause, suspend, reclassify,
-- dependency relief, cure, exit — is conditioned on WRITTEN NOTICE. Eleven
-- workstreams are blocked on the client today and not one notice is recorded
-- against any of them. This table is worth more than the ticketing module.
IF OBJECT_ID(N'psa.[notice]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[notice] (
    -- 'NOT-0001'
    [notice_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_notice] PRIMARY KEY,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_notice_01] CHECK (kind IN ('DEPENDENCY','VARIATION','RECLASSIFICATION','PAUSE','CURE','EXIT','EXCEPTION')),
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_notice_entity_id] REFERENCES psa.[entity]([entity_id]),
    [issued_on] NVARCHAR(32) NOT NULL,
    [issued_to] NVARCHAR(200) NOT NULL,
    [subject] NVARCHAR(400) NOT NULL,

    -- SharePoint item id of the sent letter
    [body_ref] NVARCHAR(400) NULL,
    [instrument_id] NVARCHAR(64) NULL CONSTRAINT [FK_notice_instrument_id] REFERENCES psa.[instrument]([instrument_id]),
    [delivery_channel] NVARCHAR(400) NULL,
    [receipt_evidence] NVARCHAR(400) NULL,
    [variation_id] NVARCHAR(64) NULL CONSTRAINT [FK_notice_variation_id] REFERENCES psa.[variation]([variation_id]),
    [work_item_id] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [issued_on_parsed] AS (CASE WHEN [issued_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [issued_on], 112) WHEN [issued_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [issued_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- client_dependency   (from schema/002_commercial.sql)
-- ------------------------------------------------------- client dependencies
--
-- A blocked workstream is only a commercial event once notice has been given.
-- days_outstanding is derived at report time, never stored.
IF OBJECT_ID(N'psa.[client_dependency]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[client_dependency] (
    -- 'DEP-0001'
    [dependency_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_client_dependency] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL,
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_client_dependency_entity_id] REFERENCES psa.[entity]([entity_id]),
    [raised_on] NVARCHAR(32) NOT NULL,

    -- the party who owes the answer
    [owner_name] NVARCHAR(200) NULL,
    [owner_department] NVARCHAR(400) NULL,
    [description] NVARCHAR(MAX) NOT NULL,
    [scope_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_client_dependency_scope_item_id] REFERENCES psa.[scope_item]([scope_item_id]),
    [impact] NVARCHAR(32) NULL CONSTRAINT [CK_client_dependency_01] CHECK (impact IN ('TIMELINE','PRICING','BOTH')),

    -- NULL = relief not yet claimable
    [notice_id] NVARCHAR(64) NULL CONSTRAINT [FK_client_dependency_notice_id] REFERENCES psa.[notice]([notice_id]),
    [resolved_on] NVARCHAR(32) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [raised_on_parsed] AS (CASE WHEN [raised_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [raised_on], 112) WHEN [raised_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [raised_on], 23) END),
    [resolved_on_parsed] AS (CASE WHEN [resolved_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [resolved_on], 112) WHEN [resolved_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [resolved_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- reclassification   (from schema/002_commercial.sql)
-- --------------------------------------------------------- reclassification
--
-- Basis changes are events, not edits, because the right to reclassify is
-- itself reserved in the agreement and has to be evidenced when exercised.
IF OBJECT_ID(N'psa.[reclassification]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[reclassification] (
    [reclass_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_reclassification] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL,
    [old_basis] NVARCHAR(32) NOT NULL,
    [new_basis] NVARCHAR(32) NOT NULL,
    [changed_on] NVARCHAR(32) NOT NULL,
    [changed_by] NVARCHAR(200) NOT NULL,
    [reason] NVARCHAR(MAX) NOT NULL,
    [instrument_id] NVARCHAR(64) NULL CONSTRAINT [FK_reclassification_instrument_id] REFERENCES psa.[instrument]([instrument_id]),
    [notice_id] NVARCHAR(64) NULL CONSTRAINT [FK_reclassification_notice_id] REFERENCES psa.[notice]([notice_id]),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [changed_on_parsed] AS (CASE WHEN [changed_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [changed_on], 112) WHEN [changed_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [changed_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- decision_note   (from schema/002_commercial.sql)
-- ----------------------------------------------------------- decision notes
--
-- The liability position depends on risk having been communicated in writing
-- BEFORE management decided. The constraint enforces the ordering, because a
-- decision note written afterwards is worth nothing.
IF OBJECT_ID(N'psa.[decision_note]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[decision_note] (
    [note_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_decision_note] PRIMARY KEY,
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_decision_note_entity_id] REFERENCES psa.[entity]([entity_id]),
    [subject] NVARCHAR(400) NOT NULL,
    [advisory_at] NVARCHAR(64) NOT NULL,
    [decision_at] NVARCHAR(64) NULL,
    [advised_by] NVARCHAR(200) NOT NULL,
    [decided_by] NVARCHAR(200) NULL,
    [outcome] NVARCHAR(MAX) NULL,
    [evidence_ref] NVARCHAR(400) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [advisory_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [advisory_at], 126), CASE WHEN [advisory_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [advisory_at], 112) END)),
    [decision_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [decision_at], 126), CASE WHEN [decision_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [decision_at], 112) END)),
    CONSTRAINT [CK_decision_note_01] CHECK (decision_at IS NULL OR advisory_at <= decision_at)
);
END;

-- --------------------------------------------------------------------------
-- work_item   (from schema/003_delivery.sql)
-- --------------------------------------------------------------- work items
--
-- One row per workstream today (the register), one row per ticket later. The
-- desk owns the ticket; the spine owns the money. contract_basis is set on the
-- work item and inherited by effort, never typed per time entry.
IF OBJECT_ID(N'psa.[work_item]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[work_item] (
    -- 'WS23', later 'ITO-1723'
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_work_item] PRIMARY KEY,

    -- 'register' | 'desk' | 'manual'
    [source] NVARCHAR(32) NOT NULL,
    [name] NVARCHAR(400) NOT NULL,
    [entity_id] NVARCHAR(64) NULL CONSTRAINT [FK_work_item_entity_id] REFERENCES psa.[entity]([entity_id]),

    -- the source string, kept verbatim
    [entity_raw] NVARCHAR(400) NULL,
    [contract_basis] NVARCHAR(32) NOT NULL CONSTRAINT [CK_work_item_01] CHECK (contract_basis IN ('BASELINE','VARIATION','UNKNOWN')),

    -- e.g. 'variation (Amendment 1)', '?'
    [contract_basis_raw] NVARCHAR(400) NULL,
    [variation_id] NVARCHAR(64) NULL CONSTRAINT [FK_work_item_variation_id] REFERENCES psa.[variation]([variation_id]),
    [status] NVARCHAR(32) NULL,
    [status_raw] NVARCHAR(400) NULL,
    [blocked_on] NVARCHAR(MAX) NULL,
    [next_action] NVARCHAR(MAX) NULL,
    [next_action_by] NVARCHAR(200) NULL,
    [risk] NVARCHAR(32) NULL CONSTRAINT [CK_work_item_02] CHECK (risk IN ('L','M','H') OR risk IS NULL),
    [container] NVARCHAR(400) NULL,
    [last_activity] NVARCHAR(32) NULL,
    [parent_id] NVARCHAR(64) NULL CONSTRAINT [FK_work_item_parent_id] REFERENCES psa.[work_item]([work_item_id]),

    -- Lane is derived from status + blocked_on + next_action_by, because the
    -- programme is run by who has to act next, not by queue or priority.
    [lane] NVARCHAR(32) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [last_activity_parsed] AS (CASE WHEN [last_activity] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [last_activity], 112) WHEN [last_activity] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [last_activity], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- work_item_scope_item   (from schema/003_delivery.sql)
-- Many-to-many: the register carries compound scope values ('2->8', '3+5',
-- '1/2', '4/8'). Each becomes two links. A row is never dropped for being
-- compound, and never silently reduced to its first element.
IF OBJECT_ID(N'psa.[work_item_scope_item]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[work_item_scope_item] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_work_item_scope_item_work_item_id] REFERENCES psa.[work_item]([work_item_id]),
    [scope_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_work_item_scope_item_scope_item_id] REFERENCES psa.[scope_item]([scope_item_id]),
    [relation] NVARCHAR(32) NOT NULL CONSTRAINT [DF_work_item_scope_item_relation] DEFAULT ('PRIMARY') CONSTRAINT [CK_work_item_scope_item_01] CHECK (relation IN ('PRIMARY','SECONDARY','SUCCEEDS','ALTERNATIVE')),

    -- the original cell, for audit
    [raw] NVARCHAR(400) NULL,
    CONSTRAINT [PK_work_item_scope_item] PRIMARY KEY ([work_item_id], [scope_item_id], [relation])
);
END;

-- --------------------------------------------------------------------------
-- work_item_note   (from schema/003_delivery.sql)
-- Append-only running record. The register's free-text next_action field is
-- thousands of characters of history in one cell; imported notes preserve it.
IF OBJECT_ID(N'psa.[work_item_note]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[work_item_note] (
    [note_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_work_item_note] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_work_item_note_work_item_id] REFERENCES psa.[work_item]([work_item_id]),
    [noted_on] NVARCHAR(64) NOT NULL,
    [author] NVARCHAR(200) NULL,
    [body] NVARCHAR(MAX) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [noted_on_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [noted_on], 126), CASE WHEN [noted_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [noted_on], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- work_item_evidence   (from schema/003_delivery.sql)
IF OBJECT_ID(N'psa.[work_item_evidence]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[work_item_evidence] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_work_item_evidence_work_item_id] REFERENCES psa.[work_item]([work_item_id]),
    [ordinal] INT NOT NULL,

    -- verbatim from the register
    [raw] NVARCHAR(400) NOT NULL,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_work_item_evidence_01] CHECK (kind IN ('DOC','SCRIPT','DELIVERABLE','PATH','UNRESOLVED')),

    -- SharePoint item id once resolved
    [resolved_ref] NVARCHAR(400) NULL,
    CONSTRAINT [PK_work_item_evidence] PRIMARY KEY ([work_item_id], [ordinal])
);
END;

-- --------------------------------------------------------------------------
-- time_entry   (from schema/003_delivery.sql)
-- -------------------------------------------------------------------- effort
--
-- Banded, not stopwatch. Baseline hours are never invoiced but are the
-- DENOMINATOR of any capacity uplift — without them every uplift is an
-- assertion. Only hours performed by Dada IT personnel count toward capacity;
-- client-employed fulfiller effort is recorded and excluded.
IF OBJECT_ID(N'psa.[time_entry]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[time_entry] (
    [time_entry_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_time_entry] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_time_entry_work_item_id] REFERENCES psa.[work_item]([work_item_id]),
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_time_entry_entity_id] REFERENCES psa.[entity]([entity_id]),
    [site_id] NVARCHAR(64) NULL CONSTRAINT [FK_time_entry_site_id] REFERENCES psa.[site]([site_id]),
    [worked_on] NVARCHAR(32) NOT NULL,

    -- 0.5 | 2 | 4 | 8 | 20
    [band_hours] DECIMAL(9,2) NOT NULL,
    [performed_by] NVARCHAR(200) NOT NULL,
    [entered_by] NVARCHAR(200) NOT NULL,
    [counts_to_capacity] INT NOT NULL CONSTRAINT [DF_time_entry_counts_to_capacity] DEFAULT (1) CONSTRAINT [CK_time_entry_01] CHECK (counts_to_capacity IN (0, 1)),
    [after_hours] INT NOT NULL CONSTRAINT [DF_time_entry_after_hours] DEFAULT (0) CONSTRAINT [CK_time_entry_02] CHECK (after_hours IN (0, 1)),
    [charge_method] NVARCHAR(32) NOT NULL CONSTRAINT [CK_time_entry_03] CHECK (charge_method IN ('INCLUDED_IN_MONTHLY_FEE','CAPACITY_UPLIFT','SEPARATE_CHARGE', 'PASS_THROUGH','NON_CHARGEABLE')),

    -- one of the six-monthly review categories
    [review_category] NVARCHAR(400) NULL,

    -- who asked for it, and how
    [authority_source] NVARCHAR(MAX) NULL,
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [worked_on_parsed] AS (CASE WHEN [worked_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [worked_on], 112) WHEN [worked_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [worked_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- capacity_declaration   (from schema/003_delivery.sql)
-- The declared capacity a uplift percentage is computed against. Stored, dated
-- and offered for the client to initial — an undisclosed denominator is the
-- single easiest way for a finance function to reject an uplift invoice.
IF OBJECT_ID(N'psa.[capacity_declaration]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[capacity_declaration] (
    [declaration_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_capacity_declaration] PRIMARY KEY,
    [effective_from] NVARCHAR(32) NOT NULL,
    [effective_to] NVARCHAR(32) NULL,
    [hours_per_month] DECIMAL(9,2) NOT NULL,
    [basis] NVARCHAR(MAX) NOT NULL,
    [agreed_by] NVARCHAR(200) NULL,
    [agreed_on] NVARCHAR(32) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [effective_from_parsed] AS (CASE WHEN [effective_from] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_from], 112) WHEN [effective_from] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_from], 23) END),
    [effective_to_parsed] AS (CASE WHEN [effective_to] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_to], 112) WHEN [effective_to] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [effective_to], 23) END),
    [agreed_on_parsed] AS (CASE WHEN [agreed_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [agreed_on], 112) WHEN [agreed_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [agreed_on], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- document   (from schema/003_delivery.sql)
-- ---------------------------------------------------------------- documents
IF OBJECT_ID(N'psa.[document]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[document] (
    [document_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_document] PRIMARY KEY,
    [title] NVARCHAR(400) NOT NULL,
    [kind] NVARCHAR(32) NOT NULL,
    [entity_id] NVARCHAR(64) NULL CONSTRAINT [FK_document_entity_id] REFERENCES psa.[entity]([entity_id]),
    [dated] NVARCHAR(32) NULL,

    -- SharePoint item id, never a path
    [source_ref] NVARCHAR(400) NULL,
    [sha256] NVARCHAR(64) NULL,
    [state] NVARCHAR(32) NOT NULL CONSTRAINT [DF_document_state] DEFAULT ('CURRENT') CONSTRAINT [CK_document_01] CHECK (state IN ('DRAFT','CURRENT','SUPERSEDED','WITHDRAWN')),
    [supersedes] NVARCHAR(64) NULL CONSTRAINT [FK_document_supersedes] REFERENCES psa.[document]([document_id]),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [dated_parsed] AS (CASE WHEN [dated] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [dated], 112) WHEN [dated] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [dated], 23) END)
);
END;

-- --------------------------------------------------------------------------
-- data_quality   (from schema/003_delivery.sql)
-- ------------------------------------------------------------- data quality
--
-- The standing rule in this programme is that flags are COUNTED, never filtered
-- out. Anything an import could not classify lands here and appears on every
-- report as a number. Nothing is ever silently dropped.
IF OBJECT_ID(N'psa.[data_quality]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[data_quality] (
    [finding_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_data_quality] PRIMARY KEY,
    [run_id] NVARCHAR(64) NOT NULL,

    -- 'work_item', 'evidence', 'scope_item'
    [subject_kind] NVARCHAR(32) NOT NULL,
    [subject_id] NVARCHAR(64) NULL,
    [code] NVARCHAR(32) NOT NULL,
    [detail] NVARCHAR(MAX) NOT NULL,
    [severity] NVARCHAR(32) NOT NULL CONSTRAINT [CK_data_quality_01] CHECK (severity IN ('INFO','WARN','ERROR'))
);
END;

-- --------------------------------------------------------------------------
-- audit_event   (from schema/003_delivery.sql)
-- -------------------------------------------------------------------- audit
IF OBJECT_ID(N'psa.[audit_event]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[audit_event] (
    [audit_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_audit_event] PRIMARY KEY,
    [occurred_at] NVARCHAR(64) NOT NULL,
    [actor] NVARCHAR(200) NOT NULL,
    [action] NVARCHAR(32) NOT NULL,
    [subject_kind] NVARCHAR(32) NOT NULL,
    [subject_id] NVARCHAR(64) NULL,
    [detail] NVARCHAR(MAX) NULL,

    -- set when an execution gate was overridden
    [override_reason] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [occurred_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [occurred_at], 126), CASE WHEN [occurred_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [occurred_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- import_run   (from schema/003_delivery.sql)
IF OBJECT_ID(N'psa.[import_run]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[import_run] (
    [run_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_import_run] PRIMARY KEY,
    [started_at] NVARCHAR(64) NOT NULL,
    [source] NVARCHAR(400) NOT NULL,
    [source_sha256] NVARCHAR(64) NULL,
    [rows_in] INT NULL,
    [rows_out] INT NULL,
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [started_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [started_at], 126), CASE WHEN [started_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [started_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- board   (from schema/004_catalogue.sql)
-- ------------------------------------------------------------------- boards
--
-- One accountable fulfiller group, one named owner, one named deputy, its own
-- SLA. A board with no owner is worse than no board -- so a board may be
-- RECORDED without one, and may not be LIVE without one. That is the rule as a
-- constraint rather than as a paragraph somebody has to remember.
IF OBJECT_ID(N'psa.[board]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board] (
    -- 'IT_HELP'
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_board] PRIMARY KEY,
    [display_name] NVARCHAR(400) NOT NULL,
    [phase] NVARCHAR(32) NOT NULL CONSTRAINT [CK_board_01] CHECK (phase IN ('2','3a','3b')),
    [fulfiller_group] NVARCHAR(400) NOT NULL,

    -- a named person, not a role
    [owner] NVARCHAR(200) NULL,
    [deputy] NVARCHAR(200) NULL,
    [restricted] INT NOT NULL CONSTRAINT [DF_board_restricted] DEFAULT (0) CONSTRAINT [CK_board_02] CHECK (restricted IN (0, 1)),
    [is_live] INT NOT NULL CONSTRAINT [DF_board_is_live] DEFAULT (0) CONSTRAINT [CK_board_03] CHECK (is_live IN (0, 1)),
    [is_unrouted] INT NOT NULL CONSTRAINT [DF_board_is_unrouted] DEFAULT (0) CONSTRAINT [CK_board_04] CHECK (is_unrouted IN (0, 1)),

    -- Closing a ticket on this board goes through the closed loop: the answer to
    -- the requester and the banding of the effort are one action, so the effort is
    -- captured by construction and not by a fulfiller remembering to. Off by
    -- default; a board turns it on when it is ready to be measured that way.
    [closed_loop_required] INT NOT NULL CONSTRAINT [DF_board_closed_loop_required] DEFAULT (0) CONSTRAINT [CK_board_05] CHECK (closed_loop_required IN (0, 1)),
    [note] NVARCHAR(MAX) NULL,
    CONSTRAINT [CK_board_06] CHECK (is_live = 0 OR (owner IS NOT NULL AND deputy IS NOT NULL))
);
END;

-- --------------------------------------------------------------------------
-- service_family   (from schema/004_catalogue.sql)
-- --------------------------------------------------------------- the tree
--
-- family -> component, and a verb set that belongs to no board.
IF OBJECT_ID(N'psa.[service_family]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[service_family] (
    -- 'SERVERS_STORAGE'
    [family_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_service_family] PRIMARY KEY,
    [display_name] NVARCHAR(400) NOT NULL,

    -- as the source workbook spelt it
    [raw_name] NVARCHAR(400) NULL,
    [note] NVARCHAR(MAX) NULL
);
END;

-- --------------------------------------------------------------------------
-- service_component   (from schema/004_catalogue.sql)
IF OBJECT_ID(N'psa.[service_component]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[service_component] (
    [component_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_service_component] PRIMARY KEY,
    [family_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_service_component_family_id] REFERENCES psa.[service_family]([family_id]),
    [display_name] NVARCHAR(400) NOT NULL,
    [raw_name] NVARCHAR(400) NULL,
    [is_draft] INT NOT NULL CONSTRAINT [DF_service_component_is_draft] DEFAULT (0) CONSTRAINT [CK_service_component_01] CHECK (is_draft IN (0, 1)),
    [note] NVARCHAR(MAX) NULL
);
END;

-- --------------------------------------------------------------------------
-- service_action   (from schema/004_catalogue.sql)
-- The verbs. The workbook's Item column is a hand-written cross-join of these
-- against ~100 components with drifting case; they are normalised once, here.
--
-- The recommendation says "six canonical verbs" while its own rulings enumerate
-- seven. The seed carries the seven that are enumerated and the discrepancy is
-- recorded rather than resolved by picking one quietly.
--
-- The load-bearing definition, kept verbatim from the workbook's margin:
--   outage  = a shared service or a clinical service is down   (impact I1)
--   failure = one device or one user                           (impact I3)
IF OBJECT_ID(N'psa.[service_action]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[service_action] (
    -- 'OUTAGE'
    [action_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_service_action] PRIMARY KEY,
    [display_name] NVARCHAR(400) NOT NULL,

    -- as the source workbook spelt it
    [raw_name] NVARCHAR(400) NULL,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_service_action_01] CHECK (kind IN ('REQUEST', 'FAULT')),
    [implies_impact] NVARCHAR(32) NULL CONSTRAINT [CK_service_action_02] CHECK (implies_impact IN ('I1', 'I2', 'I3') OR implies_impact IS NULL),
    [note] NVARCHAR(MAX) NULL
);
END;

-- --------------------------------------------------------------------------
-- catalogue_item   (from schema/004_catalogue.sql)
-- ----------------------------------------------------------- curated triples
--
-- Defaulting the scope item and the contract basis from the catalogue is what
-- lets a nurse file a ticket without ever seeing a commercial field. Which is
-- also why an item that claims to be baseline must name the baseline item it
-- sits in: "baseline, but we cannot say under which heading" is not a defence.
IF OBJECT_ID(N'psa.[catalogue_item]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[catalogue_item] (
    [catalogue_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_catalogue_item] PRIMARY KEY,
    [component_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_catalogue_item_component_id] REFERENCES psa.[service_component]([component_id]),
    [action_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_catalogue_item_action_id] REFERENCES psa.[service_action]([action_id]),
    [default_board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_catalogue_item_default_board_id] REFERENCES psa.[board]([board_id]),
    [default_scope_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_catalogue_item_default_scope_item_id] REFERENCES psa.[scope_item]([scope_item_id]),
    [default_contract_basis] NVARCHAR(32) NOT NULL CONSTRAINT [CK_catalogue_item_01] CHECK (default_contract_basis IN ('BASELINE', 'VARIATION', 'UNKNOWN')),
    [clinical_impact] INT NOT NULL CONSTRAINT [DF_catalogue_item_clinical_impact] DEFAULT (0) CONSTRAINT [CK_catalogue_item_02] CHECK (clinical_impact IN (0, 1)),
    [min_priority] NVARCHAR(32) NULL CONSTRAINT [CK_catalogue_item_03] CHECK (min_priority IN ('P1','P2','P3','P4') OR min_priority IS NULL),
    [restricted] INT NOT NULL CONSTRAINT [DF_catalogue_item_restricted] DEFAULT (0) CONSTRAINT [CK_catalogue_item_04] CHECK (restricted IN (0, 1)),
    [is_draft] INT NOT NULL CONSTRAINT [DF_catalogue_item_is_draft] DEFAULT (0) CONSTRAINT [CK_catalogue_item_05] CHECK (is_draft IN (0, 1)),
    [note] NVARCHAR(MAX) NULL,
    CONSTRAINT [UQ_catalogue_item] UNIQUE ([component_id], [action_id]),
    CONSTRAINT [CK_catalogue_item_06] CHECK (default_contract_basis <> 'BASELINE' OR default_scope_item_id IS NOT NULL)
);
END;

-- --------------------------------------------------------------------------
-- clinical_floor   (from schema/004_catalogue.sql)
-- -------------------------------------------------------------- clinical floors
--
-- Priorities no fulfiller may lower, enforced at raise AND at close. This list
-- is signed off by the Chief of Hospital, the Chief Nurse and the Quality
-- officer -- not by Dada IT. So a floor that nobody has signed is PROPOSED and
-- does not bind, and the schema will not let it claim otherwise.
IF OBJECT_ID(N'psa.[clinical_floor]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[clinical_floor] (
    [floor_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_clinical_floor] PRIMARY KEY,
    [description] NVARCHAR(MAX) NOT NULL,
    [priority] NVARCHAR(32) NOT NULL CONSTRAINT [CK_clinical_floor_01] CHECK (priority IN ('P1', 'P2')),
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [CK_clinical_floor_02] CHECK (status IN ('PROPOSED', 'SIGNED_OFF', 'WITHDRAWN')),
    [signed_off_by] NVARCHAR(200) NULL,
    [signed_off_on] NVARCHAR(32) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [signed_off_on_parsed] AS (CASE WHEN [signed_off_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [signed_off_on], 112) WHEN [signed_off_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [signed_off_on], 23) END),
    CONSTRAINT [CK_clinical_floor_03] CHECK (status <> 'SIGNED_OFF' OR (signed_off_by IS NOT NULL AND signed_off_on IS NOT NULL))
);
END;

-- --------------------------------------------------------------------------
-- sla_target   (from schema/004_catalogue.sql)
-- ------------------------------------------------------------------- the SLA
--
-- Three clocks, each with its own target, its own calendar and its own
-- attainment percentage, because the workbook's three numbers are
-- incommensurable as written: "response within 1 day" is a per-ticket target,
-- "90% within 2 hours" is a population percentile, "16 hours" has no calendar.
--
-- Every target ships with enforced = 0. The agreement contains no response or
-- resolution commitment and three clauses actively disclaim creating one
-- [MEASURED]. Turning enforcement on silently creates an obligation Dada IT is
-- not paid for and a two-to-three person team cannot meet.
IF OBJECT_ID(N'psa.[sla_target]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[sla_target] (
    [sla_target_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sla_target] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_sla_target_board_id] REFERENCES psa.[board]([board_id]),
    [priority] NVARCHAR(32) NOT NULL CONSTRAINT [CK_sla_target_01] CHECK (priority IN ('P1','P2','P3','P4')),
    [clock] NVARCHAR(32) NOT NULL CONSTRAINT [CK_sla_target_02] CHECK (clock IN ('RESPOND','RESOLUTION_PLAN','RESOLVE','ACKNOWLEDGE','DECISION')),
    [target_minutes] INT NOT NULL,
    [calendar] NVARCHAR(32) NOT NULL CONSTRAINT [CK_sla_target_03] CHECK (calendar IN ('CLINICAL_24x7', 'MANILA_BUSINESS')),

    -- stated separately from the per-ticket target
    [attainment_percent] DECIMAL(5,2) NULL,
    [enforced] INT NOT NULL CONSTRAINT [DF_sla_target_enforced] DEFAULT (0) CONSTRAINT [CK_sla_target_04] CHECK (enforced IN (0, 1)),
    [note] NVARCHAR(MAX) NULL,
    CONSTRAINT [UQ_sla_target] UNIQUE ([board_id], [priority], [clock])
);
END;

-- --------------------------------------------------------------------------
-- ticket   (from schema/005_ticket.sql)
IF OBJECT_ID(N'psa.[ticket]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_ticket] PRIMARY KEY CONSTRAINT [FK_ticket_work_item_id] REFERENCES psa.[work_item]([work_item_id]),

    -- what the desk calls it, kept verbatim
    [external_ref] NVARCHAR(400) NULL,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_board_id] REFERENCES psa.[board]([board_id]),
    [catalogue_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_catalogue_item_id] REFERENCES psa.[catalogue_item]([catalogue_item_id]),

    -- Three paths, not two. The workbook's two-board line collapses in-baseline
    -- fulfilment with fee-bearing variation: its own Request list contains
    -- "Onboard new user", "New Shared Mailbox" and "Create security group", which
    -- sit squarely inside baseline items 2 and 4 [MEASURED]. Two boards make
    -- every new-user request look like a fee event, and that destroys PMC's
    -- willingness to use the request path at all.
    [path] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_01] CHECK (path IN ('INCIDENT', 'SERVICE_REQUEST', 'VARIATION')),

    -- The requester answers two plain questions -- who is affected, and is a
    -- patient waiting -- and never sees a priority dropdown.
    [impact] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_02] CHECK (impact IN ('I1', 'I2', 'I3')),
    [urgency] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_03] CHECK (urgency IN ('U1', 'U2', 'U3')),
    [priority] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_04] CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    [priority_source] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_05] CHECK (priority_source IN ('MATRIX', 'CATALOGUE_FLOOR', 'CLINICAL_IMPACT', 'CLINICAL_FLOOR', 'OVERRIDE')),
    [requested_by] NVARCHAR(200) NULL,
    [requested_at] NVARCHAR(64) NOT NULL,
    [owner] NVARCHAR(200) NULL,
    [opened_at] NVARCHAR(64) NOT NULL,
    [closed_at] NVARCHAR(64) NULL,

    -- A pause state that stops the resolve clock. Without one, eleven of the
    -- thirty-five register rows report as a breach on day one.
    [paused_minutes] INT NOT NULL CONSTRAINT [DF_ticket_paused_minutes] DEFAULT (0) CONSTRAINT [CK_ticket_06] CHECK (paused_minutes >= 0),
    [state] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_07] CHECK (state IN ('NEW','TRIAGED','IN_PROGRESS','WAITING_CLIENT','WAITING_VENDOR','RESOLVED','CLOSED','CANCELLED')),

    -- the export row this came from
    [source_ref] NVARCHAR(400) NULL,
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [requested_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [requested_at], 126), CASE WHEN [requested_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [requested_at], 112) END)),
    [opened_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [opened_at], 126), CASE WHEN [opened_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [opened_at], 112) END)),
    [closed_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [closed_at], 126), CASE WHEN [closed_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [closed_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_event   (from schema/005_ticket.sql)
-- Append-only. A ticket's history is evidence; it is never edited in place.
IF OBJECT_ID(N'psa.[ticket_event]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_event] (
    [ticket_event_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_event] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_event_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [occurred_at] NVARCHAR(64) NOT NULL,
    [kind] NVARCHAR(32) NOT NULL,
    [actor] NVARCHAR(200) NULL,
    [detail] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [occurred_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [occurred_at], 126), CASE WHEN [occurred_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [occurred_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_handover   (from schema/005_ticket.sql)
-- Cross-board handover is ONE ticket with a changing owner, never two linked
-- tickets. The MRI-to-PACS fault is simultaneously biomedical (the scanner) and
-- IT (DICOM, AE title, network); two tickets each waiting on the other is
-- exactly what produced a twenty-five day outage.
IF OBJECT_ID(N'psa.[ticket_handover]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_handover] (
    [handover_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_handover] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_handover_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [from_board_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_handover_from_board_id] REFERENCES psa.[board]([board_id]),
    [to_board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_handover_to_board_id] REFERENCES psa.[board]([board_id]),
    [handover_at] NVARCHAR(64) NOT NULL,
    [from_owner] NVARCHAR(200) NULL,
    [to_owner] NVARCHAR(200) NULL,
    [reason] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [handover_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [handover_at], 126), CASE WHEN [handover_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [handover_at], 112) END)),
    CONSTRAINT [CK_ticket_handover_01] CHECK (from_board_id IS NULL OR from_board_id <> to_board_id)
);
END;

-- --------------------------------------------------------------------------
-- priority_override   (from schema/005_ticket.sql)
-- Lowering a priority below a clinical floor takes a named clinical escalation
-- role, a typed reason, and an audit event. Not a fulfiller's judgement call.
IF OBJECT_ID(N'psa.[priority_override]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[priority_override] (
    [override_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_priority_override] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_priority_override_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [overridden_at] NVARCHAR(64) NOT NULL,
    [was_priority] NVARCHAR(32) NOT NULL,
    [now_priority] NVARCHAR(32) NOT NULL,
    [escalation_role] NVARCHAR(32) NOT NULL CONSTRAINT [CK_priority_override_01] CHECK (escalation_role IN ('NURSING_SUPERVISOR', 'DUTY_MANAGER', 'CHIEF_OF_HOSPITAL', 'QUALITY_OFFICER')),
    [reason] NVARCHAR(MAX) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [overridden_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [overridden_at], 126), CASE WHEN [overridden_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [overridden_at], 112) END)),
    CONSTRAINT [CK_priority_override_02] CHECK (LEN(LTRIM(RTRIM(reason))) >= 15)
);
END;

-- --------------------------------------------------------------------------
-- board_status   (from schema/006_board.sql)
-- ------------------------------------------------------------ board_status
--
-- A status is not a string. If "Waiting for parts" is a name, nothing in the
-- system knows a clock should stop, and every pause becomes a special case
-- somebody codes by hand.
--
-- The design drafted three booleans -- stops_respond, stops_resolve, and one
-- more for the plan. ConnectWise carries ONE field instead, and it is better:
-- the status declares WHICH SLA MILESTONE IT REPRESENTS and the clock engine
-- derives the rest. NO_ESCALATION is the pause. Taken as-is, because inventing
-- a worse version of a solved problem is not craft.
IF OBJECT_ID(N'psa.[board_status]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board_status] (
    -- 'IT_HELP.IN_PROGRESS'
    [board_status_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_board_status] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_status_board_id] REFERENCES psa.[board]([board_id]),

    -- what a fulfiller reads
    [name] NVARCHAR(400) NOT NULL,

    -- What a REQUESTER reads, which is a different sentence. Internally
    -- "Awaiting parts from vendor, PO raised"; on the portal "We are waiting on a
    -- delivery". Without this you either leak internal language to 400 clinical
    -- staff or you write statuses too vague to be useful to the people working.
    [customer_description] NVARCHAR(MAX) NULL,
    [escalation_status] NVARCHAR(32) NOT NULL CONSTRAINT [CK_board_status_01] CHECK (escalation_status IN ('NOT_RESPONDED','RESPONDED','RESOLUTION_PLAN','RESOLVED', 'NO_ESCALATION')),
    [is_default] INT NOT NULL CONSTRAINT [DF_board_status_is_default] DEFAULT (0) CONSTRAINT [CK_board_status_02] CHECK (is_default IN (0, 1)),
    [is_closed] INT NOT NULL CONSTRAINT [DF_board_status_is_closed] DEFAULT (0) CONSTRAINT [CK_board_status_03] CHECK (is_closed IN (0, 1)),

    -- A status that forbids booking effort. This is how time stops accruing
    -- against a parked ticket, and it composes with the variation gate in 005
    -- rather than duplicating it.
    [time_entry_allowed] INT NOT NULL CONSTRAINT [DF_board_status_time_entry_allowed] DEFAULT (1) CONSTRAINT [CK_board_status_04] CHECK (time_entry_allowed IN (0, 1)),
    [display_on_board] INT NOT NULL CONSTRAINT [DF_board_status_display_on_board] DEFAULT (1) CONSTRAINT [CK_board_status_05] CHECK (display_on_board IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_board_status_sort_order] DEFAULT (0),

    -- Retired, never deleted. ConnectWise refuses to delete a board once anything
    -- references it, and the same is true of a status: the tickets that sat in it
    -- are evidence.
    [inactive] INT NOT NULL CONSTRAINT [DF_board_status_inactive] DEFAULT (0) CONSTRAINT [CK_board_status_06] CHECK (inactive IN (0, 1)),
    CONSTRAINT [UQ_board_status] UNIQUE ([board_id], [name]),
    CONSTRAINT [CK_board_status_07] CHECK (is_default = 0 OR is_closed = 0)
);
END;

-- --------------------------------------------------------------------------
-- board_role   (from schema/006_board.sql)
-- ------------------------------------------------------------- board_role
--
-- Owner and deputy is too thin, and the record already shows why: triage today
-- is one person, and when she is unavailable the path is a personal chat to a
-- CIO in another country [MEASURED]. Two names cannot express "who answers at
-- 02:00, and who answers when they do not".
--
-- ConnectWise carries four per board -- dispatchMember, dutyManagerMember,
-- oncallMember, serviceManagerMember -- and documents the duty manager as
-- "backup for the on-call member ... if the on-call member does not respond to
-- the ticket within the specified time." That is the escalation chain a hospital
-- needs, and DUTY_MANAGER is already a clinical escalation role on
-- priority_override in 005, so the vocabularies converge for free.
--
-- board.owner and board.deputy stay for now: they are seeded, tested, and the
-- is_live CHECK depends on them. This table is the model going forward, and the
-- CHECK moves here when boards are created through it rather than seeded.
IF OBJECT_ID(N'psa.[board_role]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board_role] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_role_board_id] REFERENCES psa.[board]([board_id]),
    [role] NVARCHAR(32) NOT NULL CONSTRAINT [CK_board_role_01] CHECK (role IN ('SERVICE_MANAGER','DISPATCH','ON_CALL','DUTY_MANAGER')),

    -- a named person, never a role name
    [member] NVARCHAR(200) NOT NULL,
    CONSTRAINT [PK_board_role] PRIMARY KEY ([board_id], [role])
);
END;

-- --------------------------------------------------------------------------
-- board_team   (from schema/006_board.sql)
-- --------------------------------------------------------------- the teams
IF OBJECT_ID(N'psa.[board_team]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board_team] (
    [team_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_board_team] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_team_board_id] REFERENCES psa.[board]([board_id]),
    [name] NVARCHAR(400) NOT NULL,

    -- who the queue falls to unassigned
    [team_leader] NVARCHAR(200) NULL,
    [is_default] INT NOT NULL CONSTRAINT [DF_board_team_is_default] DEFAULT (0) CONSTRAINT [CK_board_team_01] CHECK (is_default IN (0, 1)),
    CONSTRAINT [UQ_board_team] UNIQUE ([board_id], [name])
);
END;

-- --------------------------------------------------------------------------
-- board_member   (from schema/006_board.sql)
-- Membership is the access control on a restricted board, not a hint to the
-- interface. Every read path filters by this at the query, and the acceptance
-- test the record wrote for the incumbent and never ran -- can a departmental
-- fulfiller be PROVABLY excluded from a PHI-bearing board -- is answered here.
IF OBJECT_ID(N'psa.[board_member]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board_member] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_member_board_id] REFERENCES psa.[board]([board_id]),
    [member] NVARCHAR(200) NOT NULL,
    [team_id] NVARCHAR(64) NULL CONSTRAINT [FK_board_member_team_id] REFERENCES psa.[board_team]([team_id]),
    [access] NVARCHAR(32) NOT NULL CONSTRAINT [CK_board_member_01] CHECK (access IN ('READ', 'WORK', 'ADMIN')),
    CONSTRAINT [PK_board_member] PRIMARY KEY ([board_id], [member])
);
END;

-- --------------------------------------------------------------------------
-- holiday_list   (from schema/006_board.sql)
-- ------------------------------------------------------ the working week
--
-- The design said two calendars, CLINICAL_24x7 and MANILA_BUSINESS, as fixed
-- values. That breaks the first time a board needs a ward roster or a supplier's
-- support window. ConnectWise lets an SLA run on a company calendar, a customer
-- site calendar, 24x7, or a custom one -- so a calendar is a TABLE.
--
-- Philippine public holidays are rows, not code. PMC's holidays are not
-- Melbourne's, and an SLA that breaches on Bonifacio Day because the calendar
-- was compiled in is a report nobody trusts twice.
IF OBJECT_ID(N'psa.[holiday_list]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[holiday_list] (
    [holiday_list_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_holiday_list] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL
);
END;

-- --------------------------------------------------------------------------
-- holiday   (from schema/006_board.sql)
IF OBJECT_ID(N'psa.[holiday]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[holiday] (
    [holiday_list_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_holiday_holiday_list_id] REFERENCES psa.[holiday_list]([holiday_list_id]),

    -- as the source wrote it; see the port
    [observed_on] NVARCHAR(32) NOT NULL,
    [name] NVARCHAR(400) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [observed_on_parsed] AS (CASE WHEN [observed_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [observed_on], 112) WHEN [observed_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [observed_on], 23) END),
    CONSTRAINT [PK_holiday] PRIMARY KEY ([holiday_list_id], [observed_on])
);
END;

-- --------------------------------------------------------------------------
-- calendar   (from schema/006_board.sql)
-- A NULL start or end means the calendar is closed that day. 24x7 is
-- '00:00'..'24:00' on all seven, which is a row rather than a special case.
IF OBJECT_ID(N'psa.[calendar]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[calendar] (
    [calendar_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_calendar] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [monday_start] NVARCHAR(8) NULL,
    [monday_end] NVARCHAR(8) NULL,
    [tuesday_start] NVARCHAR(8) NULL,
    [tuesday_end] NVARCHAR(8) NULL,
    [wednesday_start] NVARCHAR(8) NULL,
    [wednesday_end] NVARCHAR(8) NULL,
    [thursday_start] NVARCHAR(8) NULL,
    [thursday_end] NVARCHAR(8) NULL,
    [friday_start] NVARCHAR(8) NULL,
    [friday_end] NVARCHAR(8) NULL,
    [saturday_start] NVARCHAR(8) NULL,
    [saturday_end] NVARCHAR(8) NULL,
    [sunday_start] NVARCHAR(8) NULL,
    [sunday_end] NVARCHAR(8) NULL,
    [holiday_list_id] NVARCHAR(64) NULL CONSTRAINT [FK_calendar_holiday_list_id] REFERENCES psa.[holiday_list]([holiday_list_id])
);
END;

-- --------------------------------------------------------------------------
-- ticket_clock   (from schema/007_clock.sql)
IF OBJECT_ID(N'psa.[ticket_clock]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_clock] (
    [clock_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_clock] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_clock_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [clock] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_clock_01] CHECK (clock IN ('RESPOND','RESOLUTION_PLAN','RESOLVE','ACKNOWLEDGE','DECISION')),

    -- Which working week this clock counts against. A ward roster and Manila
    -- business hours are different rows, so a clock on a clinical board and a
    -- clock on the agreement board can disagree about whether Sunday counts.
    [calendar_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_clock_calendar_id] REFERENCES psa.[calendar]([calendar_id]),
    [target_minutes] INT NOT NULL CONSTRAINT [CK_ticket_clock_02] CHECK (target_minutes > 0),
    [started_at] NVARCHAR(64) NOT NULL,

    -- Set when the ticket reaches a status whose escalation_status satisfies this
    -- clock. Until then the clock is running and elapsed is computed to now.
    [stopped_at] NVARCHAR(64) NULL,

    -- The status that stopped it, so the reason is on the record rather than
    -- inferred from a timestamp.
    [stopped_by_status] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_clock_stopped_by_status] REFERENCES psa.[board_status]([board_status_id]),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [started_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [started_at], 126), CASE WHEN [started_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [started_at], 112) END)),
    [stopped_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [stopped_at], 126), CASE WHEN [stopped_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [stopped_at], 112) END)),
    CONSTRAINT [UQ_ticket_clock] UNIQUE ([work_item_id], [clock]),
    CONSTRAINT [CK_ticket_clock_03] CHECK (stopped_at IS NULL OR stopped_at >= started_at)
);
END;

-- --------------------------------------------------------------------------
-- ticket_clock_pause   (from schema/007_clock.sql)
-- One row per interval the clock was not counting. Derived from the ticket
-- entering a status whose escalation_status is NO_ESCALATION, but stored
-- explicitly because the status list can be edited afterwards and this must
-- still recompute to the same answer.
IF OBJECT_ID(N'psa.[ticket_clock_pause]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_clock_pause] (
    [pause_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_clock_pause] PRIMARY KEY,
    [clock_id] INT NOT NULL CONSTRAINT [FK_ticket_clock_pause_clock_id] REFERENCES psa.[ticket_clock]([clock_id]),
    [paused_at] NVARCHAR(64) NOT NULL,
    [resumed_at] NVARCHAR(64) NULL,

    -- Which status paused it. NULL only for a pause applied by hand, which then
    -- needs a reason instead.
    [board_status_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_clock_pause_board_status_id] REFERENCES psa.[board_status]([board_status_id]),
    [reason] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [paused_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [paused_at], 126), CASE WHEN [paused_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [paused_at], 112) END)),
    [resumed_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [resumed_at], 126), CASE WHEN [resumed_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [resumed_at], 112) END)),
    CONSTRAINT [CK_ticket_clock_pause_01] CHECK (resumed_at IS NULL OR resumed_at >= paused_at),
    CONSTRAINT [CK_ticket_clock_pause_02] CHECK (board_status_id IS NOT NULL OR reason IS NOT NULL)
);
END;

-- --------------------------------------------------------------------------
-- workflow   (from schema/008_workflow.sql)
IF OBJECT_ID(N'psa.[workflow]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[workflow] (
    [workflow_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_workflow] PRIMARY KEY,

    -- NULL means global. A rule that pages on a clinical P1 should not have to be
    -- copied onto fourteen boards.
    [board_id] NVARCHAR(64) NULL CONSTRAINT [FK_workflow_board_id] REFERENCES psa.[board]([board_id]),
    [name] NVARCHAR(400) NOT NULL,
    [table_type] NVARCHAR(32) NOT NULL CONSTRAINT [CK_workflow_01] CHECK (table_type IN ('TICKET','WORK_ITEM','TIME_ENTRY','VARIATION')),

    -- Off by default. A rule nobody has read should not be running.
    [is_active] INT NOT NULL CONSTRAINT [DF_workflow_is_active] DEFAULT (0) CONSTRAINT [CK_workflow_02] CHECK (is_active IN (0, 1)),

    -- Time-based rules are first class, not an afterthought. And the schedule can
    -- run on SLA HOURS rather than wall clock: a rule that escalates at 80% of a
    -- target must be evaluated on the same calendar the target uses, or it fires
    -- at the wrong time on a public holiday.
    [batch_interval] INT NULL,
    [batch_frequency_unit] NVARCHAR(32) NULL CONSTRAINT [CK_workflow_03] CHECK (batch_frequency_unit IN ('MINUTES','HOURS','DAYS') OR batch_frequency_unit IS NULL),
    [batch_schedule] NVARCHAR(32) NULL CONSTRAINT [CK_workflow_04] CHECK (batch_schedule IN ('ANY_TIME','BUSINESS_HOURS','SLA_HOURS') OR batch_schedule IS NULL),
    [sort_order] INT NOT NULL CONSTRAINT [DF_workflow_sort_order] DEFAULT (0),
    [note] NVARCHAR(MAX) NULL
);
END;

-- --------------------------------------------------------------------------
-- workflow_event   (from schema/008_workflow.sql)
IF OBJECT_ID(N'psa.[workflow_event]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[workflow_event] (
    [event_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_workflow_event] PRIMARY KEY,
    [workflow_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_workflow_event_workflow_id] REFERENCES psa.[workflow]([workflow_id]),
    [name] NVARCHAR(400) NULL,
    [fires_on] NVARCHAR(32) NOT NULL CONSTRAINT [CK_workflow_event_01] CHECK (fires_on IN ('ON_CREATE','ON_STATUS_CHANGE','ON_OWNER_CHANGE','ON_NOTE_ADDED', 'ON_HANDOVER','ON_SCHEDULE','ON_SLA_THRESHOLD')),
    [execution_time] NVARCHAR(32) NOT NULL CONSTRAINT [DF_workflow_event_execution_time] DEFAULT ('ONCE') CONSTRAINT [CK_workflow_event_02] CHECK (execution_time IN ('ONCE','MULTIPLE_TIMES','CONTINUOUSLY')),
    [frequency] INT NULL,
    [frequency_unit] NVARCHAR(32) NULL CONSTRAINT [CK_workflow_event_03] CHECK (frequency_unit IN ('MINUTES','HOURS','DAYS') OR frequency_unit IS NULL),
    [max_executions] INT NULL,
    CONSTRAINT [CK_workflow_event_04] CHECK (execution_time = 'ONCE' OR (frequency IS NOT NULL AND frequency > 0 AND frequency_unit IS NOT NULL)),
    CONSTRAINT [CK_workflow_event_05] CHECK (execution_time <> 'MULTIPLE_TIMES' OR (max_executions IS NOT NULL AND max_executions > 0))
);
END;

-- --------------------------------------------------------------------------
-- workflow_trigger   (from schema/008_workflow.sql)
-- ----------------------------------------------------- the condition vocabulary
--
-- Which fields a rule may look at, and what kind of value each holds. Rows, so
-- adding a field a rule can test is a row rather than a release.
IF OBJECT_ID(N'psa.[workflow_trigger]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[workflow_trigger] (
    -- 'TICKET.PRIORITY'
    [trigger_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_workflow_trigger] PRIMARY KEY,
    [table_type] NVARCHAR(32) NOT NULL CONSTRAINT [CK_workflow_trigger_01] CHECK (table_type IN ('TICKET','WORK_ITEM','TIME_ENTRY','VARIATION')),

    -- the column the engine reads
    [field] NVARCHAR(400) NOT NULL,

    -- what an administrator sees
    [display_name] NVARCHAR(400) NOT NULL,
    [value_type] NVARCHAR(32) NOT NULL CONSTRAINT [CK_workflow_trigger_02] CHECK (value_type IN ('TEXT','NUMBER','CODE','DATE','BOOLEAN')),

    -- Where the option list comes from, when there is one. NULL means free entry.
    [option_source] NVARCHAR(400) NULL,
    CONSTRAINT [UQ_workflow_trigger] UNIQUE ([table_type], [field])
);
END;

-- --------------------------------------------------------------------------
-- workflow_condition   (from schema/008_workflow.sql)
IF OBJECT_ID(N'psa.[workflow_condition]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[workflow_condition] (
    [condition_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_workflow_condition] PRIMARY KEY,
    [event_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_workflow_condition_event_id] REFERENCES psa.[workflow_event]([event_id]),
    [trigger_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_workflow_condition_trigger_id] REFERENCES psa.[workflow_trigger]([trigger_id]),
    [operator] NVARCHAR(32) NOT NULL CONSTRAINT [CK_workflow_condition_01] CHECK (operator IN ('EQ','NE','IN','NOT_IN','LT','LTE','GT','GTE', 'IS_NULL','IS_NOT_NULL','CONTAINS')),
    [value] NVARCHAR(MAX) NULL,
    [conjunction] NVARCHAR(32) NOT NULL CONSTRAINT [DF_workflow_condition_conjunction] DEFAULT ('AND') CONSTRAINT [CK_workflow_condition_02] CHECK (conjunction IN ('AND','OR')),
    [sort_order] INT NOT NULL CONSTRAINT [DF_workflow_condition_sort_order] DEFAULT (0),
    CONSTRAINT [CK_workflow_condition_03] CHECK (operator IN ('IS_NULL','IS_NOT_NULL') OR value IS NOT NULL)
);
END;

-- --------------------------------------------------------------------------
-- workflow_action   (from schema/008_workflow.sql)
-- ------------------------------------------------------------------ actions
IF OBJECT_ID(N'psa.[workflow_action]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[workflow_action] (
    [action_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_workflow_action] PRIMARY KEY,
    [event_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_workflow_action_event_id] REFERENCES psa.[workflow_event]([event_id]),
    [action] NVARCHAR(32) NOT NULL CONSTRAINT [CK_workflow_action_01] CHECK (action IN ('SET_STATUS','SET_BOARD','ASSIGN_TEAM','ASSIGN_OWNER','NOTIFY', 'ESCALATE','ADD_NOTE','FLAG','REQUIRE_APPROVAL','APPLY_TEMPLATE')),

    -- Who a NOTIFY or ESCALATE reaches. A board role rather than a name, so the
    -- rule survives somebody leaving.
    [notify_role] NVARCHAR(32) NULL CONSTRAINT [CK_workflow_action_02] CHECK (notify_role IN ('SERVICE_MANAGER','DISPATCH','ON_CALL','DUTY_MANAGER', 'TEAM_LEADER','OWNER','REQUESTER') OR notify_role IS NULL),
    [target_board_id] NVARCHAR(64) NULL CONSTRAINT [FK_workflow_action_target_board_id] REFERENCES psa.[board]([board_id]),
    [target_status_id] NVARCHAR(64) NULL CONSTRAINT [FK_workflow_action_target_status_id] REFERENCES psa.[board_status]([board_status_id]),
    [target_team_id] NVARCHAR(64) NULL CONSTRAINT [FK_workflow_action_target_team_id] REFERENCES psa.[board_team]([team_id]),
    [target_member] NVARCHAR(200) NULL,
    [detail] NVARCHAR(MAX) NULL,
    [sort_order] INT NOT NULL CONSTRAINT [DF_workflow_action_sort_order] DEFAULT (0),
    CONSTRAINT [CK_workflow_action_03] CHECK (action NOT IN ('NOTIFY','ESCALATE') OR notify_role IS NOT NULL OR target_member IS NOT NULL)
);
END;

-- --------------------------------------------------------------------------
-- workflow_run   (from schema/008_workflow.sql)
-- --------------------------------------------------------------- the record
--
-- Append-only, and every firing writes here whether it acted or not. "Why did
-- nobody get paged" and "why did this page four times" are both questions with
-- an answer, and both get asked after the incident rather than before.
IF OBJECT_ID(N'psa.[workflow_run]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[workflow_run] (
    [run_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_workflow_run] PRIMARY KEY,
    [event_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_workflow_run_event_id] REFERENCES psa.[workflow_event]([event_id]),
    [work_item_id] NVARCHAR(64) NULL,
    [occurred_at] NVARCHAR(64) NOT NULL,
    [execution_number] INT NOT NULL CONSTRAINT [DF_workflow_run_execution_number] DEFAULT (1),
    [outcome] NVARCHAR(32) NOT NULL CONSTRAINT [CK_workflow_run_01] CHECK (outcome IN ('MATCHED','NOT_MATCHED','ACTED','SUPPRESSED','ERROR')),
    [detail] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [occurred_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [occurred_at], 126), CASE WHEN [occurred_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [occurred_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- oncall_slot   (from schema/011_oncall.sql)
IF OBJECT_ID(N'psa.[oncall_slot]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[oncall_slot] (
    [slot_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_oncall_slot] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_oncall_slot_board_id] REFERENCES psa.[board]([board_id]),

    -- The same namespace as board_member.member and board_role.member: a named
    -- person, never a role name. Who to page, not what to page.
    [member] NVARCHAR(200) NOT NULL,
    [role] NVARCHAR(32) NOT NULL CONSTRAINT [CK_oncall_slot_01] CHECK (role IN ('ON_CALL', 'DUTY_MANAGER')),
    [starts_at] NVARCHAR(64) NOT NULL,
    [ends_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [starts_at], 126), CASE WHEN [starts_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [starts_at], 112) END)),
    [ends_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [ends_at], 126), CASE WHEN [ends_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [ends_at], 112) END)),
    CONSTRAINT [CK_oncall_slot_02] CHECK (ends_at > starts_at)
);
END;

-- --------------------------------------------------------------------------
-- loop_reply   (from schema/012_closedloop.sql)
IF OBJECT_ID(N'psa.[loop_reply]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[loop_reply] (
    [loop_reply_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_loop_reply] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_loop_reply_work_item_id] REFERENCES psa.[work_item]([work_item_id]),

    -- What the fulfiller typed to the requester. Not a clinical note: the §6.1
    -- fence keeps PHI out of ticket text, and this is ticket text.
    [body] NVARCHAR(MAX) NOT NULL,
    [sent_at] NVARCHAR(64) NOT NULL,
    [sent_by] NVARCHAR(200) NOT NULL,

    -- The band recorded at reply time, in minutes, so the loop can be shown
    -- without joining time_entry. NULL when the reply banded nothing (a chase,
    -- a holding answer). The authoritative effort is still the time_entry row.
    [effort_minutes] INT NULL,
    [banded_at] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [sent_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [sent_at], 126), CASE WHEN [sent_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [sent_at], 112) END)),
    [banded_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [banded_at], 126), CASE WHEN [banded_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [banded_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_numbering   (from schema/014_numbering.sql)
-- The prefix is configuration, not a constant, because §12 is explicit: if PMC
-- cannot change it without a deployment, it is in the wrong place. Exactly one
-- row, enforced, so there is never a question of which prefix is in force.
-- The single row is written by db.seed(), not here: schema/*.sql is DDL only,
-- and the translator refuses a statement it does not recognise rather than
-- guessing what a seed INSERT should become on SQL Server.
IF OBJECT_ID(N'psa.[ticket_numbering]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_numbering] (
    [id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_numbering] PRIMARY KEY CONSTRAINT [CK_ticket_numbering_01] CHECK (id = 1),
    [prefix] NVARCHAR(32) NOT NULL CONSTRAINT [DF_ticket_numbering_prefix] DEFAULT ('PMC'),

    -- Zero padding, so PMC-000001 sorts as text in the order it was issued for
    -- the first million tickets. Twelve is well past any hospital's lifetime.
    [padding] INT NOT NULL CONSTRAINT [CK_ticket_numbering_02] CHECK (padding BETWEEN 1 AND 12)
);
END;

-- --------------------------------------------------------------------------
-- ticket_number   (from schema/014_numbering.sql)
-- The sequence itself. Append-only: a row is written when a number is ISSUED,
-- never deleted, so a number is never reused. A reused ticket number is a
-- reference that points at two different tickets, which is worse than a gap —
-- and gaps are fine. `issued_to` is filled in once the ticket exists, so a
-- number issued and then abandoned is visible as exactly that rather than
-- silently vanishing.
IF OBJECT_ID(N'psa.[ticket_number]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_number] (
    [number] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_number] PRIMARY KEY,
    [issued_at] NVARCHAR(64) NOT NULL,
    [issued_to] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_number_issued_to] REFERENCES psa.[ticket]([work_item_id]),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [issued_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [issued_at], 126), CASE WHEN [issued_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [issued_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- intake_message   (from schema/015_intake.sql)
IF OBJECT_ID(N'psa.[intake_message]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[intake_message] (
    -- RFC 5322 Message-ID, as the sender wrote it. The natural key of a message,
    -- and the reason a redelivery cannot become a second ticket.
    [message_id] NVARCHAR(400) NOT NULL CONSTRAINT [PK_intake_message] PRIMARY KEY,
    [received_at] NVARCHAR(64) NOT NULL,

    -- The address as sent, kept verbatim. Measured intake today includes consumer
    -- Gmail and Yahoo mailboxes (§6.1), and normalising that away loses evidence
    -- about who is actually raising tickets.
    [from_address] NVARCHAR(200) NULL,
    [subject] NVARCHAR(400) NULL,

    -- Which mailbox it landed in: 'helpdesk', 'support', or whatever the drop is
    -- named. This is how the double-creation is visible as a number rather than
    -- as an anecdote.
    [channel] NVARCHAR(32) NULL,

    -- What happened to it. Exactly one of these, always:
    -- NEW_TICKET  it opened a ticket
    -- APPENDED    it was a reply or a resend; it became a note on one
    -- DUPLICATE   same requester, same subject, inside the window
    -- UNCLASSIFIED it could not be placed, and is flagged rather than dropped
    [disposition] NVARCHAR(32) NOT NULL CONSTRAINT [CK_intake_message_01] CHECK (disposition IN ('NEW_TICKET','APPENDED','DUPLICATE','UNCLASSIFIED')),
    [work_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_intake_message_work_item_id] REFERENCES psa.[work_item]([work_item_id]),

    -- The message this one was judged to continue, when it was.
    [duplicate_of] NVARCHAR(400) NULL CONSTRAINT [FK_intake_message_duplicate_of] REFERENCES psa.[intake_message]([message_id]),
    [run_id] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [received_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [received_at], 126), CASE WHEN [received_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [received_at], 112) END)),
    CONSTRAINT [CK_intake_message_02] CHECK ((disposition IN ('NEW_TICKET','APPENDED')) = (work_item_id IS NOT NULL))
);
END;

-- ==========================================================================
-- COLUMNS ADDED TO TABLES THAT ALREADY EXIST
--
-- Guarded by COL_LENGTH so a re-run adds nothing twice. A schema that can
-- only be created and never evolved is not a schema, but on a live clinical
-- database the only safe evolution is ADD: the translator refuses a rename
-- or a drop rather than losing a column quietly.

IF COL_LENGTH(N'psa.[ticket]', N'board_status_id') IS NULL
ALTER TABLE psa.[ticket] ADD [board_status_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_board_status_id] REFERENCES psa.[board_status]([board_status_id]);

-- The effort banded through a loop points back at the reply that captured it, so
-- the uplift evidence can say not just how many hours but that each hour was
-- answered to the requester in the same breath.
IF COL_LENGTH(N'psa.[time_entry]', N'loop_reply_id') IS NULL
ALTER TABLE psa.[time_entry] ADD [loop_reply_id] NVARCHAR(64) NULL CONSTRAINT [FK_time_entry_loop_reply_id] REFERENCES psa.[loop_reply]([loop_reply_id]);

-- The reference itself. A record number, nothing else — no name, no date of
-- birth, no diagnosis. Everything a fulfiller needs to find the patient in the
-- system that is actually the record of care, and nothing that makes this
-- database into a second one.
IF COL_LENGTH(N'psa.[ticket]', N'patient_reference') IS NULL
ALTER TABLE psa.[ticket] ADD [patient_reference] NVARCHAR(64) NULL;

-- --------------------------------------------------------------------------
-- indexes

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_fee_line_effective' AND object_id = OBJECT_ID(N'psa.[fee_line]'))
CREATE INDEX [ix_fee_line_effective] ON psa.[fee_line] ([entity_id], [effective_from]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_time_entry_period' AND object_id = OBJECT_ID(N'psa.[time_entry]'))
CREATE INDEX [ix_time_entry_period] ON psa.[time_entry] ([entity_id], [worked_on]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_workflow_run_event' AND object_id = OBJECT_ID(N'psa.[workflow_run]'))
CREATE INDEX [ix_workflow_run_event] ON psa.[workflow_run] ([event_id], [work_item_id]);

-- "Who is on call for this board and role right now" is the only question asked
-- of this table on a hot path, so it is the shape the index serves.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_oncall_active' AND object_id = OBJECT_ID(N'psa.[oncall_slot]'))
CREATE INDEX [ix_oncall_active] ON psa.[oncall_slot] ([board_id], [role], [starts_at], [ends_at]);

-- "Have I seen this thread before" and "what else came from this requester with
-- this subject" are the two questions asked on the hot path.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_intake_thread' AND object_id = OBJECT_ID(N'psa.[intake_message]'))
CREATE INDEX [ix_intake_thread] ON psa.[intake_message] ([from_address], [subject]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_intake_ticket' AND object_id = OBJECT_ID(N'psa.[intake_message]'))
CREATE INDEX [ix_intake_ticket] ON psa.[intake_message] ([work_item_id]);

-- ==========================================================================
-- THE GATE
--
-- These two triggers are the reason for the port. A variation-path ticket
-- must not be able to consume effort, or be closed, while no variation is
-- attached: the work then stays visible as work nobody has agreed to pay
-- for, instead of disappearing into a fixed monthly fee.
--
-- Two differences from the SQLite original, both deliberate:
--
--   * SQL Server has no BEFORE trigger. SQLite refuses the offending
--     statement and leaves the transaction alone; the nearest honest
--     equivalent here is an AFTER trigger that rolls the transaction back
--     and throws. The write is still refused. The blast radius is larger:
--     a caller batching this insert with other work loses that work too.
--     That is the correct trade -- a gate that yields under a batch is not
--     a gate -- but it has to be said out loud, so it is said here.
--
--   * RAISE(ABORT, ...) becomes THROW, whose message is the SQLite message
--     word for word. Anyone who hits it should be able to search for the
--     text and find this file and the schema it came from.

-- ------------------------------------------------------------------ the gate
--
-- THIS is the blocking gap the spine was missing. Effort could be banded
-- against the thirty-five workstreams but not against tickets, so a
-- hospital-wide uplift claim could not be evidenced from ticket effort.
--
-- A variation-path ticket must be attached to a variation before it can consume
-- effort. Enforced here rather than in the importer, because an importer can be
-- bypassed and a trigger cannot: the moment somebody logs time against
-- unapproved out-of-scope work, the database refuses it and the work stays
-- visible as work nobody has agreed to pay for.
-- from schema/005_ticket.sql, where it reads: BEFORE INSERT ON time_entry
IF OBJECT_ID(N'psa.[time_entry_requires_a_variation]', N'TR') IS NULL
EXEC sp_executesql N'
CREATE TRIGGER psa.[time_entry_requires_a_variation]
ON psa.[time_entry]
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted AS inserted_row WHERE EXISTS ( SELECT 1 FROM psa.ticket t JOIN psa.work_item w ON w.work_item_id = t.work_item_id WHERE t.work_item_id = inserted_row.work_item_id AND t.path = ''VARIATION'' AND w.variation_id IS NULL))
    BEGIN
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW 50001, N''a variation-path ticket must be attached to a variation before it can consume effort'', 1;
    END
END
';

-- The same rule at close: a variation ticket cannot be resolved while the work
-- it did has no commercial home.
-- from schema/005_ticket.sql, where it reads: BEFORE UPDATE OF state ON ticket
IF OBJECT_ID(N'psa.[ticket_close_requires_a_variation]', N'TR') IS NULL
EXEC sp_executesql N'
CREATE TRIGGER psa.[ticket_close_requires_a_variation]
ON psa.[ticket]
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF (UPDATE(state))
       AND EXISTS (SELECT 1 FROM inserted AS inserted_row WHERE inserted_row.state IN (''RESOLVED'', ''CLOSED'') AND inserted_row.path = ''VARIATION'' AND (SELECT variation_id FROM psa.work_item WHERE work_item_id = inserted_row.work_item_id) IS NULL)
    BEGIN
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW 50002, N''a variation-path ticket cannot be closed with no variation attached'', 1;
    END
END
';

-- A patient reference belongs only on a board that is restricted, because
-- `restricted` is what makes membership a hard filter at the query (§5.6) and
-- what makes a read auditable (§6.1). Putting one on an open board would place a
-- patient identifier on the same queue as printer faults, which is the exact
-- defect this file exists to answer.
--
-- In the schema and not the importer, for the reason 005 gives: an importer can
-- be bypassed and a trigger cannot.
-- from schema/013_intake.sql, where it reads: BEFORE INSERT ON ticket
IF OBJECT_ID(N'psa.[patient_reference_needs_a_restricted_board]', N'TR') IS NULL
EXEC sp_executesql N'
CREATE TRIGGER psa.[patient_reference_needs_a_restricted_board]
ON psa.[ticket]
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted AS inserted_row WHERE inserted_row.patient_reference IS NOT NULL AND (SELECT restricted FROM psa.board WHERE board_id = inserted_row.board_id) = 0)
    BEGIN
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW 50003, N''a patient reference may only be held on a restricted board'', 1;
    END
END
';

-- The same rule on the way through, so a ticket cannot acquire one by being
-- moved or edited onto an open board.
-- from schema/013_intake.sql, where it reads: BEFORE UPDATE ON ticket
IF OBJECT_ID(N'psa.[patient_reference_stays_on_a_restricted_board]', N'TR') IS NULL
EXEC sp_executesql N'
CREATE TRIGGER psa.[patient_reference_stays_on_a_restricted_board]
ON psa.[ticket]
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted AS inserted_row WHERE inserted_row.patient_reference IS NOT NULL AND (SELECT restricted FROM psa.board WHERE board_id = inserted_row.board_id) = 0)
    BEGIN
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW 50004, N''a patient reference may only be held on a restricted board'', 1;
    END
END
';

/*----------------------------------------------------------- the verify gate */
--
-- Count what is actually there before committing. If the schema is short an
-- object the transaction goes back: a half-created spine that looks installed is
-- worse than one that plainly is not.

SELECT @Tables = COUNT(*) FROM sys.tables t
  JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = @Schema;
SELECT @Triggers = COUNT(*) FROM sys.triggers tr
  JOIN sys.tables t ON t.object_id = tr.parent_id
  JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = @Schema;
SELECT @Indexes = COUNT(*) FROM sys.indexes i
  JOIN sys.tables t ON t.object_id = i.object_id
  JOIN sys.schemas s ON s.schema_id = t.schema_id
 WHERE s.name = @Schema AND i.type = 2 AND i.is_unique = 0 AND i.is_primary_key = 0;

IF @Tables <> 53 OR @Triggers <> 4 OR @Indexes < 6
BEGIN
    ROLLBACK TRANSACTION;
    RAISERROR(N'VERIFY FAILED: found %d tables (expected 53), %d triggers (expected 4), %d indexes (expected at least 6). Rolled back; nothing was created.',
              16, 1, @Tables, @Triggers, @Indexes);
    RETURN;
END;

COMMIT TRANSACTION;

PRINT N'Created: ' + CAST(@Tables AS NVARCHAR(10)) + N' tables, '
                   + CAST(@Triggers AS NVARCHAR(10)) + N' triggers, '
                   + CAST(@Indexes AS NVARCHAR(10)) + N' indexes in [psa].';
PRINT N'The gate is live: a variation-path ticket cannot consume effort or close';
PRINT N'with no variation attached.';
PRINT N'';
PRINT N'Seeded: nothing. No board is live, no clinical floor is signed and no SLA';
PRINT N'target is enforced until somebody with the authority says so.';


/*=============================================================================
  ROLLBACK

  In dependency order, children first. Uncomment and run against the same
  database. It drops the schema and everything this script created in it, so
  read it before you run it: anything imported since is dropped with it.

    DROP TRIGGER IF EXISTS psa.[time_entry_requires_a_variation];
    DROP TRIGGER IF EXISTS psa.[ticket_close_requires_a_variation];
    DROP TRIGGER IF EXISTS psa.[patient_reference_needs_a_restricted_board];
    DROP TRIGGER IF EXISTS psa.[patient_reference_stays_on_a_restricted_board];
    DROP TABLE IF EXISTS psa.[intake_message];
    DROP TABLE IF EXISTS psa.[ticket_number];
    DROP TABLE IF EXISTS psa.[ticket_numbering];
    DROP TABLE IF EXISTS psa.[loop_reply];
    DROP TABLE IF EXISTS psa.[oncall_slot];
    DROP TABLE IF EXISTS psa.[workflow_run];
    DROP TABLE IF EXISTS psa.[workflow_action];
    DROP TABLE IF EXISTS psa.[workflow_condition];
    DROP TABLE IF EXISTS psa.[workflow_trigger];
    DROP TABLE IF EXISTS psa.[workflow_event];
    DROP TABLE IF EXISTS psa.[workflow];
    DROP TABLE IF EXISTS psa.[ticket_clock_pause];
    DROP TABLE IF EXISTS psa.[ticket_clock];
    DROP TABLE IF EXISTS psa.[calendar];
    DROP TABLE IF EXISTS psa.[holiday];
    DROP TABLE IF EXISTS psa.[holiday_list];
    DROP TABLE IF EXISTS psa.[board_member];
    DROP TABLE IF EXISTS psa.[board_team];
    DROP TABLE IF EXISTS psa.[board_role];
    DROP TABLE IF EXISTS psa.[board_status];
    DROP TABLE IF EXISTS psa.[priority_override];
    DROP TABLE IF EXISTS psa.[ticket_handover];
    DROP TABLE IF EXISTS psa.[ticket_event];
    DROP TABLE IF EXISTS psa.[ticket];
    DROP TABLE IF EXISTS psa.[sla_target];
    DROP TABLE IF EXISTS psa.[clinical_floor];
    DROP TABLE IF EXISTS psa.[catalogue_item];
    DROP TABLE IF EXISTS psa.[service_action];
    DROP TABLE IF EXISTS psa.[service_component];
    DROP TABLE IF EXISTS psa.[service_family];
    DROP TABLE IF EXISTS psa.[board];
    DROP TABLE IF EXISTS psa.[import_run];
    DROP TABLE IF EXISTS psa.[audit_event];
    DROP TABLE IF EXISTS psa.[data_quality];
    DROP TABLE IF EXISTS psa.[document];
    DROP TABLE IF EXISTS psa.[capacity_declaration];
    DROP TABLE IF EXISTS psa.[time_entry];
    DROP TABLE IF EXISTS psa.[work_item_evidence];
    DROP TABLE IF EXISTS psa.[work_item_note];
    DROP TABLE IF EXISTS psa.[work_item_scope_item];
    DROP TABLE IF EXISTS psa.[work_item];
    DROP TABLE IF EXISTS psa.[decision_note];
    DROP TABLE IF EXISTS psa.[reclassification];
    DROP TABLE IF EXISTS psa.[client_dependency];
    DROP TABLE IF EXISTS psa.[notice];
    DROP TABLE IF EXISTS psa.[variation_event];
    DROP TABLE IF EXISTS psa.[variation];
    DROP TABLE IF EXISTS psa.[fee_line];
    DROP TABLE IF EXISTS psa.[instrument_scope_item];
    DROP TABLE IF EXISTS psa.[scope_item];
    DROP TABLE IF EXISTS psa.[instrument];
    DROP TABLE IF EXISTS psa.[site];
    DROP TABLE IF EXISTS psa.[entity];
    DROP SCHEMA IF EXISTS psa;
=============================================================================*/
