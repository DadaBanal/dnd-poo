/*==============================================================================
  PMC / Dada IT -- PSA spine, SQL Server schema
  Target: DND-SQL01\PMC_SS, database PMC_PSA, schema [psa]

  GENERATED FILE -- DO NOT EDIT.
      source:     platform/psa-spine/schema/  (the SQLite files, the one source)
      translator: platform/psa-spine/tools/sqlite_to_tsql.py
      decisions:  platform/psa-spine/tools/tsql-decisions.json
      regenerate: python3 tools/sqlite_to_tsql.py --write
      drift gate: python3 tools/sqlite_to_tsql.py --check   (CI runs this)

  An edit made here is lost on the next regeneration and, worse, is invisible in
  the SQLite copy that the importer and the reports actually run against. Change
  the files under schema/ and regenerate.

  ---------------------------------------------------------------------------
  HOW TO RUN IT

      sqlcmd -I -S "DND-SQL01\PMC_SS" -d PMC_PSA -i PMC_PSA_Spine_SqlServer.sql

  -I (quoted identifiers on) matters: two filtered UNIQUE indexes below need
  QUOTED_IDENTIFIER ON, and sqlcmd's default is OFF, so without it the apply
  stops at the first of them and rolls back. The script also sets it itself.

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

  VERIFIED on SQL Server 2022 Express (16.0) in a container, 25 Sep 2026: applies,
  passes its own gate, both triggers fire. NOT VERIFIED on DND-SQL01\PMC_SS itself,
  which no session here can reach. Run it with @Apply = 0 first and read the plan.

  Comments in this file never contain a slash-star pair: T-SQL nests block
  comments, and the first run found the header itself unterminated because of one.
==============================================================================*/

SET NOCOUNT ON;
-- A filtered index cannot be created with QUOTED_IDENTIFIER OFF (sqlcmd's
-- default); the nested EXEC batches inherit this session setting.
SET QUOTED_IDENTIFIER ON;

-- XACT_ABORT means a failure anywhere in the apply below takes the whole
-- transaction with it rather than leaving half a schema behind.
SET XACT_ABORT ON;

DECLARE @Apply         BIT = 0;      -- <<<< set to 1 to make changes
DECLARE @AllowExisting BIT = 0;      -- <<<< set to 1 to fill in what is missing

DECLARE @Schema        SYSNAME = N'psa';
DECLARE @Database      SYSNAME = N'PMC_PSA';  -- D7's name; the desk refuses any other
DECLARE @DbName        SYSNAME = DB_NAME();   -- RAISERROR takes variables, not calls
DECLARE @Existing      INT;
DECLARE @Tables        INT;
DECLARE @Triggers      INT;
DECLARE @Indexes       INT;

/*------------------------------------------------------------------ preflight */

IF @DbName <> @Database
BEGIN
    RAISERROR(N'Refusing: connected to database [%s], expected [%s] on DND-SQL01\PMC_SS. Nothing was changed.',
              16, 1, @DbName, @Database);
    RETURN;
END;

SELECT @Existing = COUNT(*)
  FROM sys.objects o
  JOIN sys.schemas s ON s.schema_id = o.schema_id
 WHERE s.name = @Schema AND o.type IN ('U', 'TR');

IF @Existing > 0 AND @AllowExisting = 0
BEGIN
    RAISERROR(N'Refusing: schema [%s] already holds %d objects. This script is not meant to run twice. Set @AllowExisting = 1 to create only what is missing. Nothing was changed.',
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
    PRINT N'    psa.api_alert';
    PRINT N'    psa.contact';
    PRINT N'    psa.configuration';
    PRINT N'    psa.ticket_configuration';
    PRINT N'    psa.integration_link';
    PRINT N'    psa.board_record_type';
    PRINT N'    psa.sla_target_type';
    PRINT N'    psa.change_approval';
    PRINT N'    psa.ticket_link';
    PRINT N'    psa.notification';
    PRINT N'    psa.ticket_template';
    PRINT N'    psa.ticket_template_task';
    PRINT N'    psa.ticket_task';
    PRINT N'    psa.attachment';
    PRINT N'    psa.user_view';
    PRINT N'    psa.standard_note';
    PRINT N'    psa.ticket_schedule';
    PRINT N'    psa.survey_response';
    PRINT N'    psa.work_role';
    PRINT N'    psa.work_type';
    PRINT N'    psa.department';
    PRINT N'    psa.department_board';
    PRINT N'    psa.schedule_status';
    PRINT N'    psa.service_location';
    PRINT N'    psa.schedule_block';
    PRINT N'    psa.kb_article';
    PRINT N'    psa.kb_revision';
    PRINT N'    psa.kb_ticket';
    PRINT N'    psa.security_role';
    PRINT N'    psa.role_permission';
    PRINT N'    psa.member_role';
    PRINT N'    psa.project';
    PRINT N'    psa.project_phase';
    PRINT N'    psa.phase_dependency';
    PRINT N'    psa.project_ticket';
    PRINT N'    psa.report_def';
    PRINT N'    psa.ext_source';
    PRINT N'    psa.ext_agreement';
    PRINT N'    psa.ext_product';
    PRINT N'    psa.ext_purchase_order';
    PRINT N'    psa.ext_invoice';
    PRINT N'    psa.ext_link';
    PRINT N'    psa.ext_po_line';
    PRINT N'    psa.ext_change';
    PRINT N'    psa.agreement';
    PRINT N'    psa.agreement_item';
    PRINT N'    psa.timesheet';
    PRINT N'    psa.timesheet_event';
    PRINT N'    psa.member_capacity';
    PRINT N'    psa.role_grant';
    PRINT N'    psa.recurrence';
    PRINT N'    psa.approval';
    PRINT N'    psa.channel_target';
    PRINT N'    psa.page';
    PRINT N'    psa.kb_file';
    PRINT N'    psa.opportunity';
    PRINT N'    psa.quote';
    PRINT N'    psa.quote_line';
    PRINT N'    psa.member';
    PRINT N'    psa.calendar_feed';
    PRINT N'    psa.mail_exclusion';
    PRINT N'    psa.configuration_type';
    PRINT N'    psa.configuration_status';
    PRINT N'    psa.configuration_question';
    PRINT N'    psa.configuration_answer';
    PRINT N'    psa.mail_template';
    PRINT N'    psa.kb_category';
    PRINT N'    psa.company_status';
    PRINT N'    psa.company_type';
    PRINT N'    psa.board_auto_assign';
    PRINT N'    psa.member_presence';
    PRINT N'    psa.board_intake_address';
    PRINT N'    psa.status_mail';
    PRINT N'    psa.calendar_sync';
    PRINT N'    psa.outlook_busy';
    PRINT N'    psa.priority';
    PRINT N'    psa.ticket_cc';
    PRINT N'    psa.dispatch_view';
    PRINT N'    psa.time_timer';
    PRINT N'    psa.ticket_resource';
    PRINT N'    psa.project_member';
    PRINT N'    psa.project_note';
    PRINT N'    psa.project_contact';
    PRINT N'    psa.project_ticket_dependency';
    PRINT N'    psa.project_plan_item';
    PRINT N'    psa.project_status';
    PRINT N'    psa.project_type';
    PRINT N'    psa.project_role';
    PRINT N'    psa.project_issue';
    PRINT N'    psa.chat_session';
    PRINT N'    psa.chat_message';
    PRINT N'    psa.api_token';
    PRINT N'    psa.local_account';
    PRINT N'    psa.ix_fee_line_effective';
    PRINT N'    psa.ix_time_entry_period';
    PRINT N'    psa.ix_workflow_run_event';
    PRINT N'    psa.ix_oncall_active';
    PRINT N'    psa.ix_intake_thread';
    PRINT N'    psa.ix_intake_ticket';
    PRINT N'    psa.ix_contact_email';
    PRINT N'    psa.ux_contact_ad_guid';
    PRINT N'    psa.ix_configuration_entity';
    PRINT N'    psa.ux_configuration_ad_guid';
    PRINT N'    psa.ix_change_approval_ticket';
    PRINT N'    psa.ix_notification_status';
    PRINT N'    psa.ix_ticket_task_ticket';
    PRINT N'    psa.ix_attachment_ticket';
    PRINT N'    psa.ix_ticket_event_ticket';
    PRINT N'    psa.ix_ticket_clock_ticket';
    PRINT N'    psa.ix_ticket_clock_pause_clock';
    PRINT N'    psa.ix_ticket_board_state';
    PRINT N'    psa.ix_ticket_parent';
    PRINT N'    psa.ix_user_view_member';
    PRINT N'    psa.ix_standard_note_board';
    PRINT N'    psa.ix_ticket_merged';
    PRINT N'    psa.ix_ticket_schedule_day';
    PRINT N'    psa.ix_ticket_schedule_ticket';
    PRINT N'    psa.ix_time_entry_ticket';
    PRINT N'    psa.ix_department_board_board';
    PRINT N'    psa.ix_schedule_block_day';
    PRINT N'    psa.ix_schedule_block_member';
    PRINT N'    psa.ix_project_phase_project';
    PRINT N'    psa.ix_project_ticket_project';
    PRINT N'    psa.ix_ext_link_ref';
    PRINT N'    psa.ix_ext_po_line_po';
    PRINT N'    psa.ix_ext_change_ref';
    PRINT N'    psa.ix_kb_ticket_ticket';
    PRINT N'    psa.ix_ext_invoice_agreement';
    PRINT N'    psa.ix_agreement_item_ref';
    PRINT N'    psa.ix_timesheet_event_sheet';
    PRINT N'    psa.ix_time_entry_sheet';
    PRINT N'    psa.ix_recurrence_due';
    PRINT N'    psa.ix_approval_ticket';
    PRINT N'    psa.ix_approval_approver';
    PRINT N'    psa.ix_page_open';
    PRINT N'    psa.ix_kb_file_article';
    PRINT N'    psa.ix_opportunity_stage';
    PRINT N'    psa.ix_quote_opportunity';
    PRINT N'    psa.ix_quote_line_quote';
    PRINT N'    psa.ix_calendar_feed_hash';
    PRINT N'    psa.ix_audit_event_when';
    PRINT N'    psa.ix_audit_event_actor';
    PRINT N'    psa.ix_audit_event_subject';
    PRINT N'    psa.ix_configuration_question_type';
    PRINT N'    psa.ix_calendar_sync_status';
    PRINT N'    psa.ix_outlook_busy_member';
    PRINT N'    psa.ux_time_timer_running';
    PRINT N'    psa.ix_time_timer_member';
    PRINT N'    psa.ix_ticket_resource_member';
    PRINT N'    psa.ix_project_member_member';
    PRINT N'    psa.ix_project_note_project';
    PRINT N'    psa.ix_project_plan_item_project';
    PRINT N'    psa.ix_project_issue_project';
    PRINT N'    psa.ix_chat_session_status';
    PRINT N'    psa.ix_chat_session_requester';
    PRINT N'    psa.ix_chat_message_chat';
    PRINT N'    psa.ux_api_token_sha256';
    PRINT N'    psa.time_entry_requires_a_variation';
    PRINT N'    psa.ticket_close_requires_a_variation';
    PRINT N'    psa.patient_reference_needs_a_restricted_board';
    PRINT N'    psa.patient_reference_stays_on_a_restricted_board';
    PRINT N'';
    PRINT N'  146 tables, 64 indexes, 4 triggers.';
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
    [subject_id] NVARCHAR(400) NULL,
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
-- more for the plan. The reference PSA carries ONE field instead, and it is better:
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

    -- Retired, never deleted. The reference PSA refuses to delete a board once anything
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
-- The reference PSA carries four per board -- dispatchMember, dutyManagerMember,
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
-- support window. The reference PSA lets an SLA run on a company calendar, a customer
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
    [id] INT NOT NULL CONSTRAINT [PK_ticket_numbering] PRIMARY KEY CONSTRAINT [CK_ticket_numbering_01] CHECK (id = 1),
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
    CONSTRAINT [CK_intake_message_02] CHECK ((((disposition IN ('NEW_TICKET','APPENDED')) AND (work_item_id IS NOT NULL)) OR (NOT (disposition IN ('NEW_TICKET','APPENDED')) AND NOT (work_item_id IS NOT NULL))))
);
END;

-- --------------------------------------------------------------------------
-- api_alert   (from schema/016_api_alert.sql)
IF OBJECT_ID(N'psa.[api_alert]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[api_alert] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_api_alert_board_id] REFERENCES psa.[board]([board_id]),

    -- Chosen by the sender. Stable across firings of the same condition.
    [dedup_key] NVARCHAR(200) NOT NULL,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_api_alert_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [first_seen] NVARCHAR(64) NOT NULL,
    [last_seen] NVARCHAR(64) NOT NULL,
    [times] INT NOT NULL CONSTRAINT [DF_api_alert_times] DEFAULT (1) CONSTRAINT [CK_api_alert_01] CHECK (times >= 1),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [first_seen_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [first_seen], 126), CASE WHEN [first_seen] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [first_seen], 112) END)),
    [last_seen_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_seen], 126), CASE WHEN [last_seen] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_seen], 112) END)),
    CONSTRAINT [PK_api_alert] PRIMARY KEY ([board_id], [dedup_key])
);
END;

-- --------------------------------------------------------------------------
-- contact   (from schema/020_contacts.sql)
IF OBJECT_ID(N'psa.[contact]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[contact] (
    [contact_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_contact] PRIMARY KEY,
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_contact_entity_id] REFERENCES psa.[entity]([entity_id]),
    [display_name] NVARCHAR(400) NOT NULL,
    [email] NVARCHAR(400) NULL,
    [phone] NVARCHAR(32) NULL,

    -- ward or department, as AD holds it
    [department] NVARCHAR(400) NULL,
    [title] NVARCHAR(400) NULL,
    [office] NVARCHAR(400) NULL,
    [upn] NVARCHAR(400) NULL,
    [sam_account] NVARCHAR(32) NULL,
    [ad_object_guid] NVARCHAR(64) NULL,
    [source] NVARCHAR(32) NOT NULL CONSTRAINT [CK_contact_01] CHECK (source IN ('AD', 'ENTRA', 'MANUAL', 'INTAKE')),
    [inactive] INT NOT NULL CONSTRAINT [DF_contact_inactive] DEFAULT (0) CONSTRAINT [CK_contact_02] CHECK (inactive IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,
    [last_synced_at] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [last_synced_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_synced_at], 126), CASE WHEN [last_synced_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_synced_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- configuration   (from schema/021_configurations.sql)
IF OBJECT_ID(N'psa.[configuration]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[configuration] (
    [configuration_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_configuration] PRIMARY KEY,
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_configuration_entity_id] REFERENCES psa.[entity]([entity_id]),

    -- the hostname, as AD holds it
    [name] NVARCHAR(400) NOT NULL,
    [config_type] NVARCHAR(32) NOT NULL CONSTRAINT [CK_configuration_01] CHECK (config_type IN ('WORKSTATION', 'LAPTOP', 'SERVER', 'PRINTER', 'NETWORK', 'MOBILE', 'OTHER')),
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_configuration_status] DEFAULT ('ACTIVE') CONSTRAINT [CK_configuration_02] CHECK (status IN ('ACTIVE', 'INACTIVE', 'RETIRED')),
    [contact_id] NVARCHAR(64) NULL CONSTRAINT [FK_configuration_contact_id] REFERENCES psa.[contact]([contact_id]),
    [site_id] NVARCHAR(64) NULL CONSTRAINT [FK_configuration_site_id] REFERENCES psa.[site]([site_id]),
    [dns_name] NVARCHAR(400) NULL,
    [os_name] NVARCHAR(400) NULL,
    [os_version] NVARCHAR(32) NULL,
    [manufacturer] NVARCHAR(400) NULL,
    [model] NVARCHAR(400) NULL,
    [serial_number] NVARCHAR(400) NULL,
    [description] NVARCHAR(MAX) NULL,

    -- The ScreenConnect session this machine's agent reports as. It is what a
    -- launch link needs, and nothing here can read it from ScreenConnect, so it is
    -- set on the configuration page (NOT VERIFIED: a bulk export route).
    [remote_session_id] NVARCHAR(64) NULL,
    [ad_object_guid] NVARCHAR(64) NULL,
    [source] NVARCHAR(32) NOT NULL CONSTRAINT [CK_configuration_03] CHECK (source IN ('AD', 'SCREENCONNECT', 'MANUAL')),
    [created_at] NVARCHAR(64) NOT NULL,
    [last_synced_at] NVARCHAR(64) NULL,

    -- AD's LastLogonDate, as a freshness hint
    [last_seen_at] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [last_synced_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_synced_at], 126), CASE WHEN [last_synced_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_synced_at], 112) END)),
    [last_seen_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_seen_at], 126), CASE WHEN [last_seen_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_seen_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_configuration   (from schema/021_configurations.sql)
-- Which configurations a ticket concerns, as Dada PSA's Configurations tab.
IF OBJECT_ID(N'psa.[ticket_configuration]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_configuration] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_configuration_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [configuration_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_configuration_configuration_id] REFERENCES psa.[configuration]([configuration_id]),
    [linked_at] NVARCHAR(64) NOT NULL,
    [linked_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [linked_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [linked_at], 126), CASE WHEN [linked_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [linked_at], 112) END)),
    CONSTRAINT [PK_ticket_configuration] PRIMARY KEY ([work_item_id], [configuration_id])
);
END;

