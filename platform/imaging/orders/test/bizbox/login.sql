-- Tests only: the connector's login, as PMC's DBA would make it. Least
-- privilege: SELECT on the one view, nothing else, so every table and every
-- write is refused. The password arrives as the sqlcmd variable ro_password.
USE master;
GO
IF SUSER_ID('pmc_orders_ro') IS NULL
  CREATE LOGIN pmc_orders_ro WITH PASSWORD = '$(ro_password)', CHECK_POLICY = ON, DEFAULT_DATABASE = BizBoxSim;
GO
USE BizBoxSim;
GO
IF USER_ID('pmc_orders_ro') IS NULL CREATE USER pmc_orders_ro FOR LOGIN pmc_orders_ro;
GRANT SELECT ON dbo.v_pmc_imaging_orders TO pmc_orders_ro;
GO
