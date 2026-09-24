-- Tests only. A SYNTHETIC stand-in for BizBox's database: this is NOT BizBox's
-- schema. BizBox's real tables are NOT VERIFIED; PMC's DBA maps them onto the
-- view below with the vendor (README, "The BizBox connector"). The connector
-- only needs the view's shape. Carried from the HIS-link research proof.
CREATE DATABASE BizBoxSim;
GO
USE BizBoxSim;
GO
CREATE TABLE dbo.patient (
  hospital_no   varchar(12)   NOT NULL PRIMARY KEY,
  last_name     nvarchar(60)  NOT NULL,
  first_name    nvarchar(60)  NOT NULL,
  middle_name   nvarchar(60)  NULL,
  birth_date    date          NULL,
  sex           char(1)       NULL,
  rowver        rowversion
);
CREATE TABLE dbo.imaging_order (
  order_no         varchar(16)   NOT NULL PRIMARY KEY,
  hospital_no      varchar(12)   NOT NULL REFERENCES dbo.patient(hospital_no),
  encounter_no     varchar(16)   NULL,
  section          varchar(8)    NOT NULL,   -- XRAY / CT / MRI / US / CATH / ECHO
  procedure_code   varchar(16)   NOT NULL,
  procedure_desc   nvarchar(64)  NOT NULL,
  referring_doctor nvarchar(64)  NULL,
  priority         varchar(8)    NOT NULL DEFAULT 'ROUTINE',
  scheduled_at     datetime2(0)  NOT NULL,
  status           varchar(12)   NOT NULL DEFAULT 'ORDERED',  -- ORDERED / CANCELLED
  rowver           rowversion
);
GO
-- The contract: one view. change_seq is the larger rowversion of the order and
-- its patient, so a corrected name or birth date is a change too.
CREATE VIEW dbo.v_pmc_imaging_orders AS
SELECT o.order_no, o.hospital_no, p.last_name, p.first_name, p.middle_name, p.birth_date, p.sex,
       o.encounter_no, o.section, o.procedure_code, o.procedure_desc, o.referring_doctor,
       o.priority, o.scheduled_at, o.status,
       CAST(CASE WHEN o.rowver > p.rowver THEN o.rowver ELSE p.rowver END AS bigint) AS change_seq
FROM dbo.imaging_order AS o
JOIN dbo.patient AS p ON p.hospital_no = o.hospital_no;
GO