-- --------------------------------------------------------------------------
-- integration_link   (from schema/021_configurations.sql)
-- Links out to the tools the desk does not replace: ScreenConnect first, and
-- anything else that can be opened by URL. A template names fields in braces,
-- e.g. {remote_session_id}; each value is URL-encoded when the link is drawn,
-- and a link whose field is empty is shown disabled with the reason. HTTPS only.
-- The instance's own address is typed in Setup, never shipped here.
IF OBJECT_ID(N'psa.[integration_link]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[integration_link] (
    [link_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_integration_link] PRIMARY KEY,
    [label] NVARCHAR(400) NOT NULL,
    [applies_to] NVARCHAR(32) NOT NULL CONSTRAINT [CK_integration_link_01] CHECK (applies_to IN ('CONFIGURATION', 'CONTACT')),
    [url_template] NVARCHAR(400) NOT NULL CONSTRAINT [CK_integration_link_02] CHECK (url_template LIKE 'https://%'),
    [inactive] INT NOT NULL CONSTRAINT [DF_integration_link_inactive] DEFAULT (0) CONSTRAINT [CK_integration_link_03] CHECK (inactive IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- board_record_type   (from schema/022_record_type.sql)
-- The board's Types: Dada PSA's Types tab. On a service board they are
-- Incident, Request, Problem and Event, the four of the reference PSA's ITIL example
-- and Dada's column A, and a ticket reads Type > Subtype > Item (Incident >
-- Printers > Fix). A board with no rows takes every Type, so a board set up
-- before this migration behaves as it did. ticket.record_type holds the Type.
IF OBJECT_ID(N'psa.[board_record_type]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board_record_type] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_record_type_board_id] REFERENCES psa.[board]([board_id]),
    [record_type] NVARCHAR(32) NOT NULL CONSTRAINT [CK_board_record_type_01] CHECK (record_type IN ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT')),
    [is_default] INT NOT NULL CONSTRAINT [DF_board_record_type_is_default] DEFAULT (0) CONSTRAINT [CK_board_record_type_02] CHECK (is_default IN (0, 1)),
    CONSTRAINT [PK_board_record_type] PRIMARY KEY ([board_id], [record_type])
);
END;

-- --------------------------------------------------------------------------
-- sla_target_type   (from schema/022_record_type.sql)
-- SLA targets for one record type on a board. ITIL measures a service request
-- by its fulfilment time, not an incident's restore time, and Dada's workbook
-- had separate numbers for the two ("respond within 2 h" for Help, "within 1
-- day" for Request). Merging the boards must not merge those numbers, so a
-- ticket takes its record type's targets where they exist and the board's
-- general ones (sla_target) where they do not.
IF OBJECT_ID(N'psa.[sla_target_type]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[sla_target_type] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_sla_target_type_board_id] REFERENCES psa.[board]([board_id]),
    [record_type] NVARCHAR(32) NOT NULL CONSTRAINT [CK_sla_target_type_01] CHECK (record_type IN ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT')),
    [priority] NVARCHAR(32) NOT NULL CONSTRAINT [CK_sla_target_type_02] CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    [clock] NVARCHAR(32) NOT NULL CONSTRAINT [CK_sla_target_type_03] CHECK (clock IN ('RESPOND', 'RESOLUTION_PLAN', 'RESOLVE', 'ACKNOWLEDGE', 'DECISION')),
    [target_minutes] INT NOT NULL CONSTRAINT [CK_sla_target_type_04] CHECK (target_minutes > 0),
    [calendar] NVARCHAR(32) NOT NULL CONSTRAINT [CK_sla_target_type_05] CHECK (calendar IN ('CLINICAL_24x7', 'MANILA_BUSINESS')),
    [attainment_percent] DECIMAL(5,2) NULL,
    [enforced] INT NOT NULL CONSTRAINT [DF_sla_target_type_enforced] DEFAULT (0) CONSTRAINT [CK_sla_target_type_06] CHECK (enforced IN (0, 1)),
    [note] NVARCHAR(MAX) NULL,
    CONSTRAINT [PK_sla_target_type] PRIMARY KEY ([board_id], [record_type], [priority], [clock])
);
END;

-- --------------------------------------------------------------------------
-- change_approval   (from schema/022_record_type.sql)
-- The authorisation record. Append-only: a decision is evidence, and a later
-- decision is a new row, never an edit. The person who owns the change cannot
-- authorise it (separation of duties; enforced in board.decide_change).
IF OBJECT_ID(N'psa.[change_approval]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[change_approval] (
    [approval_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_change_approval] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_change_approval_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [decided_by] NVARCHAR(200) NOT NULL,
    [authority] NVARCHAR(32) NOT NULL CONSTRAINT [CK_change_approval_01] CHECK (authority IN ('CHANGE_AUTHORITY', 'CAB', 'ECAB', 'CLIENT')),
    [decision] NVARCHAR(32) NOT NULL CONSTRAINT [CK_change_approval_02] CHECK (decision IN ('APPROVED', 'DECLINED')),
    [decided_at] NVARCHAR(64) NOT NULL,
    [comment] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [decided_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [decided_at], 126), CASE WHEN [decided_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [decided_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_link   (from schema/022_record_type.sql)
-- ------------------------------------------------ incident -> problem -> change
--
-- ITIL's chain: incidents are linked to the problem that causes them, and a
-- problem (or anything else) to the change that fixes it. The reference PSA does this
-- by bundling child tickets under a parent, which stops workflow and billing on
-- the children and is a known cause of SLA reports running for years on open
-- children (VERIFIED, visionary360.com/the-hidden-sla-killer-in-connectwise-psa-
-- child-merged-tickets/). A link here changes neither ticket: each keeps its
-- own clocks, status and time.
--
-- This is not handover. One fault worked by two teams is still ONE ticket that
-- moves (005, board.move): two tickets each waiting on the other is what produced
-- the twenty-five day MRI-to-PACS outage. A link joins two different pieces of
-- work, such as twelve incidents and the one problem behind them.
IF OBJECT_ID(N'psa.[ticket_link]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_link] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_link_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [linked_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_link_linked_id] REFERENCES psa.[ticket]([work_item_id]),
    [relation] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_link_01] CHECK (relation IN ('CAUSED_BY', 'FIXED_BY', 'RELATED')),
    [linked_at] NVARCHAR(64) NOT NULL,
    [linked_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [linked_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [linked_at], 126), CASE WHEN [linked_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [linked_at], 112) END)),
    CONSTRAINT [PK_ticket_link] PRIMARY KEY ([work_item_id], [linked_id])
);
END;

-- --------------------------------------------------------------------------
-- notification   (from schema/024_workflow_runner.sql)
-- A NOTIFY or ESCALATE action writes here. The desk sends no mail yet: this is
-- the queue a sender works through, and until one exists it is what the desk
-- shows as "who was told what". Nothing is lost for the lack of a sender.
IF OBJECT_ID(N'psa.[notification]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[notification] (
    [notification_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_notification] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_notification_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [event_id] NVARCHAR(64) NULL CONSTRAINT [FK_notification_event_id] REFERENCES psa.[workflow_event]([event_id]),

    -- a member id or an address
    [recipient] NVARCHAR(400) NOT NULL,

    -- the board role it was resolved from
    [recipient_role] NVARCHAR(32) NULL,

    -- carries the ticket token, e.g. [PMC-000123]
    [subject] NVARCHAR(400) NOT NULL,
    [body] NVARCHAR(MAX) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_notification_status] DEFAULT ('PENDING') CONSTRAINT [CK_notification_01] CHECK (status IN ('PENDING', 'SENT', 'FAILED', 'NO_SENDER')),
    [sent_at] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [sent_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [sent_at], 126), CASE WHEN [sent_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [sent_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_template   (from schema/026_tasks_templates.sql)
IF OBJECT_ID(N'psa.[ticket_template]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_template] (
    [template_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_ticket_template] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_template_board_id] REFERENCES psa.[board]([board_id]),
    [name] NVARCHAR(400) NOT NULL,
    [summary] NVARCHAR(400) NULL,
    [record_type] NVARCHAR(32) NULL CONSTRAINT [CK_ticket_template_01] CHECK (record_type IN ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT')),
    [catalogue_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_template_catalogue_item_id] REFERENCES psa.[catalogue_item]([catalogue_item_id]),
    [description] NVARCHAR(MAX) NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_ticket_template_inactive] DEFAULT (0) CONSTRAINT [CK_ticket_template_02] CHECK (inactive IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_template_task   (from schema/026_tasks_templates.sql)
IF OBJECT_ID(N'psa.[ticket_template_task]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_template_task] (
    [template_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_template_task_template_id] REFERENCES psa.[ticket_template]([template_id]),
    [sort_order] INT NOT NULL,
    [text] NVARCHAR(400) NOT NULL,
    CONSTRAINT [PK_ticket_template_task] PRIMARY KEY ([template_id], [sort_order])
);
END;

-- --------------------------------------------------------------------------
-- ticket_task   (from schema/026_tasks_templates.sql)
-- A ticket's checklist. Done is a time and a person, never a bare flag: who
-- ticked it off is what an audit asks.
IF OBJECT_ID(N'psa.[ticket_task]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_task] (
    [task_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_task] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_task_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [text] NVARCHAR(400) NOT NULL,
    [sort_order] INT NOT NULL CONSTRAINT [DF_ticket_task_sort_order] DEFAULT (0),
    [template_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_task_template_id] REFERENCES psa.[ticket_template]([template_id]),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,
    [done_at] NVARCHAR(64) NULL,
    [done_by] NVARCHAR(200) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [done_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [done_at], 126), CASE WHEN [done_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [done_at], 112) END)),
    CONSTRAINT [CK_ticket_task_01] CHECK ((((done_at IS NULL) AND (done_by IS NULL)) OR (NOT (done_at IS NULL) AND NOT (done_by IS NULL))))
);
END;

-- --------------------------------------------------------------------------
-- attachment   (from schema/027_attachments.sql)
IF OBJECT_ID(N'psa.[attachment]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[attachment] (
    [attachment_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_attachment] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_attachment_work_item_id] REFERENCES psa.[ticket]([work_item_id]),

    -- cleaned; never used as a path
    [filename] NVARCHAR(400) NOT NULL,

    -- from the file's own bytes
    [media_type] NVARCHAR(400) NOT NULL,
    [size_received] INT NOT NULL CONSTRAINT [CK_attachment_01] CHECK (size_received > 0),
    [size_stored] INT NOT NULL CONSTRAINT [CK_attachment_02] CHECK (size_stored > 0),

    -- of the file as served; also its name on disk
    [sha256] NVARCHAR(64) NOT NULL,
    [encoding] NVARCHAR(32) NOT NULL CONSTRAINT [CK_attachment_03] CHECK (encoding IN ('IDENTITY', 'GZIP')),

    -- what compression did, in words
    [treatment] NVARCHAR(400) NOT NULL,
    [source] NVARCHAR(32) NOT NULL CONSTRAINT [CK_attachment_04] CHECK (source IN ('DESK', 'PORTAL', 'EMAIL')),
    [uploaded_by] NVARCHAR(200) NOT NULL,
    [uploaded_at] NVARCHAR(64) NOT NULL,
    [review_status] NVARCHAR(32) NOT NULL CONSTRAINT [CK_attachment_05] CHECK (review_status IN ('PENDING', 'CLEARED', 'WITHHELD')),
    [reviewed_by] NVARCHAR(200) NULL,
    [reviewed_at] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [uploaded_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [uploaded_at], 126), CASE WHEN [uploaded_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [uploaded_at], 112) END)),
    [reviewed_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [reviewed_at], 126), CASE WHEN [reviewed_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [reviewed_at], 112) END)),
    CONSTRAINT [CK_attachment_06] CHECK ((((review_status = 'PENDING') AND (reviewed_by IS NULL)) OR (NOT (review_status = 'PENDING') AND NOT (reviewed_by IS NULL))))
);
END;

-- --------------------------------------------------------------------------
-- user_view   (from schema/031_views_and_standard_notes.sql)
IF OBJECT_ID(N'psa.[user_view]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[user_view] (
    [view_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_user_view] PRIMARY KEY,

    -- the person, as board_member.member
    [member] NVARCHAR(200) NOT NULL,
    [name] NVARCHAR(400) NOT NULL,

    -- the board's query string, e.g. board=IT_HELP&pri=P1
    [query] NVARCHAR(MAX) NOT NULL,
    [sort_order] INT NOT NULL CONSTRAINT [DF_user_view_sort_order] DEFAULT (0),
    [created_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- standard_note   (from schema/031_views_and_standard_notes.sql)
IF OBJECT_ID(N'psa.[standard_note]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[standard_note] (
    [note_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_standard_note] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_standard_note_board_id] REFERENCES psa.[board]([board_id]),

    -- what the picker shows
    [name] NVARCHAR(400) NOT NULL,

    -- what lands in the note box
    [body] NVARCHAR(MAX) NOT NULL,
    [flag] NVARCHAR(32) NOT NULL CONSTRAINT [CK_standard_note_01] CHECK (flag IN ('DISCUSSION', 'INTERNAL')),
    [inactive] INT NOT NULL CONSTRAINT [DF_standard_note_inactive] DEFAULT (0) CONSTRAINT [CK_standard_note_02] CHECK (inactive IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ticket_schedule   (from schema/032_merge_schedule_survey.sql)
IF OBJECT_ID(N'psa.[ticket_schedule]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_schedule] (
    [schedule_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ticket_schedule] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_schedule_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [member] NVARCHAR(200) NOT NULL,
    [starts_at] NVARCHAR(64) NOT NULL,
    [ends_at] NVARCHAR(64) NOT NULL,
    [note] NVARCHAR(MAX) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [starts_at], 126), CASE WHEN [starts_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [starts_at], 112) END)),
    [ends_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [ends_at], 126), CASE WHEN [ends_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [ends_at], 112) END)),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    CONSTRAINT [CK_ticket_schedule_01] CHECK (ends_at > starts_at)
);
END;

-- --------------------------------------------------------------------------
-- survey_response   (from schema/032_merge_schedule_survey.sql)
IF OBJECT_ID(N'psa.[survey_response]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[survey_response] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_survey_response] PRIMARY KEY CONSTRAINT [FK_survey_response_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [score] INT NOT NULL CONSTRAINT [CK_survey_response_01] CHECK (score BETWEEN 1 AND 5),
    [comment] NVARCHAR(MAX) NULL,
    [answered_by] NVARCHAR(200) NOT NULL,
    [answered_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [answered_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [answered_at], 126), CASE WHEN [answered_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [answered_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- work_role   (from schema/033_time_entry.sql)
-- Dada PSA's WorkRole and WorkType, as the desk needs them: a name, whether
-- it is still offered, and for a type the bill default Dada PSA gives it
-- (WorkType.billTime: Billable, DoNotBill, NoCharge). Setup › Time edits both.
IF OBJECT_ID(N'psa.[work_role]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[work_role] (
    [work_role_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_work_role] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_work_role_inactive] DEFAULT (0) CONSTRAINT [CK_work_role_01] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_work_role_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- work_type   (from schema/033_time_entry.sql)
IF OBJECT_ID(N'psa.[work_type]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[work_type] (
    [work_type_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_work_type] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [bill_time] NVARCHAR(32) NOT NULL CONSTRAINT [DF_work_type_bill_time] DEFAULT ('BILLABLE') CONSTRAINT [CK_work_type_01] CHECK (bill_time IN ('BILLABLE', 'DO_NOT_BILL', 'NO_CHARGE')),
    [inactive] INT NOT NULL CONSTRAINT [DF_work_type_inactive] DEFAULT (0) CONSTRAINT [CK_work_type_02] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_work_type_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- department   (from schema/034_departments.sql)
IF OBJECT_ID(N'psa.[department]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[department] (
    [name] NVARCHAR(400) NOT NULL CONSTRAINT [PK_department] PRIMARY KEY,
    [source] NVARCHAR(32) NOT NULL CONSTRAINT [DF_department_source] DEFAULT ('MANUAL') CONSTRAINT [CK_department_01] CHECK (source IN ('PAYROLL', 'MANUAL')),
    [retired] INT NOT NULL CONSTRAINT [DF_department_retired] DEFAULT (0) CONSTRAINT [CK_department_02] CHECK (retired IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,
    [last_seen_at] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [last_seen_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_seen_at], 126), CASE WHEN [last_seen_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_seen_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- department_board   (from schema/034_departments.sql)
IF OBJECT_ID(N'psa.[department_board]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[department_board] (
    [department] NVARCHAR(400) NOT NULL CONSTRAINT [FK_department_board_department] REFERENCES psa.[department]([name]),
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_department_board_board_id] REFERENCES psa.[board]([board_id]),
    [ticked_at] NVARCHAR(64) NOT NULL,
    [ticked_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [ticked_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [ticked_at], 126), CASE WHEN [ticked_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [ticked_at], 112) END)),
    CONSTRAINT [PK_department_board] PRIMARY KEY ([department], [board_id])
);
END;

-- --------------------------------------------------------------------------
-- schedule_status   (from schema/038_schedule.sql)
IF OBJECT_ID(N'psa.[schedule_status]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[schedule_status] (
    [status_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_schedule_status] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [is_default] INT NOT NULL CONSTRAINT [DF_schedule_status_is_default] DEFAULT (0) CONSTRAINT [CK_schedule_status_01] CHECK (is_default IN (0, 1)),
    [inactive] INT NOT NULL CONSTRAINT [DF_schedule_status_inactive] DEFAULT (0) CONSTRAINT [CK_schedule_status_02] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_schedule_status_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- service_location   (from schema/038_schedule.sql)
IF OBJECT_ID(N'psa.[service_location]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[service_location] (
    [location_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_service_location] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_service_location_inactive] DEFAULT (0) CONSTRAINT [CK_service_location_01] CHECK (inactive IN (0, 1))
);
END;

-- --------------------------------------------------------------------------
-- schedule_block   (from schema/038_schedule.sql)
-- What is on a person's schedule that is not a ticket. TIME_OFF blocks a
-- visit outright; a MEETING or an ACTIVITY is a clash like any other, which
-- "allow the double booking" can override.
IF OBJECT_ID(N'psa.[schedule_block]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[schedule_block] (
    [block_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_schedule_block] PRIMARY KEY,
    [member] NVARCHAR(200) NOT NULL,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_schedule_block_01] CHECK (kind IN ('MEETING', 'ACTIVITY', 'TIME_OFF')),
    [name] NVARCHAR(400) NOT NULL,
    [starts_at] NVARCHAR(64) NOT NULL,
    [ends_at] NVARCHAR(64) NOT NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [starts_at], 126), CASE WHEN [starts_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [starts_at], 112) END)),
    [ends_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [ends_at], 126), CASE WHEN [ends_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [ends_at], 112) END)),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    CONSTRAINT [CK_schedule_block_02] CHECK (ends_at > starts_at)
);
END;

-- --------------------------------------------------------------------------
-- kb_article   (from schema/039_knowledge.sql)
IF OBJECT_ID(N'psa.[kb_article]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[kb_article] (
    -- 'KB-0001'
    [article_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_kb_article] PRIMARY KEY,
    [title] NVARCHAR(400) NOT NULL,
    [body] NVARCHAR(MAX) NOT NULL,
    [audience] NVARCHAR(32) NOT NULL CONSTRAINT [DF_kb_article_audience] DEFAULT ('INTERNAL') CONSTRAINT [CK_kb_article_01] CHECK (audience IN ('INTERNAL', 'REQUESTER')),
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_kb_article_status] DEFAULT ('DRAFT') CONSTRAINT [CK_kb_article_02] CHECK (status IN ('DRAFT', 'PUBLISHED', 'RETIRED')),
    [board_id] NVARCHAR(64) NULL CONSTRAINT [FK_kb_article_board_id] REFERENCES psa.[board]([board_id]),
    [catalogue_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_kb_article_catalogue_item_id] REFERENCES psa.[catalogue_item]([catalogue_item_id]),
    [version] INT NOT NULL CONSTRAINT [DF_kb_article_version] DEFAULT (1),
    [uses] INT NOT NULL CONSTRAINT [DF_kb_article_uses] DEFAULT (0),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,
    [updated_at] NVARCHAR(64) NOT NULL,
    [updated_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- kb_revision   (from schema/039_knowledge.sql)
IF OBJECT_ID(N'psa.[kb_revision]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[kb_revision] (
    [article_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_kb_revision_article_id] REFERENCES psa.[kb_article]([article_id]),
    [version] INT NOT NULL,
    [title] NVARCHAR(400) NOT NULL,
    [body] NVARCHAR(MAX) NOT NULL,
    [saved_at] NVARCHAR(64) NOT NULL,
    [saved_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [saved_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [saved_at], 126), CASE WHEN [saved_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [saved_at], 112) END)),
    CONSTRAINT [PK_kb_revision] PRIMARY KEY ([article_id], [version])
);
END;

-- --------------------------------------------------------------------------
-- kb_ticket   (from schema/039_knowledge.sql)
IF OBJECT_ID(N'psa.[kb_ticket]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[kb_ticket] (
    [article_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_kb_ticket_article_id] REFERENCES psa.[kb_article]([article_id]),
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_kb_ticket_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [linked_at] NVARCHAR(64) NOT NULL,
    [linked_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [linked_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [linked_at], 126), CASE WHEN [linked_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [linked_at], 112) END)),
    CONSTRAINT [PK_kb_ticket] PRIMARY KEY ([article_id], [work_item_id])
);
END;

-- --------------------------------------------------------------------------
-- security_role   (from schema/040_security_roles.sql)
IF OBJECT_ID(N'psa.[security_role]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[security_role] (
    [role_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_security_role] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [is_default] INT NOT NULL CONSTRAINT [DF_security_role_is_default] DEFAULT (0) CONSTRAINT [CK_security_role_01] CHECK (is_default IN (0, 1)),
    [inactive] INT NOT NULL CONSTRAINT [DF_security_role_inactive] DEFAULT (0) CONSTRAINT [CK_security_role_02] CHECK (inactive IN (0, 1))
);
END;

-- --------------------------------------------------------------------------
-- role_permission   (from schema/040_security_roles.sql)
IF OBJECT_ID(N'psa.[role_permission]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[role_permission] (
    [role_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_role_permission_role_id] REFERENCES psa.[security_role]([role_id]),
    [module] NVARCHAR(32) NOT NULL CONSTRAINT [CK_role_permission_01] CHECK (module IN ('KNOWLEDGE', 'PROJECTS', 'REPORTS', 'SCHEDULE', 'FINANCE')),
    [level] NVARCHAR(32) NOT NULL CONSTRAINT [CK_role_permission_02] CHECK (level IN ('NONE', 'READ', 'WRITE', 'ADMIN')),
    CONSTRAINT [PK_role_permission] PRIMARY KEY ([role_id], [module])
);
END;

-- --------------------------------------------------------------------------
-- member_role   (from schema/040_security_roles.sql)
IF OBJECT_ID(N'psa.[member_role]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[member_role] (
    [member] NVARCHAR(200) NOT NULL CONSTRAINT [PK_member_role] PRIMARY KEY,
    [role_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_member_role_role_id] REFERENCES psa.[security_role]([role_id]),
    [assigned_at] NVARCHAR(64) NOT NULL,
    [assigned_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [assigned_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [assigned_at], 126), CASE WHEN [assigned_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [assigned_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- project   (from schema/041_projects.sql)
IF OBJECT_ID(N'psa.[project]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project] (
    -- 'PRJ-0001'
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_project] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [board_id] NVARCHAR(64) NULL CONSTRAINT [FK_project_board_id] REFERENCES psa.[board]([board_id]),
    [manager] NVARCHAR(200) NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_project_status] DEFAULT ('PLANNED') CONSTRAINT [CK_project_01] CHECK (status IN ('PLANNED', 'ACTIVE', 'ON_HOLD', 'DONE', 'CANCELLED')),
    [starts_on] NVARCHAR(32) NULL,
    [ends_on] NVARCHAR(32) NULL,
    [budget_hours] DECIMAL(9,2) NULL,
    [description] NVARCHAR(MAX) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_on_parsed] AS (CASE WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 112) WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 23) END),
    [ends_on_parsed] AS (CASE WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 112) WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 23) END),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- project_phase   (from schema/041_projects.sql)
IF OBJECT_ID(N'psa.[project_phase]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_phase] (
    [phase_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_project_phase] PRIMARY KEY,
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_phase_project_id] REFERENCES psa.[project]([project_id]),
    [parent_id] INT NULL CONSTRAINT [FK_project_phase_parent_id] REFERENCES psa.[project_phase]([phase_id]),
    [name] NVARCHAR(400) NOT NULL,
    [sort_order] INT NOT NULL CONSTRAINT [DF_project_phase_sort_order] DEFAULT (0),
    [starts_on] NVARCHAR(32) NULL,
    [ends_on] NVARCHAR(32) NULL,
    [budget_hours] DECIMAL(9,2) NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_project_phase_status] DEFAULT ('OPEN') CONSTRAINT [CK_project_phase_01] CHECK (status IN ('OPEN', 'DONE')),
    [created_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_on_parsed] AS (CASE WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 112) WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 23) END),
    [ends_on_parsed] AS (CASE WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 112) WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 23) END),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- phase_dependency   (from schema/041_projects.sql)
IF OBJECT_ID(N'psa.[phase_dependency]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[phase_dependency] (
    [phase_id] INT NOT NULL CONSTRAINT [FK_phase_dependency_phase_id] REFERENCES psa.[project_phase]([phase_id]),
    [depends_on] INT NOT NULL CONSTRAINT [FK_phase_dependency_depends_on] REFERENCES psa.[project_phase]([phase_id]),
    CONSTRAINT [PK_phase_dependency] PRIMARY KEY ([phase_id], [depends_on]),
    CONSTRAINT [CK_phase_dependency_01] CHECK (phase_id <> depends_on)
);
END;

-- --------------------------------------------------------------------------
-- project_ticket   (from schema/041_projects.sql)
IF OBJECT_ID(N'psa.[project_ticket]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_ticket] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_project_ticket] PRIMARY KEY CONSTRAINT [FK_project_ticket_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_ticket_project_id] REFERENCES psa.[project]([project_id]),
    [phase_id] INT NULL CONSTRAINT [FK_project_ticket_phase_id] REFERENCES psa.[project_phase]([phase_id]),
    [linked_at] NVARCHAR(64) NOT NULL,
    [linked_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [linked_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [linked_at], 126), CASE WHEN [linked_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [linked_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- report_def   (from schema/042_report_defs.sql)
IF OBJECT_ID(N'psa.[report_def]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[report_def] (
    [report_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_report_def] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [dataset] NVARCHAR(32) NOT NULL CONSTRAINT [CK_report_def_01] CHECK (dataset IN ('TICKETS', 'TIME', 'VISITS', 'PROJECTS', 'KNOWLEDGE')),
    [columns] NVARCHAR(400) NOT NULL,
    [group_by] NVARCHAR(64) NULL,
    [filters] NVARCHAR(400) NULL,
    [owner] NVARCHAR(200) NOT NULL,
    [shared] INT NOT NULL CONSTRAINT [DF_report_def_shared] DEFAULT (0) CONSTRAINT [CK_report_def_02] CHECK (shared IN (0, 1)),
    [pinned] INT NOT NULL CONSTRAINT [DF_report_def_pinned] DEFAULT (0) CONSTRAINT [CK_report_def_03] CHECK (pinned IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ext_source   (from schema/043_bizbox_mirror.sql)
IF OBJECT_ID(N'psa.[ext_source]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_source] (
    -- 'BIZBOX'
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_ext_source] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [last_sync_at] NVARCHAR(64) NULL,
    [last_sync_by] NVARCHAR(200) NULL,
    [last_result] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [last_sync_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_sync_at], 126), CASE WHEN [last_sync_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_sync_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- ext_agreement   (from schema/043_bizbox_mirror.sql)
IF OBJECT_ID(N'psa.[ext_agreement]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_agreement] (
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ext_agreement_source_id] REFERENCES psa.[ext_source]([source_id]),
    [ext_ref] NVARCHAR(400) NOT NULL,
    [name] NVARCHAR(400) NOT NULL,
    [party] NVARCHAR(400) NULL,
    [starts_on] NVARCHAR(32) NULL,
    [ends_on] NVARCHAR(32) NULL,
    [status] NVARCHAR(32) NULL,
    [amount] DECIMAL(19,4) NULL,
    [currency] NVARCHAR(32) NULL,
    [present] INT NOT NULL CONSTRAINT [DF_ext_agreement_present] DEFAULT (1) CONSTRAINT [CK_ext_agreement_01] CHECK (present IN (0, 1)),
    [synced_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_on_parsed] AS (CASE WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 112) WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 23) END),
    [ends_on_parsed] AS (CASE WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 112) WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 23) END),
    [synced_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [synced_at], 126), CASE WHEN [synced_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [synced_at], 112) END)),
    CONSTRAINT [PK_ext_agreement] PRIMARY KEY ([source_id], [ext_ref])
);
END;

-- --------------------------------------------------------------------------
-- ext_product   (from schema/043_bizbox_mirror.sql)
IF OBJECT_ID(N'psa.[ext_product]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_product] (
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ext_product_source_id] REFERENCES psa.[ext_source]([source_id]),
    [ext_ref] NVARCHAR(400) NOT NULL,
    [name] NVARCHAR(400) NOT NULL,
    [category] NVARCHAR(400) NULL,
    [unit] NVARCHAR(32) NULL,
    [unit_cost] DECIMAL(19,4) NULL,
    [present] INT NOT NULL CONSTRAINT [DF_ext_product_present] DEFAULT (1) CONSTRAINT [CK_ext_product_01] CHECK (present IN (0, 1)),
    [synced_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [synced_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [synced_at], 126), CASE WHEN [synced_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [synced_at], 112) END)),
    CONSTRAINT [PK_ext_product] PRIMARY KEY ([source_id], [ext_ref])
);
END;

-- --------------------------------------------------------------------------
-- ext_purchase_order   (from schema/043_bizbox_mirror.sql)
IF OBJECT_ID(N'psa.[ext_purchase_order]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_purchase_order] (
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ext_purchase_order_source_id] REFERENCES psa.[ext_source]([source_id]),
    [ext_ref] NVARCHAR(400) NOT NULL,
    [vendor] NVARCHAR(400) NULL,
    [ordered_on] NVARCHAR(32) NULL,
    [status] NVARCHAR(32) NULL,
    [total] DECIMAL(19,4) NULL,
    [currency] NVARCHAR(32) NULL,
    [present] INT NOT NULL CONSTRAINT [DF_ext_purchase_order_present] DEFAULT (1) CONSTRAINT [CK_ext_purchase_order_01] CHECK (present IN (0, 1)),
    [synced_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [ordered_on_parsed] AS (CASE WHEN [ordered_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [ordered_on], 112) WHEN [ordered_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [ordered_on], 23) END),
    [synced_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [synced_at], 126), CASE WHEN [synced_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [synced_at], 112) END)),
    CONSTRAINT [PK_ext_purchase_order] PRIMARY KEY ([source_id], [ext_ref])
);
END;

-- --------------------------------------------------------------------------
-- ext_invoice   (from schema/043_bizbox_mirror.sql)
IF OBJECT_ID(N'psa.[ext_invoice]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_invoice] (
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ext_invoice_source_id] REFERENCES psa.[ext_source]([source_id]),
    [ext_ref] NVARCHAR(400) NOT NULL,
    [party] NVARCHAR(400) NULL,
    [invoiced_on] NVARCHAR(32) NULL,
    [due_on] NVARCHAR(32) NULL,
    [status] NVARCHAR(32) NULL,
    [total] DECIMAL(19,4) NULL,
    [currency] NVARCHAR(32) NULL,
    [agreement_ref] NVARCHAR(400) NULL,
    [present] INT NOT NULL CONSTRAINT [DF_ext_invoice_present] DEFAULT (1) CONSTRAINT [CK_ext_invoice_01] CHECK (present IN (0, 1)),
    [synced_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [invoiced_on_parsed] AS (CASE WHEN [invoiced_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [invoiced_on], 112) WHEN [invoiced_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [invoiced_on], 23) END),
    [due_on_parsed] AS (CASE WHEN [due_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [due_on], 112) WHEN [due_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [due_on], 23) END),
    [synced_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [synced_at], 126), CASE WHEN [synced_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [synced_at], 112) END)),
    CONSTRAINT [PK_ext_invoice] PRIMARY KEY ([source_id], [ext_ref])
);
END;

-- --------------------------------------------------------------------------
-- ext_link   (from schema/043_bizbox_mirror.sql)
-- A ticket or a project names the BizBox record it concerns: the PO a
-- replacement printer was bought on, the agreement a vendor visit is under.
IF OBJECT_ID(N'psa.[ext_link]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_link] (
    [subject_kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ext_link_01] CHECK (subject_kind IN ('TICKET', 'PROJECT')),
    [subject_id] NVARCHAR(64) NOT NULL,
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ext_link_source_id] REFERENCES psa.[ext_source]([source_id]),
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ext_link_02] CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE')),
    [ext_ref] NVARCHAR(400) NOT NULL,
    [linked_at] NVARCHAR(64) NOT NULL,
    [linked_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [linked_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [linked_at], 126), CASE WHEN [linked_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [linked_at], 112) END)),
    CONSTRAINT [PK_ext_link] PRIMARY KEY ([subject_kind], [subject_id], [source_id], [kind], [ext_ref])
);
END;

-- --------------------------------------------------------------------------
-- ext_po_line   (from schema/043_bizbox_mirror.sql)
-- A purchase order's lines, as the reference PSA shows them under a PO: the
-- item, its description, quantity ordered and received, and unit cost. Keyed
-- by BizBox's own line reference; po_ref ties it to its order.
IF OBJECT_ID(N'psa.[ext_po_line]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_po_line] (
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ext_po_line_source_id] REFERENCES psa.[ext_source]([source_id]),
    [ext_ref] NVARCHAR(400) NOT NULL,
    [po_ref] NVARCHAR(400) NOT NULL,
    [line_no] INT NULL,
    [product_ref] NVARCHAR(400) NULL,
    [description] NVARCHAR(400) NULL,
    [quantity] DECIMAL(19,4) NULL,
    [received_qty] DECIMAL(19,4) NULL,
    [unit_cost] DECIMAL(19,4) NULL,
    [present] INT NOT NULL CONSTRAINT [DF_ext_po_line_present] DEFAULT (1) CONSTRAINT [CK_ext_po_line_01] CHECK (present IN (0, 1)),
    [synced_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [synced_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [synced_at], 126), CASE WHEN [synced_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [synced_at], 112) END)),
    CONSTRAINT [PK_ext_po_line] PRIMARY KEY ([source_id], [ext_ref])
);
END;

-- --------------------------------------------------------------------------
-- ext_change   (from schema/043_bizbox_mirror.sql)
-- Room for edits back to BizBox, later. A person proposes a change to a
-- mirrored field; it is recorded here, PENDING, and BizBox is NOT touched. When
-- a write path is approved (a BizBox API or a stored procedure SQL01 creates),
-- a writer takes PENDING rows, applies them, and marks each APPLIED or
-- REJECTED with BizBox's answer; the next sync then shows the new value. Until
-- then the desk says plainly that BizBox has not changed.
IF OBJECT_ID(N'psa.[ext_change]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ext_change] (
    [change_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_ext_change] PRIMARY KEY,
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ext_change_source_id] REFERENCES psa.[ext_source]([source_id]),
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ext_change_01] CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE')),
    [ext_ref] NVARCHAR(400) NOT NULL,
    [field] NVARCHAR(32) NOT NULL,
    [old_value] NVARCHAR(400) NULL,
    [new_value] NVARCHAR(400) NULL,
    [reason] NVARCHAR(MAX) NOT NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_ext_change_status] DEFAULT ('PENDING') CONSTRAINT [CK_ext_change_02] CHECK (status IN ('PENDING', 'APPLIED', 'REJECTED', 'CANCELLED')),
    [requested_at] NVARCHAR(64) NOT NULL,
    [requested_by] NVARCHAR(200) NOT NULL,
    [decided_at] NVARCHAR(64) NULL,
    [decided_by] NVARCHAR(200) NULL,
    [answer] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [requested_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [requested_at], 126), CASE WHEN [requested_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [requested_at], 112) END)),
    [decided_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [decided_at], 126), CASE WHEN [decided_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [decided_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- agreement   (from schema/045_agreements.sql)
IF OBJECT_ID(N'psa.[agreement]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[agreement] (
    -- AGR-0001
    [agreement_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_agreement] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,

    -- the supplier, as BizBox names it
    [party] NVARCHAR(400) NULL,
    [starts_on] NVARCHAR(32) NULL,
    [ends_on] NVARCHAR(32) NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_agreement_status] DEFAULT ('DRAFT') CONSTRAINT [CK_agreement_01] CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'CANCELLED')),
    [amount] DECIMAL(19,4) NULL,
    [currency] NVARCHAR(32) NULL,
    [notes] NVARCHAR(MAX) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,
    [updated_at] NVARCHAR(64) NOT NULL,
    [updated_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_on_parsed] AS (CASE WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 112) WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 23) END),
    [ends_on_parsed] AS (CASE WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 112) WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 23) END),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- agreement_item   (from schema/045_agreements.sql)
-- What an agreement covers: a mirrored BizBox invoice, purchase order or
-- product, by the mirror's own key. A row here is the desk's; the sync
-- marks a mirrored record absent but never removes it, so a covering
-- survives, and the page says the record is gone from BizBox.
IF OBJECT_ID(N'psa.[agreement_item]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[agreement_item] (
    [agreement_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_agreement_item_agreement_id] REFERENCES psa.[agreement]([agreement_id]),
    [source_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_agreement_item_source_id] REFERENCES psa.[ext_source]([source_id]),
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_agreement_item_01] CHECK (kind IN ('INVOICE', 'PURCHASE_ORDER', 'PRODUCT')),
    [ext_ref] NVARCHAR(200) NOT NULL,
    [added_at] NVARCHAR(64) NOT NULL,
    [added_by] NVARCHAR(200) NOT NULL,
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [added_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [added_at], 126), CASE WHEN [added_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [added_at], 112) END)),
    CONSTRAINT [PK_agreement_item] PRIMARY KEY ([agreement_id], [source_id], [kind], [ext_ref])
);
END;

-- --------------------------------------------------------------------------
-- timesheet   (from schema/046_timesheets.sql)
IF OBJECT_ID(N'psa.[timesheet]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[timesheet] (
    [timesheet_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_timesheet] PRIMARY KEY,

    -- time_entry.performed_by, as spelt there
    [member] NVARCHAR(200) NOT NULL,

    -- the Monday, YYYY-MM-DD
    [week_start] NVARCHAR(32) NOT NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_timesheet_status] DEFAULT ('OPEN') CONSTRAINT [CK_timesheet_01] CHECK (status IN ('OPEN', 'SUBMITTED', 'APPROVED', 'REJECTED')),
    [created_at] NVARCHAR(64) NOT NULL,
    [submitted_at] NVARCHAR(64) NULL,
    [submitted_by] NVARCHAR(200) NULL,
    [decided_at] NVARCHAR(64) NULL,
    [decided_by] NVARCHAR(200) NULL,

    -- the decision's reason, or why it was reopened
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [week_start_parsed] AS (CASE WHEN [week_start] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [week_start], 112) WHEN [week_start] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [week_start], 23) END),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [submitted_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [submitted_at], 126), CASE WHEN [submitted_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [submitted_at], 112) END)),
    [decided_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [decided_at], 126), CASE WHEN [decided_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [decided_at], 112) END)),
    CONSTRAINT [UQ_timesheet] UNIQUE ([member], [week_start])
);
END;

-- --------------------------------------------------------------------------
-- timesheet_event   (from schema/046_timesheets.sql)
-- Append-only: submit, approve, reject, reopen, each with who and when.
IF OBJECT_ID(N'psa.[timesheet_event]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[timesheet_event] (
    [event_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_timesheet_event] PRIMARY KEY,
    [timesheet_id] INT NOT NULL CONSTRAINT [FK_timesheet_event_timesheet_id] REFERENCES psa.[timesheet]([timesheet_id]),
    [occurred_at] NVARCHAR(64) NOT NULL,
    [actor] NVARCHAR(200) NOT NULL,
    [action] NVARCHAR(32) NOT NULL CONSTRAINT [CK_timesheet_event_01] CHECK (action IN ('SUBMIT', 'APPROVE', 'REJECT', 'REOPEN')),
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [occurred_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [occurred_at], 126), CASE WHEN [occurred_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [occurred_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- member_capacity   (from schema/046_timesheets.sql)
-- Hours a week a person is expected to record, for the utilisation figure.
-- Unset means the desk's default (40). Not the capacity declaration of 003,
-- which is the client's denominator for the uplift; this is the team's own.
IF OBJECT_ID(N'psa.[member_capacity]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[member_capacity] (
    [member] NVARCHAR(200) NOT NULL CONSTRAINT [PK_member_capacity] PRIMARY KEY,
    [hours_per_week] DECIMAL(9,2) NOT NULL,
    [set_at] NVARCHAR(64) NOT NULL,
    [set_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [set_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [set_at], 126), CASE WHEN [set_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [set_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- role_grant   (from schema/046_timesheets.sql)
-- The module vocabulary belongs to the code (security.MODULES), not to a
-- CHECK. 040's role_permission listed five modules in its CHECK, so the sixth
-- (Timesheets) could not be written into it on either store: OR IGNORE
-- swallowed the refusal and every role silently had no level. role_grant takes
-- its place: the same key and levels, no list of modules. The rows already in
-- role_permission are read across by the desk the first time a role is
-- looked up (security.ensure_roles). role_permission stays, superseded and
-- unread, because the port never drops a table on a live database.
IF OBJECT_ID(N'psa.[role_grant]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[role_grant] (
    [role_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_role_grant_role_id] REFERENCES psa.[security_role]([role_id]),
    [module] NVARCHAR(32) NOT NULL,
    [level] NVARCHAR(32) NOT NULL CONSTRAINT [CK_role_grant_01] CHECK (level IN ('NONE', 'READ', 'WRITE', 'ADMIN')),
    CONSTRAINT [PK_role_grant] PRIMARY KEY ([role_id], [module])
);
END;

-- --------------------------------------------------------------------------
-- recurrence   (from schema/047_recurring.sql)
IF OBJECT_ID(N'psa.[recurrence]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[recurrence] (
    [recurrence_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_recurrence] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_recurrence_board_id] REFERENCES psa.[board]([board_id]),
    [template_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_recurrence_template_id] REFERENCES psa.[ticket_template]([template_id]),
    [cadence] NVARCHAR(32) NOT NULL CONSTRAINT [CK_recurrence_01] CHECK (cadence IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')),
    [every_n] INT NOT NULL CONSTRAINT [DF_recurrence_every_n] DEFAULT (1),

    -- the day of the month the series was set on
    [anchor_day] INT NOT NULL,

    -- YYYY-MM-DD
    [next_due_on] NVARCHAR(32) NOT NULL,

    -- a board member, or NULL for the board's queue
    [owner] NVARCHAR(200) NULL,
    [entity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_recurrence_entity_id] REFERENCES psa.[entity]([entity_id]),
    [contact_id] NVARCHAR(64) NULL CONSTRAINT [FK_recurrence_contact_id] REFERENCES psa.[contact]([contact_id]),
    [configuration_id] NVARCHAR(64) NULL CONSTRAINT [FK_recurrence_configuration_id] REFERENCES psa.[configuration]([configuration_id]),
    [impact] NVARCHAR(32) NOT NULL CONSTRAINT [DF_recurrence_impact] DEFAULT ('I3') CONSTRAINT [CK_recurrence_02] CHECK (impact IN ('I1', 'I2', 'I3')),
    [urgency] NVARCHAR(32) NOT NULL CONSTRAINT [DF_recurrence_urgency] DEFAULT ('U3') CONSTRAINT [CK_recurrence_03] CHECK (urgency IN ('U1', 'U2', 'U3')),
    [active] INT NOT NULL CONSTRAINT [DF_recurrence_active] DEFAULT (1) CONSTRAINT [CK_recurrence_04] CHECK (active IN (0, 1)),
    [last_raised_at] NVARCHAR(64) NULL,
    [last_work_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_recurrence_last_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [next_due_on_parsed] AS (CASE WHEN [next_due_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [next_due_on], 112) WHEN [next_due_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [next_due_on], 23) END),
    [last_raised_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_raised_at], 126), CASE WHEN [last_raised_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_raised_at], 112) END)),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- approval   (from schema/049_approvals.sql)
IF OBJECT_ID(N'psa.[approval]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[approval] (
    [approval_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_approval] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_approval_work_item_id] REFERENCES psa.[ticket]([work_item_id]),

    -- email, lower case
    [approver] NVARCHAR(200) NOT NULL,
    [requested_at] NVARCHAR(64) NOT NULL,
    [requested_by] NVARCHAR(200) NOT NULL,
    [reason] NVARCHAR(MAX) NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_approval_status] DEFAULT ('PENDING') CONSTRAINT [CK_approval_01] CHECK (status IN ('PENDING', 'APPROVED', 'DECLINED', 'WITHDRAWN')),
    [decided_at] NVARCHAR(64) NULL,
    [decided_by] NVARCHAR(200) NULL,
    [note] NVARCHAR(MAX) NULL,

    -- where the ticket goes back to
    [return_status_id] NVARCHAR(64) NULL CONSTRAINT [FK_approval_return_status_id] REFERENCES psa.[board_status]([board_status_id]),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [requested_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [requested_at], 126), CASE WHEN [requested_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [requested_at], 112) END)),
    [decided_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [decided_at], 126), CASE WHEN [decided_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [decided_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- channel_target   (from schema/050_channels.sql)
IF OBJECT_ID(N'psa.[channel_target]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[channel_target] (
    -- a short name: helpdesk-alerts
    [target_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_channel_target] PRIMARY KEY,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [DF_channel_target_kind] DEFAULT ('TEAMS_WEBHOOK') CONSTRAINT [CK_channel_target_01] CHECK (kind IN ('TEAMS_WEBHOOK')),

    -- what people call it
    [label] NVARCHAR(400) NOT NULL,

    -- also carries pages to the on-call
    [pages] INT NOT NULL CONSTRAINT [DF_channel_target_pages] DEFAULT (0) CONSTRAINT [CK_channel_target_02] CHECK (pages IN (0, 1)),
    [note] NVARCHAR(MAX) NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_channel_target_inactive] DEFAULT (0) CONSTRAINT [CK_channel_target_03] CHECK (inactive IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- page   (from schema/050_channels.sql)
IF OBJECT_ID(N'psa.[page]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[page] (
    [page_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_page] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_page_work_item_id] REFERENCES psa.[ticket]([work_item_id]),

    -- who is being paged
    [member] NVARCHAR(200) NOT NULL,
    [role] NVARCHAR(32) NOT NULL CONSTRAINT [CK_page_01] CHECK (role IN ('ON_CALL', 'DUTY_MANAGER', 'NAMED')),
    [started_at] NVARCHAR(64) NOT NULL,
    [started_by] NVARCHAR(200) NOT NULL,
    [every_minutes] INT NOT NULL CONSTRAINT [CK_page_02] CHECK (every_minutes BETWEEN 1 AND 120),
    [max_attempts] INT NOT NULL CONSTRAINT [CK_page_03] CHECK (max_attempts BETWEEN 1 AND 20),
    [attempts] INT NOT NULL CONSTRAINT [DF_page_attempts] DEFAULT (0),
    [last_sent_at] NVARCHAR(64) NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_page_status] DEFAULT ('OPEN') CONSTRAINT [CK_page_04] CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'EXHAUSTED', 'STOPPED')),
    [ended_at] NVARCHAR(64) NULL,
    [ended_by] NVARCHAR(200) NULL,
    [note] NVARCHAR(MAX) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [started_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [started_at], 126), CASE WHEN [started_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [started_at], 112) END)),
    [last_sent_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_sent_at], 126), CASE WHEN [last_sent_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_sent_at], 112) END)),
    [ended_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [ended_at], 126), CASE WHEN [ended_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [ended_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- kb_file   (from schema/051_kb_files.sql)
IF OBJECT_ID(N'psa.[kb_file]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[kb_file] (
    [file_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_kb_file] PRIMARY KEY,
    [article_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_kb_file_article_id] REFERENCES psa.[kb_article]([article_id]),
    [filename] NVARCHAR(400) NOT NULL,
    [caption] NVARCHAR(400) NULL,
    [media_type] NVARCHAR(400) NOT NULL,
    [size_received] INT NOT NULL CONSTRAINT [CK_kb_file_01] CHECK (size_received > 0),
    [size_stored] INT NOT NULL CONSTRAINT [CK_kb_file_02] CHECK (size_stored > 0),
    [sha256] NVARCHAR(64) NOT NULL,
    [encoding] NVARCHAR(32) NOT NULL CONSTRAINT [CK_kb_file_03] CHECK (encoding IN ('IDENTITY', 'GZIP')),
    [treatment] NVARCHAR(400) NOT NULL,
    [uploaded_by] NVARCHAR(200) NOT NULL,
    [uploaded_at] NVARCHAR(64) NOT NULL,
    [review_status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_kb_file_review_status] DEFAULT ('PENDING') CONSTRAINT [CK_kb_file_04] CHECK (review_status IN ('PENDING', 'CLEARED', 'WITHHELD')),
    [reviewed_by] NVARCHAR(200) NULL,
    [reviewed_at] NVARCHAR(64) NULL,
    [removed_at] NVARCHAR(64) NULL,
    [removed_by] NVARCHAR(200) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [uploaded_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [uploaded_at], 126), CASE WHEN [uploaded_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [uploaded_at], 112) END)),
    [reviewed_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [reviewed_at], 126), CASE WHEN [reviewed_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [reviewed_at], 112) END)),
    [removed_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [removed_at], 126), CASE WHEN [removed_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [removed_at], 112) END)),
    CONSTRAINT [CK_kb_file_05] CHECK ((((review_status = 'PENDING') AND (reviewed_by IS NULL)) OR (NOT (review_status = 'PENDING') AND NOT (reviewed_by IS NULL))))
);
END;

-- --------------------------------------------------------------------------
-- opportunity   (from schema/052_sales.sql)
IF OBJECT_ID(N'psa.[opportunity]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[opportunity] (
    -- 'OPP-0001'
    [opportunity_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_opportunity] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [entity_id] NVARCHAR(64) NULL CONSTRAINT [FK_opportunity_entity_id] REFERENCES psa.[entity]([entity_id]),
    [contact_id] NVARCHAR(64) NULL CONSTRAINT [FK_opportunity_contact_id] REFERENCES psa.[contact]([contact_id]),
    [stage] NVARCHAR(32) NOT NULL CONSTRAINT [DF_opportunity_stage] DEFAULT ('LEAD') CONSTRAINT [CK_opportunity_01] CHECK (stage IN ('LEAD', 'QUALIFIED', 'PROPOSAL', 'WON', 'LOST')),
    [probability] INT NOT NULL CONSTRAINT [DF_opportunity_probability] DEFAULT (10) CONSTRAINT [CK_opportunity_02] CHECK (probability BETWEEN 0 AND 100),

    -- expected close, a day
    [expected_on] NVARCHAR(32) NULL,
    [amount] DECIMAL(19,4) NULL,
    [currency] NVARCHAR(32) NULL,
    [owner] NVARCHAR(200) NULL,
    [notes] NVARCHAR(MAX) NULL,

    -- once won
    [agreement_id] NVARCHAR(64) NULL CONSTRAINT [FK_opportunity_agreement_id] REFERENCES psa.[agreement]([agreement_id]),
    [lost_reason] NVARCHAR(400) NULL,
    [closed_at] NVARCHAR(64) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,
    [updated_at] NVARCHAR(64) NOT NULL,
    [updated_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [expected_on_parsed] AS (CASE WHEN [expected_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [expected_on], 112) WHEN [expected_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [expected_on], 23) END),
    [closed_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [closed_at], 126), CASE WHEN [closed_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [closed_at], 112) END)),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- quote   (from schema/052_sales.sql)
IF OBJECT_ID(N'psa.[quote]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[quote] (
    -- 'Q-0001'
    [quote_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_quote] PRIMARY KEY,
    [opportunity_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_quote_opportunity_id] REFERENCES psa.[opportunity]([opportunity_id]),
    [name] NVARCHAR(400) NOT NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_quote_status] DEFAULT ('DRAFT') CONSTRAINT [CK_quote_01] CHECK (status IN ('DRAFT', 'SENT', 'ACCEPTED', 'DECLINED', 'EXPIRED')),
    [valid_until] NVARCHAR(32) NULL,
    [tax_percent] DECIMAL(5,2) NOT NULL CONSTRAINT [DF_quote_tax_percent] DEFAULT (0) CONSTRAINT [CK_quote_02] CHECK (tax_percent BETWEEN 0 AND 100),
    [subtotal] DECIMAL(19,4) NOT NULL CONSTRAINT [DF_quote_subtotal] DEFAULT (0),
    [total] DECIMAL(19,4) NOT NULL CONSTRAINT [DF_quote_total] DEFAULT (0),
    [note] NVARCHAR(MAX) NULL,
    [sent_at] NVARCHAR(64) NULL,
    [decided_at] NVARCHAR(64) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,
    [updated_at] NVARCHAR(64) NOT NULL,
    [updated_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [valid_until_parsed] AS (CASE WHEN [valid_until] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [valid_until], 112) WHEN [valid_until] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [valid_until], 23) END),
    [sent_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [sent_at], 126), CASE WHEN [sent_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [sent_at], 112) END)),
    [decided_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [decided_at], 126), CASE WHEN [decided_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [decided_at], 112) END)),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- quote_line   (from schema/052_sales.sql)
IF OBJECT_ID(N'psa.[quote_line]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[quote_line] (
    [line_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_quote_line] PRIMARY KEY,
    [quote_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_quote_line_quote_id] REFERENCES psa.[quote]([quote_id]),
    [sort_order] INT NOT NULL CONSTRAINT [DF_quote_line_sort_order] DEFAULT (0),
    [description] NVARCHAR(400) NOT NULL,
    [quantity] DECIMAL(12,3) NOT NULL CONSTRAINT [CK_quote_line_01] CHECK (quantity > 0),
    [unit_price] DECIMAL(19,4) NOT NULL CONSTRAINT [CK_quote_line_02] CHECK (unit_price >= 0),
    [line_total] DECIMAL(19,4) NOT NULL
);
END;

-- --------------------------------------------------------------------------
-- member   (from schema/053_members.sql)
-- 053: members as records, a calendar feed, and a board's own intake address
--
-- Until now a member was a string: the sign-in identifier repeated across
-- board_member, member_role, member_capacity, oncall_slot, time_entry and
-- local_account, with a name only when the AD contact import happened to
-- carry it. The reference PSA's Member is a record with 123 fields; a
-- hospital desk needs about fifteen of them, and one page per person.
--
-- The identifier stays the key everywhere. This step adds a table beside the
-- rows that already exist and changes none of them, so a member who has no
-- row here is exactly what they were yesterday.
IF OBJECT_ID(N'psa.[member]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[member] (
    -- the identifier every other table carries
    [member] NVARCHAR(200) NOT NULL CONSTRAINT [PK_member] PRIMARY KEY,
    [display_name] NVARCHAR(400) NULL,
    [title] NVARCHAR(400) NULL,
    [email] NVARCHAR(400) NULL,
    [phone] NVARCHAR(32) NULL,
    [mobile] NVARCHAR(32) NULL,

    -- a department name, as Setup › Departments has it
    [department] NVARCHAR(400) NULL,

    -- where Dada IT keeps them: the office, a ward store room
    [location] NVARCHAR(400) NULL,

    -- a member identifier
    [reports_to] NVARCHAR(200) NULL,
    [default_board_id] NVARCHAR(64) NULL CONSTRAINT [FK_member_default_board_id] REFERENCES psa.[board]([board_id]),
    [work_role_id] NVARCHAR(64) NULL CONSTRAINT [FK_member_work_role_id] REFERENCES psa.[work_role]([work_role_id]),

    -- a member identifier; who approves this person's week
    [time_approver] NVARCHAR(200) NULL,

    -- the day they left; memberships were ended then
    [inactive_from] NVARCHAR(32) NULL,
    [notes] NVARCHAR(MAX) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,
    [updated_at] NVARCHAR(64) NOT NULL,
    [updated_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [inactive_from_parsed] AS (CASE WHEN [inactive_from] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [inactive_from], 112) WHEN [inactive_from] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [inactive_from], 23) END),
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- calendar_feed   (from schema/053_members.sql)
-- A person's calendar feed (.ics), for the phone's own calendar app: one
-- token per member, stored hashed, rotated from their profile. The feed
-- names tickets, boards and places, never a ticket's summary.
IF OBJECT_ID(N'psa.[calendar_feed]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[calendar_feed] (
    [member] NVARCHAR(200) NOT NULL CONSTRAINT [PK_calendar_feed] PRIMARY KEY,
    [token_hash] NVARCHAR(64) NOT NULL,
    [created_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- mail_exclusion   (from schema/055_mail_setup.sql)
-- 055: the email connector's settings on the desk
--
-- What arrives by mail is decided by three things: which board claims the
-- address it was sent to (053), the board's reply policy (023), and what
-- must never open a ticket. The third lived in code: delivery-system senders
-- and auto-replies (the loop guard), and the desk's own addresses passed on
-- the command line. A hospital mailbox also gets vendor newsletters, a
-- monitoring system's digests and a scanner's "document attached" mail, and
-- each of those is a decision a person makes once, here, not a code change.
--
-- A row is an exclusion: mail from an ADDRESS, from a DOMAIN, or whose
-- SUBJECT contains a phrase, is imported and recorded (nothing is dropped,
-- as intake has always promised) but opens nothing, with the reason on the
-- data-quality finding.
IF OBJECT_ID(N'psa.[mail_exclusion]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[mail_exclusion] (
    [exclusion_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_mail_exclusion] PRIMARY KEY,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_mail_exclusion_01] CHECK (kind IN ('ADDRESS', 'DOMAIN', 'SUBJECT')),

    -- lower case; an address, a domain, or a phrase
    [pattern] NVARCHAR(400) NOT NULL,
    [note] NVARCHAR(400) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- configuration_type   (from schema/056_configuration_types.sql)
-- 056: configuration types and statuses as setup tables, with typed questions
--
-- 021 fixed seven types and three statuses in a CHECK. A hospital's CMDB
-- outgrows that the day biomedical devices join it: an infusion pump is not
-- OTHER, and the questions asked of it (its asset tag, its last calibration)
-- are not asked of a printer. The reference PSA has ConfigurationType,
-- ConfigurationStatus and ConfigurationTypeQuestion; these are the same.
--
-- The 021 columns stay, and the CHECKs with them: a type MAPS TO one of the
-- seven codes and a status to one of the three, so every report, filter and
-- API shape that reads config_type or status keeps its meaning. The seven
-- and the three are written as rows on first use (configurations.
-- ensure_vocabulary), each mapping to itself; nothing is seeded here.
IF OBJECT_ID(N'psa.[configuration_type]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[configuration_type] (
    [type_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_configuration_type] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [maps_to] NVARCHAR(32) NOT NULL CONSTRAINT [CK_configuration_type_01] CHECK (maps_to IN ('WORKSTATION', 'LAPTOP', 'SERVER', 'PRINTER', 'NETWORK', 'MOBILE', 'OTHER')),
    [inactive] INT NOT NULL CONSTRAINT [DF_configuration_type_inactive] DEFAULT (0) CONSTRAINT [CK_configuration_type_02] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_configuration_type_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- configuration_status   (from schema/056_configuration_types.sql)
IF OBJECT_ID(N'psa.[configuration_status]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[configuration_status] (
    [status_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_configuration_status] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [maps_to] NVARCHAR(32) NOT NULL CONSTRAINT [CK_configuration_status_01] CHECK (maps_to IN ('ACTIVE', 'INACTIVE', 'RETIRED')),
    [inactive] INT NOT NULL CONSTRAINT [DF_configuration_status_inactive] DEFAULT (0) CONSTRAINT [CK_configuration_status_02] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_configuration_status_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- configuration_question   (from schema/056_configuration_types.sql)
-- A question a type asks of every configuration of that type.
IF OBJECT_ID(N'psa.[configuration_question]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[configuration_question] (
    [question_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_configuration_question] PRIMARY KEY,
    [type_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_configuration_question_type_id] REFERENCES psa.[configuration_type]([type_id]),
    [label] NVARCHAR(400) NOT NULL,
    [field_type] NVARCHAR(32) NOT NULL CONSTRAINT [CK_configuration_question_01] CHECK (field_type IN ('TEXT', 'NUMBER', 'DATE', 'CHECKBOX')),
    [required] INT NOT NULL CONSTRAINT [DF_configuration_question_required] DEFAULT (0) CONSTRAINT [CK_configuration_question_02] CHECK (required IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_configuration_question_sort_order] DEFAULT (0),
    [inactive] INT NOT NULL CONSTRAINT [DF_configuration_question_inactive] DEFAULT (0) CONSTRAINT [CK_configuration_question_03] CHECK (inactive IN (0, 1))
);
END;

-- --------------------------------------------------------------------------
-- configuration_answer   (from schema/056_configuration_types.sql)
IF OBJECT_ID(N'psa.[configuration_answer]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[configuration_answer] (
    [configuration_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_configuration_answer_configuration_id] REFERENCES psa.[configuration]([configuration_id]),
    [question_id] INT NOT NULL CONSTRAINT [FK_configuration_answer_question_id] REFERENCES psa.[configuration_question]([question_id]),
    [value] NVARCHAR(400) NULL,
    CONSTRAINT [PK_configuration_answer] PRIMARY KEY ([configuration_id], [question_id])
);
END;

-- --------------------------------------------------------------------------
-- mail_template   (from schema/057_small_setup.sql)
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
IF OBJECT_ID(N'psa.[mail_template]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[mail_template] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_mail_template_board_id] REFERENCES psa.[board]([board_id]),
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_mail_template_01] CHECK (kind IN ('OPENED', 'UPDATED', 'CLOSED', 'ASSIGNED', 'SCHEDULED', 'APPROVAL')),
    [subject] NVARCHAR(400) NOT NULL,
    [body] NVARCHAR(MAX) NOT NULL,
    [updated_at] NVARCHAR(64) NOT NULL,
    [updated_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END)),
    CONSTRAINT [PK_mail_template] PRIMARY KEY ([board_id], [kind])
);
END;

-- --------------------------------------------------------------------------
-- kb_category   (from schema/057_small_setup.sql)
-- Knowledge categories: a name a reader browses by; an article may have one.
IF OBJECT_ID(N'psa.[kb_category]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[kb_category] (
    [category_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_kb_category] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_kb_category_inactive] DEFAULT (0) CONSTRAINT [CK_kb_category_01] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_kb_category_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- company_status   (from schema/057_small_setup.sql)
-- A company's status (a customer, a former customer, a prospect) and type (a
-- hospital department, a supplier, a partner): words, not rules.
IF OBJECT_ID(N'psa.[company_status]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[company_status] (
    [status_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_company_status] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_company_status_inactive] DEFAULT (0) CONSTRAINT [CK_company_status_01] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_company_status_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- company_type   (from schema/057_small_setup.sql)
IF OBJECT_ID(N'psa.[company_type]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[company_type] (
    [type_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_company_type] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_company_type_inactive] DEFAULT (0) CONSTRAINT [CK_company_type_01] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_company_type_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- board_auto_assign   (from schema/057_small_setup.sql)
IF OBJECT_ID(N'psa.[board_auto_assign]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board_auto_assign] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_auto_assign_board_id] REFERENCES psa.[board]([board_id]),
    [catalogue_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_auto_assign_catalogue_item_id] REFERENCES psa.[catalogue_item]([catalogue_item_id]),
    [member] NVARCHAR(200) NOT NULL,
    CONSTRAINT [PK_board_auto_assign] PRIMARY KEY ([board_id], [catalogue_item_id])
);
END;

-- --------------------------------------------------------------------------
-- member_presence   (from schema/057_small_setup.sql)
-- The in/out board: where each member is right now, said by themselves.
IF OBJECT_ID(N'psa.[member_presence]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[member_presence] (
    [member] NVARCHAR(200) NOT NULL CONSTRAINT [PK_member_presence] PRIMARY KEY,
    [state] NVARCHAR(32) NOT NULL CONSTRAINT [CK_member_presence_01] CHECK (state IN ('IN', 'OUT', 'ON_SITE', 'REMOTE', 'LEAVE')),
    [note] NVARCHAR(400) NULL,
    [back_at] NVARCHAR(64) NULL,
    [set_at] NVARCHAR(64) NOT NULL,
    [set_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [back_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [back_at], 126), CASE WHEN [back_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [back_at], 112) END)),
    [set_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [set_at], 126), CASE WHEN [set_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [set_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- board_intake_address   (from schema/058_mail_cutover.sql)
-- 058: the mail cut-over (SQL01, 1 Oct 2026). Three addresses (helpdesk@, its
-- help@ alias, and support@) all land on one board, and the requester hears
-- at each status change in that status's own words.

-- A board claims as many addresses as it is sent mail on; an address belongs
-- to one board. Lower case, as intake compares them. Before 058 a board
-- claimed one (board.intake_address). `init` moves any such value here and
-- empties the column (db.seed, which every init runs), so the claim lives in
-- one place only; the column stays, unread, for the databases that have it.
IF OBJECT_ID(N'psa.[board_intake_address]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[board_intake_address] (
    [address] NVARCHAR(200) NOT NULL CONSTRAINT [PK_board_intake_address] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_board_intake_address_board_id] REFERENCES psa.[board]([board_id])
);
END;

-- --------------------------------------------------------------------------
-- status_mail   (from schema/058_mail_cutover.sql)
-- The emails a requester gets as their ticket moves: one per status (mail_key
-- is the board_status_id) and one when someone picks the ticket up (mail_key
-- 'PICKED_UP'). No row: nothing is sent, as before 058. A row with no words
-- uses the desk's words. Placeholders as for mail_template, and none carries
-- the summary, a note or the requester's own subject (6.1).
IF OBJECT_ID(N'psa.[status_mail]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[status_mail] (
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_status_mail_board_id] REFERENCES psa.[board]([board_id]),
    [mail_key] NVARCHAR(64) NOT NULL,
    [enabled] INT NOT NULL CONSTRAINT [DF_status_mail_enabled] DEFAULT (1) CONSTRAINT [CK_status_mail_01] CHECK (enabled IN (0, 1)),
    [subject] NVARCHAR(400) NULL,
    [body] NVARCHAR(MAX) NULL,
    [updated_at] NVARCHAR(64) NOT NULL,
    [updated_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END)),
    CONSTRAINT [PK_status_mail] PRIMARY KEY ([board_id], [mail_key])
);
END;

-- --------------------------------------------------------------------------
-- calendar_sync   (from schema/059_outlook_calendar.sql)
-- What to write: one row per change. A visit or block removed before it was
-- ever written is SUPERSEDED, never sent.
IF OBJECT_ID(N'psa.[calendar_sync]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[calendar_sync] (
    [sync_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_calendar_sync] PRIMARY KEY,
    [kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_calendar_sync_01] CHECK (kind IN ('VISIT', 'BLOCK')),
    [ref_id] INT NOT NULL,
    [member] NVARCHAR(200) NOT NULL,
    [action] NVARCHAR(32) NOT NULL CONSTRAINT [CK_calendar_sync_02] CHECK (action IN ('UPSERT', 'DELETE')),
    [event_id] NVARCHAR(400) NULL,
    [created_at] NVARCHAR(64) NOT NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_calendar_sync_status] DEFAULT ('PENDING') CONSTRAINT [CK_calendar_sync_03] CHECK (status IN ('PENDING', 'SENT', 'FAILED', 'NO_MAILBOX', 'SUPERSEDED')),
    [sent_at] NVARCHAR(64) NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [sent_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [sent_at], 126), CASE WHEN [sent_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [sent_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- outlook_busy   (from schema/059_outlook_calendar.sql)
-- What each member's Outlook calendar says they are doing, as busy blocks
-- only: never a subject, an attendee or a body. Replaced on every pull.
IF OBJECT_ID(N'psa.[outlook_busy]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[outlook_busy] (
    [busy_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_outlook_busy] PRIMARY KEY,
    [member] NVARCHAR(200) NOT NULL,
    [starts_at] NVARCHAR(64) NOT NULL,
    [ends_at] NVARCHAR(64) NOT NULL,
    [show_as] NVARCHAR(32) NOT NULL CONSTRAINT [CK_outlook_busy_01] CHECK (show_as IN ('BUSY', 'TENTATIVE', 'OOF', 'WORKING_ELSEWHERE')),
    [pulled_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [starts_at], 126), CASE WHEN [starts_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [starts_at], 112) END)),
    [ends_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [ends_at], 126), CASE WHEN [ends_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [ends_at], 112) END)),
    [pulled_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [pulled_at], 126), CASE WHEN [pulled_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [pulled_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- priority   (from schema/060_priority.sql)
-- 060: the Priority setup table, in the reference PSA's shape (Dada, 1 Oct
-- 2026: "priorities should match what connectwise has and can be overriden").
--
-- ConnectWise's Priority entity is id, name (50), color (a named colour),
-- sortOrder and defaultFlag (MEASURED from its OpenAPI schema, docs/
-- WS36-connectwise-model-20260909.md). The desk's P1-P4 codes stay the key
-- every clock and floor already uses; this table gives each its name and
-- colour, editable at Setup > Priorities. The names seeded are the desk's
-- reading of ConnectWise's defaults (NOT VERIFIED against a live instance:
-- its documentation is behind a sign-in); a wrong word is a setup edit.
IF OBJECT_ID(N'psa.[priority]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[priority] (
    [priority_id] NVARCHAR(32) NOT NULL CONSTRAINT [PK_priority] PRIMARY KEY CONSTRAINT [CK_priority_01] CHECK (priority_id IN ('P1', 'P2', 'P3', 'P4')),
    [name] NVARCHAR(400) NOT NULL,
    [color] NVARCHAR(32) NOT NULL CONSTRAINT [CK_priority_02] CHECK (color IN ('Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Cyan', 'Lime', 'Purple', 'Pink', 'Gray', 'Black', 'White')),
    [sort_order] INT NOT NULL CONSTRAINT [DF_priority_sort_order] DEFAULT (0),
    [is_default] INT NOT NULL CONSTRAINT [DF_priority_is_default] DEFAULT (0) CONSTRAINT [CK_priority_03] CHECK (is_default IN (0, 1))
);
END;

-- --------------------------------------------------------------------------
-- ticket_cc   (from schema/061_ticket_cc.sql)
-- 061: Cc on a ticket (Dada, 1 Oct 2026: "can we add a cc on the tickets").
--
-- The people copied on a ticket, as the reference PSA's ticket Cc field: the
-- addresses an email came in with (never the sender, never the desk's own
-- addresses), and whatever a person types on the ticket. The requester's
-- emails (we have it, status changes, picked up, closed) go to them as Cc,
-- within the allowed domains. They see nothing on the portal; the requester
-- does. Carries no words of the ticket: an address only.
IF OBJECT_ID(N'psa.[ticket_cc]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_cc] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_cc_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [address] NVARCHAR(200) NOT NULL,
    [source] NVARCHAR(32) NOT NULL CONSTRAINT [CK_ticket_cc_01] CHECK (source IN ('EMAIL', 'DESK')),
    [added_at] NVARCHAR(64) NOT NULL,
    [added_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [added_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [added_at], 126), CASE WHEN [added_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [added_at], 112) END)),
    CONSTRAINT [PK_ticket_cc] PRIMARY KEY ([work_item_id], [address])
);
END;

-- --------------------------------------------------------------------------
-- dispatch_view   (from schema/063_dispatch_view.sql)
-- 063: whose rows the Dispatch board shows (Dada, 1 Oct 2026: "can we have
-- an edit view as to who will be displayed on the dispatch portal").
--
-- The reference PSA's dispatch portal shows a chosen set of resources, not
-- everyone on every board. Here each dispatcher keeps one view: the people
-- whose rows they want, as a comma-separated list of member identifiers,
-- and optionally the one board. Nobody else's. The URL's `who=` shows a set
-- once; this is the one that applies when the URL says nothing.
IF OBJECT_ID(N'psa.[dispatch_view]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[dispatch_view] (
    -- the dispatcher, as board_member.member
    [member] NVARCHAR(200) NOT NULL CONSTRAINT [PK_dispatch_view] PRIMARY KEY,

    -- member identifiers, comma-separated, lower case
    [people] NVARCHAR(MAX) NOT NULL,

    -- the one board, or NULL for all theirs
    [board_id] NVARCHAR(64) NULL CONSTRAINT [FK_dispatch_view_board_id] REFERENCES psa.[board]([board_id]),
    [updated_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [updated_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [updated_at], 126), CASE WHEN [updated_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [updated_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- time_timer   (from schema/065_time_timer.sql)
IF OBJECT_ID(N'psa.[time_timer]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[time_timer] (
    [timer_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_time_timer] PRIMARY KEY,
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_time_timer_work_item_id] REFERENCES psa.[work_item]([work_item_id]),
    [member] NVARCHAR(200) NOT NULL,
    [started_at] NVARCHAR(64) NOT NULL,

    -- Set when the person stops it. A stopped timer is kept until its entry is
    -- saved or it is discarded, so a stop is never a loss.
    [stopped_at] NVARCHAR(64) NULL,

    -- Accumulated seconds the timer was paused for, and when the current pause
    -- began (NULL when it is running). Elapsed is (stop or now) - started_at
    -- - paused_seconds, and while paused it is paused_at - started_at - the rest.
    [paused_seconds] INT NOT NULL CONSTRAINT [DF_time_timer_paused_seconds] DEFAULT (0) CONSTRAINT [CK_time_timer_01] CHECK (paused_seconds >= 0),
    [paused_at] NVARCHAR(64) NULL,

    -- What the person was doing, typed while it runs so it is not invented
    -- afterwards. Carried into the time entry's note.
    [note] NVARCHAR(MAX) NULL,

    -- The entry it became, once saved. A timer with this set is spent.
    [time_entry_id] INT NULL CONSTRAINT [FK_time_timer_time_entry_id] REFERENCES psa.[time_entry]([time_entry_id]),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [started_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [started_at], 126), CASE WHEN [started_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [started_at], 112) END)),
    [stopped_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [stopped_at], 126), CASE WHEN [stopped_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [stopped_at], 112) END)),
    [paused_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [paused_at], 126), CASE WHEN [paused_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [paused_at], 112) END)),
    CONSTRAINT [CK_time_timer_02] CHECK (stopped_at IS NULL OR stopped_at >= started_at),
    CONSTRAINT [CK_time_timer_03] CHECK (paused_at IS NULL OR paused_at >= started_at),
    CONSTRAINT [CK_time_timer_04] CHECK (time_entry_id IS NULL OR stopped_at IS NOT NULL)
);
END;

-- --------------------------------------------------------------------------
-- ticket_resource   (from schema/067_ticket_resource.sql)
IF OBJECT_ID(N'psa.[ticket_resource]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[ticket_resource] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_resource_work_item_id] REFERENCES psa.[work_item]([work_item_id]),
    [member] NVARCHAR(200) NOT NULL,
    [added_at] NVARCHAR(64) NOT NULL,
    [added_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [added_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [added_at], 126), CASE WHEN [added_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [added_at], 112) END)),
    CONSTRAINT [PK_ticket_resource] PRIMARY KEY ([work_item_id], [member])
);
END;

-- --------------------------------------------------------------------------
-- project_member   (from schema/068_project_team.sql)
IF OBJECT_ID(N'psa.[project_member]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_member] (
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_member_project_id] REFERENCES psa.[project]([project_id]),
    [member] NVARCHAR(200) NOT NULL,
    [project_role] NVARCHAR(32) NOT NULL CONSTRAINT [DF_project_member_project_role] DEFAULT ('TEAM_MEMBER'),
    [starts_on] NVARCHAR(32) NULL,
    [ends_on] NVARCHAR(32) NULL,
    [hours] DECIMAL(9,2) NULL,
    [added_at] NVARCHAR(64) NOT NULL,
    [added_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [starts_on_parsed] AS (CASE WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 112) WHEN [starts_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [starts_on], 23) END),
    [ends_on_parsed] AS (CASE WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 112) WHEN [ends_on] LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN TRY_CONVERT(DATE, [ends_on], 23) END),
    [added_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [added_at], 126), CASE WHEN [added_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [added_at], 112) END)),
    CONSTRAINT [PK_project_member] PRIMARY KEY ([project_id], [member])
);
END;

-- --------------------------------------------------------------------------
-- project_note   (from schema/068_project_team.sql)
IF OBJECT_ID(N'psa.[project_note]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_note] (
    [note_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_project_note] PRIMARY KEY,
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_note_project_id] REFERENCES psa.[project]([project_id]),
    [body] NVARCHAR(MAX) NOT NULL,
    [written_at] NVARCHAR(64) NOT NULL,
    [written_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [written_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [written_at], 126), CASE WHEN [written_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [written_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- project_contact   (from schema/069_project_plan.sql)
IF OBJECT_ID(N'psa.[project_contact]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_contact] (
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_contact_project_id] REFERENCES psa.[project]([project_id]),
    [contact_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_contact_contact_id] REFERENCES psa.[contact]([contact_id]),
    [role] NVARCHAR(400) NULL,
    [added_at] NVARCHAR(64) NOT NULL,
    [added_by] NVARCHAR(200) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [added_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [added_at], 126), CASE WHEN [added_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [added_at], 112) END)),
    CONSTRAINT [PK_project_contact] PRIMARY KEY ([project_id], [contact_id])
);
END;

-- --------------------------------------------------------------------------
-- project_ticket_dependency   (from schema/069_project_plan.sql)
IF OBJECT_ID(N'psa.[project_ticket_dependency]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_ticket_dependency] (
    [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_ticket_dependency_work_item_id] REFERENCES psa.[project_ticket]([work_item_id]),
    [depends_on] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_ticket_dependency_depends_on] REFERENCES psa.[project_ticket]([work_item_id]),
    CONSTRAINT [PK_project_ticket_dependency] PRIMARY KEY ([work_item_id], [depends_on]),
    CONSTRAINT [CK_project_ticket_dependency_01] CHECK (work_item_id <> depends_on)
);
END;

-- --------------------------------------------------------------------------
-- project_plan_item   (from schema/069_project_plan.sql)
IF OBJECT_ID(N'psa.[project_plan_item]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_plan_item] (
    [item_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_project_plan_item] PRIMARY KEY,
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_plan_item_project_id] REFERENCES psa.[project]([project_id]),
    [phase_id] INT NULL CONSTRAINT [FK_project_plan_item_phase_id] REFERENCES psa.[project_phase]([phase_id]),
    [summary] NVARCHAR(400) NOT NULL,
    [budget_hours] DECIMAL(9,2) NULL,
    [sort_order] INT NOT NULL CONSTRAINT [DF_project_plan_item_sort_order] DEFAULT (0),
    [created_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- project_status   (from schema/070_project_setup.sql)
IF OBJECT_ID(N'psa.[project_status]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_status] (
    [status_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_project_status] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [indicator] NVARCHAR(32) NOT NULL CONSTRAINT [DF_project_status_indicator] DEFAULT ('ON_TRACK') CONSTRAINT [CK_project_status_01] CHECK (indicator IN ('ON_TRACK', 'AT_RISK', 'HIGH_RISK', 'OFF_TRACK')),
    [is_default] INT NOT NULL CONSTRAINT [DF_project_status_is_default] DEFAULT (0) CONSTRAINT [CK_project_status_02] CHECK (is_default IN (0, 1)),
    [is_closed] INT NOT NULL CONSTRAINT [DF_project_status_is_closed] DEFAULT (0) CONSTRAINT [CK_project_status_03] CHECK (is_closed IN (0, 1)),
    [no_time] INT NOT NULL CONSTRAINT [DF_project_status_no_time] DEFAULT (0) CONSTRAINT [CK_project_status_04] CHECK (no_time IN (0, 1)),
    [inactive] INT NOT NULL CONSTRAINT [DF_project_status_inactive] DEFAULT (0) CONSTRAINT [CK_project_status_05] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_project_status_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- project_type   (from schema/070_project_setup.sql)
IF OBJECT_ID(N'psa.[project_type]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_type] (
    [type_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_project_type] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [is_default] INT NOT NULL CONSTRAINT [DF_project_type_is_default] DEFAULT (0) CONSTRAINT [CK_project_type_01] CHECK (is_default IN (0, 1)),
    [inactive] INT NOT NULL CONSTRAINT [DF_project_type_inactive] DEFAULT (0) CONSTRAINT [CK_project_type_02] CHECK (inactive IN (0, 1))
);
END;

-- --------------------------------------------------------------------------
-- project_role   (from schema/070_project_setup.sql)
IF OBJECT_ID(N'psa.[project_role]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_role] (
    [role_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_project_role] PRIMARY KEY,
    [name] NVARCHAR(400) NOT NULL,
    [inactive] INT NOT NULL CONSTRAINT [DF_project_role_inactive] DEFAULT (0) CONSTRAINT [CK_project_role_01] CHECK (inactive IN (0, 1)),
    [sort_order] INT NOT NULL CONSTRAINT [DF_project_role_sort_order] DEFAULT (0)
);
END;

-- --------------------------------------------------------------------------
-- project_issue   (from schema/070_project_setup.sql)
IF OBJECT_ID(N'psa.[project_issue]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[project_issue] (
    [issue_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_project_issue] PRIMARY KEY,
    [project_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_project_issue_project_id] REFERENCES psa.[project]([project_id]),
    [summary] NVARCHAR(400) NOT NULL,
    [details] NVARCHAR(MAX) NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_project_issue_status] DEFAULT ('OPEN') CONSTRAINT [CK_project_issue_01] CHECK (status IN ('OPEN', 'CLOSED')),
    [assigned_to] NVARCHAR(200) NULL,
    [raised_by] NVARCHAR(200) NOT NULL,
    [raised_at] NVARCHAR(64) NOT NULL,
    [work_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_project_issue_work_item_id] REFERENCES psa.[ticket]([work_item_id]),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [raised_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [raised_at], 126), CASE WHEN [raised_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [raised_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- chat_session   (from schema/071_chat.sql)
IF OBJECT_ID(N'psa.[chat_session]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[chat_session] (
    [chat_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_chat_session] PRIMARY KEY,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_chat_session_board_id] REFERENCES psa.[board]([board_id]),
    [requester] NVARCHAR(200) NOT NULL,
    [subject] NVARCHAR(400) NOT NULL,
    [status] NVARCHAR(32) NOT NULL CONSTRAINT [DF_chat_session_status] DEFAULT ('WAITING') CONSTRAINT [CK_chat_session_01] CHECK (status IN ('WAITING', 'ACTIVE', 'CLOSED')),
    [started_at] NVARCHAR(64) NOT NULL,
    [picked_by] NVARCHAR(200) NULL,
    [picked_at] NVARCHAR(64) NULL,
    [closed_at] NVARCHAR(64) NULL,
    [closed_by] NVARCHAR(200) NULL,
    [work_item_id] NVARCHAR(64) NULL CONSTRAINT [FK_chat_session_work_item_id] REFERENCES psa.[ticket]([work_item_id]),
    [last_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [started_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [started_at], 126), CASE WHEN [started_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [started_at], 112) END)),
    [picked_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [picked_at], 126), CASE WHEN [picked_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [picked_at], 112) END)),
    [closed_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [closed_at], 126), CASE WHEN [closed_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [closed_at], 112) END)),
    [last_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_at], 126), CASE WHEN [last_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- chat_message   (from schema/071_chat.sql)
IF OBJECT_ID(N'psa.[chat_message]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[chat_message] (
    [message_id] INT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_chat_message] PRIMARY KEY,
    [chat_id] INT NOT NULL CONSTRAINT [FK_chat_message_chat_id] REFERENCES psa.[chat_session]([chat_id]),
    [sender] NVARCHAR(200) NOT NULL,
    [sender_kind] NVARCHAR(32) NOT NULL CONSTRAINT [CK_chat_message_01] CHECK (sender_kind IN ('REQUESTER', 'STAFF', 'SYSTEM')),
    [body] NVARCHAR(MAX) NOT NULL,
    [sent_at] NVARCHAR(64) NOT NULL,

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [sent_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [sent_at], 126), CASE WHEN [sent_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [sent_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- api_token   (from schema/local/api_token.sql)
IF OBJECT_ID(N'psa.[api_token]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[api_token] (
    [token_id] NVARCHAR(64) NOT NULL CONSTRAINT [PK_api_token] PRIMARY KEY,

    -- sha256 of the token, lower-case hex. The token itself is never stored.
    [token_sha256] NVARCHAR(64) NOT NULL,

    -- What it is for, in words: 'orthanc monitoring', 'UPS alerts'.
    [label] NVARCHAR(400) NOT NULL,
    [board_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_api_token_board_id] REFERENCES psa.[board]([board_id]),
    [created_at] NVARCHAR(64) NOT NULL,
    [created_by] NVARCHAR(200) NOT NULL,
    [last_used_at] NVARCHAR(64) NULL,
    [disabled] INT NOT NULL CONSTRAINT [DF_api_token_disabled] DEFAULT (0) CONSTRAINT [CK_api_token_01] CHECK (disabled IN (0, 1)),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [last_used_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_used_at], 126), CASE WHEN [last_used_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_used_at], 112) END))
);
END;

-- --------------------------------------------------------------------------
-- local_account   (from schema/local/local_account.sql)
IF OBJECT_ID(N'psa.[local_account]', N'U') IS NULL
BEGIN
CREATE TABLE psa.[local_account] (
    [username] NVARCHAR(200) NOT NULL CONSTRAINT [PK_local_account] PRIMARY KEY,

    -- 'scrypt$N$r$p$salt_hex$hash_hex'. Never a password, never reversible.
    [scrypt_hash] NVARCHAR(256) NOT NULL,

    -- Cross-board admin (calendars, clinical floors, catalogue) as against a
    -- board-scoped ADMIN membership. Off by default; a break-glass account is not
    -- a superuser unless somebody deliberately made it one.
    [is_sysadmin] INT NOT NULL CONSTRAINT [DF_local_account_is_sysadmin] DEFAULT (0) CONSTRAINT [CK_local_account_01] CHECK (is_sysadmin IN (0, 1)),
    [created_at] NVARCHAR(64) NOT NULL,

    -- 'cli' always. The column exists so a future non-CLI path would have to lie
    -- to hide itself, which is harder than leaving a truthful field blank.
    [created_by] NVARCHAR(200) NOT NULL,
    [last_login_at] NVARCHAR(64) NULL,
    [disabled] INT NOT NULL CONSTRAINT [DF_local_account_disabled] DEFAULT (0) CONSTRAINT [CK_local_account_02] CHECK (disabled IN (0, 1)),

    -- Dates are kept as the source wrote them. These read them,
    -- without deciding for the reader which shape was meant.
    [created_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [created_at], 126), CASE WHEN [created_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [created_at], 112) END)),
    [last_login_at_parsed] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [last_login_at], 126), CASE WHEN [last_login_at] LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN TRY_CONVERT(DATETIME2(0), [last_login_at], 112) END))
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

IF COL_LENGTH(N'psa.[board]', N'calendar_id') IS NULL
ALTER TABLE psa.[board] ADD [calendar_id] NVARCHAR(64) NULL CONSTRAINT [FK_board_calendar_id] REFERENCES psa.[calendar]([calendar_id]);

-- Dada PSA flags every note: Discussion (the requester sees it), Internal
-- (fulfillers only) and Resolution (the answer, which the requester sees).
-- NULL is a system event: a status change, an import, a routing.
IF COL_LENGTH(N'psa.[ticket_event]', N'note_flag') IS NULL
ALTER TABLE psa.[ticket_event] ADD [note_flag] NVARCHAR(32) NULL CONSTRAINT [CK_ticket_event_note_flag_01] CHECK (note_flag IN ('DISCUSSION', 'INTERNAL', 'RESOLUTION'));

-- Who the ticket is for, in Dada PSA's words the contact. requested_by
-- already carries it; this is the time of the last touch, for the board's
-- "Updated" column and for sorting by it.
IF COL_LENGTH(N'psa.[ticket]', N'updated_at') IS NULL
ALTER TABLE psa.[ticket] ADD [updated_at] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[ticket]', N'intake_source') IS NULL
ALTER TABLE psa.[ticket] ADD [intake_source] NVARCHAR(32) NULL CONSTRAINT [CK_ticket_intake_source_01] CHECK (intake_source IN ('EMAIL', 'PHONE', 'WALK_UP', 'PORTAL', 'API', 'DESK', 'IMPORT'));

-- Nullable, as every added column must be (the port refuses to invent values
-- for rows that already exist): NULL and 0 both mean active.
IF COL_LENGTH(N'psa.[board]', N'inactive') IS NULL
ALTER TABLE psa.[board] ADD [inactive] INT NULL CONSTRAINT [CK_board_inactive_01] CHECK (inactive IN (0, 1));

IF COL_LENGTH(N'psa.[board]', N'description') IS NULL
ALTER TABLE psa.[board] ADD [description] NVARCHAR(MAX) NULL;

-- Which contact a ticket is for. requested_by keeps what intake was told,
-- verbatim; contact_id is the resolved person, when there is one.
IF COL_LENGTH(N'psa.[ticket]', N'contact_id') IS NULL
ALTER TABLE psa.[ticket] ADD [contact_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_contact_id] REFERENCES psa.[contact]([contact_id]);

IF COL_LENGTH(N'psa.[ticket]', N'record_type') IS NULL
ALTER TABLE psa.[ticket] ADD [record_type] NVARCHAR(32) NULL CONSTRAINT [CK_ticket_record_type_01] CHECK (record_type IN ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT'));

-- A catalogue item can say what it is; blank means "from the action's kind"
-- (FAULT -> INCIDENT, REQUEST -> SERVICE_REQUEST).
IF COL_LENGTH(N'psa.[catalogue_item]', N'record_type') IS NULL
ALTER TABLE psa.[catalogue_item] ADD [record_type] NVARCHAR(32) NULL CONSTRAINT [CK_catalogue_item_record_type_01] CHECK (record_type IN ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT'));

-- The board's kind (Dada, 23 Sep 2026: "those are board types"). A SERVICE board
-- is the front door for incidents, requests, problems and events; a CHANGE board
-- runs the change lifecycle and its approval gate; a PROJECT board runs projects
-- and no SLA clocks (the reference PSA's projectFlag: "SLA timers do not run on project
-- tickets", VERIFIED, docs.connectwise.com/ConnectWise_Documentation/090/020/140/
-- 010/020). NULL reads as SERVICE, so every board made before this is one.
IF COL_LENGTH(N'psa.[board]', N'kind') IS NULL
ALTER TABLE psa.[board] ADD [kind] NVARCHAR(32) NULL CONSTRAINT [CK_board_kind_01] CHECK (kind IN ('SERVICE', 'CHANGE', 'PROJECT'));

-- ------------------------------------------------------------ change enablement
--
-- ITIL 4 names three types of change, and the reference PSA's Service Transition page
-- uses the same three (VERIFIED, docs.connectwise.com/ConnectWise_Business_
-- Knowledge/110/030): STANDARD is pre-authorised and needs no approval; NORMAL
-- is authorised by a change authority before it is built; EMERGENCY goes ahead
-- at once and is authorised as soon as it can be, afterwards. Dada PSA's
-- ticket has no change fields (only Ticket.approved), so these are the spine's
-- own, named as such.
IF COL_LENGTH(N'psa.[ticket]', N'change_type') IS NULL
ALTER TABLE psa.[ticket] ADD [change_type] NVARCHAR(32) NULL CONSTRAINT [CK_ticket_change_type_01] CHECK (change_type IN ('STANDARD', 'NORMAL', 'EMERGENCY'));

IF COL_LENGTH(N'psa.[ticket]', N'change_risk') IS NULL
ALTER TABLE psa.[ticket] ADD [change_risk] NVARCHAR(32) NULL CONSTRAINT [CK_ticket_change_risk_01] CHECK (change_risk IN ('LOW', 'MEDIUM', 'HIGH'));

IF COL_LENGTH(N'psa.[ticket]', N'planned_start') IS NULL
ALTER TABLE psa.[ticket] ADD [planned_start] NVARCHAR(64) NULL;

-- the implementation window
IF COL_LENGTH(N'psa.[ticket]', N'planned_end') IS NULL
ALTER TABLE psa.[ticket] ADD [planned_end] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[ticket]', N'backout_plan') IS NULL
ALTER TABLE psa.[ticket] ADD [backout_plan] NVARCHAR(MAX) NULL;

-- how it is undone if it fails

-- A status a change may enter only once it is authorised (Approved, Scheduled,
-- Implementing). NULL or 0: no gate. The engine enforces it; see board.change_status.
IF COL_LENGTH(N'psa.[board_status]', N'requires_approval') IS NULL
ALTER TABLE psa.[board_status] ADD [requires_approval] INT NULL CONSTRAINT [CK_board_status_requires_approval_01] CHECK (requires_approval IN (0, 1));

IF COL_LENGTH(N'psa.[board]', N'closed_reply_policy') IS NULL
ALTER TABLE psa.[board] ADD [closed_reply_policy] NVARCHAR(32) NULL CONSTRAINT [CK_board_closed_reply_policy_01] CHECK (closed_reply_policy IN ('REOPEN', 'NEW_TICKET'));

-- REOPEN only within this many days of closing; older replies open a new ticket.
IF COL_LENGTH(N'psa.[board]', N'reopen_within_days') IS NULL
ALTER TABLE psa.[board] ADD [reopen_within_days] INT NULL CONSTRAINT [CK_board_reopen_within_days_01] CHECK (reopen_within_days > 0);

IF COL_LENGTH(N'psa.[board]', N'reopen_status_id') IS NULL
ALTER TABLE psa.[board] ADD [reopen_status_id] NVARCHAR(64) NULL CONSTRAINT [FK_board_reopen_status_id] REFERENCES psa.[board_status]([board_status_id]);

-- Dada PSA's "customer updated": the requester has written since a fulfiller
-- last did. Set by every inbound reply (mail or portal), cleared by a fulfiller's
-- note, shown on the board so a reply is never missed. NULL reads as 0.
IF COL_LENGTH(N'psa.[ticket]', N'customer_updated') IS NULL
ALTER TABLE psa.[ticket] ADD [customer_updated] INT NULL CONSTRAINT [CK_ticket_customer_updated_01] CHECK (customer_updated IN (0, 1));

IF COL_LENGTH(N'psa.[workflow_event]', N'tested_at') IS NULL
ALTER TABLE psa.[workflow_event] ADD [tested_at] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[workflow_event]', N'tested_matches') IS NULL
ALTER TABLE psa.[workflow_event] ADD [tested_matches] INT NULL;

IF COL_LENGTH(N'psa.[ticket_event]', N'is_resolution') IS NULL
ALTER TABLE psa.[ticket_event] ADD [is_resolution] INT NULL CONSTRAINT [CK_ticket_event_is_resolution_01] CHECK (is_resolution IN (0, 1));

-- Which template a workflow rule's APPLY_TEMPLATE action applies.
IF COL_LENGTH(N'psa.[workflow_action]', N'target_template_id') IS NULL
ALTER TABLE psa.[workflow_action] ADD [target_template_id] NVARCHAR(64) NULL CONSTRAINT [FK_workflow_action_target_template_id] REFERENCES psa.[ticket_template]([template_id]);

-- Emailing the requester: the reference PSA mails the contact on a new ticket and on a
-- Discussion note, per board. Here the mail says only that the ticket moved and
-- links to the portal; the note's words never leave the desk (§6.1). NULL reads
-- as off: no email leaves until a board turns it on, once the portal is
-- reachable over https.
IF COL_LENGTH(N'psa.[board]', N'notify_requester') IS NULL
ALTER TABLE psa.[board] ADD [notify_requester] INT NULL CONSTRAINT [CK_board_notify_requester_01] CHECK (notify_requester IN (0, 1));

IF COL_LENGTH(N'psa.[attachment]', N'purged_at') IS NULL
ALTER TABLE psa.[attachment] ADD [purged_at] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[attachment]', N'purge_reason') IS NULL
ALTER TABLE psa.[attachment] ADD [purge_reason] NVARCHAR(32) NULL CONSTRAINT [CK_attachment_purge_reason_01] CHECK (purge_reason IN ('WITHHELD', 'CLOSED', 'MISSING'));

IF COL_LENGTH(N'psa.[ticket]', N'parent_id') IS NULL
ALTER TABLE psa.[ticket] ADD [parent_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_parent_id] REFERENCES psa.[ticket]([work_item_id]);

IF COL_LENGTH(N'psa.[ticket]', N'merged_into') IS NULL
ALTER TABLE psa.[ticket] ADD [merged_into] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_merged_into] REFERENCES psa.[ticket]([work_item_id]);

IF COL_LENGTH(N'psa.[time_entry]', N'time_start') IS NULL
ALTER TABLE psa.[time_entry] ADD [time_start] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[time_entry]', N'time_end') IS NULL
ALTER TABLE psa.[time_entry] ADD [time_end] NVARCHAR(64) NULL;

-- Added columns are NULL-able by the port's rule (a migration invents no data);
-- the engine writes every one of them on every new row.
IF COL_LENGTH(N'psa.[time_entry]', N'hours_deduct') IS NULL
ALTER TABLE psa.[time_entry] ADD [hours_deduct] DECIMAL(9,2) NULL CONSTRAINT [DF_time_entry_hours_deduct] DEFAULT (0);

IF COL_LENGTH(N'psa.[time_entry]', N'actual_hours') IS NULL
ALTER TABLE psa.[time_entry] ADD [actual_hours] DECIMAL(9,2) NULL;

IF COL_LENGTH(N'psa.[time_entry]', N'work_role_id') IS NULL
ALTER TABLE psa.[time_entry] ADD [work_role_id] NVARCHAR(64) NULL CONSTRAINT [FK_time_entry_work_role_id] REFERENCES psa.[work_role]([work_role_id]);

IF COL_LENGTH(N'psa.[time_entry]', N'work_type_id') IS NULL
ALTER TABLE psa.[time_entry] ADD [work_type_id] NVARCHAR(64) NULL CONSTRAINT [FK_time_entry_work_type_id] REFERENCES psa.[work_type]([work_type_id]);

IF COL_LENGTH(N'psa.[time_entry]', N'billable_option') IS NULL
ALTER TABLE psa.[time_entry] ADD [billable_option] NVARCHAR(32) NULL CONSTRAINT [DF_time_entry_billable_option] DEFAULT ('NO_DEFAULT') CONSTRAINT [CK_time_entry_billable_option_01] CHECK (billable_option IN ('BILLABLE', 'DO_NOT_BILL', 'NO_CHARGE', 'NO_DEFAULT'));

-- The note the entry was written with, when it was (Dada PSA's time entry
-- carries its notes; here the note is the ticket_event and this points at it).
IF COL_LENGTH(N'psa.[time_entry]', N'ticket_event_id') IS NULL
ALTER TABLE psa.[time_entry] ADD [ticket_event_id] INT NULL CONSTRAINT [FK_time_entry_ticket_event_id] REFERENCES psa.[ticket_event]([ticket_event_id]);

-- Dada PSA's TimeEntry.status, the part of it the desk has a use for.
IF COL_LENGTH(N'psa.[time_entry]', N'entry_status') IS NULL
ALTER TABLE psa.[time_entry] ADD [entry_status] NVARCHAR(32) NULL CONSTRAINT [DF_time_entry_entry_status] DEFAULT ('OPEN') CONSTRAINT [CK_time_entry_entry_status_01] CHECK (entry_status IN ('OPEN', 'READY_TO_BILL', 'BILLED', 'WRITTEN_OFF', 'BILLED_AGREEMENT'));

IF COL_LENGTH(N'psa.[board]', N'default_work_role_id') IS NULL
ALTER TABLE psa.[board] ADD [default_work_role_id] NVARCHAR(64) NULL CONSTRAINT [FK_board_default_work_role_id] REFERENCES psa.[work_role]([work_role_id]);

IF COL_LENGTH(N'psa.[board]', N'default_work_type_id') IS NULL
ALTER TABLE psa.[board] ADD [default_work_type_id] NVARCHAR(64) NULL CONSTRAINT [FK_board_default_work_type_id] REFERENCES psa.[work_type]([work_type_id]);

IF COL_LENGTH(N'psa.[board]', N'notify_owner') IS NULL
ALTER TABLE psa.[board] ADD [notify_owner] INT NULL CONSTRAINT [CK_board_notify_owner_01] CHECK (notify_owner IN (0, 1));

IF COL_LENGTH(N'psa.[service_family]', N'inactive') IS NULL
ALTER TABLE psa.[service_family] ADD [inactive] INT NULL CONSTRAINT [DF_service_family_inactive] DEFAULT (0) CONSTRAINT [CK_service_family_inactive_01] CHECK (inactive IN (0, 1));

IF COL_LENGTH(N'psa.[service_action]', N'inactive') IS NULL
ALTER TABLE psa.[service_action] ADD [inactive] INT NULL CONSTRAINT [DF_service_action_inactive] DEFAULT (0) CONSTRAINT [CK_service_action_inactive_01] CHECK (inactive IN (0, 1));

IF COL_LENGTH(N'psa.[holiday]', N'all_day') IS NULL
ALTER TABLE psa.[holiday] ADD [all_day] INT NULL CONSTRAINT [DF_holiday_all_day] DEFAULT (1) CONSTRAINT [CK_holiday_all_day_01] CHECK (all_day IN (0, 1));

IF COL_LENGTH(N'psa.[holiday]', N'time_start') IS NULL
ALTER TABLE psa.[holiday] ADD [time_start] NVARCHAR(8) NULL;

IF COL_LENGTH(N'psa.[holiday]', N'time_end') IS NULL
ALTER TABLE psa.[holiday] ADD [time_end] NVARCHAR(8) NULL;

IF COL_LENGTH(N'psa.[calendar]', N'inactive') IS NULL
ALTER TABLE psa.[calendar] ADD [inactive] INT NULL CONSTRAINT [DF_calendar_inactive] DEFAULT (0) CONSTRAINT [CK_calendar_inactive_01] CHECK (inactive IN (0, 1));

IF COL_LENGTH(N'psa.[ticket_schedule]', N'status_id') IS NULL
ALTER TABLE psa.[ticket_schedule] ADD [status_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_schedule_status_id] REFERENCES psa.[schedule_status]([status_id]);

IF COL_LENGTH(N'psa.[ticket_schedule]', N'location_id') IS NULL
ALTER TABLE psa.[ticket_schedule] ADD [location_id] NVARCHAR(64) NULL CONSTRAINT [FK_ticket_schedule_location_id] REFERENCES psa.[service_location]([location_id]);

IF COL_LENGTH(N'psa.[ticket_schedule]', N'is_lead') IS NULL
ALTER TABLE psa.[ticket_schedule] ADD [is_lead] INT NULL CONSTRAINT [DF_ticket_schedule_is_lead] DEFAULT (0) CONSTRAINT [CK_ticket_schedule_is_lead_01] CHECK (is_lead IN (0, 1));

IF COL_LENGTH(N'psa.[ticket_schedule]', N'conflict_allowed') IS NULL
ALTER TABLE psa.[ticket_schedule] ADD [conflict_allowed] INT NULL CONSTRAINT [DF_ticket_schedule_conflict_allowed] DEFAULT (0) CONSTRAINT [CK_ticket_schedule_conflict_allowed_01] CHECK (conflict_allowed IN (0, 1));

IF COL_LENGTH(N'psa.[ticket_schedule]', N'done_at') IS NULL
ALTER TABLE psa.[ticket_schedule] ADD [done_at] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[ticket_schedule]', N'acknowledged_at') IS NULL
ALTER TABLE psa.[ticket_schedule] ADD [acknowledged_at] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[ext_invoice]', N'supplier_ref') IS NULL
ALTER TABLE psa.[ext_invoice] ADD [supplier_ref] NVARCHAR(400) NULL;

-- Which sheet an entry sits on. Stamped when the entry is written into an
-- open week, and on every entry of the week when it is submitted, so rows
-- that predate this step join their sheet the first time it is submitted.
IF COL_LENGTH(N'psa.[time_entry]', N'timesheet_id') IS NULL
ALTER TABLE psa.[time_entry] ADD [timesheet_id] INT NULL CONSTRAINT [FK_time_entry_timesheet_id] REFERENCES psa.[timesheet]([timesheet_id]);

-- The recurrence a ticket was raised by, so the ticket says so and a report can group them.
IF COL_LENGTH(N'psa.[ticket]', N'recurrence_id') IS NULL
ALTER TABLE psa.[ticket] ADD [recurrence_id] INT NULL CONSTRAINT [FK_ticket_recurrence_id] REFERENCES psa.[recurrence]([recurrence_id]);

IF COL_LENGTH(N'psa.[configuration]', N'purchased_on') IS NULL
ALTER TABLE psa.[configuration] ADD [purchased_on] NVARCHAR(32) NULL;

IF COL_LENGTH(N'psa.[configuration]', N'warranty_ends_on') IS NULL
ALTER TABLE psa.[configuration] ADD [warranty_ends_on] NVARCHAR(32) NULL;

IF COL_LENGTH(N'psa.[configuration]', N'installed_on') IS NULL
ALTER TABLE psa.[configuration] ADD [installed_on] NVARCHAR(32) NULL;

IF COL_LENGTH(N'psa.[configuration]', N'vendor') IS NULL
ALTER TABLE psa.[configuration] ADD [vendor] NVARCHAR(400) NULL;

IF COL_LENGTH(N'psa.[configuration]', N'purchase_ref') IS NULL
ALTER TABLE psa.[configuration] ADD [purchase_ref] NVARCHAR(400) NULL;

-- the BizBox PO number, as a plain reference
IF COL_LENGTH(N'psa.[configuration]', N'location') IS NULL
ALTER TABLE psa.[configuration] ADD [location] NVARCHAR(400) NULL;

-- the ward and room, in words
IF COL_LENGTH(N'psa.[configuration]', N'agreement_id') IS NULL
ALTER TABLE psa.[configuration] ADD [agreement_id] NVARCHAR(64) NULL CONSTRAINT [FK_configuration_agreement_id] REFERENCES psa.[agreement]([agreement_id]);

IF COL_LENGTH(N'psa.[department]', N'approver') IS NULL
ALTER TABLE psa.[department] ADD [approver] NVARCHAR(200) NULL;

-- an email at the hospital
IF COL_LENGTH(N'psa.[catalogue_item]', N'needs_approval') IS NULL
ALTER TABLE psa.[catalogue_item] ADD [needs_approval] INT NULL CONSTRAINT [DF_catalogue_item_needs_approval] DEFAULT (0) CONSTRAINT [CK_catalogue_item_needs_approval_01] CHECK (needs_approval IN (0, 1));

-- Added columns are NULL-able by the port's rule (a row from before 050 has no
-- value); the desk reads NULL as EMAIL everywhere.
IF COL_LENGTH(N'psa.[notification]', N'channel') IS NULL
ALTER TABLE psa.[notification] ADD [channel] NVARCHAR(32) NULL CONSTRAINT [DF_notification_channel] DEFAULT ('EMAIL') CONSTRAINT [CK_notification_channel_01] CHECK (channel IN ('EMAIL', 'TEAMS'));

IF COL_LENGTH(N'psa.[notification]', N'target_id') IS NULL
ALTER TABLE psa.[notification] ADD [target_id] NVARCHAR(64) NULL CONSTRAINT [FK_notification_target_id] REFERENCES psa.[channel_target]([target_id]);

IF COL_LENGTH(N'psa.[notification]', N'page_id') IS NULL
ALTER TABLE psa.[notification] ADD [page_id] INT NULL CONSTRAINT [FK_notification_page_id] REFERENCES psa.[page]([page_id]);

IF COL_LENGTH(N'psa.[workflow_action]', N'channel') IS NULL
ALTER TABLE psa.[workflow_action] ADD [channel] NVARCHAR(32) NULL CONSTRAINT [DF_workflow_action_channel] DEFAULT ('EMAIL') CONSTRAINT [CK_workflow_action_channel_01] CHECK (channel IN ('EMAIL', 'TEAMS', 'PAGE'));

-- A card's channel is also written to target_member: 008's CHECK asks that a
-- notify reach someone, and for a card the someone is the channel.
IF COL_LENGTH(N'psa.[workflow_action]', N'target_id') IS NULL
ALTER TABLE psa.[workflow_action] ADD [target_id] NVARCHAR(64) NULL CONSTRAINT [FK_workflow_action_target_id] REFERENCES psa.[channel_target]([target_id]);

-- A board claims an address. Mail to it lands on that board, whichever
-- mailbox delivered it: Exchange can alias biomed@ onto the one helpdesk
-- mailbox and one pickup task serves every board, or each board can have a
-- mailbox of its own with a pickup task each. The reference PSA needs a
-- connector (a mailbox and a credential) per board; this needs an address.
IF COL_LENGTH(N'psa.[board]', N'intake_address') IS NULL
ALTER TABLE psa.[board] ADD [intake_address] NVARCHAR(400) NULL;

-- The address the message was routed by, when one was.
IF COL_LENGTH(N'psa.[intake_message]', N'to_address') IS NULL
ALTER TABLE psa.[intake_message] ADD [to_address] NVARCHAR(400) NULL;

-- 054: the source of a change on the audit trail, and the indexes a reader needs
--
-- Setup > Audit reads audit_event, which every change has written since 003.
-- What it could not say is WHERE a change came from: the desk, the portal, the
-- API, the mail pickup, the rules runner, or a command on the host. The
-- reference PSA's audit entry carries a source (Member / API / Workflow /
-- Portal / EmailConnector ...); this adds the same, stamped by the entry point
-- and never by the engine that made the change. Rows from before this step
-- read as unknown, which is the truth.
IF COL_LENGTH(N'psa.[audit_event]', N'source') IS NULL
ALTER TABLE psa.[audit_event] ADD [source] NVARCHAR(32) NULL;

-- The type and status a configuration has, when it is one made here; NULL
-- reads as the 021 code in config_type / status.
IF COL_LENGTH(N'psa.[configuration]', N'type_id') IS NULL
ALTER TABLE psa.[configuration] ADD [type_id] NVARCHAR(64) NULL CONSTRAINT [FK_configuration_type_id] REFERENCES psa.[configuration_type]([type_id]);

IF COL_LENGTH(N'psa.[configuration]', N'status_id') IS NULL
ALTER TABLE psa.[configuration] ADD [status_id] NVARCHAR(64) NULL CONSTRAINT [FK_configuration_status_id] REFERENCES psa.[configuration_status]([status_id]);

-- The survey per board: NULL is on, as it always was; the question is the
-- board's own words, else the desk's.
IF COL_LENGTH(N'psa.[board]', N'survey_enabled') IS NULL
ALTER TABLE psa.[board] ADD [survey_enabled] INT NULL CONSTRAINT [CK_board_survey_enabled_01] CHECK (survey_enabled IN (0, 1));

IF COL_LENGTH(N'psa.[board]', N'survey_question') IS NULL
ALTER TABLE psa.[board] ADD [survey_question] NVARCHAR(400) NULL;

IF COL_LENGTH(N'psa.[kb_article]', N'category_id') IS NULL
ALTER TABLE psa.[kb_article] ADD [category_id] NVARCHAR(64) NULL CONSTRAINT [FK_kb_article_category_id] REFERENCES psa.[kb_category]([category_id]);

IF COL_LENGTH(N'psa.[entity]', N'status_id') IS NULL
ALTER TABLE psa.[entity] ADD [status_id] NVARCHAR(64) NULL CONSTRAINT [FK_entity_status_id] REFERENCES psa.[company_status]([status_id]);

IF COL_LENGTH(N'psa.[entity]', N'type_id') IS NULL
ALTER TABLE psa.[entity] ADD [type_id] NVARCHAR(64) NULL CONSTRAINT [FK_entity_type_id] REFERENCES psa.[company_type]([type_id]);

-- Auto-assign: a rule per Subtype > Item pair names the member; with no rule,
-- the board's mode: nobody (NULL or OFF), the member with the fewest open
-- tickets on the board, or the default team's leader. A ticket that arrives
-- with an owner keeps it.
IF COL_LENGTH(N'psa.[board]', N'auto_assign') IS NULL
ALTER TABLE psa.[board] ADD [auto_assign] NVARCHAR(32) NULL CONSTRAINT [CK_board_auto_assign_01] CHECK (auto_assign IN ('OFF', 'LEAST_LOADED', 'TEAM_LEADER'));

-- Which address a notification goes out from: the one the requester wrote
-- to, when a board claims it. NULL: the sender's own mailbox, as before.
IF COL_LENGTH(N'psa.[notification]', N'from_address') IS NULL
ALTER TABLE psa.[notification] ADD [from_address] NVARCHAR(200) NULL;

-- 059: the desk's schedule on each member's Outlook calendar, and their
-- Outlook busy times on the desk (Dada, 1 Oct 2026: "the members should have
-- their accounts calendars synced with the actual calendars on outlook").
--
-- The desk holds no mail or calendar credential. It queues what changed;
-- scripts/Sync-PsaCalendars.ps1 on DND-SQL01 writes it to the member's
-- calendar through Microsoft Graph (the mail app's certificate, Exchange RBAC
-- for Applications "Application Calendars.ReadWrite" scoped to the desk's
-- members) and reports back, then reads each member's busy times back in.

-- The Outlook event a visit or a block is, once it has been written.
IF COL_LENGTH(N'psa.[ticket_schedule]', N'outlook_event_id') IS NULL
ALTER TABLE psa.[ticket_schedule] ADD [outlook_event_id] NVARCHAR(400) NULL;

IF COL_LENGTH(N'psa.[schedule_block]', N'outlook_event_id') IS NULL
ALTER TABLE psa.[schedule_block] ADD [outlook_event_id] NVARCHAR(400) NULL;

-- 062: a desk sysadmin by the member record (SQL01 part 29, 1 Oct 2026:
-- a Windows sign-in is never a sysadmin, so every member change answers 403
-- and "members cannot be removed").
--
-- Until now the cross-board flag lived only on a break-glass local account
-- and on the Entra claim, so the normal Windows sign-in could run no Setup
-- page that needs it. The flag is now also on the member record: a Windows
-- or Entra sign-in whose member row carries it is a sysadmin, live at every
-- request, so granting and revoking take effect without a sign-out. Set on
-- Setup > Members by a sysadmin (never on yourself, never the last one off),
-- or by `psaspine set-sysadmin` on the host for the first one.
IF COL_LENGTH(N'psa.[member]', N'is_sysadmin') IS NULL
ALTER TABLE psa.[member] ADD [is_sysadmin] INT NULL CONSTRAINT [DF_member_is_sysadmin] DEFAULT (0);

-- 064: a note may be written as rich text (Dada, 2 Oct 2026: "a proper text
-- editor via html or like html or teams text editor").
--
-- A technician writes a note the way they write a Teams message, and pastes
-- out of Outlook or Word. So `ticket_event.detail` may now hold HTML as well
-- as plain text, and this column says which it is: NULL or 'TEXT' for every
-- note ever written until now and every note that arrives by email, 'HTML'
-- for one written in the editor.
--
-- Nothing is stored as HTML until `richtext.clean` has rebuilt it out of its
-- own allow-lists, and the PHI scan reads `richtext.text` of it, never the
-- markup, so a patient's name cannot hide inside an attribute.
IF COL_LENGTH(N'psa.[ticket_event]', N'body_format') IS NULL
ALTER TABLE psa.[ticket_event] ADD [body_format] NVARCHAR(32) NULL;

-- NULL reads as TEXT

-- And the requester's email carries the note as it was written. The text of
-- the email is always there; this is the same email with the note's own
-- formatting in it, built when the note is written and sent as the HTML part.
IF COL_LENGTH(N'psa.[notification]', N'body_html') IS NULL
ALTER TABLE psa.[notification] ADD [body_html] NVARCHAR(MAX) NULL;

-- 066: an email's inline images, shown where the sender put them (Dada, 6 Oct
-- 2026: "images are not rendering on the ticket").
--
-- A picture pasted into an Outlook message is not a link. It travels inside
-- the message as a part of its own, and the HTML points at it with
-- `<img src="cid:image004.jpg@01DD5349.6A321CD0">`, the Content-ID of that
-- part. Intake has always kept the part itself, as an attachment through the
-- patient-details review; what it threw away was the name the HTML calls it
-- by, so the note could never find its own picture again.
--
-- This is that name, as the sending client wrote it, without the angle
-- brackets. It is read only when a note is drawn: the stored HTML keeps
-- `cid:...`, never a URL, and the page decides what the person looking may
-- see -- the desk any file not withheld, the requester's portal only a
-- file that has been cleared. NULL for every file that came any other way.
IF COL_LENGTH(N'psa.[attachment]', N'content_id') IS NULL
ALTER TABLE psa.[attachment] ADD [content_id] NVARCHAR(400) NULL;

IF COL_LENGTH(N'psa.[project_ticket]', N'budget_hours') IS NULL
ALTER TABLE psa.[project_ticket] ADD [budget_hours] DECIMAL(9,2) NULL;

IF COL_LENGTH(N'psa.[project]', N'entity_id') IS NULL
ALTER TABLE psa.[project] ADD [entity_id] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[project]', N'is_template') IS NULL
ALTER TABLE psa.[project] ADD [is_template] INT NULL;

IF COL_LENGTH(N'psa.[project]', N'health') IS NULL
ALTER TABLE psa.[project] ADD [health] NVARCHAR(32) NULL;

IF COL_LENGTH(N'psa.[project_ticket]', N'starts_on') IS NULL
ALTER TABLE psa.[project_ticket] ADD [starts_on] NVARCHAR(32) NULL;

IF COL_LENGTH(N'psa.[project_ticket]', N'due_on') IS NULL
ALTER TABLE psa.[project_ticket] ADD [due_on] NVARCHAR(32) NULL;

IF COL_LENGTH(N'psa.[project]', N'project_status_id') IS NULL
ALTER TABLE psa.[project] ADD [project_status_id] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[project]', N'project_type_id') IS NULL
ALTER TABLE psa.[project] ADD [project_type_id] NVARCHAR(64) NULL;

IF COL_LENGTH(N'psa.[api_token]', N'scope') IS NULL
ALTER TABLE psa.[api_token] ADD [scope] NVARCHAR(32) NULL CONSTRAINT [DF_api_token_scope] DEFAULT ('RAISE') CONSTRAINT [CK_api_token_scope_01] CHECK (scope IN ('RAISE', 'READ', 'WRITE'));

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

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_contact_email' AND object_id = OBJECT_ID(N'psa.[contact]'))
CREATE INDEX [ix_contact_email] ON psa.[contact] ([email]);

-- One contact per AD object. Manual contacts have no GUID, and there may be many
-- of them, so NULL is kept out of the index (see the translator's emit_index).
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ux_contact_ad_guid' AND object_id = OBJECT_ID(N'psa.[contact]'))
CREATE UNIQUE INDEX [ux_contact_ad_guid] ON psa.[contact] ([ad_object_guid]) WHERE [ad_object_guid] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_configuration_entity' AND object_id = OBJECT_ID(N'psa.[configuration]'))
CREATE INDEX [ix_configuration_entity] ON psa.[configuration] ([entity_id]);

-- One configuration per AD object; manual ones have no GUID (see 020).
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ux_configuration_ad_guid' AND object_id = OBJECT_ID(N'psa.[configuration]'))
CREATE UNIQUE INDEX [ux_configuration_ad_guid] ON psa.[configuration] ([ad_object_guid]) WHERE [ad_object_guid] IS NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_change_approval_ticket' AND object_id = OBJECT_ID(N'psa.[change_approval]'))
CREATE INDEX [ix_change_approval_ticket] ON psa.[change_approval] ([work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_notification_status' AND object_id = OBJECT_ID(N'psa.[notification]'))
CREATE INDEX [ix_notification_status] ON psa.[notification] ([status]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_task_ticket' AND object_id = OBJECT_ID(N'psa.[ticket_task]'))
CREATE INDEX [ix_ticket_task_ticket] ON psa.[ticket_task] ([work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_attachment_ticket' AND object_id = OBJECT_ID(N'psa.[attachment]'))
CREATE INDEX [ix_attachment_ticket] ON psa.[attachment] ([work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_event_ticket' AND object_id = OBJECT_ID(N'psa.[ticket_event]'))
CREATE INDEX [ix_ticket_event_ticket] ON psa.[ticket_event] ([work_item_id], [ticket_event_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_clock_ticket' AND object_id = OBJECT_ID(N'psa.[ticket_clock]'))
CREATE INDEX [ix_ticket_clock_ticket] ON psa.[ticket_clock] ([work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_clock_pause_clock' AND object_id = OBJECT_ID(N'psa.[ticket_clock_pause]'))
CREATE INDEX [ix_ticket_clock_pause_clock] ON psa.[ticket_clock_pause] ([clock_id], [paused_at]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_board_state' AND object_id = OBJECT_ID(N'psa.[ticket]'))
CREATE INDEX [ix_ticket_board_state] ON psa.[ticket] ([board_id], [state]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_parent' AND object_id = OBJECT_ID(N'psa.[ticket]'))
CREATE INDEX [ix_ticket_parent] ON psa.[ticket] ([parent_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_user_view_member' AND object_id = OBJECT_ID(N'psa.[user_view]'))
CREATE INDEX [ix_user_view_member] ON psa.[user_view] ([member], [sort_order]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_standard_note_board' AND object_id = OBJECT_ID(N'psa.[standard_note]'))
CREATE INDEX [ix_standard_note_board] ON psa.[standard_note] ([board_id], [inactive], [name]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_merged' AND object_id = OBJECT_ID(N'psa.[ticket]'))
CREATE INDEX [ix_ticket_merged] ON psa.[ticket] ([merged_into]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_schedule_day' AND object_id = OBJECT_ID(N'psa.[ticket_schedule]'))
CREATE INDEX [ix_ticket_schedule_day] ON psa.[ticket_schedule] ([starts_at]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_schedule_ticket' AND object_id = OBJECT_ID(N'psa.[ticket_schedule]'))
CREATE INDEX [ix_ticket_schedule_ticket] ON psa.[ticket_schedule] ([work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_time_entry_ticket' AND object_id = OBJECT_ID(N'psa.[time_entry]'))
CREATE INDEX [ix_time_entry_ticket] ON psa.[time_entry] ([work_item_id], [worked_on]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_department_board_board' AND object_id = OBJECT_ID(N'psa.[department_board]'))
CREATE INDEX [ix_department_board_board] ON psa.[department_board] ([board_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_schedule_block_day' AND object_id = OBJECT_ID(N'psa.[schedule_block]'))
CREATE INDEX [ix_schedule_block_day] ON psa.[schedule_block] ([starts_at]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_schedule_block_member' AND object_id = OBJECT_ID(N'psa.[schedule_block]'))
CREATE INDEX [ix_schedule_block_member] ON psa.[schedule_block] ([member]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_project_phase_project' AND object_id = OBJECT_ID(N'psa.[project_phase]'))
CREATE INDEX [ix_project_phase_project] ON psa.[project_phase] ([project_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_project_ticket_project' AND object_id = OBJECT_ID(N'psa.[project_ticket]'))
CREATE INDEX [ix_project_ticket_project] ON psa.[project_ticket] ([project_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ext_link_ref' AND object_id = OBJECT_ID(N'psa.[ext_link]'))
CREATE INDEX [ix_ext_link_ref] ON psa.[ext_link] ([source_id], [kind], [ext_ref]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ext_po_line_po' AND object_id = OBJECT_ID(N'psa.[ext_po_line]'))
CREATE INDEX [ix_ext_po_line_po] ON psa.[ext_po_line] ([source_id], [po_ref]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ext_change_ref' AND object_id = OBJECT_ID(N'psa.[ext_change]'))
CREATE INDEX [ix_ext_change_ref] ON psa.[ext_change] ([source_id], [kind], [ext_ref]);

-- Two lookups the primary keys do not serve, found by EXPLAIN on a 50,000-row
-- mirror: the Knowledge pod on a ticket (kb_ticket by ticket; its key leads
-- with the article) and the invoices under an agreement. Plain CREATE INDEX:
-- the port guards every index with its own IF NOT EXISTS.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_kb_ticket_ticket' AND object_id = OBJECT_ID(N'psa.[kb_ticket]'))
CREATE INDEX [ix_kb_ticket_ticket] ON psa.[kb_ticket] ([work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ext_invoice_agreement' AND object_id = OBJECT_ID(N'psa.[ext_invoice]'))
CREATE INDEX [ix_ext_invoice_agreement] ON psa.[ext_invoice] ([source_id], [agreement_ref]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_agreement_item_ref' AND object_id = OBJECT_ID(N'psa.[agreement_item]'))
CREATE INDEX [ix_agreement_item_ref] ON psa.[agreement_item] ([source_id], [kind], [ext_ref]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_timesheet_event_sheet' AND object_id = OBJECT_ID(N'psa.[timesheet_event]'))
CREATE INDEX [ix_timesheet_event_sheet] ON psa.[timesheet_event] ([timesheet_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_time_entry_sheet' AND object_id = OBJECT_ID(N'psa.[time_entry]'))
CREATE INDEX [ix_time_entry_sheet] ON psa.[time_entry] ([timesheet_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_recurrence_due' AND object_id = OBJECT_ID(N'psa.[recurrence]'))
CREATE INDEX [ix_recurrence_due] ON psa.[recurrence] ([active], [next_due_on]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_approval_ticket' AND object_id = OBJECT_ID(N'psa.[approval]'))
CREATE INDEX [ix_approval_ticket] ON psa.[approval] ([work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_approval_approver' AND object_id = OBJECT_ID(N'psa.[approval]'))
CREATE INDEX [ix_approval_approver] ON psa.[approval] ([approver], [status]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_page_open' AND object_id = OBJECT_ID(N'psa.[page]'))
CREATE INDEX [ix_page_open] ON psa.[page] ([status], [work_item_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_kb_file_article' AND object_id = OBJECT_ID(N'psa.[kb_file]'))
CREATE INDEX [ix_kb_file_article] ON psa.[kb_file] ([article_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_opportunity_stage' AND object_id = OBJECT_ID(N'psa.[opportunity]'))
CREATE INDEX [ix_opportunity_stage] ON psa.[opportunity] ([stage], [expected_on]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_quote_opportunity' AND object_id = OBJECT_ID(N'psa.[quote]'))
CREATE INDEX [ix_quote_opportunity] ON psa.[quote] ([opportunity_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_quote_line_quote' AND object_id = OBJECT_ID(N'psa.[quote_line]'))
CREATE INDEX [ix_quote_line_quote] ON psa.[quote_line] ([quote_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_calendar_feed_hash' AND object_id = OBJECT_ID(N'psa.[calendar_feed]'))
CREATE INDEX [ix_calendar_feed_hash] ON psa.[calendar_feed] ([token_hash]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_audit_event_when' AND object_id = OBJECT_ID(N'psa.[audit_event]'))
CREATE INDEX [ix_audit_event_when] ON psa.[audit_event] ([occurred_at]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_audit_event_actor' AND object_id = OBJECT_ID(N'psa.[audit_event]'))
CREATE INDEX [ix_audit_event_actor] ON psa.[audit_event] ([actor]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_audit_event_subject' AND object_id = OBJECT_ID(N'psa.[audit_event]'))
CREATE INDEX [ix_audit_event_subject] ON psa.[audit_event] ([subject_kind], [subject_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_configuration_question_type' AND object_id = OBJECT_ID(N'psa.[configuration_question]'))
CREATE INDEX [ix_configuration_question_type] ON psa.[configuration_question] ([type_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_calendar_sync_status' AND object_id = OBJECT_ID(N'psa.[calendar_sync]'))
CREATE INDEX [ix_calendar_sync_status] ON psa.[calendar_sync] ([status]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_outlook_busy_member' AND object_id = OBJECT_ID(N'psa.[outlook_busy]'))
CREATE INDEX [ix_outlook_busy_member] ON psa.[outlook_busy] ([member], [starts_at]);

-- One running timer per person per ticket. Two would double-count the same
-- hour, and a person who wants a second one wants a second ticket. Nothing
-- stops the same person running timers on several tickets at once, which is
-- what a technician carrying three jobs actually does.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ux_time_timer_running' AND object_id = OBJECT_ID(N'psa.[time_timer]'))
CREATE UNIQUE INDEX [ux_time_timer_running] ON psa.[time_timer] ([work_item_id], [member]) WHERE [stopped_at] IS NULL;

-- What the Time pod and the header indicator read: this person's timers,
-- newest first.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_time_timer_member' AND object_id = OBJECT_ID(N'psa.[time_timer]'))
CREATE INDEX [ix_time_timer_member] ON psa.[time_timer] ([member], [stopped_at]);

-- "My tickets": every ticket a person is on, by person.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_resource_member' AND object_id = OBJECT_ID(N'psa.[ticket_resource]'))
CREATE INDEX [ix_ticket_resource_member] ON psa.[ticket_resource] ([member]);

-- "My projects": every project a person is on, by person.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_project_member_member' AND object_id = OBJECT_ID(N'psa.[project_member]'))
CREATE INDEX [ix_project_member_member] ON psa.[project_member] ([member]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_project_note_project' AND object_id = OBJECT_ID(N'psa.[project_note]'))
CREATE INDEX [ix_project_note_project] ON psa.[project_note] ([project_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_project_plan_item_project' AND object_id = OBJECT_ID(N'psa.[project_plan_item]'))
CREATE INDEX [ix_project_plan_item_project] ON psa.[project_plan_item] ([project_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_project_issue_project' AND object_id = OBJECT_ID(N'psa.[project_issue]'))
CREATE INDEX [ix_project_issue_project] ON psa.[project_issue] ([project_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_chat_session_status' AND object_id = OBJECT_ID(N'psa.[chat_session]'))
CREATE INDEX [ix_chat_session_status] ON psa.[chat_session] ([status], [board_id]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_chat_session_requester' AND object_id = OBJECT_ID(N'psa.[chat_session]'))
CREATE INDEX [ix_chat_session_requester] ON psa.[chat_session] ([requester]);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_chat_message_chat' AND object_id = OBJECT_ID(N'psa.[chat_message]'))
CREATE INDEX [ix_chat_message_chat] ON psa.[chat_message] ([chat_id], [message_id]);

-- One token, one row. A table-level unique index rather than an inline UNIQUE
-- because the port's DDL reader takes the former and refuses the latter.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ux_api_token_sha256' AND object_id = OBJECT_ID(N'psa.[api_token]'))
CREATE UNIQUE INDEX [ux_api_token_sha256] ON psa.[api_token] ([token_sha256]);

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
 WHERE s.name = @Schema AND i.type = 2 AND i.is_primary_key = 0 AND i.is_unique_constraint = 0;

IF @Tables <> 146 OR @Triggers <> 4 OR @Indexes < 64
BEGIN
    ROLLBACK TRANSACTION;
    RAISERROR(N'VERIFY FAILED: found %d tables (expected 146), %d triggers (expected 4), %d indexes (expected at least 64). Rolled back; nothing was created.',
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
    ALTER TABLE psa.[entity] DROP CONSTRAINT IF EXISTS [FK_entity_type_id];
    ALTER TABLE psa.[entity] DROP CONSTRAINT IF EXISTS [FK_entity_status_id];
    ALTER TABLE psa.[kb_article] DROP CONSTRAINT IF EXISTS [FK_kb_article_category_id];
    ALTER TABLE psa.[configuration] DROP CONSTRAINT IF EXISTS [FK_configuration_status_id];
    ALTER TABLE psa.[configuration] DROP CONSTRAINT IF EXISTS [FK_configuration_type_id];
    ALTER TABLE psa.[workflow_action] DROP CONSTRAINT IF EXISTS [FK_workflow_action_target_id];
    ALTER TABLE psa.[notification] DROP CONSTRAINT IF EXISTS [FK_notification_page_id];
    ALTER TABLE psa.[notification] DROP CONSTRAINT IF EXISTS [FK_notification_target_id];
    ALTER TABLE psa.[configuration] DROP CONSTRAINT IF EXISTS [FK_configuration_agreement_id];
    ALTER TABLE psa.[ticket] DROP CONSTRAINT IF EXISTS [FK_ticket_recurrence_id];
    ALTER TABLE psa.[time_entry] DROP CONSTRAINT IF EXISTS [FK_time_entry_timesheet_id];
    ALTER TABLE psa.[ticket_schedule] DROP CONSTRAINT IF EXISTS [FK_ticket_schedule_location_id];
    ALTER TABLE psa.[ticket_schedule] DROP CONSTRAINT IF EXISTS [FK_ticket_schedule_status_id];
    ALTER TABLE psa.[board] DROP CONSTRAINT IF EXISTS [FK_board_default_work_type_id];
    ALTER TABLE psa.[board] DROP CONSTRAINT IF EXISTS [FK_board_default_work_role_id];
    ALTER TABLE psa.[time_entry] DROP CONSTRAINT IF EXISTS [FK_time_entry_ticket_event_id];
    ALTER TABLE psa.[time_entry] DROP CONSTRAINT IF EXISTS [FK_time_entry_work_type_id];
    ALTER TABLE psa.[time_entry] DROP CONSTRAINT IF EXISTS [FK_time_entry_work_role_id];
    ALTER TABLE psa.[ticket] DROP CONSTRAINT IF EXISTS [FK_ticket_merged_into];
    ALTER TABLE psa.[ticket] DROP CONSTRAINT IF EXISTS [FK_ticket_parent_id];
    ALTER TABLE psa.[workflow_action] DROP CONSTRAINT IF EXISTS [FK_workflow_action_target_template_id];
    ALTER TABLE psa.[board] DROP CONSTRAINT IF EXISTS [FK_board_reopen_status_id];
    ALTER TABLE psa.[ticket] DROP CONSTRAINT IF EXISTS [FK_ticket_contact_id];
    ALTER TABLE psa.[board] DROP CONSTRAINT IF EXISTS [FK_board_calendar_id];
    ALTER TABLE psa.[time_entry] DROP CONSTRAINT IF EXISTS [FK_time_entry_loop_reply_id];
    ALTER TABLE psa.[ticket] DROP CONSTRAINT IF EXISTS [FK_ticket_board_status_id];
    DROP TABLE IF EXISTS psa.[local_account];
    DROP TABLE IF EXISTS psa.[api_token];
    DROP TABLE IF EXISTS psa.[chat_message];
    DROP TABLE IF EXISTS psa.[chat_session];
    DROP TABLE IF EXISTS psa.[project_issue];
    DROP TABLE IF EXISTS psa.[project_role];
    DROP TABLE IF EXISTS psa.[project_type];
    DROP TABLE IF EXISTS psa.[project_status];
    DROP TABLE IF EXISTS psa.[project_plan_item];
    DROP TABLE IF EXISTS psa.[project_ticket_dependency];
    DROP TABLE IF EXISTS psa.[project_contact];
    DROP TABLE IF EXISTS psa.[project_note];
    DROP TABLE IF EXISTS psa.[project_member];
    DROP TABLE IF EXISTS psa.[ticket_resource];
    DROP TABLE IF EXISTS psa.[time_timer];
    DROP TABLE IF EXISTS psa.[dispatch_view];
    DROP TABLE IF EXISTS psa.[ticket_cc];
    DROP TABLE IF EXISTS psa.[priority];
    DROP TABLE IF EXISTS psa.[outlook_busy];
    DROP TABLE IF EXISTS psa.[calendar_sync];
    DROP TABLE IF EXISTS psa.[status_mail];
    DROP TABLE IF EXISTS psa.[board_intake_address];
    DROP TABLE IF EXISTS psa.[member_presence];
    DROP TABLE IF EXISTS psa.[board_auto_assign];
    DROP TABLE IF EXISTS psa.[company_type];
    DROP TABLE IF EXISTS psa.[company_status];
    DROP TABLE IF EXISTS psa.[kb_category];
    DROP TABLE IF EXISTS psa.[mail_template];
    DROP TABLE IF EXISTS psa.[configuration_answer];
    DROP TABLE IF EXISTS psa.[configuration_question];
    DROP TABLE IF EXISTS psa.[configuration_status];
    DROP TABLE IF EXISTS psa.[configuration_type];
    DROP TABLE IF EXISTS psa.[mail_exclusion];
    DROP TABLE IF EXISTS psa.[calendar_feed];
    DROP TABLE IF EXISTS psa.[member];
    DROP TABLE IF EXISTS psa.[quote_line];
    DROP TABLE IF EXISTS psa.[quote];
    DROP TABLE IF EXISTS psa.[opportunity];
    DROP TABLE IF EXISTS psa.[kb_file];
    DROP TABLE IF EXISTS psa.[page];
    DROP TABLE IF EXISTS psa.[channel_target];
    DROP TABLE IF EXISTS psa.[approval];
    DROP TABLE IF EXISTS psa.[recurrence];
    DROP TABLE IF EXISTS psa.[role_grant];
    DROP TABLE IF EXISTS psa.[member_capacity];
    DROP TABLE IF EXISTS psa.[timesheet_event];
    DROP TABLE IF EXISTS psa.[timesheet];
    DROP TABLE IF EXISTS psa.[agreement_item];
    DROP TABLE IF EXISTS psa.[agreement];
    DROP TABLE IF EXISTS psa.[ext_change];
    DROP TABLE IF EXISTS psa.[ext_po_line];
    DROP TABLE IF EXISTS psa.[ext_link];
    DROP TABLE IF EXISTS psa.[ext_invoice];
    DROP TABLE IF EXISTS psa.[ext_purchase_order];
    DROP TABLE IF EXISTS psa.[ext_product];
    DROP TABLE IF EXISTS psa.[ext_agreement];
    DROP TABLE IF EXISTS psa.[ext_source];
    DROP TABLE IF EXISTS psa.[report_def];
    DROP TABLE IF EXISTS psa.[project_ticket];
    DROP TABLE IF EXISTS psa.[phase_dependency];
    DROP TABLE IF EXISTS psa.[project_phase];
    DROP TABLE IF EXISTS psa.[project];
    DROP TABLE IF EXISTS psa.[member_role];
    DROP TABLE IF EXISTS psa.[role_permission];
    DROP TABLE IF EXISTS psa.[security_role];
    DROP TABLE IF EXISTS psa.[kb_ticket];
    DROP TABLE IF EXISTS psa.[kb_revision];
    DROP TABLE IF EXISTS psa.[kb_article];
    DROP TABLE IF EXISTS psa.[schedule_block];
    DROP TABLE IF EXISTS psa.[service_location];
    DROP TABLE IF EXISTS psa.[schedule_status];
    DROP TABLE IF EXISTS psa.[department_board];
    DROP TABLE IF EXISTS psa.[department];
    DROP TABLE IF EXISTS psa.[work_type];
    DROP TABLE IF EXISTS psa.[work_role];
    DROP TABLE IF EXISTS psa.[survey_response];
    DROP TABLE IF EXISTS psa.[ticket_schedule];
    DROP TABLE IF EXISTS psa.[standard_note];
    DROP TABLE IF EXISTS psa.[user_view];
    DROP TABLE IF EXISTS psa.[attachment];
    DROP TABLE IF EXISTS psa.[ticket_task];
    DROP TABLE IF EXISTS psa.[ticket_template_task];
    DROP TABLE IF EXISTS psa.[ticket_template];
    DROP TABLE IF EXISTS psa.[notification];
    DROP TABLE IF EXISTS psa.[ticket_link];
    DROP TABLE IF EXISTS psa.[change_approval];
    DROP TABLE IF EXISTS psa.[sla_target_type];
    DROP TABLE IF EXISTS psa.[board_record_type];
    DROP TABLE IF EXISTS psa.[integration_link];
    DROP TABLE IF EXISTS psa.[ticket_configuration];
    DROP TABLE IF EXISTS psa.[configuration];
    DROP TABLE IF EXISTS psa.[contact];
    DROP TABLE IF EXISTS psa.[api_alert];
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
