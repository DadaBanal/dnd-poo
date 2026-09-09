# WS36 — the ConnectWise PSA entity model, extracted

**9 September 2026. GENERATED FILE — do not hand-edit.**

```
git clone --depth 1 https://github.com/HealthITAU/pyconnectwise <path>
python3 tools/connectwise_model.py --source <path> --write
```

**[VERIFIED 9 Sep 2026]** Extracted from `HealthITAU/pyconnectwise` at commit `5ea14c1`, file `src/pyconnectwise/models/manage/__init__.py`.

**432 entities and 5573 fields**, once the 341 `Reference`/`Info`/transport wrappers are set aside. 334 closed vocabularies. 773 classes in all.

## What this is, and what it is not

ConnectWise's own documentation is behind ConnectWise University authentication and cannot be read from a build. `pyconnectwise` is code-generated from **ConnectWise's own OpenAPI schemas**, so the entity names, field names and types below are ConnectWise's. The generation is a third party's and the grouping is ours.

**It carries no behaviour.** An enum tells you the values a field accepts and never what the product does with them. Every design claim drawn from this file is INFERRED unless it is also stated in ConnectWise's documentation.

**It has already earned its place.** Reading it falsified a claim this programme had recorded as VERIFIED — that ConnectWise cannot derive priority from impact and urgency. It can; the matrix is on `SLA`, not on `Priority`. See `WS36-psa-build-scope-20260909.md` §2.2.1 and the correction block in `WS36-psa-recommendation-20260909.md`.

**There is no drift gate on this file.** It is generated from an external clone that CI does not have, unlike `sqlserver/`, which is generated from this repository and is gated. Regenerate deliberately and name the upstream commit when you do.

## The shape of a complete PSA

| Domain | Entities | Why it is here |
|---|---|---|
| **Service delivery — the board** | 29 | The unit of configuration. A board owns its statuses, types, teams and rules. |
| **Service delivery — the ticket** | 21 | The work itself, and everything that hangs off it. |
| **SLA and calendars** | 9 | Three clocks, four calendar kinds, and the working week as data. |
| **Workflow — the rules engine** | 10 | Scope, condition, execution policy and typed actions, all as rows. |
| **Commercial — agreements and billing** | 51 | Where a PSA turns work into money. The half the spine already models differently. |
| **Procurement** | 30 | A module Dada asked for. Every one of these extends the same base record. |
| **Configurations — the CMDB** | 5 | What a ticket is ABOUT. Medical devices become configuration items. |
| **Companies, contacts and sites** | 42 | Who asks, and where they are. |
| **Projects** | 12 | The other work type extending the same base. Phases, tasks, budgets. |
| **Sales and marketing** | 27 | Not PMC's problem this year. Listed so the omission is a decision. |
| **Time and expense** | 10 | The numerator of any capacity claim. |
| **Finance — general ledger and accounting** | 30 | The export into an accounting system. Out of scope, and it is here so that is a decision. |
| **Members, security and system** | 93 | The plumbing. Note the audit trail is a first-class entity. |
| **Classification and reference data** | 9 | The lookup tables every module hangs off. |
| **Reference and transport shapes** | 341 | Not entities: embedded shapes and request wrappers. |
| **Unclassified** | 54 | Did not match a group. |

**[INFERRED]** The count is the point. A PSA that a hospital would call complete is not a ticket table with some columns; it is roughly this many objects, and the ones Dada asked for later — procurement, finance — are already whole domains here. That is the argument for the base class in `WS36-psa-build-scope` §5.1: each of these arrives as a table extending `work_item`, or it arrives as a rewrite.

## Closed vocabularies

Every enumerated field in the model. These are the ones worth arguing with, because each is a decision somebody at ConnectWise made and had to live with.

- **AccountingPackageReference.identifier** — `QB99` · `Mas200` · `GPlains` · `SBA` · `Mas200v4` · `Other`
- **AccountingPackageSetup.expenseFormat** — `Default` · `Condensed`
- **AccountingPackageSetup.invoiceFormat** — `Default` · `Condensed` · `Detailed`
- **ActivityStopwatch.billableOption** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ActivityStopwatch.status** — `Reset` · `Running` · `Paused` · `Stopped`
- **Addition.agreementStatus** — `Active` · `Cancelled` · `Expired` · `Inactive`
- **Addition.billCustomer** — `Billable` · `DoNotBill` · `NoCharge`
- **Agreement.agreementStatus** — `Active` · `Cancelled` · `Expired` · `Inactive`
- **Agreement.applicationCycle** — `Contract2Weeks` · `Contract4Weeks` · `ContractYear` · `CalendarMonth` · `CalendarQuarter` · `CalendarWeek` · `ContractQuarter` · `CalendarYear`
- **Agreement.applicationUnits** — `Amount` · `Hours` · `Incidents`
- **Agreement.billExpenses** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Agreement.billProducts** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Agreement.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Agreement.employeeCompNotExceed** — `Billing` · `Amount` · `Percent`
- **Agreement.employeeCompRate** — `Actual` · `Hourly`
- **Agreement.invoicingCycle** — `ContractYear` · `CalendarYear`
- **Agreement.periodType** — `Current` · `Future` · `Both` · `Undefined`
- **AgreementType.applicationCycle** — `Contract2Weeks` · `Contract4Weeks` · `ContractYear` · `CalendarMonth` · `CalendarQuarter` · `CalendarWeek` · `ContractQuarter` · `CalendarYear`
- **AgreementType.applicationUnits** — `Amount` · `Hours` · `Incidents`
- **AgreementType.billExpenses** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **AgreementType.billProducts** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **AgreementType.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **AgreementType.employeeCompNotExceed** — `Billing` · `Amount` · `Percent`
- **AgreementType.employeeCompRate** — `Actual` · `Hourly`
- **AgreementType.invoicingCycle** — `ContractYear` · `CalendarYear`
- **AgreementType.prefixSuffixOption** — `Prefix` · `Suffix`
- **AgreementTypeInfo.applicationUnits** — `Amount` · `Hours` · `Incidents`
- **AgreementTypeWorkRole.rateType** — `AdjAmount` · `Custom` · `Multiplier`
- **AgreementTypeWorkType.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **AgreementTypeWorkType.overageRateType** — `AdjAmount` · `Custom` · `Multiplier`
- **AgreementTypeWorkType.rateType** — `AdjAmount` · `Custom` · `Multiplier`
- **AgreementWorkRole.rateType** — `AdjAmount` · `Custom` · `Multiplier`
- **AgreementWorkType.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **AgreementWorkType.overageRateType** — `AdjAmount` · `Custom` · `Multiplier`
- **AgreementWorkType.rateType** — `AdjAmount` · `Custom` · `Multiplier`
- **AuditTrailEntryGetRequest.type** — `None` · `Ticket` · `Contact` · `Company` · `Opportunity` · `Time` · `Activity` · `ProductCatalog` · `ProjectTicket` · `Purchasing` · `Configuration` · `Schedule` · `Agreement` · `AgreementAddition` · `Project` · `Invoice` · `PurchaseOrder` · `Expense`
- **BillingCycle.billingOptions** — `BiMonthly` · `BiWeekly` · `Monthly` · `NotRecurring` · `Quarterly` · `SemiAnnual` · `Weekly` · `Yearly`
- **BillingSetup.prefixSuffixFlag** — `Prefix` · `Suffix`
- **BillingSetupRouting.invoiceRule** — `All` · `Standard` · `Project` · `Agreement`
- **BillingSetupRouting.routingRule** — `Account` · `Territory` · `Creator` · `Department` · `Location` · `Member` · `Project` · `Sales`
- **Board.allSort** — `Ascending` · `Descending`
- **Board.billExpense** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Board.billProduct** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Board.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Board.internalAnalysisSort** — `Ascending` · `Descending`
- **Board.percentageCalculation** — `ActualHours` · `Manual` · `ClosedPhases` · `ClosedTickets`
- **Board.problemSort** — `Ascending` · `Descending`
- **Board.resolutionSort** — `Ascending` · `Descending`
- **BoardAutoTemplate.budgetHoursSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.discussionSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.documentsSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.financeInformationSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.internalAnalysisSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.resolutionSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.resourcesSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.sendNotesAsEmailSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.summarySetting** — `Append` · `Overwrite` · `Ignore`
- **BoardAutoTemplate.tasksSetting** — `Append` · `Overwrite` · `Ignore`
- **BoardInfo.allSort** — `Ascending` · `Descending`
- **BoardInfo.internalAnalysisSort** — `Ascending` · `Descending`
- **BoardInfo.problemSort** — `Ascending` · `Descending`
- **BoardInfo.resolutionSort** — `Ascending` · `Descending`
- **BoardStatus.escalationStatus** — `NotResponded` · `Responded` · `ResolutionPlan` · `Resolved` · `NoEscalation`
- **BoardType.category** — `Reactive` · `Proactive`
- **CatalogItem.billableOption** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **CatalogItem.priceAttribute** — `FixedFee` · `NotToExceed` · `OverrideRate` · `TimeAndMaterials`
- **CatalogItem.productClass** — `Agreement` · `Bundle` · `Inventory` · `NonInventory` · `Service`
- **CatalogItem.recurringCycleType** — `ContractYear` · `CalendarYear`
- **CatalogItemInfo.billableOption** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **CatalogItemInfo.productClass** — `Agreement` · `Bundle` · `Inventory` · `NonInventory` · `Service`
- **ChargeCode.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ClearPickerRequest.type** — `Company` · `Vendor`
- **Commission.billingMethod** — `Agreement` · `CreditMemo` · `DownPayment` · `Miscellaneous` · `Progress` · `Standard`
- **Commission.commissionBasis** — `GrossProfit` · `SalesAmount`
- **Commission.invoiceOption** — `AllInvoices` · `PaidInvoices`
- **CompanyManagementSummary.deviceType** — `WorkstationsAndServers` · `BackupStats` · `Servers` · `Workstations`
- **CompanyMerge.accountNumber** — `From` · `To`
- **CompanyMerge.activities** — `Discard` · `Merge`
- **CompanyMerge.billingAddress** — `From` · `To`
- **CompanyMerge.billingContact** — `From` · `To`
- **CompanyMerge.billingTerms** — `From` · `To`
- **CompanyMerge.contacts** — `Discard` · `Merge`
- **CompanyMerge.dateAcquired** — `From` · `To`
- **CompanyMerge.documents** — `Discard` · `Merge`
- **CompanyMerge.fax** — `From` · `To`
- **CompanyMerge.identifier** — `From` · `To`
- **CompanyMerge.market** — `From` · `To`
- **CompanyMerge.name** — `From` · `To`
- **CompanyMerge.notes** — `Discard` · `Merge`
- **CompanyMerge.numberOfEmployees** — `From` · `To`
- **CompanyMerge.opportunities** — `Discard` · `Merge`
- **CompanyMerge.phone** — `From` · `To`
- **CompanyMerge.primaryAddress** — `From` · `To`
- **CompanyMerge.primaryContact** — `From` · `To`
- **CompanyMerge.projects** — `Discard` · `Merge`
- **CompanyMerge.revenue** — `From` · `To`
- **CompanyMerge.revenueYear** — `From` · `To`
- **CompanyMerge.services** — `Discard` · `Merge`
- **CompanyMerge.sicCode** — `From` · `To`
- **CompanyMerge.sites** — `Discard` · `Merge`
- **CompanyMerge.sourceList** — `From` · `To`
- **CompanyMerge.status** — `From` · `To`
- **CompanyMerge.taxCode** — `From` · `To`
- **CompanyMerge.territory** — `From` · `To`
- **CompanyMerge.timeZone** — `From` · `To`
- **CompanyMerge.type** — `From` · `To`
- **CompanyMerge.userDefinedField1** — `From` · `To`
- **CompanyMerge.userDefinedField10** — `From` · `To`
- **CompanyMerge.userDefinedField2** — `From` · `To`
- **CompanyMerge.userDefinedField3** — `From` · `To`
- **CompanyMerge.userDefinedField4** — `From` · `To`
- **CompanyMerge.userDefinedField5** — `From` · `To`
- **CompanyMerge.userDefinedField6** — `From` · `To`
- **CompanyMerge.userDefinedField7** — `From` · `To`
- **CompanyMerge.userDefinedField8** — `From` · `To`
- **CompanyMerge.userDefinedField9** — `From` · `To`
- **CompanyMerge.website** — `From` · `To`
- **ConfigurationQuestion.fieldType** — `TextArea` · `Currency` · `Date` · `Hyperlink` · `IPAddress` · `Checkbox` · `Number` · `Percent` · `Text` · `Password`
- **ConfigurationTypeQuestion.entryType** — `Date` · `EntryField` · `List` · `Option`
- **ConfigurationTypeQuestion.fieldType** — `TextArea` · `Currency` · `Date` · `Hyperlink` · `IPAddress` · `Checkbox` · `Number` · `Percent` · `Text` · `Password`
- **ConfigurationTypeQuestionInfo.entryType** — `Date` · `EntryField` · `List` · `Option`
- **ConfigurationTypeQuestionInfo.fieldType** — `TextArea` · `Currency` · `Date` · `Hyperlink` · `IPAddress` · `Checkbox` · `Number` · `Percent` · `Text` · `Password`
- **ConnectWiseHostedSetup.type** — `Tab` · `Pod` · `ToolbarButton`
- **Contact.gender** — `Female` · `Male`
- **Contact.presence** — `NoAgent` · `Online` · `DoNotDisturb` · `Away` · `Offline`
- **ContactCommunication.communicationType** — `Email` · `Fax` · `Phone`
- **ContactCommunicationItem.communicationType** — `Email` · `Fax` · `Phone`
- **ConvertItem.recordType** — `ProjectIssue` · `ProjectTicket` · `ServiceTicket`
- **ConvertToProject.recordType** — `ProjectIssue` · `ProjectTicket` · `ServiceTicket`
- **CorporateStructure.fiscalYearStart** — `January` · `February` · `March` · `April` · `May` · `June` · `July` · `August` · `September` · `October` · `November` · `December`
- **CorporateStructure.levelCount** — `Level1` · `Level2` · `Level3` · `Level4` · `Level5`
- **Country.coreEntityCountryCode** — `AF` · `AX` · `AL` · `DZ` · `AS` · `AD` · `AO` · `AI` · `AQ` · `AR` · `AM` · `AW` · `AT` · `AZ` · `BH` · `BD` · `BB` · `BY` · `BZ` · `BJ` · `BM` · `BT` · `BO` · `BQ` · `BA` · `BW` · `BV` · `IO` · `BN` · `BG` · `BF` · `BI` · `CM` · `CV` · `KY` · `CF` · `TD` · `CL` · `CX` · `CC` · `CO` · `KM` · `CG` · `CK` · `CI` · `HR` · `CU` · `CW` · `CY` · `CZ` · `CD` · `DK` · `DJ` · `DM` · `EC` · `EG` · `GQ` · `ER` · `EE` · `ET` · `FK` · `FO` · `FJ` · `FI` · `FR` · `GF` · `PF` · `TF` · `GA` · `GM` · `GE` · `GH` · `GI` · `GR` · `GL` · `GD` · `GP` · `GU` · `GT` · `GG` · `GN` · `GW` · `GY` · `HT` · `HM` · `HN` · `HK` · `HU` · `IS` · `IN` · `IR` · `IQ` · `IE` · `IM` · `IT` · `JM` · `JP` · `JE` · `JO` · `KZ` · `KE` · `KI` · `XK` · `KW` · `KG` · `LA` · `LV` · `LB` · `LS` · `LR` · `LY` · `LI` · `LT` · `LU` · `MO` · `MK` · `MG` · `MW` · `MY` · `ML` · `MT` · `MH` · `MQ` · `MR` · `MU` · `YT` · `FM` · `MD` · `MC` · `MN` · `ME` · `MS` · `MZ` · `NA` · `NR` · `NP` · `NC` · `NZ` · `NI` · `NE` · `NG` · `NU` · `NF` · `KP` · `MP` · `OM` · `PK` · `PW` · `PS` · `PG` · `PY` · `PE` · `PN` · `PL` · `PT` · `PR` · `RE` · `RO` · `RU` · `RW` · `BL` · `SH` · `PM` · `VC` · `WS` · `SM` · `ST` · `SN` · `RS` · `SC` · `SL` · `SX` · `SK` · `SI` · `SB` · `SO` · `ZA` · `GS` · `KR` · `SS` · `ES` · `LK` · `SD` · `SR` · `SJ` · `SZ` · `SE` · `SY` · `TJ` · `TZ` · `TH` · `TL` · `TG` · `TK` · `TO` · `TN` · `TR` · `TV` · `UG` · `UA` · `GB` · `UM` · `UZ` · `VU` · `VN` · `WF` · `EH` · `YE` · `ZM` · `ZW` · `US` · `CR` · `MX` · `AE` · `VI` · `VG` · `SA` · `KH` · `AU` · `ID` · `CA` · `BR` · `TW` · `TM` · `TC` · `QA` · `MM` · `CN` · `SG` · `IL` · `VA` · `DE` · `NL` · `AG` · `BE` · `LC` · `UY` · `PH` · `BS` · `VE` · `CH` · `MF` · `KN` · `TT` · `DO` · `PA` · `MV` · `SV` · `NO` · `MA` · `AC` · `TA`
- **CustomFieldValue.entryMethod** — `Date` · `EntryField` · `List` · `Option`
- **CustomFieldValue.type** — `TextArea` · `Button` · `Currency` · `Date` · `Hyperlink` · `IPAddress` · `Checkbox` · `Number` · `Percent` · `Text` · `Password`
- **CustomReport.module** — `Companies` · `Finance` · `Marketing` · `Procurement` · `Project` · `Sales` · `ServiceDesk` · `TimeExpense`
- **EmailConnector.emailServerType** — `IMAP` · `Office365` · `Google`
- **ExpenseEntry.billableOption** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ExpenseEntry.chargeToType** — `ServiceTicket` · `ProjectTicket` · `ChargeCode` · `Activity`
- **ExpenseEntry.status** — `Open` · `Rejected` · `PendingApproval` · `ErrorsCorrected` · `PendingProjectApproval` · `ApprovedByTierOne` · `RejectBySecondTier` · `ApprovedByTierTwo` · `ReadyToBill` · `Billed` · `WrittenOff` · `BilledAgreement`
- **ExpenseReport.status** — `Open` · `Rejected` · `PendingApproval` · `ErrorsCorrected` · `PendingProjectApproval` · `ApprovedByTierOne` · `RejectBySecondTier` · `ApprovedByTierTwo` · `ReadyToBill` · `Billed` · `WrittenOff` · `BilledAgreement`
- **ExpenseType.billExpenses** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ExpenseType.invoiceMarkupOption** — `Amount` · `Mile` · `Percent`
- **ExportAccountingBatchRequest.summarizeInvoices** — `Default` · `Condensed` · `Detailed`
- **ForecastItem.forecastType** — `Other1` · `Other2` · `Agreement` · `Product` · `Service`
- **GLAccount.glType** — `AP` · `AR` · `EE` · `EI` · `EO` · `IA` · `IT` · `P` · `PF` · `R` · `RA` · `RD` · `RE` · `RP` · `ST` · `SD` · `ET` · `FT` · `PT`
- **GLCaption.segment10type** — `Account` · `Class`
- **GLCaption.segment1type** — `Account` · `Class`
- **GLCaption.segment2type** — `Account` · `Class`
- **GLCaption.segment3type** — `Account` · `Class`
- **GLCaption.segment4type** — `Account` · `Class`
- **GLCaption.segment5type** — `Account` · `Class`
- **GLCaption.segment6type** — `Account` · `Class`
- **GLCaption.segment7type** — `Account` · `Class`
- **GLCaption.segment8type** — `Account` · `Class`
- **GLCaption.segment9type** — `Account` · `Class`
- **Invoice.applyToType** — `All` · `Agreement` · `Project` · `ProjectPhase` · `SalesOrder` · `Ticket`
- **Invoice.type** — `Agreement` · `CreditMemo` · `DownPayment` · `Miscellaneous` · `Progress` · `Standard`
- **InvoiceTemplate.headerAddressPosition** — `Center` · `LeftSide` · `RightSide`
- **InvoiceTemplate.headerLogoPosition** — `Center` · `LeftSide` · `RightSide`
- **InvoiceTemplate.headerTitleFont** — `Regular` · `RegularBold` · `Large` · `LargeBold` · `ExtraLarge` · `ExtraLargeBold`
- **InvoiceTemplate.headerTitlePosition** — `Center` · `LeftSide` · `RightSide`
- **Link.screenLink** — `Company` · `Contact` · `Service` · `Invoice` · `PurchaseOrder` · `SalesOrder`
- **LinkInfo.screenLink** — `Company` · `Contact` · `Service` · `Invoice` · `PurchaseOrder` · `SalesOrder`
- **ManagedDevicesIntegration.defaultBillingLevel** — `Detail` · `Summary`
- **ManagedDevicesIntegration.loginBy** — `Global` · `Member`
- **ManagedDevicesIntegrationNotification.logType** — `All` · `Error` · `NewManagedSolution` · `NewDeviceType` · `NewConfiguration` · `NewAddition` · `Info`
- **ManagementBackup.billingLevel** — `Detail` · `Summary`
- **ManagementItSolution.managementItSolutionType** — `LevelPlatforms` · `NAble` · `Continuum` · `Custom`
- **MappedType.glType** — `AP` · `AR` · `EE` · `EI` · `EO` · `IA` · `IT` · `P` · `PF` · `R` · `RA` · `RD` · `RE` · `RP` · `ST` · `SD` · `ET` · `FT` · `PT`
- **MarketplaceImport.marketplaceImportType** — `Agreements` · `Configurations` · `CRMSurveys` · `CustomReports` · `CustomerPortalTypes` · `HTMLEmailTemplates` · `Products` · `ProjectBoards` · `ProjectTemplates` · `ReportWriterReports` · `ServiceBoards` · `TicketTemplates` · `Views`
- **Member.agreementInvoicingDisplayOptions** — `RemainOnInvoicingScreen` · `ShowRecentInvoices`
- **Member.authenticationServiceType** — `AuthAnvil` · `GoogleAuthenticator` · `Email`
- **Member.companyActivityTabFormat** — `SummaryList` · `DetailList`
- **Member.defaultEmail** — `Office` · `Mobile` · `Home`
- **Member.defaultPhone** — `Office` · `Mobile` · `Home`
- **Member.globalSearchDefaultSort** — `None` · `LastUpdatedDesc` · `LastUpdatedAsc` · `CreatedDesc` · `CreatedAsc`
- **Member.globalSearchDefaultTicketFilter** — `OpenRecords` · `ClosedRecords` · `AllRecords`
- **Member.invoiceScreenDefaultTabFormat** — `ShowInvoicingTab` · `ShowAgreementInvoicingTab`
- **Member.invoiceTimeTabFormat** — `SummaryList` · `DetailList`
- **Member.invoicingDisplayOptions** — `RemainOnInvoicingScreen` · `ShowRecentInvoices`
- **Member.licenseClass** — `A` · `C` · `F` · `X`
- **Member.phoneIntegrationType** — `TAPI` · `SKYPE` · `NONE`
- **MemberAccrual.accrualType** — `Holiday` · `PTO` · `Sick` · `Vacation`
- **MemberDelegation.delegationType** — `Approval` · `Project`
- **MemberInfo.licenseClass** — `A` · `C` · `F` · `X`
- **MemberNotificationSetting.notificationTrigger** — `ActivityStatusReq` · `CustomerUpdated` · `ExpenseReport` · `TicketStatusChange` · `TicketStatusRequest` · `TimeNagApprover` · `TimeNagMember` · `TimeSheet` · `WorkflowRules`
- **MemberNotificationSetting.notificationType** — `Email` · `Push`
- **MemberSkill.skillLevel** — `Beginner` · `Intermediate` · `Advanced` · `Expert`
- **MyAccount.agreementInvoicingDisplayOptions** — `RemainOnInvoicingScreen` · `ShowRecentInvoices`
- **MyAccount.authenticationServiceType** — `AuthAnvil` · `GoogleAuthenticator` · `Email`
- **MyAccount.companyActivityTabFormat** — `SummaryList` · `DetailList`
- **MyAccount.defaultEmail** — `Office` · `Mobile` · `Home`
- **MyAccount.defaultPhone** — `Office` · `Mobile` · `Home`
- **MyAccount.globalSearchDefaultSort** — `None` · `LastUpdatedDesc` · `LastUpdatedAsc` · `CreatedDesc` · `CreatedAsc`
- **MyAccount.globalSearchDefaultTicketFilter** — `OpenRecords` · `ClosedRecords` · `AllRecords`
- **MyAccount.invoiceScreenDefaultTabFormat** — `ShowInvoicingTab` · `ShowAgreementInvoicingTab`
- **MyAccount.invoiceTimeTabFormat** — `SummaryList` · `DetailList`
- **MyAccount.invoicingDisplayOptions** — `RemainOnInvoicingScreen` · `ShowRecentInvoices`
- **MyAccount.licenseClass** — `A` · `C` · `F` · `X`
- **MyAccount.phoneIntegrationType** — `TAPI` · `SKYPE` · `NONE`
- **MyMember.agreementInvoicingDisplayOptions** — `RemainOnInvoicingScreen` · `ShowRecentInvoices`
- **MyMember.authenticationServiceType** — `AuthAnvil` · `GoogleAuthenticator` · `Email`
- **MyMember.companyActivityTabFormat** — `SummaryList` · `DetailList`
- **MyMember.defaultEmail** — `Office` · `Mobile` · `Home`
- **MyMember.defaultPhone** — `Office` · `Mobile` · `Home`
- **MyMember.invoiceScreenDefaultTabFormat** — `ShowInvoicingTab` · `ShowAgreementInvoicingTab`
- **MyMember.invoiceTimeTabFormat** — `SummaryList` · `DetailList`
- **MyMember.invoicingDisplayOptions** — `RemainOnInvoicingScreen` · `ShowRecentInvoices`
- **MyMember.licenseClass** — `A` · `C` · `F` · `X`
- **MyMemberInfo.licenseClass** — `A` · `C` · `F` · `X`
- **MySecurity.addLevel** — `None` · `My` · `All`
- **MySecurity.deleteLevel** — `None` · `My` · `All`
- **MySecurity.editLevel** — `None` · `My` · `All`
- **MySecurity.inquireLevel** — `None` · `My` · `All`
- **MySecurityCustomizeItem.customizeIdentifier** — `CompanyReports` · `FinanceReports` · `MarketingReports` · `ProcurementReports` · `ProjectReports` · `SalesReports` · `ServiceReports` · `SystemReports` · `TimeAndExpenseReports` · `CompanyConfigurations` · `FinanceAgreements` · `ProjectScheduling` · `ServiceResourceScheduling` · `SystemManageHostedApi` · `SystemMyAccount` · `SystemCustomMenuEntry` · `SystemMassMaintenance` · `SystemTableSetup`
- **Other.contactSync** — `FL` · `LF` · `CFL` · `CLF`
- **OwnershipType.coreEntityOwnershipType** — `CharitableOrganization` · `Clinic` · `Government` · `Hospital` · `PrivateSchoolForProfit` · `PrivateSchoolNonProfit` · `PublicCompany` · `PublicSchool` · `Regulator` · `Reseller` · `SmallBusiness`
- **PortalCalendar.weekStart** — `Sunday` · `Monday` · `Tuesday` · `Wednesday` · `Thursday` · `Friday` · `Saturday`
- **PortalConfiguration.language** — `English` · `Spanish` · `French` · `British` · `Australian` · `BrazilianPortuguese` · `CanadianFrench` · `German` · `NewZealand` · `Dutch`
- **PortalConfigurationProjectSetup.onlyDisplay** — `DoNotDisplay` · `Closed30Days` · `Closed60Days` · `Closed90Days` · `Closed120Days` · `AllClosed`
- **PortalConfigurationServiceSetup.displayClosedTicketsOption** — `DoNotDisplay` · `Closed30Days` · `Closed60Days` · `Closed90Days` · `Closed120Days` · `AllClosed`
- **PricingBreak.priceMethod** — `FlatRateForRange` · `PercentMarkupFromCost` · `PercentMarkdownFromPrice` · `PricePerUnit`
- **Priority.color** — `Black` · `Blue` · `Cyan` · `Gray` · `Green` · `Lime` · `Orange` · `Pink` · `Purple` · `Red` · `White` · `Yellow` · `Custom`
- **ProcurementSetting.costingMethod** — `FIFO` · `LIFO` · `AverageCosting`
- **ProcurementSetting.prefixSuffixType** — `Prefix` · `Suffix`
- **ProductItem.billableOption** — `Billable` · `DoNotBill` · `NoCharge`
- **ProductItem.priceMethod** — `FlatRateForRange` · `PercentMarkupFromCost` · `PercentMarkdownFromPrice` · `PricePerUnit`
- **ProductItem.productClass** — `Agreement` · `Bundle` · `Inventory` · `NonInventory` · `Service`
- **ProductRecurring.cycleType** — `ContractYear` · `CalendarYear`
- **ProductType.typeXref** — `InventoryPart` · `NonInventoryPart` · `OtherCharge` · `Service`
- **Project.billExpenses** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Project.billProducts** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Project.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Project.billingMethod** — `ActualRates` · `FixedFee` · `NotToExceed` · `OverrideRate`
- **Project.billingRateType** — `StaffMember` · `WorkRole`
- **Project.budgetAnalysis** — `ActualHours` · `BillableHours`
- **ProjectPhase.billExpenses** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ProjectPhase.billProducts** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ProjectPhase.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ProjectPhase.billingMethod** — `ActualRates` · `FixedFee` · `NotToExceed` · `OverrideRate`
- **ProjectSecurityRoleSetting.addLevel** — `None` · `My` · `All`
- **ProjectSecurityRoleSetting.deleteLevel** — `None` · `My` · `All`
- **ProjectSecurityRoleSetting.editLevel** — `None` · `My` · `All`
- **ProjectSecurityRoleSetting.inquireLevel** — `None` · `My` · `All`
- **ProjectTicket.billExpenses** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ProjectTicket.billProducts** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ProjectTicket.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ProjectTicket.knowledgeBaseLinkType** — `Activity` · `ProjectIssue` · `KnowledgeBaseArticle` · `ProjectTicket` · `ServiceTicket` · `Time`
- **ProjectTicket.predecessorType** — `Ticket` · `Phase`
- **ProjectTicket.subBillingMethod** — `ActualRates` · `FixedFee` · `NotToExceed` · `OverrideRate`
- **ProjectTicketNote.noteType** — `TicketNote` · `TimeEntryNote` · `MeetingNote`
- **PurchaseOrderLineItem.receivedStatus** — `Waiting` · `FullyReceived` · `PartiallyReceiveCancelRest` · `PartiallyReceiveCloneRest`
- **SLA.basedOn** — `AllHours` · `Customer` · `MyCalendar` · `Custom`
- **ScheduleStopwatch.billableOption** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **ScheduleStopwatch.status** — `Reset` · `Running` · `Paused` · `Stopped`
- **SecurityRoleSetting.addLevel** — `None` · `My` · `All`
- **SecurityRoleSetting.deleteLevel** — `None` · `My` · `All`
- **SecurityRoleSetting.editLevel** — `None` · `My` · `All`
- **SecurityRoleSetting.inquireLevel** — `None` · `My` · `All`
- **Service.scheduleSpan** — `Standard` · `OfficeHours` · `Overnight`
- **Service.srNotify** — `All` · `NewAndClosedRequests` · `ClosedRequestsOnly` · `NewRequestsOnly` · `None`
- **ServiceEmailTemplate.type** — `Any` · `Closed` · `Invoice` · `New` · `SalesOrder` · `PurchaseOrder` · `RMA` · `Specific`
- **ServiceLocation.where** — `OnSite` · `Remote` · `InHouse`
- **ServiceSignoff.task** — `All` · `Closed` · `Open`
- **ServiceSurveyQuestion.type** — `OpenEnded` · `Selection`
- **ServiceTemplate.billingMethod** — `ActualRates` · `FixedFee` · `NotToExceed` · `OverrideRate`
- **ServiceTemplate.impact** — `Low` · `Medium` · `High`
- **ServiceTemplate.severity** — `Low` · `Medium` · `High`
- **ServiceTicketNote.noteType** — `TicketNote` · `TimeEntryNote` · `MeetingNote`
- **SsoConfiguration.ssoType** — `CWSSO` · `SAML`
- **SurveyQuestion.entryType** — `Date` · `EntryField` · `List` · `Option`
- **SurveyQuestion.fieldType** — `TextArea` · `Button` · `Currency` · `Date` · `Hyperlink` · `IPAddress` · `Checkbox` · `Number` · `Percent` · `Text` · `Password`
- **Task.childScheduleAction** — `Transfer` · `Delete` · `Done`
- **TaxCode.levelFiveRateType** — `Amount` · `Percent`
- **TaxCode.levelFourRateType** — `Amount` · `Percent`
- **TaxCode.levelOneRateType** — `Amount` · `Percent`
- **TaxCode.levelSixRateType** — `Amount` · `Percent`
- **TaxCode.levelThreeRateType** — `Amount` · `Percent`
- **TaxCode.levelTwoRateType** — `Amount` · `Percent`
- **TaxCodeLevel.rateType** — `Amount` · `Percent`
- **TaxCodeXRef.levelFive** — `NonTaxable` · `Taxable`
- **TaxCodeXRef.levelFour** — `NonTaxable` · `Taxable`
- **TaxCodeXRef.levelOne** — `NonTaxable` · `Taxable`
- **TaxCodeXRef.levelSix** — `NonTaxable` · `Taxable`
- **TaxCodeXRef.levelThree** — `NonTaxable` · `Taxable`
- **TaxCodeXRef.levelTwo** — `NonTaxable` · `Taxable`
- **TaxIntegration.taxIntegrationType** — `Avalara`
- **TaxIntegrationInfo.taxIntegrationType** — `Avalara`
- **Team.type** — `Individual` · `Team`
- **Ticket.billExpenses** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Ticket.billProducts** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Ticket.billTime** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **Ticket.billingMethod** — `ActualRates` · `FixedFee` · `NotToExceed` · `OverrideRate`
- **Ticket.impact** — `Low` · `Medium` · `High`
- **Ticket.knowledgeBaseLinkType** — `Activity` · `ProjectIssue` · `KnowledgeBaseArticle` · `ProjectTicket` · `ServiceTicket` · `Time`
- **Ticket.predecessorType** — `Ticket` · `Phase`
- **Ticket.recordType** — `ProjectIssue` · `ProjectTicket` · `ServiceTicket`
- **Ticket.severity** — `Low` · `Medium` · `High`
- **Ticket.subBillingMethod** — `ActualRates` · `FixedFee` · `NotToExceed` · `OverrideRate`
- **TicketStopwatch.billableOption** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **TicketStopwatch.status** — `Reset` · `Running` · `Paused` · `Stopped`
- **TicketSync.vendorType** — `Zenith`
- **TimeAccrual.holidayAvailableType** — `AnniversaryYear` · `CalendarYear`
- **TimeAccrual.ptoAvailableType** — `AnniversaryYear` · `CalendarYear`
- **TimeAccrual.sickAvailableType** — `AnniversaryYear` · `CalendarYear`
- **TimeAccrual.vacationAvailableType** — `AnniversaryYear` · `CalendarYear`
- **TimeAccrualDetail.accrualType** — `Holiday` · `PTO` · `Sick` · `Vacation`
- **TimeEntry.billableOption** — `Billable` · `DoNotBill` · `NoCharge` · `NoDefault`
- **TimeEntry.chargeToType** — `ServiceTicket` · `ProjectTicket` · `ChargeCode` · `Activity`
- **TimeEntry.status** — `Open` · `Rejected` · `PendingApproval` · `ErrorsCorrected` · `PendingProjectApproval` · `ApprovedByTierOne` · `RejectBySecondTier` · `ApprovedByTierTwo` · `ReadyToBill` · `Billed` · `WrittenOff` · `BilledAgreement`
- **TimeEntryAudit.source** — `None` · `Member` · `API` · `Workflow` · `Portal` · `Mobile` · `Network` · `EmailConnector` · `MassMaintenance` · `Application` · `SystemAPI` · `Conversion`
- **TimeEntryAudit.type** — `Activity` · `CloseDate` · `Company` · `Contact` · `Conversion` · `Document` · `Forecast` · `Note` · `Notes` · `Opportunity` · `Products` · `Stage` · `Status` · `Surveys` · `Team` · `Tracks` · `Configuration` · `ConfigurationQuestions` · `DeviceBackupDetails` · `Tickets` · `Subject` · `ActivityOverview` · `Schedule` · `Resources` · `ExpenseEntry` · `Member` · `Date` · `Classification` · `Amount` · `ExpenseType` · `WorkType` · `WorkRole` · `Mileage` · `Billing` · `ExpenseHeader` · `Project` · `TimeEntry` · `TicketStatus` · `DateTime` · `DeductHours` · `ActualHours` · `Invoice` · `CompanyFinance` · `Billable` · `SalesOrder` · `Shipping` · `Profile` · `Group` · `GroupContact` · `GroupCompany` · `Options` · `Site` · `Agreement` · `Addition` · `Adjustment` · `API` · `ProjectFinance` · `CompanyProfile` · `CompanyTeam` · `CompanyMgmt` · `InvoiceTotal` · `BillingInformation` · `ShippingInformation` · `BillingStatus` · `Location` · `Department` · `Territory` · `Payment` · `Credit` · `SubcontractorInformation` · `InvoicingParameters` · `ApplicationParameters` · `Finance` · `Invoicing` · `Email` · `Batching` · `KnowledgeBase` · `KbArticle` · `KnowledgeBaseApproval` · `KnowledgeBaseTicket` · `ManageNetwork` · `Tasks` · `CustomField` · `ScreenConnect` · `SLA` · `Ticket` · `Workflow` · `Record` · `CombinedTickets` · `Template` · `PurchaseOrder` · `Meeting` · `RmaOverview` · `ReturnedBy` · `PurchasedFromVendor` · `WarrantyVendor` · `RepairVendor` · `AdditionalDetails` · `TicketTemplate` · `AutoGeneration` · `TimeInternalNote` · `TimeDiscussion` · `TimeInternal` · `TimeResolution`
- **TimeExpense.defaultSpecialInvoiceType** — `Agreement` · `CreditMemo` · `DownPayment` · `Miscellaneous` · `Progress` · `Standard`
- **TimePeriodSetup.periodApplyTo** — `Both` · `Expense` · `Time`
- **TimePeriodSetup.type** — `Weekly` · `BiWeekly` · `SemiMonthly` · `Monthly`
- **TimeSheet.status** — `Open` · `Rejected` · `PendingApproval` · `ErrorsCorrected` · `PendingProjectApproval` · `ApprovedByTierOne` · `RejectBySecondTier` · `ApprovedByTierTwo` · `ReadyToBill` · `Billed` · `WrittenOff` · `BilledAgreement`
- **TimeSheetTierUpdate.approvalType** — `DataEntry` · `Tier1Update` · `Tier2Update` · `Billing` · `Service` · `Project` · `MonthlySummary` · `SalesActivity` · `Schedule`
- **TrackAction.notifyType** — `CreateActivity` · `SendEmail` · `AddToGroup` · `AttachTrack` · `ChangeCompanyStatus` · `CreateServiceTicket`
- **UnpostedExpense.classification** — `NonReimbursable` · `Reimbursable` · `Personal`
- **UnpostedExpense.glType** — `AP` · `AR` · `EE` · `EI` · `EO` · `IA` · `IT` · `P` · `PF` · `R` · `RA` · `RD` · `RE` · `RP` · `ST` · `SD` · `ET` · `FT` · `PT`
- **UnpostedInvoice.invoiceType** — `Agreement` · `CreditMemo` · `DownPayment` · `Miscellaneous` · `Progress` · `Standard`
- **UnpostedProcurement.procurementType** — `Purchase` · `Adjustment` · `Transfer`
- **UserDefinedField.entryTypeIdentifier** — `Date` · `EntryField` · `List` · `Option`
- **UserDefinedField.fieldTypeIdentifier** — `TextArea` · `Button` · `Currency` · `Date` · `Hyperlink` · `IPAddress` · `Checkbox` · `Number` · `Percent` · `Text` · `Password`
- **UserDefinedFieldInfo.entryTypeIdentifier** — `Date` · `EntryField` · `List` · `Option`
- **UserDefinedFieldInfo.fieldTypeIdentifier** — `TextArea` · `Button` · `Currency` · `Date` · `Hyperlink` · `IPAddress` · `Checkbox` · `Number` · `Percent` · `Text` · `Password`
- **WorkType.accrualType** — `Holiday` · `PTO` · `Sick` · `Vacation`
- **WorkType.billTime** — `Billable` · `DoNotBill` · `NoCharge`
- **WorkType.rateType** — `AdjAmount` · `Custom` · `Multiplier`
- **Workflow.batchFrequencyUnit** — `Minutes` · `Hours` · `Days`
- **Workflow.batchSchedule** — `AnyTime` · `MyCompanyOfficeHours` · `SlaHours`
- **WorkflowAction.attachConfigurationsFor** — `Company` · `Contact`
- **WorkflowEvent.executionTime** — `Once` · `MultipleTimes` · `Continuously`
- **WorkflowEvent.frequencyUnit** — `Minutes` · `Hours` · `Days` · `Months`

## Entities in full

The ones a board engine, an SLA engine, a rules engine, a CMDB, procurement or billing would be built against.

### Service delivery — the board

#### `Board` — 61 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `allSort` | `Ascending` \| `Descending` |  |  |  |
| `autoAssignNewECTicketsFlag` | bool \| None |  |  |  |
| `autoAssignNewPortalTicketsFlag` | bool \| None |  |  |  |
| `autoAssignNewTicketsFlag` | bool \| None |  |  |  |
| `autoAssignTicketOwnerFlag` | bool \| None |  |  |  |
| `autoCloseStatus` | ServiceStatusReference \| None |  |  |  |
| `billExpense` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billProduct` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billTicketSeparatelyFlag` | bool \| None |  |  |  |
| `billTicketsAfterClosedFlag` | bool \| None |  |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billUnapprovedTimeExpenseFlag` | bool \| None |  |  |  |
| `boardIcon` | DocumentReference \| None |  |  |  |
| `closedLoopAllFlag` | bool \| None |  |  |  |
| `closedLoopDiscussionsFlag` | bool \| None |  |  |  |
| `closedLoopInternalAnalysisFlag` | bool \| None |  |  |  |
| `closedLoopResolutionFlag` | bool \| None |  |  |  |
| `contactTemplate` | ServiceEmailTemplateReference \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `discussionsLockedFlag` | bool \| None |  |  |  |
| `dispatchMember` | MemberReference \| None |  |  |  |
| `dutyManagerMember` | MemberReference \| None |  |  |  |
| `emailConnectorAllowReopenClosedFlag` | bool \| None |  |  |  |
| `emailConnectorNeverReopenByDaysClosedFlag` | bool \| None |  |  | This field can only be set when emailConnectorAllowReopenClosed is true |
| `emailConnectorNeverReopenByDaysFlag` | bool \| None |  |  | This field can only be set when emailConnectorAllowReopenClosed is true |
| `emailConnectorNewTicketNoMatchFlag` | bool \| None |  |  | This field can only be set when emailConnectorAllowReopenClosed is true |
| `emailConnectorReopenDaysClosedLimit` | int \| None |  |  | This field can only be set when emailConnectorNeverReopenByDaysClosedFlag and emailConn… |
| `emailConnectorReopenDaysLimit` | int \| None |  |  | This field can only be set when emailConnectorNeverReopenByDaysFlag and emailConnectorA… |
| `emailConnectorReopenResourcesFlag` | bool \| None |  |  | This field can only be set when emailConnectorAllowReopenClosed is true |
| `emailConnectorReopenStatus` | ServiceStatusReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `internalAnalysisSort` | `Ascending` \| `Descending` |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `markFirstNoteIssueFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `notifyEmailFrom` | str \| None |  | 50 |  |
| `notifyEmailFromName` | str \| None |  | 60 |  |
| `oncallMember` | MemberReference \| None |  |  |  |
| `overrideBillingSetupFlag` | bool \| None |  |  |  |
| `percentageCalculation` | `ActualHours` \| `Manual` \| `ClosedPhases` \| `ClosedTickets` |  |  |  |
| `problemSort` | `Ascending` \| `Descending` |  |  |  |
| `projectFlag` | bool \| None |  |  |  |
| `resolutionSort` | `Ascending` \| `Descending` |  |  |  |
| `resourceTemplate` | ServiceEmailTemplateReference \| None |  |  |  |
| `restrictBoardByDefaultFlag` | bool \| None |  |  |  |
| `sendToCCFlag` | bool \| None |  |  |  |
| `sendToContactFlag` | bool \| None |  |  |  |
| `sendToResourceFlag` | bool \| None |  |  |  |
| `serviceManagerMember` | MemberReference \| None |  |  |  |
| `showDependenciesFlag` | bool \| None |  |  | This field only shows if it is Project Board. |
| `showEstimatesFlag` | bool \| None |  |  | This field only shows if it is Project Board. |
| `signOffTemplate` | ServiceSignoffReference \| None |  |  |  |
| `timeEntryDiscussionFlag` | bool \| None |  |  |  |
| `timeEntryInternalAnalysisFlag` | bool \| None |  |  |  |
| `timeEntryLockedFlag` | bool \| None |  |  |  |
| `timeEntryResolutionFlag` | bool \| None |  |  |  |
| `useMemberDisplayNameFlag` | bool \| None |  |  |  |
| `workRole` | WorkRoleReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |

#### `BoardAutoAssignResource` — 4 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `id` | int \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `notifyWho` | NotificationRecipientReference \| None |  |  |  |

#### `BoardAutoTemplate` — 18 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `autoApplyFlag` | bool \| None |  |  |  |
| `board` | BoardReference \| None |  |  |  |
| `budgetHoursSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `discussionSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `documentsSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `financeInformationSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `id` | int \| None |  |  |  |
| `internalAnalysisSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `item` | ServiceItemReference \| None |  |  |  |
| `resolutionSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `resourcesSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `sendNotesAsEmailSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `serviceTemplate` | ServiceTemplateReference \| None |  |  |  |
| `subtype` | ServiceSubTypeReference \| None |  |  |  |
| `summarySetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `tasksSetting` | `Append` \| `Overwrite` \| `Ignore` |  |  |  |
| `type` | ServiceTypeReference \| None |  |  |  |

#### `BoardDefault` — 6 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `agreementId` | int \| None |  |  |  |
| `board` | BoardReference \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `serviceType` | ServiceTypeReference \| None |  |  |  |

#### `BoardExcludedMember` — 4 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `boardId` | int \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `memberId` | int \| None |  |  |  |

#### `BoardItem` — 5 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `board` | BoardReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 50 |  |

#### `BoardNotification` — 5 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `email` | str \| None |  | 50 |  |
| `id` | int \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `notifyWho` | NotificationRecipientReference \| None |  |  |  |

#### `BoardStatus` — 16 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `board` | BoardReference \| None |  |  |  |
| `closedStatus` | bool \| None |  |  |  |
| `customStatusIndicatorName` | str \| None |  | 30 |  |
| `customerPortalDescription` | str \| None |  | 500 |  |
| `customerPortalFlag` | bool \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `displayOnBoard` | bool \| None |  |  |  |
| `emailTemplate` | ServiceEmailTemplateReference \| None |  |  |  |
| `escalationStatus` | `NotResponded` \| `Responded` \| `ResolutionPlan` \| `Resolved` \| `NoEscalation` |  |  |  |
| `id` | int \| None |  |  |  |
| `inactive` | bool \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `sortOrder` | int \| None |  |  |  |
| `statusIndicator` | StatusIndicatorReference \| None |  |  |  |
| `timeEntryNotAllowed` | bool \| None |  |  |  |

#### `BoardStatusNotification` — 7 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `email` | str \| None |  | 255 | Service Status Notification email must be entered if the notify type is "Email Address" |
| `id` | int \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `notifyWho` | NotificationRecipientReference \| None |  |  |  |
| `status` | ServiceStatusReference \| None |  |  |  |
| `workflowStep` | int \| None |  |  |  |

#### `BoardSubType` — 8 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `addAllTypesFlag` | bool \| None |  |  |  |
| `board` | BoardReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `removeAllTypesFlag` | bool \| None |  |  |  |
| `typeAssociationIds` | list[int] \| None |  |  |  |

#### `BoardTeam` — 10 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `boardId` | int \| None |  |  |  |
| `businessUnitId` | int \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `locationId` | int \| None |  |  |  |
| `members` | list[int] \| None |  |  |  |
| `name` | str | **y** | 30 |  |
| `notifyOnTicketDelete` | bool \| None |  |  |  |
| `teamLeader` | MemberReference \| None |  |  |  |

#### `BoardType` — 11 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `board` | BoardReference \| None |  |  |  |
| `category` | `Reactive` \| `Proactive` |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `integrationXref` | str \| None |  | 50 |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `requestForChangeFlag` | bool \| None |  |  |  |

#### `BoardTypeSubTypeItemAssociation` — 6 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `board` | BoardReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `item` | ServiceItemReference \| None |  |  |  |
| `subType` | ServiceSubTypeReference \| None |  |  |  |
| `type` | ServiceTypeReference \| None |  |  |  |

#### `Priority` — 7 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `color` | `Black` \| `Blue` \| `Cyan` \| `Gray` \| `Green` \| `Lime` \| `Orange` \| `Pink` \| `Purple` \| `Red` \| `White` \| `Yellow` \| `Custom` | **y** |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `imageLink` | str \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `sortOrder` | int \| None |  |  |  |

#### `ServiceLocation` — 5 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `defaultFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `name` | str | **y** | 30 |  |
| `where` | `OnSite` \| `Remote` \| `InHouse` | **y** |  |  |

#### `ServiceNote` — 16 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `contact` | ContactReference \| None |  |  |  |
| `createdBy` | str \| None |  |  |  |
| `customerUpdatedFlag` | bool \| None |  |  |  |
| `dateCreated` | datetime \| None |  |  |  |
| `detailDescriptionFlag` | bool \| None |  |  |  |
| `externalFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalAnalysisFlag` | bool \| None |  |  |  |
| `internalFlag` | bool \| None |  |  |  |
| `issueFlag` | bool \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `processNotifications` | bool \| None |  |  |  |
| `resolutionFlag` | bool \| None |  |  |  |
| `text` | str \| None |  |  |  |
| `ticketId` | int \| None |  |  |  |

#### `ServiceSignoff` — 57 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `billingMethodsText` | str \| None |  | 2000 |  |
| `billingMethodsTextFlag` | bool \| None |  |  | On add/post, if billingMethodsText.Length > 0, this is set to true |
| `billingTermsFlag` | bool \| None |  |  |  |
| `companyInfoFlag` | bool \| None |  |  |  |
| `configurationsFlag` | bool \| None |  |  |  |
| `creditCardFieldsFlag` | bool \| None |  |  |  |
| `customerSignoffFieldsFlag` | bool \| None |  |  |  |
| `customerSignoffText` | str \| None |  | 4000 |  |
| `customerSignoffTextFlag` | bool \| None |  |  | On add/post, if customerSignoffText.Length > 0, this is set to true |
| `defaultFFFlag` | bool \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `discussionFlag` | bool \| None |  |  |  |
| `expenseAgreementFlag` | bool \| None |  |  |  |
| `expenseAmountFlag` | bool \| None |  |  |  |
| `expenseBillFlag` | bool \| None |  |  |  |
| `expenseDateFlag` | bool \| None |  |  |  |
| `expenseFlag` | bool \| None |  |  | On add/post, if any expense related flag is set to true, this is also set to true |
| `expenseManualEntry` | int \| None |  |  |  |
| `expenseManualFlag` | bool \| None |  |  |  |
| `expenseMemberFlag` | bool \| None |  |  |  |
| `expenseNotesFlag` | bool \| None |  |  |  |
| `expenseTaxFlag` | bool \| None |  |  |  |
| `expenseTypeFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalNotesFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `productAgreementFlag` | bool \| None |  |  |  |
| `productBillFlag` | bool \| None |  |  |  |
| `productDescriptionFlag` | bool \| None |  |  |  |
| `productExtendedAmountFlag` | bool \| None |  |  |  |
| `productFlag` | bool \| None |  |  | On add/post, if any product related flag is set to true, this is also set to true |
| `productManualEntry` | int \| None |  |  |  |
| `productManualFlag` | bool \| None |  |  |  |
| `productPriceFlag` | bool \| None |  |  |  |
| `productQuantityFlag` | bool \| None |  |  |  |
| `productTaxFlag` | bool \| None |  |  |  |
| `resolutionFlag` | bool \| None |  |  |  |
| `summaryFlag` | bool \| None |  |  |  |
| `task` | `All` \| `Closed` \| `Open` |  |  | On add/post, if this is set but no value is set for taskFlag, taskFlag is set to true |
| `taskFlag` | bool \| None |  |  | On add/post, if this is set to true but no value is set for task, task is defaulted to … |
| `technicianSignoffFlag` | bool \| None |  |  |  |
| `timeAgreementFlag` | bool \| None |  |  |  |
| `timeBillFlag` | bool \| None |  |  |  |
| `timeDateFlag` | bool \| None |  |  |  |
| `timeExtendedAmountFlag` | bool \| None |  |  |  |
| `timeFlag` | bool \| None |  |  | On add/post, if any time related flag is set to true, this is also set to true |
| `timeHoursFlag` | bool \| None |  |  |  |
| `timeManualEntry` | int \| None |  |  |  |
| `timeManualFlag` | bool \| None |  |  |  |
| `timeMemberFlag` | bool \| None |  |  |  |
| `timeNotesFlag` | bool \| None |  |  |  |
| `timeRateFlag` | bool \| None |  |  |  |
| `timeStartEndFlag` | bool \| None |  |  |  |
| `timeTaxFlag` | bool \| None |  |  |  |
| `timeWorkTypeFlag` | bool \| None |  |  |  |
| `visibleLogoFlag` | bool \| None |  |  |  |

#### `ServiceSurvey` — 13 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `footerText` | str \| None |  | 500 |  |
| `footerTextVisibleFlag` | bool \| None |  |  |  |
| `headerIncludeLogoFlag` | bool \| None |  |  |  |
| `headerText` | str \| None |  | 4000 |  |
| `headerTextVisibleFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `notifyMember` | MemberReference \| None |  |  |  |
| `notifyWho` | GenericIdIdentifierReference \| None |  |  |  |
| `notifyWhoVisibleFlag` | bool \| None |  |  |  |
| `thankYouText` | str \| None |  | 4000 |  |

#### `ServiceSurveyQuestion` — 10 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `id` | int \| None |  |  |  |
| `includeFlag` | bool \| None |  |  |  |
| `noAnswerPoints` | int \| None |  |  |  |
| `options` | list[ServiceSurveyQuestionOption] \| None |  |  |  |
| `question` | str | **y** | 1000 |  |
| `requiredFlag` | bool \| None |  |  |  |
| `sequenceNumber` | int \| None |  |  |  |
| `surveyId` | int \| None |  |  |  |
| `type` | `OpenEnded` \| `Selection` | **y** |  |  |

#### `ServiceTeam` — 7 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `deleteNotifyFlag` | bool \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `leader` | MemberReference \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `name` | str \| None |  |  |  |

#### `ServiceTemplate` — 48 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `agreement` | AgreementReference \| None |  |  |  |
| `assignedBy` | MemberReference \| None |  |  |  |
| `assignedNotifyFlag` | bool \| None |  |  |  |
| `attachScheduleToNewServiceFlag` | bool \| None |  |  |  |
| `billComplete_Flag` | bool \| None |  |  |  |
| `billServiceSeparatelyFlag` | bool \| None |  |  |  |
| `billUnapprovedTimeAndExpensesFlag` | bool \| None |  |  |  |
| `billingAmount` | float \| None |  |  |  |
| `billingMethod` | `ActualRates` \| `FixedFee` \| `NotToExceed` \| `OverrideRate` |  |  |  |
| `board` | BoardReference \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `contact` | ContactReference \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `emailCC` | str \| None |  |  |  |
| `emailCCFlag` | bool \| None |  |  |  |
| `emailContactFlag` | bool \| None |  |  |  |
| `emailResourceFlag` | bool \| None |  |  |  |
| `expenseBillableFlag` | bool \| None |  |  |  |
| `expenseInvoiceFlag` | bool \| None |  |  |  |
| `hoursBudget` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `impact` | `Low` \| `Medium` \| `High` |  |  |  |
| `internalAnalysis` | str \| None |  |  |  |
| `item` | ServiceItemReference \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `name` | str \| None |  |  |  |
| `overrideFlag` | bool \| None |  |  |  |
| `priority` | PriorityReference \| None |  |  |  |
| `problem` | str \| None |  |  |  |
| `productInvoiceFlag` | bool \| None |  |  |  |
| `purchaseOrderNumber` | str \| None |  |  |  |
| `reference` | str \| None |  |  |  |
| `restrictDownpaymentFlag` | bool \| None |  |  |  |
| `scheduleDaysBefore` | int \| None |  |  |  |
| `serviceDaysBefore` | int \| None |  |  |  |
| `serviceLocation` | ServiceLocationReference \| None |  |  |  |
| `severity` | `Low` \| `Medium` \| `High` |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `source` | ServiceSourceReference \| None |  |  |  |
| `status` | ServiceStatusReference \| None |  |  |  |
| `subtype` | ServiceSubTypeReference \| None |  |  |  |
| `summary` | str \| None |  |  |  |
| `team` | ServiceTeamReference \| None |  |  |  |
| `templateFlag` | bool \| None |  |  |  |
| `timeBillableFlag` | bool \| None |  |  |  |
| `timeInvoiceFlag` | bool \| None |  |  |  |
| `type` | ServiceTypeReference \| None |  |  |  |

#### `Source` — 6 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `dateEntered` | datetime \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `enteredBy` | str \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `name` | str | **y** | 50 |  |

### Service delivery — the ticket

#### `ScheduleEntry` — 23 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `acknowledgedDate` | datetime \| None |  |  |  |
| `acknowledgedFlag` | bool \| None |  |  |  |
| `addMemberToProjectFlag` | bool \| None |  |  |  |
| `allowScheduleConflictsFlag` | bool \| None |  |  |  |
| `closeDate` | datetime \| None |  |  |  |
| `dateEnd` | datetime \| None |  |  |  |
| `dateStart` | datetime \| None |  |  |  |
| `doneFlag` | bool \| None |  |  |  |
| `hours` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `meetingFlag` | bool \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `name` | str \| None |  | 250 |  |
| `objectId` | int \| None |  |  |  |
| `ownerFlag` | bool \| None |  |  |  |
| `projectRoleId` | int \| None |  |  |  |
| `reminder` | ReminderReference \| None |  |  |  |
| `span` | ScheduleSpanReference \| None |  |  |  |
| `status` | ScheduleStatusReference \| None |  |  |  |
| `type` | ScheduleTypeReference \| None |  |  |  |
| `where` | ServiceLocationReference \| None |  |  |  |

#### `Ticket` — 108 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `actualHours` | float \| None |  |  |  |
| `addressLine1` | str \| None |  | 50 |  |
| `addressLine2` | str \| None |  | 50 |  |
| `agreement` | AgreementReference \| None |  |  |  |
| `allowAllClientsPortalView` | bool \| None |  |  |  |
| `approved` | bool \| None |  |  |  |
| `automaticEmailCc` | str \| None |  | 1000 |  |
| `automaticEmailCcFlag` | bool \| None |  |  |  |
| `automaticEmailContactFlag` | bool \| None |  |  |  |
| `automaticEmailResourceFlag` | bool \| None |  |  |  |
| `billExpenses` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billProducts` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billingAmount` | float \| None |  |  |  |
| `billingMethod` | `ActualRates` \| `FixedFee` \| `NotToExceed` \| `OverrideRate` |  |  |  |
| `board` | BoardReference \| None |  |  |  |
| `budgetHours` | float \| None |  |  |  |
| `city` | str \| None |  | 50 |  |
| `closedBy` | str \| None |  |  |  |
| `closedDate` | datetime \| None |  |  |  |
| `closedFlag` | bool \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `contact` | ContactReference \| None |  |  |  |
| `contactEmailAddress` | str \| None |  | 250 |  |
| `contactEmailLookup` | str \| None |  |  |  |
| `contactName` | str \| None |  | 62 |  |
| `contactPhoneExtension` | str \| None |  | 15 |  |
| `contactPhoneNumber` | str \| None |  | 20 |  |
| `country` | CountryReference \| None |  |  |  |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerUpdatedFlag` | bool \| None |  |  |  |
| `dateResolved` | str \| None |  |  |  |
| `dateResplan` | str \| None |  |  |  |
| `dateResponded` | str \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `duration` | int \| None |  |  |  |
| `escalationLevel` | int \| None |  |  |  |
| `escalationStartDateUTC` | datetime \| None |  |  |  |
| `estimatedExpenseCost` | float \| None |  |  |  |
| `estimatedExpenseRevenue` | float \| None |  |  |  |
| `estimatedProductCost` | float \| None |  |  |  |
| `estimatedProductRevenue` | float \| None |  |  |  |
| `estimatedStartDate` | datetime \| None |  |  |  |
| `estimatedTimeCost` | float \| None |  |  |  |
| `estimatedTimeRevenue` | float \| None |  |  |  |
| `externalXRef` | str \| None |  | 100 |  |
| `hasChildTicket` | bool \| None |  |  |  |
| `hasMergedChildTicketFlag` | bool \| None |  |  |  |
| `hourlyRate` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `impact` | `Low` \| `Medium` \| `High` |  |  | Required On Updates; |
| `initialDescription` | str \| None |  |  | Only available for POST, will not be returned in the response |
| `initialDescriptionFrom` | str \| None |  |  |  |
| `initialInternalAnalysis` | str \| None |  |  | Only available for POST, will not be returned in the response |
| `initialResolution` | str \| None |  |  | Only available for POST, will not be returned in the response |
| `integratorTags` | list[str] \| None |  |  |  |
| `isInSla` | bool \| None |  |  |  |
| `item` | ServiceItemReference \| None |  |  |  |
| `knowledgeBaseCategoryId` | int \| None |  |  |  |
| `knowledgeBaseLinkId` | int \| None |  |  |  |
| `knowledgeBaseLinkType` | `Activity` \| `ProjectIssue` \| `KnowledgeBaseArticle` \| `ProjectTicket` \| `ServiceTicket` \| `Time` |  |  |  |
| `knowledgeBaseSubCategoryId` | int \| None |  |  |  |
| `lagDays` | int \| None |  |  |  |
| `lagNonworkingDaysFlag` | bool \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `mergedParentTicket` | TicketReference \| None |  |  |  |
| `minutesBeforeWaiting` | int \| None |  |  |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `opportunity` | OpportunityReference \| None |  |  |  |
| `owner` | MemberReference \| None |  |  |  |
| `parentTicketId` | int \| None |  |  |  |
| `poNumber` | str \| None |  | 50 |  |
| `predecessorClosedFlag` | bool \| None |  |  |  |
| `predecessorId` | int \| None |  |  |  |
| `predecessorType` | `Ticket` \| `Phase` |  |  |  |
| `priority` | PriorityReference \| None |  |  |  |
| `processNotifications` | bool \| None |  |  | Can be set to false to skip notification processing when adding or updating a ticket (D… |
| `recordType` | `ProjectIssue` \| `ProjectTicket` \| `ServiceTicket` |  |  |  |
| `requestForChangeFlag` | bool \| None |  |  |  |
| `requiredDate` | datetime \| None |  |  |  |
| `resPlanMinutes` | int \| None |  |  |  |
| `resolveMinutes` | int \| None |  |  |  |
| `resources` | str \| None |  |  |  |
| `resplanSkippedMinutes` | int \| None |  |  |  |
| `respondMinutes` | int \| None |  |  |  |
| `respondedSkippedMinutes` | int \| None |  |  |  |
| `serviceLocation` | ServiceLocationReference \| None |  |  |  |
| `severity` | `Low` \| `Medium` \| `High` |  |  | Required On Updates; |
| `site` | SiteReference \| None |  |  |  |
| `siteName` | str \| None |  | 50 |  |
| `skipCallback` | bool \| None |  |  |  |
| `sla` | SLAReference \| None |  |  |  |
| `slaStatus` | str \| None |  |  |  |
| `source` | ServiceSourceReference \| None |  |  |  |
| `stateIdentifier` | str \| None |  | 50 |  |
| `status` | ServiceStatusReference \| None |  |  |  |
| `subBillingAmount` | float \| None |  |  |  |
| `subBillingMethod` | `ActualRates` \| `FixedFee` \| `NotToExceed` \| `OverrideRate` |  |  |  |
| `subDateAccepted` | str \| None |  |  |  |
| `subType` | ServiceSubTypeReference \| None |  |  |  |
| `summary` | str | **y** | 100 |  |
| `team` | ServiceTeamReference \| None |  |  |  |
| `type` | ServiceTypeReference \| None |  |  |  |
| `workRole` | WorkRoleReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |
| `zip` | str \| None |  | 12 |  |

#### `TicketBundle` — 1 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `childTicketIds` | list[int] \| None |  |  |  |

#### `TicketMerge` — 2 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `mergeTicketIds` | list[int | **y** |  |  |
| `status` | ServiceStatusReference \| None |  |  |  |

#### `TicketNote` — 14 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `contact` | ContactReference \| None |  |  |  |
| `customerUpdatedFlag` | bool \| None |  |  |  |
| `detailDescriptionFlag` | bool \| None |  |  |  |
| `externalFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalAnalysisFlag` | bool \| None |  |  |  |
| `internalFlag` | bool \| None |  |  |  |
| `issueFlag` | bool \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `processNotifications` | bool \| None |  |  |  |
| `resolutionFlag` | bool \| None |  |  |  |
| `text` | str \| None |  |  |  |
| `ticketId` | int \| None |  |  |  |

#### `TicketTask` — 0 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|

### SLA and calendars

#### `Calendar` — 18 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `fridayEndTime` | str \| None |  |  |  |
| `fridayStartTime` | str \| None |  |  |  |
| `holidayList` | HolidayListReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `mondayEndTime` | str \| None |  |  |  |
| `mondayStartTime` | str \| None |  |  |  |
| `name` | str | **y** |  |  |
| `saturdayEndTime` | str \| None |  |  |  |
| `saturdayStartTime` | str \| None |  |  |  |
| `sundayEndTime` | str \| None |  |  |  |
| `sundayStartTime` | str \| None |  |  |  |
| `thursdayEndTime` | str \| None |  |  |  |
| `thursdayStartTime` | str \| None |  |  |  |
| `tuesdayEndTime` | str \| None |  |  |  |
| `tuesdayStartTime` | str \| None |  |  |  |
| `wednesdayEndTime` | str \| None |  |  |  |
| `wednesdayStartTime` | str \| None |  |  |  |

#### `Holiday` — 8 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `allDayFlag` | bool \| None |  |  | Can be set to false to set a holiday for specific hours (Defaults to True) |
| `date` | date | **y** |  |  |
| `holidayList` | HolidayListReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `timeEnd` | datetime \| None |  |  |  |
| `timeStart` | datetime \| None |  |  |  |

#### `HolidayList` — 0 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|

#### `SLA` — 22 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `applicationOrder` | int \| None |  |  |  |
| `basedOn` | `AllHours` \| `Customer` \| `MyCalendar` \| `Custom` | **y** |  |  |
| `customCalendar` | CalendarReference \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `hiImpactHiUrgency` | PriorityReference \| None |  |  |  |
| `hiImpactLowUrgency` | PriorityReference \| None |  |  |  |
| `hiImpactMedUrgency` | PriorityReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `lowImpactHiUrgency` | PriorityReference \| None |  |  |  |
| `lowImpactLowUrgency` | PriorityReference \| None |  |  |  |
| `lowImpactMedUrgency` | PriorityReference \| None |  |  |  |
| `medImpactHiUrgency` | PriorityReference \| None |  |  |  |
| `medImpactLowUrgency` | PriorityReference \| None |  |  |  |
| `medImpactMedUrgency` | PriorityReference \| None |  |  |  |
| `name` | str | **y** | 25 |  |
| `planWithin` | float \| None |  |  |  |
| `planWithinPercent` | int \| None |  |  |  |
| `resolutionHours` | float \| None |  |  |  |
| `resolutionPercent` | int \| None |  |  |  |
| `respondHours` | float \| None |  |  |  |
| `respondPercent` | int \| None |  |  |  |

#### `SLAPriority` — 10 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `id` | int \| None |  |  |  |
| `planWithin` | float \| None |  |  |  |
| `planWithinPercent` | int \| None |  |  |  |
| `priority` | PriorityReference \| None |  |  |  |
| `resolutionHours` | float \| None |  |  |  |
| `resolutionPercent` | int \| None |  |  |  |
| `respondHours` | float \| None |  |  |  |
| `respondPercent` | int \| None |  |  |  |
| `sla` | SLAReference \| None |  |  |  |

#### `WorkRole` — 10 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `addAllAgreementExclusions` | bool \| None |  |  | Used only on create to add the work role to all agreement and agreement type exclusion … |
| `addAllLocations` | bool \| None |  |  |  |
| `hourlyRate` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `integrationXref` | str \| None |  | 50 |  |
| `locationIds` | list[int] \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `removeAllLocations` | bool \| None |  |  |  |

#### `WorkType` — 17 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `accrualType` | `Holiday` \| `PTO` \| `Sick` \| `Vacation` |  |  |  |
| `activityDefaultFlag` | bool \| None |  |  |  |
| `addAllAgreementExclusions` | bool \| None |  |  | Used only on create to add the work type to all agreement and agreement type exclusion … |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` | **y** |  |  |
| `costMultiplier` | float \| None |  |  |  |
| `hoursMax` | float \| None |  |  |  |
| `hoursMin` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `integrationXRef` | str \| None |  | 50 |  |
| `name` | str | **y** | 50 |  |
| `overallDefaultFlag` | bool \| None |  |  |  |
| `rate` | float | **y** |  |  |
| `rateType` | `AdjAmount` \| `Custom` \| `Multiplier` | **y** |  |  |
| `roundBillHoursTo` | float \| None |  |  |  |
| `utilizationFlag` | bool \| None |  |  |  |

### Workflow — the rules engine

#### `Workflow` — 12 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `activateFlag` | bool \| None |  |  | Batches can not be turned on until after the workflow is created and it has atleast one… |
| `batchFrequencyUnit` | `Minutes` \| `Hours` \| `Days` |  |  | If not specified, defaults to Minutes. Months is not supported as month length varies |
| `batchInterval` | int \| None |  |  |  |
| `batchLastRan` | datetime \| None |  |  |  |
| `batchSchedule` | `AnyTime` \| `MyCompanyOfficeHours` \| `SlaHours` |  |  | If activateFlag is true, batchSchedule is required |
| `board` | BoardReference \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `name` | str | **y** | 100 |  |
| `tableType` | WorkflowTableTypeReference \| None |  |  |  |

#### `WorkflowAction` — 42 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `activityStatus` | ActivityStatusReference \| None |  |  |  |
| `activityType` | ActivityTypeReference \| None |  |  |  |
| `attachConfigurationsFor` | `Company` \| `Contact` |  |  | Required when notifyType is set to: "Attach Configuration" |
| `attachedTrack` | TrackReference \| None |  |  |  |
| `attachments` | list[int] \| None |  |  |  |
| `auditNotesFlag` | bool \| None |  |  |  |
| `automateScript` | AutomateScriptReference \| None |  |  |  |
| `bccContact` | ContactReference \| None |  |  |  |
| `board` | BoardReference \| None |  |  |  |
| `boardStatus` | ServiceStatusReference \| None |  |  |  |
| `ccContact` | ContactReference \| None |  |  |  |
| `companyStatus` | CompanyStatusReference \| None |  |  |  |
| `configurationStatus` | ConfigurationStatusReference \| None |  |  |  |
| `configurationType` | ConfigurationTypeReference \| None |  |  |  |
| `daysToExecute` | int \| None |  |  |  |
| `detailNotesFlag` | bool \| None |  |  |  |
| `emailFrom` | str \| None |  | 250 | Required when notifyFrom is set to: "Email Address" |
| `emailRecipient` | str \| None |  | 250 | Required when notifyWho is set to: "Email Address" |
| `group` | GroupReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalNotesFlag` | bool \| None |  |  |  |
| `invoiceMinDays` | int \| None |  |  |  |
| `notes` | str \| None |  |  |  |
| `notifyFrom` | NotificationRecipientReference \| None |  |  |  |
| `notifyType` | NotifyTypeReference | **y** |  |  |
| `notifyWho` | NotificationRecipientReference \| None |  |  |  |
| `projectStatus` | ProjectStatusReference \| None |  |  |  |
| `salesOrderStatus` | OrderStatusReference \| None |  |  |  |
| `scriptFailStatus` | ServiceStatusReference \| None |  |  |  |
| `scriptSuccessStatus` | ServiceStatusReference \| None |  |  |  |
| `serviceItem` | ServiceItemReference \| None |  |  |  |
| `servicePriority` | PriorityReference \| None |  |  |  |
| `serviceSubType` | ServiceSubTypeReference \| None |  |  |  |
| `serviceSurvey` | ServiceSurveyReference \| None |  |  |  |
| `serviceTemplate` | ServiceTemplateReference \| None |  |  |  |
| `serviceType` | ServiceTypeReference \| None |  |  |  |
| `specificMemberFrom` | MemberReference \| None |  |  |  |
| `specificMemberTo` | MemberReference \| None |  |  |  |
| `specificTeamTo` | GenericBoardTeamReference \| None |  |  |  |
| `subject` | str \| None |  | 100 | Required when notifyType is set to: "Create Activity", "Send Email", "Assign Resource" |
| `updateOwnerFlag` | bool \| None |  |  |  |

#### `WorkflowEvent` — 8 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `eventCondition` | str | **y** |  |  |
| `executionTime` | `Once` \| `MultipleTimes` \| `Continuously` |  |  | Defaults to Once when not specified |
| `frequencyOfExecution` | int \| None |  |  | Required when exectionTimes is set to MultipleTimes or Continuously |
| `frequencyUnit` | `Minutes` \| `Hours` \| `Days` \| `Months` |  |  | Required when exectionTimes is set to MultipleTimes or Continuously |
| `id` | int \| None |  |  |  |
| `maxNumberOfExecution` | int \| None |  |  | Required when exectionTimes is set to MultipleTimes |
| `name` | str \| None |  |  |  |

#### `WorkflowNotifyType` — 6 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `externalFlag` | bool \| None |  |  | If the current action effects external objects e.g. integrations or sending an email |
| `id` | int \| None |  |  |  |
| `identifier` | str \| None |  |  |  |
| `isSetupFlag` | bool \| None |  |  | If the current action is available because it is already set up. Pertains to integratio… |
| `name` | str \| None |  |  |  |

#### `WorkflowTableType` — 0 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|

#### `WorkflowTrigger` — 8 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `customField` | UserDefinedFieldReference \| None |  |  |  |
| `description` | str \| None |  |  |  |
| `expectedType` | str \| None |  |  |  |
| `hasOperatorFlag` | bool \| None |  |  |  |
| `hasOptionsFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `name` | str \| None |  |  |  |

#### `WorkflowTriggerOption` — 4 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `customField` | UserDefinedFieldReference \| None |  |  |  |
| `name` | str \| None |  |  |  |
| `value` | str \| None |  |  |  |

### Commercial — agreements and billing

#### `Agreement` — 78 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `agreementStatus` | `Active` \| `Cancelled` \| `Expired` \| `Inactive` |  |  |  |
| `allowOverruns` | bool \| None |  |  |  |
| `applicationCycle` | `Contract2Weeks` \| `Contract4Weeks` \| `ContractYear` \| `CalendarMonth` \| `CalendarQuarter` \| `CalendarWeek` \| `ContractQuarter` \| `CalendarYear` |  |  |  |
| `applicationLimit` | float \| None |  |  |  |
| `applicationUnits` | `Amount` \| `Hours` \| `Incidents` |  |  |  |
| `applicationUnlimitedFlag` | bool \| None |  |  |  |
| `autoInvoiceFlag` | bool \| None |  |  |  |
| `billAmount` | float \| None |  |  |  |
| `billExpenses` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billOneTimeFlag` | bool \| None |  |  |  |
| `billProducts` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billStartDate` | datetime \| None |  |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billToCompany` | CompanyReference \| None |  |  |  |
| `billToContact` | ContactReference \| None |  |  |  |
| `billToSite` | SiteReference \| None |  |  |  |
| `billableExpenseInvoice` | bool \| None |  |  |  |
| `billableProductInvoice` | bool \| None |  |  |  |
| `billableTimeInvoice` | bool \| None |  |  |  |
| `billingCycle` | BillingCycleReference \| None |  |  |  |
| `billingTerms` | BillingTermsReference \| None |  |  |  |
| `bottomComment` | bool \| None |  |  |  |
| `cancelledFlag` | bool \| None |  |  |  |
| `carryOverUnused` | bool \| None |  |  |  |
| `chargeToFirm` | bool \| None |  |  |  |
| `compHourlyRate` | float \| None |  |  |  |
| `compLimitAmount` | float \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `companyLocation` | SystemLocationReference \| None |  |  |  |
| `contact` | ContactReference \| None |  |  |  |
| `coverAgreementExpense` | bool \| None |  |  |  |
| `coverAgreementProduct` | bool \| None |  |  |  |
| `coverAgreementTime` | bool \| None |  |  |  |
| `coverSalesTax` | bool \| None |  |  |  |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerPO` | str \| None |  | 50 |  |
| `dateCancelled` | datetime \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `employeeCompNotExceed` | `Billing` \| `Amount` \| `Percent` |  |  |  |
| `employeeCompRate` | `Actual` \| `Hourly` |  |  | Required On Updates; |
| `endDate` | datetime \| None |  |  |  |
| `expireWhenZero` | bool \| None |  |  |  |
| `expiredDays` | int \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalNotes` | str \| None |  |  |  |
| `invoiceDescription` | str \| None |  |  |  |
| `invoiceTemplate` | InvoiceTemplateReference \| None |  |  |  |
| `invoicingCycle` | `ContractYear` \| `CalendarYear` |  |  | Required On Updates; |
| `limit` | int \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `name` | str | **y** | 100 |  |
| `nextInvoiceDate` | datetime \| None |  |  |  |
| `noEndingDateFlag` | bool \| None |  |  |  |
| `oneTimeFlag` | bool \| None |  |  |  |
| `opportunity` | OpportunityReference \| None |  |  |  |
| `parentAgreement` | AgreementReference \| None |  |  |  |
| `periodType` | `Current` \| `Future` \| `Both` \| `Undefined` |  |  |  |
| `projectType` | ProjectTypeReference \| None |  |  |  |
| `prorateFirstBill` | float \| None |  |  |  |
| `prorateFlag` | bool \| None |  |  |  |
| `reasonCancelled` | str \| None |  | 100 |  |
| `restrictDepartmentFlag` | bool \| None |  |  |  |
| `restrictDownPayment` | bool \| None |  |  |  |
| `restrictLocationFlag` | bool \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `sla` | SLAReference \| None |  |  |  |
| `startDate` | datetime \| None |  |  |  |
| `subContractCompany` | CompanyReference \| None |  |  |  |
| `subContractContact` | ContactReference \| None |  |  |  |
| `taxCode` | TaxCodeReference \| None |  |  |  |
| `taxable` | bool \| None |  |  |  |
| `topComment` | bool \| None |  |  |  |
| `type` | AgreementTypeReference \| None |  |  |  |
| `workOrder` | str \| None |  | 20 |  |
| `workRole` | WorkRoleReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |

#### `AgreementAdjustment` — 7 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `agreementId` | int \| None |  |  |  |
| `amount` | float \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `description` | str \| None |  | 1000 |  |
| `effectiveDate` | datetime \| None |  |  |  |
| `id` | int \| None |  |  |  |

#### `AgreementSite` — 6 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `agreementId` | int \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |

#### `AgreementType` — 64 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `addAllWorkRoleExclusions` | bool \| None |  |  |  |
| `addAllWorkTypeExclusions` | bool \| None |  |  |  |
| `allowOverrunsFlag` | bool \| None |  |  |  |
| `applicationCycle` | `Contract2Weeks` \| `Contract4Weeks` \| `ContractYear` \| `CalendarMonth` \| `CalendarQuarter` \| `CalendarWeek` \| `ContractQuarter` \| `CalendarYear` |  |  |  |
| `applicationLimit` | float \| None |  |  |  |
| `applicationUnits` | `Amount` \| `Hours` \| `Incidents` |  |  |  |
| `applicationUnlimitedFlag` | bool \| None |  |  |  |
| `autoInvoiceFlag` | bool \| None |  |  |  |
| `billAmount` | float \| None |  |  |  |
| `billExpenses` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` | **y** |  |  |
| `billOneTimeFlag` | bool \| None |  |  |  |
| `billProducts` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` | **y** |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` | **y** |  |  |
| `billableExpenseInvoiceFlag` | bool \| None |  |  |  |
| `billableProductInvoiceFlag` | bool \| None |  |  |  |
| `billableTimeInvoiceFlag` | bool \| None |  |  |  |
| `billingCycle` | BillingCycleReference \| None |  |  |  |
| `billingTerms` | BillingTermsReference \| None |  |  |  |
| `bottomCommentFlag` | bool \| None |  |  |  |
| `carryOverUnusedFlag` | bool \| None |  |  |  |
| `chargeToFirmFlag` | bool \| None |  |  |  |
| `compHourlyRate` | float \| None |  |  |  |
| `compLimitAmount` | float \| None |  |  |  |
| `copyWorkRolesFlag` | bool \| None |  |  |  |
| `copyWorkTypesFlag` | bool \| None |  |  |  |
| `coverAgreementExpenseFlag` | bool \| None |  |  |  |
| `coverAgreementProductFlag` | bool \| None |  |  |  |
| `coverAgreementTimeFlag` | bool \| None |  |  |  |
| `coverSalesTaxFlag` | bool \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `emailTemplate` | EmailTemplateReference \| None |  |  |  |
| `employeeCompNotExceed` | `Billing` \| `Amount` \| `Percent` | **y** |  |  |
| `employeeCompRate` | `Actual` \| `Hourly` | **y** |  |  |
| `exclusionWorkRoleIds` | list[int] \| None |  |  |  |
| `exclusionWorkTypeIds` | list[int] \| None |  |  |  |
| `expireWhenZero` | bool \| None |  |  |  |
| `expiredDays` | int \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `integrationXRef` | str \| None |  | 50 |  |
| `invoiceDescription` | str \| None |  | 4000 |  |
| `invoicePreSuffix` | str \| None |  | 5 |  |
| `invoiceTemplate` | InvoiceTemplateReference \| None |  |  |  |
| `invoicingCycle` | `ContractYear` \| `CalendarYear` | **y** |  |  |
| `limit` | int \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `oneTimeFlag` | bool \| None |  |  |  |
| `prePaymentFlag` | bool \| None |  |  |  |
| `prefixSuffixOption` | `Prefix` \| `Suffix` |  |  |  |
| `projectType` | ProjectTypeReference \| None |  |  |  |
| `prorateFlag` | bool \| None |  |  |  |
| `removeAllWorkRoleExclusions` | bool \| None |  |  |  |
| `removeAllWorkTypeExclusions` | bool \| None |  |  |  |
| `restrictDepartmentFlag` | bool \| None |  |  |  |
| `restrictDownPaymentFlag` | bool \| None |  |  |  |
| `restrictLocationFlag` | bool \| None |  |  |  |
| `sla` | SLAReference \| None |  |  |  |
| `taxableFlag` | bool \| None |  |  |  |
| `topCommentFlag` | bool \| None |  |  |  |
| `workRole` | WorkRoleReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |

#### `AgreementWorkRole` — 10 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `agreementId` | int \| None |  |  |  |
| `effectiveDate` | datetime \| None |  |  |  |
| `endingDate` | datetime \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `limitTo` | float \| None |  |  |  |
| `locationId` | int \| None |  |  |  |
| `rate` | float \| None |  |  |  |
| `rateType` | `AdjAmount` \| `Custom` \| `Multiplier` | **y** |  |  |
| `workRole` | WorkRoleReference \| None |  |  |  |

#### `AgreementWorkType` — 18 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `agreementId` | int \| None |  |  |  |
| `agreementLimit` | float \| None |  |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` | **y** |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `effectiveDate` | datetime \| None |  |  |  |
| `endingDate` | datetime \| None |  |  |  |
| `hoursMax` | float \| None |  |  |  |
| `hoursMin` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `locationId` | int \| None |  |  |  |
| `overageRate` | float \| None |  |  |  |
| `overageRateType` | `AdjAmount` \| `Custom` \| `Multiplier` |  |  |  |
| `rate` | float \| None |  |  |  |
| `rateType` | `AdjAmount` \| `Custom` \| `Multiplier` | **y** |  |  |
| `roundBillHours` | float \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |

#### `BillingStatus` — 8 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `closedFlag` | bool \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 30 |  |
| `sentFlag` | bool \| None |  |  |  |
| `sortOrder` | int \| None |  |  |  |

#### `Invoice` — 72 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `accountNumber` | str \| None |  |  |  |
| `addToBatchEmailList` | bool \| None |  |  |  |
| `adjustedBy` | str \| None |  |  |  |
| `adjustmentReason` | str \| None |  |  |  |
| `agreement` | AgreementReference \| None |  |  |  |
| `agreementAmount` | float \| None |  |  |  |
| `applyToId` | int \| None |  |  |  |
| `applyToType` | `All` \| `Agreement` \| `Project` \| `ProjectPhase` \| `SalesOrder` \| `Ticket` |  |  |  |
| `attention` | str \| None |  | 60 |  |
| `balance` | float \| None |  |  |  |
| `billToCompany` | CompanyReference \| None |  |  |  |
| `billingSetupReference` | BillingSetupReference \| None |  |  |  |
| `billingSite` | SiteReference \| None |  |  |  |
| `billingSiteAddressLine1` | str \| None |  |  |  |
| `billingSiteAddressLine2` | str \| None |  |  |  |
| `billingSiteCity` | str \| None |  |  |  |
| `billingSiteCountry` | str \| None |  |  |  |
| `billingSiteState` | str \| None |  |  |  |
| `billingSiteZip` | str \| None |  |  |  |
| `billingTerms` | BillingTermsReference \| None |  |  |  |
| `bottomComment` | str \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `credits` | float \| None |  |  |  |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerPO` | str \| None |  | 50 |  |
| `date` | datetime \| None |  |  |  |
| `departmentId` | int \| None |  |  | departmentId is only required for special invoices |
| `downpaymentApplied` | float \| None |  |  |  |
| `downpaymentPreviouslyTaxedFlag` | bool \| None |  |  |  |
| `dueDate` | datetime \| None |  |  |  |
| `emailTemplateId` | int \| None |  |  | Can be obtained via InvoiceEmailTemplate report |
| `expenseTotal` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalNotes` | str \| None |  |  |  |
| `invoiceNumber` | str \| None |  | 15 | Required On Updates; |
| `invoiceTemplate` | InvoiceTemplateDetailReference \| None |  |  |  |
| `locationId` | int \| None |  |  | Required On Updates; |
| `overrideDownPaymentAmountFlag` | bool \| None |  |  |  |
| `payments` | float \| None |  |  |  |
| `phase` | ProjectPhaseReference \| None |  |  |  |
| `previousProgressApplied` | float \| None |  |  |  |
| `productTotal` | float \| None |  |  |  |
| `project` | ProjectReference \| None |  |  |  |
| `reference` | str \| None |  | 50 |  |
| `remainingDownpayment` | float \| None |  |  |  |
| `restrictDownpaymentFlag` | bool \| None |  |  |  |
| `salesOrder` | SalesOrderReference \| None |  |  |  |
| `salesTax` | float \| None |  |  |  |
| `serviceAdjustmentAmount` | float \| None |  |  |  |
| `serviceTotal` | float \| None |  |  |  |
| `shipToAttention` | str \| None |  | 60 |  |
| `shipToCompany` | CompanyReference \| None |  |  |  |
| `shippingSite` | SiteReference \| None |  |  |  |
| `shippingSiteAddressLine1` | str \| None |  |  |  |
| `shippingSiteAddressLine2` | str \| None |  |  |  |
| `shippingSiteCity` | str \| None |  |  |  |
| `shippingSiteCountry` | str \| None |  |  |  |
| `shippingSiteState` | str \| None |  |  |  |
| `shippingSiteZip` | str \| None |  |  |  |
| `specialInvoiceFlag` | bool \| None |  |  |  |
| `status` | BillingStatusReference \| None |  |  |  |
| `subtotal` | float \| None |  |  |  |
| `taxCode` | TaxCodeReference \| None |  |  |  |
| `taxableFlag` | bool \| None |  |  |  |
| `templateSetupId` | int \| None |  |  | Can be obtained via InvoiceTemplate report |
| `territoryId` | int \| None |  |  |  |
| `ticket` | TicketReference \| None |  |  |  |
| `topComment` | str \| None |  |  |  |
| `total` | float \| None |  |  |  |
| `type` | `Agreement` \| `CreditMemo` \| `DownPayment` \| `Miscellaneous` \| `Progress` \| `Standard` | **y** |  |  |

#### `InvoiceTemplate` — 174 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `adjustmentAgrTypeVisibleFlag` | bool \| None |  |  |  |
| `adjustmentAmountCaption` | str \| None |  | 50 |  |
| `adjustmentAmountVisibleFlag` | bool \| None |  |  |  |
| `adjustmentDescriptionCaption` | str \| None |  | 50 |  |
| `adjustmentDescriptionVisibleFlag` | bool \| None |  |  |  |
| `adjustmentPriceCaption` | str \| None |  | 50 |  |
| `adjustmentPriceVisibleFlag` | bool \| None |  |  |  |
| `adjustmentQuantityCaption` | str \| None |  | 50 |  |
| `adjustmentQuantityVisibleFlag` | bool \| None |  |  |  |
| `adjustmentTotalVisibleFlag` | bool \| None |  |  |  |
| `creditCreditAmountCaption` | str \| None |  | 50 |  |
| `creditCreditAmountVisibleFlag` | bool \| None |  |  |  |
| `creditRemainingAmountCaption` | str \| None |  | 50 |  |
| `creditRemainingAmountVisibleFlag` | bool \| None |  |  |  |
| `currencyIdVisibleFlag` | bool \| None |  |  |  |
| `currencySymbolVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailAgreementExtAmountVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailAgreementVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailBillableVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailContactsVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailExtAmountVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailMembersVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailNonbillableCaption` | str \| None |  | 50 |  |
| `expenseDetailNotesVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailPmPhaseVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailPmSummaryVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailPrimarySortDirection` | str \| None |  |  |  |
| `expenseDetailPrimarySortField` | str \| None |  |  |  |
| `expenseDetailSecondarySortDirection` | str \| None |  |  |  |
| `expenseDetailSecondarySortField` | str \| None |  |  |  |
| `expenseDetailSrAddressVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailSrContactVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailSrTicketSummaryVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailSubtotalVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailTicketNumberVisibleFlag` | bool \| None |  |  |  |
| `expenseDetailVisibleFlag` | bool \| None |  |  |  |
| `expensesAmountCaption` | str \| None |  | 50 |  |
| `expensesAmountVisibleFlag` | bool \| None |  |  |  |
| `expensesCollapsedFlag` | bool \| None |  |  |  |
| `expensesStaffCaption` | str \| None |  | 50 |  |
| `expensesStaffVisibleFlag` | bool \| None |  |  |  |
| `expensesTotalVisibleFlag` | bool \| None |  |  |  |
| `expensesTypeCaption` | str \| None |  | 50 |  |
| `expensesTypeVisibleFlag` | bool \| None |  |  |  |
| `headerAccountCaption` | str \| None |  | 50 |  |
| `headerAccountVisibleFlag` | bool \| None |  |  |  |
| `headerAddressPosition` | `Center` \| `LeftSide` \| `RightSide` |  |  |  |
| `headerDueDateCaption` | str \| None |  | 50 |  |
| `headerDueDateVisibleFlag` | bool \| None |  |  |  |
| `headerHoursBasedExtendedAmountVisibleFlag` | bool \| None |  |  |  |
| `headerLogoPosition` | `Center` \| `LeftSide` \| `RightSide` |  |  |  |
| `headerPoNumberCaption` | str \| None |  | 50 |  |
| `headerPoNumberVisibleFlag` | bool \| None |  |  |  |
| `headerReferenceCaption` | str \| None |  | 50 |  |
| `headerReferenceVisibleFlag` | bool \| None |  |  |  |
| `headerShipToCaption` | str \| None |  | 50 |  |
| `headerShipToVisibleFlag` | bool \| None |  |  |  |
| `headerTaxIdCaption` | str \| None |  | 50 |  |
| `headerTaxIdVisibleFlag` | bool \| None |  |  |  |
| `headerTermsCaption` | str \| None |  | 50 |  |
| `headerTermsVisibleFlag` | bool \| None |  |  |  |
| `headerTitleCaption` | str \| None |  | 50 |  |
| `headerTitleFont` | `Regular` \| `RegularBold` \| `Large` \| `LargeBold` \| `ExtraLarge` \| `ExtraLargeBold` |  |  |  |
| `headerTitlePosition` | `Center` \| `LeftSide` \| `RightSide` |  |  |  |
| `headerTitleVisibleFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `invoiceBalanceDueCaption` | str \| None |  | 50 |  |
| `invoiceBalanceDueVisibleFlag` | bool \| None |  |  |  |
| `invoiceCreditAmountCaption` | str \| None |  | 50 |  |
| `invoiceCreditAmountVisibleFlag` | bool \| None |  |  |  |
| `invoicePaymentAmountCaption` | str \| None |  | 50 |  |
| `invoicePaymentAmountVisibleFlag` | bool \| None |  |  |  |
| `logoVisibleFlag` | bool \| None |  |  |  |
| `marginBottom` | float \| None |  |  |  |
| `marginLeft` | float \| None |  |  |  |
| `marginRight` | float \| None |  |  |  |
| `marginTop` | float \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `otherChargesAmountCaption` | str \| None |  | 50 |  |
| `otherChargesAmountVisibleFlag` | bool \| None |  |  |  |
| `otherChargesCollapsedFlag` | bool \| None |  |  |  |
| `otherChargesDescriptionCaption` | str \| None |  | 50 |  |
| `otherChargesDescriptionVisibleFlag` | bool \| None |  |  |  |
| `otherChargesDisplaySixDecimals` | bool \| None |  |  |  |
| `otherChargesItemIdVisibleFlag` | bool \| None |  |  |  |
| `otherChargesPriceCaption` | str \| None |  | 50 |  |
| `otherChargesPriceVisibleFlag` | bool \| None |  |  |  |
| `otherChargesQuantityCaption` | str \| None |  | 50 |  |
| `otherChargesQuantityVisibleFlag` | bool \| None |  |  |  |
| `otherChargesSerialNumberVisibleFlag` | bool \| None |  |  |  |
| `otherChargesTotalVisibleFlag` | bool \| None |  |  |  |
| `payableCaption` | str \| None |  | 1000 |  |
| `portalFlag` | bool \| None |  |  |  |
| `projectHeaderAmountCaption` | str \| None |  | 50 |  |
| `projectHeaderAmountVisibleFlag` | bool \| None |  |  |  |
| `projectHeaderBillingMethodCaption` | str \| None |  | 50 |  |
| `projectHeaderBillingMethodVisibleFlag` | bool \| None |  |  |  |
| `projectHeaderBillingTypeCaption` | str \| None |  | 50 |  |
| `projectHeaderBillingTypeVisibleFlag` | bool \| None |  |  |  |
| `projectHeaderCompanyNameCaption` | str \| None |  | 50 |  |
| `projectHeaderCompanyNameVisibleFlag` | bool \| None |  |  |  |
| `projectHeaderContactNameCaption` | str \| None |  | 50 |  |
| `projectHeaderContactNameVisibleFlag` | bool \| None |  |  |  |
| `projectHeaderOriginalDownpaymentCaption` | str \| None |  | 50 |  |
| `projectHeaderOriginalDownpaymentVisibleFlag` | bool \| None |  |  |  |
| `projectHeaderProjectNameCaption` | str \| None |  | 50 |  |
| `projectHeaderProjectNameVisibleFlag` | bool \| None |  |  |  |
| `remitToVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderAmountCaption` | str \| None |  | 50 |  |
| `serviceHeaderAmountVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderBillingMethodCaption` | str \| None |  | 50 |  |
| `serviceHeaderBillingMethodVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderBundledTicketsVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderClosedTasksVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderCompanyNameCaption` | str \| None |  | 50 |  |
| `serviceHeaderCompanyNameVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderContactNameCaption` | str \| None |  | 50 |  |
| `serviceHeaderContactNameVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderDetailDescriptionCaption` | str \| None |  | 50 |  |
| `serviceHeaderDetailDescriptionVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderOpenTasksVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderResolutionCaption` | str \| None |  | 50 |  |
| `serviceHeaderResolutionVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderSummaryCaption` | str \| None |  | 50 |  |
| `serviceHeaderSummaryVisibleFlag` | bool \| None |  |  |  |
| `serviceHeaderTicketNumberCaption` | str \| None |  | 50 |  |
| `serviceHeaderTicketNumberVisibleFlag` | bool \| None |  |  |  |
| `servicesAmountCaption` | str \| None |  | 50 |  |
| `servicesAmountVisibleFlag` | bool \| None |  |  |  |
| `servicesCollapsedFlag` | bool \| None |  |  |  |
| `servicesHoursCaption` | str \| None |  | 50 |  |
| `servicesHoursVisibleFlag` | bool \| None |  |  |  |
| `servicesMemberNameCaption` | str \| None |  | 50 |  |
| `servicesMemberNameVisibleFlag` | bool \| None |  |  |  |
| `servicesRateCaption` | str \| None |  | 50 |  |
| `servicesRateVisibleFlag` | bool \| None |  |  |  |
| `servicesStaffCaption` | str \| None |  | 50 |  |
| `servicesStaffVisibleFlag` | bool \| None |  |  |  |
| `servicesTotalVisibleFlag` | bool \| None |  |  |  |
| `servicesWorkRoleCaption` | str \| None |  | 50 |  |
| `servicesWorkRoleVisibleFlag` | bool \| None |  |  |  |
| `servicesWorkTypeCaption` | str \| None |  | 50 |  |
| `servicesWorkTypeVisibleFlag` | bool \| None |  |  |  |
| `timeDetailAgreementVisibleFlag` | bool \| None |  |  |  |
| `timeDetailAmountBasedExtAmountVisibleFlag` | bool \| None |  |  |  |
| `timeDetailAmountBasedHourlyRateVisibleFlag` | bool \| None |  |  |  |
| `timeDetailAmountBasedHoursVisibleFlag` | bool \| None |  |  |  |
| `timeDetailBillableVisibleFlag` | bool \| None |  |  |  |
| `timeDetailContactsVisibleFlag` | bool \| None |  |  |  |
| `timeDetailDatesVisibleFlag` | bool \| None |  |  |  |
| `timeDetailDollarAmountsOnHourseBasedVisibleFlag` | bool \| None |  |  |  |
| `timeDetailExtendedAmountVisibleFlag` | bool \| None |  |  |  |
| `timeDetailHourlyRateVisibleFlag` | bool \| None |  |  |  |
| `timeDetailHoursBasedExtAmountVisibleFlag` | bool \| None |  |  |  |
| `timeDetailHoursBasedHoursVisibleFlag` | bool \| None |  |  |  |
| `timeDetailHoursVisibleFlag` | bool \| None |  |  |  |
| `timeDetailHoursbasedHourlyRateVisibleFlag` | bool \| None |  |  |  |
| `timeDetailMembersVisibleFlag` | bool \| None |  |  |  |
| `timeDetailNonBillableCaption` | str \| None |  | 50 |  |
| `timeDetailNotesVisibleFlag` | bool \| None |  |  |  |
| `timeDetailPmPhaseVisibleFlag` | bool \| None |  |  |  |
| `timeDetailPmSummaryVisibleFlag` | bool \| None |  |  |  |
| `timeDetailPrimarySortDirection` | str \| None |  |  |  |
| `timeDetailPrimarySortField` | str \| None |  |  |  |
| `timeDetailSRAddressVisibleFlag` | bool \| None |  |  |  |
| `timeDetailSRContactVisibleFlag` | bool \| None |  |  |  |
| `timeDetailSRTicketSummaryVisibleFlag` | bool \| None |  |  |  |
| `timeDetailSecondarySortDirection` | str \| None |  |  |  |
| `timeDetailSecondarySortField` | str \| None |  |  |  |
| `timeDetailStartEndTimeVisibleFlag` | bool \| None |  |  |  |
| `timeDetailSubtotalVisibleFlag` | bool \| None |  |  |  |
| `timeDetailTicketNumberVisibleFlag` | bool \| None |  |  |  |
| `timeDetailVisibleFlag` | bool \| None |  |  |  |

### Procurement

#### `CatalogItem` — 42 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `billableOption` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `calculatedCost` | float \| None |  |  |  |
| `calculatedCostFlag` | bool \| None |  |  |  |
| `calculatedPrice` | float \| None |  |  |  |
| `calculatedPriceFlag` | bool \| None |  |  |  |
| `category` | ProductCategoryReference \| None |  |  |  |
| `cost` | float \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerDescription` | str | **y** | 6000 |  |
| `dateEntered` | datetime \| None |  |  |  |
| `description` | str | **y** | 60 |  |
| `dropShipFlag` | bool \| None |  |  |  |
| `entityType` | EntityTypeReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `identifier` | str | **y** | 60 |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `integrationXRef` | str \| None |  | 50 |  |
| `manufacturer` | ManufacturerReference \| None |  |  |  |
| `manufacturerPartNumber` | str \| None |  | 50 |  |
| `minStockLevel` | int \| None |  |  |  |
| `notes` | str \| None |  |  |  |
| `phaseProductFlag` | bool \| None |  |  |  |
| `price` | float \| None |  |  |  |
| `priceAttribute` | `FixedFee` \| `NotToExceed` \| `OverrideRate` \| `TimeAndMaterials` |  |  |  |
| `productClass` | `Agreement` \| `Bundle` \| `Inventory` \| `NonInventory` \| `Service` |  |  | Defaults to Non-Inventory |
| `recurringBillCycle` | BillingCycleReference \| None |  |  |  |
| `recurringCost` | float \| None |  |  |  |
| `recurringCycleType` | `ContractYear` \| `CalendarYear` |  |  |  |
| `recurringFlag` | bool \| None |  |  |  |
| `recurringOneTimeFlag` | bool \| None |  |  |  |
| `recurringRevenue` | float \| None |  |  |  |
| `serializedCostFlag` | bool \| None |  |  |  |
| `serializedFlag` | bool \| None |  |  |  |
| `sla` | SLAReference \| None |  |  |  |
| `specialOrderFlag` | bool \| None |  |  |  |
| `subcategory` | ProductSubCategoryReference \| None |  |  |  |
| `taxableFlag` | bool \| None |  |  |  |
| `type` | ProductTypeReference \| None |  |  |  |
| `unitOfMeasure` | UnitOfMeasureReference \| None |  |  |  |
| `vendor` | CompanyReference \| None |  |  |  |
| `vendorSku` | str \| None |  | 50 |  |

#### `ProductItem` — 67 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `addComponentsFlag` | bool \| None |  |  |  |
| `agreement` | AgreementReference \| None |  |  |  |
| `agreementAmount` | float \| None |  |  |  |
| `billableOption` | `Billable` \| `DoNotBill` \| `NoCharge` | **y** |  |  |
| `businessUnitId` | int \| None |  |  | Required On Updates; |
| `bypassForecastUpdate` | bool \| None |  |  |  |
| `calculatedCost` | float \| None |  |  |  |
| `calculatedCostFlag` | bool \| None |  |  |  |
| `calculatedPrice` | float \| None |  |  |  |
| `calculatedPriceFlag` | bool \| None |  |  |  |
| `cancelledBy` | int \| None |  |  |  |
| `cancelledDate` | datetime \| None |  |  |  |
| `cancelledFlag` | bool \| None |  |  |  |
| `cancelledReason` | str \| None |  | 100 |  |
| `catalogItem` | CatalogItemReference \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `cost` | float \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerDescription` | str \| None |  | 6000 | Required On Updates; |
| `description` | str \| None |  | 2000 |  |
| `discount` | float \| None |  |  |  |
| `dropshipFlag` | bool \| None |  |  |  |
| `entityType` | EntityTypeReference \| None |  |  |  |
| `forecastDetailId` | int \| None |  |  |  |
| `forecastStatus` | OpportunityStatusReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `ignorePricingSchedulesFlag` | bool \| None |  |  |  |
| `integrationXRef` | str \| None |  |  |  |
| `internalNotes` | str \| None |  | 1000 |  |
| `invoice` | InvoiceReference \| None |  |  |  |
| `invoiceGrouping` | InvoiceGroupingReference \| None |  |  |  |
| `listPrice` | float \| None |  |  |  |
| `locationId` | int \| None |  |  | Required On Updates; |
| `minimumStockFlag` | bool \| None |  |  |  |
| `needToOrderQuantity` | int \| None |  |  |  |
| `needToPurchaseFlag` | bool \| None |  |  |  |
| `opportunity` | OpportunityReference \| None |  |  |  |
| `phase` | ProjectPhaseReference \| None |  |  |  |
| `phaseProductFlag` | bool \| None |  |  |  |
| `poApprovedFlag` | bool \| None |  |  |  |
| `price` | float \| None |  |  |  |
| `priceMethod` | `FlatRateForRange` \| `PercentMarkupFromCost` \| `PercentMarkdownFromPrice` \| `PricePerUnit` |  |  |  |
| `productClass` | `Agreement` \| `Bundle` \| `Inventory` \| `NonInventory` \| `Service` |  |  |  |
| `productSuppliedFlag` | bool \| None |  |  |  |
| `project` | ProjectReference \| None |  |  |  |
| `purchaseDate` | datetime \| None |  |  |  |
| `quantity` | float \| None |  |  |  |
| `quantityCancelled` | float \| None |  |  |  |
| `recurring` | ProductRecurring \| None |  |  |  |
| `salesOrder` | SalesOrderReference \| None |  |  |  |
| `sequenceNumber` | float \| None |  |  |  |
| `serialNumberIds` | list[int] \| None |  |  |  |
| `serialNumbers` | list[str] \| None |  |  |  |
| `shipSet` | str \| None |  | 10 |  |
| `sla` | SLAReference \| None |  |  |  |
| `specialOrderFlag` | bool \| None |  |  |  |
| `subContractorAmountLimit` | float \| None |  |  |  |
| `subContractorShipToId` | int \| None |  |  |  |
| `taxableFlag` | bool \| None |  |  |  |
| `ticket` | TicketReference \| None |  |  |  |
| `vendor` | CompanyReference \| None |  |  |  |
| `vendorSku` | str \| None |  | 50 |  |
| `warehouse` | str \| None |  |  |  |
| `warehouseBin` | str \| None |  |  |  |
| `warehouseBinId` | int \| None |  |  |  |
| `warehouseId` | int \| None |  |  |  |

#### `PurchaseOrder` — 51 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `businessUnitId` | int \| None |  |  |  |
| `cancelReason` | str \| None |  |  |  |
| `closedFlag` | bool \| None |  |  | The closed flag can only be updated via updating the purchase order status to a closed/… |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerCity` | str \| None |  |  |  |
| `customerCompany` | CompanyReference \| None |  |  |  |
| `customerContact` | ContactReference \| None |  |  |  |
| `customerCountry` | CountryReference \| None |  |  |  |
| `customerExtension` | str \| None |  |  |  |
| `customerName` | str \| None |  |  |  |
| `customerPhone` | str \| None |  |  |  |
| `customerSite` | SiteReference \| None |  |  |  |
| `customerSiteName` | str \| None |  |  |  |
| `customerState` | str \| None |  |  |  |
| `customerStreetLine1` | str \| None |  |  |  |
| `customerStreetLine2` | str \| None |  |  |  |
| `customerZip` | str \| None |  |  |  |
| `dateClosed` | datetime \| None |  |  |  |
| `dropShipCustomerFlag` | bool \| None |  |  |  |
| `enteredBy` | str \| None |  |  |  |
| `freightCost` | float \| None |  |  |  |
| `freightPackingSlip` | str \| None |  |  |  |
| `freightTaxTotal` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalNotes` | str \| None |  |  |  |
| `locationId` | int \| None |  |  |  |
| `poDate` | datetime \| None |  |  | Required On Updates; |
| `poNumber` | str \| None |  | 50 | Required On Updates; |
| `salesTax` | float \| None |  |  |  |
| `shipmentDate` | datetime \| None |  |  |  |
| `shipmentMethod` | ShipmentMethodReference \| None |  |  |  |
| `shippingInstructions` | str \| None |  |  |  |
| `status` | PurchaseOrderStatusReference \| None |  |  |  |
| `subTotal` | float \| None |  |  |  |
| `taxCode` | TaxCodeReference \| None |  |  |  |
| `taxFreightFlag` | bool \| None |  |  |  |
| `taxPoFlag` | bool \| None |  |  |  |
| `terms` | BillingTermsReference \| None |  |  |  |
| `total` | float \| None |  |  |  |
| `trackingNumber` | str \| None |  | 50 |  |
| `updateShipmentInfo` | bool \| None |  |  | Determines whether or not to update all of the shipment info for each associated line i… |
| `updateVendorOrderNumber` | bool \| None |  |  | Determines whether or not to update vendor order number for each associated line item w… |
| `vendorCompany` | CompanyReference \| None |  |  |  |
| `vendorContact` | ContactReference \| None |  |  |  |
| `vendorInvoiceDate` | datetime \| None |  |  |  |
| `vendorInvoiceNumber` | str \| None |  | 50 |  |
| `vendorOrderNumber` | str \| None |  | 50 |  |
| `vendorSite` | SiteReference \| None |  |  |  |
| `warehouse` | WarehouseReference \| None |  |  |  |

#### `PurchaseOrderLineItem` — 34 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `backorderedFlag` | bool \| None |  |  |  |
| `canceledBy` | str \| None |  |  |  |
| `canceledFlag` | bool \| None |  |  |  |
| `canceledReason` | str \| None |  | 100 |  |
| `closedFlag` | bool \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `dateCanceled` | datetime \| None |  |  |  |
| `dateCanceledUtc` | datetime \| None |  |  |  |
| `dateReceived` | datetime \| None |  |  |  |
| `description` | str | **y** | 6000 |  |
| `displayInternalNotesFlag` | bool \| None |  |  |  |
| `expectedShipDate` | datetime \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalNotes` | str \| None |  | 1000 |  |
| `lineNumber` | int | **y** |  |  |
| `packingSlip` | str \| None |  | 50 |  |
| `product` | IvItemReference \| None |  |  |  |
| `purchaseOrderId` | int \| None |  |  |  |
| `quantity` | float | **y** |  |  |
| `receivedQuantity` | int \| None |  |  |  |
| `receivedStatus` | `Waiting` \| `FullyReceived` \| `PartiallyReceiveCancelRest` \| `PartiallyReceiveCloneRest` |  |  |  |
| `serialNumbers` | str \| None |  |  |  |
| `shipDate` | datetime \| None |  |  |  |
| `shipSet` | str \| None |  | 10 |  |
| `shipmentMethod` | ShipmentMethodReference \| None |  |  |  |
| `tax` | float \| None |  |  |  |
| `trackingNumber` | str \| None |  | 50 |  |
| `unitCost` | float \| None |  |  |  |
| `unitOfMeasure` | UnitOfMeasureReference \| None |  |  |  |
| `vendorOrderNumber` | str \| None |  | 50 |  |
| `vendorSku` | str \| None |  | 50 |  |
| `warehouse` | WarehouseReference \| None |  |  |  |
| `warehouseBin` | WarehouseBinReference \| None |  |  |  |

### Configurations — the CMDB

#### `ConfigurationQuestion` — 8 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `answer` | str \| bool \| int \| None |  |  |  |
| `answerId` | int \| None |  |  |  |
| `fieldType` | `TextArea` \| `Currency` \| `Date` \| `Hyperlink` \| `IPAddress` \| `Checkbox` \| `Number` \| `Percent` \| `Text` \| `Password` |  |  |  |
| `numberOfDecimals` | int \| None |  |  |  |
| `question` | str \| None |  |  |  |
| `questionId` | int \| None |  |  |  |
| `requiredFlag` | bool \| None |  |  |  |
| `sequenceNumber` | float \| None |  |  |  |

#### `ConfigurationStatus` — 5 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `closedFlag` | bool \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `description` | str | **y** | 50 |  |
| `id` | int \| None |  |  |  |

#### `ConfigurationType` — 5 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `systemFlag` | bool \| None |  |  |  |

#### `ConfigurationTypeQuestion` — 10 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `configurationType` | ConfigurationTypeReference \| None |  |  |  |
| `entryType` | `Date` \| `EntryField` \| `List` \| `Option` | **y** |  |  |
| `fieldType` | `TextArea` \| `Currency` \| `Date` \| `Hyperlink` \| `IPAddress` \| `Checkbox` \| `Number` \| `Percent` \| `Text` \| `Password` | **y** |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `numberOfDecimals` | int \| None |  |  |  |
| `question` | str | **y** | 1000 |  |
| `requiredFlag` | bool \| None |  |  |  |
| `sequenceNumber` | float | **y** |  |  |

### Companies, contacts and sites

#### `Company` — 69 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `accountNumber` | str \| None |  |  |  |
| `addressLine1` | str \| None |  | 50 | At least one address field is required -- addressLine1, addressLine2, city, state, zip … |
| `addressLine2` | str \| None |  | 50 | At least one address field is required -- addressLine1, addressLine2, city, state, zip … |
| `annualRevenue` | float \| None |  |  |  |
| `billToCompany` | CompanyReference \| None |  |  |  |
| `billingContact` | ContactReference \| None |  |  |  |
| `billingSite` | SiteReference \| None |  |  |  |
| `billingTerms` | BillingTermsReference \| None |  |  |  |
| `calendar` | CalendarReference \| None |  |  |  |
| `city` | str \| None |  | 50 | At least one address field is required -- addressLine1, addressLine2, city, state, zip … |
| `companyEntityType` | EntityTypeReference \| None |  |  |  |
| `country` | CountryReference \| None |  |  |  |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `dateAcquired` | datetime \| None |  |  |  |
| `dateDeleted` | datetime \| None |  |  |  |
| `defaultContact` | ContactReference \| None |  |  |  |
| `deletedBy` | str \| None |  |  |  |
| `deletedFlag` | bool \| None |  |  |  |
| `facebookUrl` | str \| None |  |  |  |
| `faxNumber` | str \| None |  | 30 |  |
| `id` | int \| None |  |  |  |
| `identifier` | str | **y** | 30 |  |
| `integratorTags` | list[str] \| None |  |  |  |
| `invoiceCCEmailAddress` | str \| None |  |  |  |
| `invoiceDeliveryMethod` | BillingDeliveryReference \| None |  |  |  |
| `invoiceTemplate` | InvoiceTemplateReference \| None |  |  |  |
| `invoiceToEmailAddress` | str \| None |  |  |  |
| `isVendorFlag` | bool \| None |  |  |  |
| `leadFlag` | bool \| None |  |  |  |
| `leadSource` | str \| None |  | 50 |  |
| `linkedInUrl` | str \| None |  |  |  |
| `market` | MarketDescriptionReference \| None |  |  |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `numberOfEmployees` | int \| None |  |  |  |
| `ownershipType` | OwnershipTypeReference \| None |  |  |  |
| `parentCompany` | CompanyReference \| None |  |  |  |
| `phoneNumber` | str \| None |  | 30 |  |
| `pricingSchedule` | PricingScheduleReference \| None |  |  |  |
| `resellerIdentifier` | str \| None |  |  |  |
| `revenueYear` | int \| None |  |  |  |
| `sicCode` | SicCodeReference \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `state` | str \| None |  | 50 | At least one address field is required -- addressLine1, addressLine2, city, state, zip … |
| `status` | CompanyStatusReference \| None |  |  |  |
| `taxCode` | TaxCodeReference \| None |  |  |  |
| `taxIdentifier` | str \| None |  |  |  |
| `territory` | SystemLocationReference \| None |  |  |  |
| `territoryManager` | MemberReference \| None |  |  |  |
| `timeZoneSetup` | TimeZoneSetupReference \| None |  |  |  |
| `twitterUrl` | str \| None |  |  |  |
| `types` | list[CompanyTypeReference] \| None |  |  | Integrer array of Company_Type_Recids to be assigned to company that can be passed in o… |
| `unsubscribeFlag` | bool \| None |  |  |  |
| `userDefinedField1` | str \| None |  | 50 |  |
| `userDefinedField10` | str \| None |  | 50 |  |
| `userDefinedField2` | str \| None |  | 50 |  |
| `userDefinedField3` | str \| None |  | 50 |  |
| `userDefinedField4` | str \| None |  | 50 |  |
| `userDefinedField5` | str \| None |  | 50 |  |
| `userDefinedField6` | str \| None |  | 50 |  |
| `userDefinedField7` | str \| None |  | 50 |  |
| `userDefinedField8` | str \| None |  | 50 |  |
| `userDefinedField9` | str \| None |  | 50 |  |
| `vendorIdentifier` | str \| None |  |  |  |
| `website` | str \| None |  | 255 |  |
| `yearEstablished` | int \| None |  |  |  |
| `zip` | str \| None |  | 12 | At least one address field is required -- addressLine1, addressLine2, city, state, zip … |

#### `CompanyConfiguration` — 56 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `activeFlag` | bool \| None |  |  |  |
| `backupBillableSpaceGb` | float \| None |  |  |  |
| `backupFailed` | int \| None |  |  |  |
| `backupIncomplete` | int \| None |  |  |  |
| `backupMonth` | int \| None |  |  |  |
| `backupProtectedDeviceList` | str \| None |  |  |  |
| `backupRestores` | int \| None |  |  |  |
| `backupServerName` | str \| None |  | 50 |  |
| `backupSuccesses` | int \| None |  |  |  |
| `backupYear` | int \| None |  |  |  |
| `billFlag` | bool \| None |  |  |  |
| `businessUnitId` | int \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `companyLocationId` | int \| None |  |  |  |
| `contact` | ContactReference \| None |  |  |  |
| `cpuSpeed` | str \| None |  | 100 |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `defaultGateway` | str \| None |  | 50 |  |
| `deviceIdentifier` | str \| None |  | 100 |  |
| `displayVendorFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `installationDate` | datetime \| None |  |  |  |
| `installedBy` | MemberReference \| None |  |  |  |
| `ipAddress` | str \| None |  | 50 |  |
| `lastBackupDate` | datetime \| None |  |  |  |
| `lastLoginName` | str \| None |  | 100 |  |
| `localHardDrives` | str \| None |  |  |  |
| `locationId` | int \| None |  |  |  |
| `macAddress` | str \| None |  | 25 |  |
| `managementLink` | str \| None |  | 1000 |  |
| `manufacturer` | ManufacturerReference \| None |  |  |  |
| `manufacturerPartNumber` | str \| None |  | 50 |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `modelNumber` | str \| None |  | 50 |  |
| `name` | str | **y** | 100 |  |
| `needsRenewalFlag` | bool \| None |  |  |  |
| `notes` | str \| None |  |  |  |
| `osInfo` | str \| None |  | 250 |  |
| `osType` | str \| None |  | 250 |  |
| `parentConfigurationId` | int \| None |  |  |  |
| `purchaseDate` | datetime \| None |  |  |  |
| `questions` | list[ConfigurationQuestion] \| None |  |  |  |
| `ram` | str \| None |  | 25 |  |
| `remoteLink` | str \| None |  | 1000 |  |
| `serialNumber` | str \| None |  | 250 |  |
| `showAutomateFlag` | bool \| None |  |  |  |
| `showRemoteFlag` | bool \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `sla` | SLAReference \| None |  |  |  |
| `status` | ConfigurationStatusReference \| None |  |  |  |
| `tagNumber` | str \| None |  | 50 |  |
| `type` | ConfigurationTypeReference \| None |  |  |  |
| `vendor` | CompanyReference \| None |  |  |  |
| `vendorNotes` | str \| None |  |  |  |
| `warrantyExpirationDate` | datetime \| None |  |  |  |

#### `CompanySite` — 26 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `addressFormat` | str \| None |  |  |  |
| `addressLine1` | str \| None |  | 50 |  |
| `addressLine2` | str \| None |  | 50 |  |
| `billSeparateFlag` | bool \| None |  |  |  |
| `calendar` | CalendarReference \| None |  |  |  |
| `city` | str \| None |  | 50 |  |
| `company` | CompanyReference \| None |  |  |  |
| `coreEntitySiteIdentifier` | str \| None |  | 36 |  |
| `country` | CountryReference \| None |  |  |  |
| `defaultBillingFlag` | bool \| None |  |  |  |
| `defaultMailingFlag` | bool \| None |  |  |  |
| `defaultShippingFlag` | bool \| None |  |  |  |
| `entityType` | EntityTypeReference \| None |  |  |  |
| `expenseReimbursement` | float \| None |  |  |  |
| `faxNumber` | str \| None |  | 30 |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `name` | str | **y** | 50 |  |
| `phoneNumber` | str \| None |  | 30 |  |
| `primaryAddressFlag` | bool \| None |  |  |  |
| `stateReference` | StateReference \| None |  |  |  |
| `taxCode` | TaxCodeReference \| None |  |  |  |
| `timeZone` | TimeZoneSetupReference \| None |  |  |  |
| `zip` | str \| None |  | 12 |  |

#### `CompanyTeam` — 11 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `accountManagerFlag` | bool \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `contact` | ContactReference \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `salesFlag` | bool \| None |  |  |  |
| `teamRole` | TeamRoleReference \| None |  |  |  |
| `techFlag` | bool \| None |  |  |  |

#### `Contact` — 62 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `addressLine1` | str \| None |  |  |  |
| `addressLine2` | str \| None |  |  |  |
| `anniversary` | datetime \| None |  |  |  |
| `assistantContact` | ContactReference \| None |  |  |  |
| `birthDay` | str \| None |  |  |  |
| `children` | str \| None |  |  |  |
| `childrenFlag` | bool \| None |  |  |  |
| `city` | str \| None |  |  |  |
| `communicationItems` | list[ContactCommunicationItem] \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `companyLocation` | SystemLocationReference \| None |  |  |  |
| `country` | CountryReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `defaultBillingFlag` | bool \| None |  |  |  |
| `defaultFlag` | bool \| None |  |  |  |
| `defaultMergeContactId` | int \| None |  |  |  |
| `defaultPhoneExtension` | str \| None |  |  |  |
| `defaultPhoneNbr` | str \| None |  |  |  |
| `defaultPhoneType` | str \| None |  |  |  |
| `department` | ContactDepartmentReference \| None |  |  |  |
| `disablePortalLoginFlag` | bool \| None |  |  |  |
| `facebookUrl` | str \| None |  |  |  |
| `firstName` | str \| None |  |  |  |
| `gender` | `Female` \| `Male` |  |  |  |
| `id` | int \| None |  |  |  |
| `ignoreDuplicates` | bool \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `integratorTags` | list[str] \| None |  |  |  |
| `lastName` | str \| None |  |  |  |
| `linkedInUrl` | str \| None |  |  |  |
| `managerContact` | ContactReference \| None |  |  |  |
| `marriedFlag` | bool \| None |  |  |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `nickName` | str \| None |  |  |  |
| `photo` | DocumentReference \| None |  |  |  |
| `portalPassword` | str \| None |  |  |  |
| `portalSecurityLevel` | int \| None |  |  |  |
| `presence` | `NoAgent` \| `Online` \| `DoNotDisturb` \| `Away` \| `Offline` |  |  |  |
| `relationship` | RelationshipReference \| None |  |  |  |
| `relationshipOverride` | str \| None |  |  |  |
| `school` | str \| None |  |  |  |
| `securityIdentifier` | str \| None |  |  |  |
| `significantOther` | str \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `state` | str \| None |  |  |  |
| `title` | str \| None |  |  |  |
| `twitterUrl` | str \| None |  |  |  |
| `typeIds` | list[int] \| None |  |  | Integrer array of Contact_Type_Recids to be assigned to contact that can be passed in o… |
| `types` | list[ContactTypeReference] \| None |  |  |  |
| `unsubscribeFlag` | bool \| None |  |  |  |
| `userDefinedField1` | str \| None |  | 50 |  |
| `userDefinedField10` | str \| None |  | 50 |  |
| `userDefinedField2` | str \| None |  | 50 |  |
| `userDefinedField3` | str \| None |  | 50 |  |
| `userDefinedField4` | str \| None |  | 50 |  |
| `userDefinedField5` | str \| None |  | 50 |  |
| `userDefinedField6` | str \| None |  | 50 |  |
| `userDefinedField7` | str \| None |  | 50 |  |
| `userDefinedField8` | str \| None |  | 50 |  |
| `userDefinedField9` | str \| None |  | 50 |  |
| `zip` | str \| None |  |  |  |

#### `ContactDepartment` — 3 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `id` | int \| None |  |  |  |
| `name` | str | **y** | 30 |  |

### Projects

#### `Project` — 65 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `actualEnd` | datetime \| None |  |  |  |
| `actualHours` | float \| None |  |  |  |
| `actualStart` | datetime \| None |  |  |  |
| `agreement` | AgreementReference \| None |  |  |  |
| `billExpenses` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billProducts` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billProjectAfterClosedFlag` | bool \| None |  |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billToCompany` | CompanyReference \| None |  |  |  |
| `billToContact` | ContactReference \| None |  |  |  |
| `billToSite` | SiteReference \| None |  |  |  |
| `billUnapprovedTimeAndExpense` | bool \| None |  |  |  |
| `billingAmount` | float \| None |  |  |  |
| `billingAttention` | str \| None |  | 50 |  |
| `billingMethod` | `ActualRates` \| `FixedFee` \| `NotToExceed` \| `OverrideRate` | **y** |  |  |
| `billingRateType` | `StaffMember` \| `WorkRole` |  |  | Required On Updates; |
| `billingStartDate` | datetime \| None |  |  |  |
| `billingTerms` | BillingTermsReference \| None |  |  |  |
| `board` | ProjectBoardReference \| None |  |  |  |
| `budgetAnalysis` | `ActualHours` \| `BillableHours` |  |  | Required On Updates; |
| `budgetFlag` | bool \| None |  |  |  |
| `budgetHours` | float \| None |  |  |  |
| `closedFlag` | bool \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `companyLocation` | SystemLocationReference \| None |  |  |  |
| `contact` | ContactReference \| None |  |  |  |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerPO` | str \| None |  | 50 |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `description` | str \| None |  |  |  |
| `doNotDisplayInPortalFlag` | bool \| None |  |  |  |
| `downpayment` | float \| None |  |  |  |
| `estimatedEnd` | datetime | **y** |  |  |
| `estimatedExpenseCost` | float \| None |  |  |  |
| `estimatedExpenseRevenue` | float \| None |  |  |  |
| `estimatedHours` | float \| None |  |  |  |
| `estimatedProductCost` | float \| None |  |  |  |
| `estimatedProductRevenue` | float \| None |  |  |  |
| `estimatedStart` | datetime | **y** |  |  |
| `estimatedTimeCost` | float \| None |  |  |  |
| `estimatedTimeRevenue` | float \| None |  |  |  |
| `expenseApprover` | MemberReference \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `includeDependenciesFlag` | bool \| None |  |  |  |
| `includeEstimatesFlag` | bool \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `manager` | MemberReference \| None |  |  |  |
| `name` | str | **y** | 100 |  |
| `opportunity` | OpportunityReference \| None |  |  |  |
| `percentComplete` | float \| None |  |  |  |
| `projectTemplateId` | int \| None |  |  |  |
| `restrictDownPaymentFlag` | bool \| None |  |  |  |
| `scheduledEnd` | datetime \| None |  |  |  |
| `scheduledHours` | float \| None |  |  |  |
| `scheduledStart` | datetime \| None |  |  |  |
| `shipToCompany` | CompanyReference \| None |  |  |  |
| `shipToContact` | ContactReference \| None |  |  |  |
| `shipToSite` | SiteReference \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `status` | ProjectStatusReference \| None |  |  |  |
| `taxCode` | TaxCodeReference \| None |  |  |  |
| `timeApprover` | MemberReference \| None |  |  |  |
| `type` | ProjectTypeReference \| None |  |  |  |

#### `ProjectPhase` — 48 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `actualEnd` | datetime \| None |  |  |  |
| `actualHours` | float \| None |  |  |  |
| `actualStart` | datetime \| None |  |  |  |
| `agreement` | AgreementReference \| None |  |  |  |
| `billExpenses` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billPhaseClosedFlag` | bool \| None |  |  | This phase can only be billed after it has been closed |
| `billProducts` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billProjectClosedFlag` | bool \| None |  |  | This phase can only be billed after the project has been closed |
| `billSeparatelyFlag` | bool \| None |  |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `billToCompany` | CompanyReference \| None |  |  |  |
| `billToContact` | ContactReference \| None |  |  |  |
| `billToSite` | SiteReference \| None |  |  |  |
| `billingMethod` | `ActualRates` \| `FixedFee` \| `NotToExceed` \| `OverrideRate` |  |  | billingMethod is required if the phase billSeparatelyFlag is true |
| `billingStartDate` | datetime \| None |  |  |  |
| `board` | ProjectBoardReference \| None |  |  |  |
| `budgetHours` | float \| None |  |  |  |
| `businessUnitId` | int \| None |  |  |  |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `deadlineDate` | datetime \| None |  |  |  |
| `description` | str | **y** | 100 |  |
| `downpayment` | float \| None |  |  |  |
| `estimatedExpenseCost` | float \| None |  |  |  |
| `estimatedExpenseRevenue` | float \| None |  |  |  |
| `estimatedProductCost` | float \| None |  |  |  |
| `estimatedProductRevenue` | float \| None |  |  |  |
| `estimatedTimeCost` | float \| None |  |  |  |
| `estimatedTimeRevenue` | float \| None |  |  |  |
| `hourlyRate` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `locationId` | int \| None |  |  |  |
| `markAsMilestoneFlag` | bool \| None |  |  |  |
| `notes` | str \| None |  |  |  |
| `opportunity` | OpportunityReference \| None |  |  |  |
| `parentPhase` | ProjectPhaseReference \| None |  |  |  |
| `poAmount` | float \| None |  |  |  |
| `poNumber` | str \| None |  | 25 |  |
| `projectId` | int \| None |  |  |  |
| `scheduledEnd` | datetime \| None |  |  |  |
| `scheduledHours` | float \| None |  |  |  |
| `scheduledStart` | datetime \| None |  |  |  |
| `shipToCompany` | CompanyReference \| None |  |  |  |
| `shipToContact` | ContactReference \| None |  |  |  |
| `shipToSite` | SiteReference \| None |  |  |  |
| `status` | PhaseStatusReference \| None |  |  |  |
| `wbsCode` | str \| None |  | 50 |  |

#### `ProjectTicket` — 76 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `actualHours` | float \| None |  |  |  |
| `addressLine1` | str \| None |  | 50 |  |
| `addressLine2` | str \| None |  | 50 |  |
| `agreement` | AgreementReference \| None |  |  |  |
| `allowAllClientsPortalView` | bool \| None |  |  |  |
| `approved` | bool \| None |  |  |  |
| `automaticEmailCc` | str \| None |  | 1000 |  |
| `automaticEmailCcFlag` | bool \| None |  |  |  |
| `automaticEmailContactFlag` | bool \| None |  |  |  |
| `automaticEmailResourceFlag` | bool \| None |  |  |  |
| `billExpenses` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billProducts` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `billTime` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  |  |
| `board` | BoardReference \| None |  |  |  |
| `budgetHours` | float \| None |  |  |  |
| `city` | str \| None |  | 50 |  |
| `closedBy` | str \| None |  |  |  |
| `closedDate` | datetime \| None |  |  |  |
| `closedFlag` | bool \| None |  |  |  |
| `company` | CompanyReference \| None |  |  |  |
| `contact` | ContactReference \| None |  |  |  |
| `contactEmailAddress` | str \| None |  | 250 |  |
| `contactEmailLookup` | str \| None |  |  |  |
| `contactName` | str \| None |  | 62 |  |
| `contactPhoneExtension` | str \| None |  | 15 |  |
| `contactPhoneNumber` | str \| None |  | 20 |  |
| `country` | CountryReference \| None |  |  |  |
| `currency` | CurrencyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `customerUpdatedFlag` | bool \| None |  |  |  |
| `department` | SystemDepartmentReference \| None |  |  |  |
| `duration` | int \| None |  |  |  |
| `estimatedStartDate` | datetime \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `initialDescription` | str \| None |  |  | Only available for POST, will not be returned in the response |
| `initialInternalAnalysis` | str \| None |  |  | Only available for POST, will not be returned in the response |
| `initialResolution` | str \| None |  |  | Only available for POST, will not be returned in the response |
| `isIssueFlag` | bool \| None |  |  |  |
| `item` | ServiceItemReference \| None |  |  |  |
| `knowledgeBaseCategoryId` | int \| None |  |  |  |
| `knowledgeBaseLinkId` | int \| None |  |  |  |
| `knowledgeBaseLinkType` | `Activity` \| `ProjectIssue` \| `KnowledgeBaseArticle` \| `ProjectTicket` \| `ServiceTicket` \| `Time` |  |  |  |
| `knowledgeBaseSubCategoryId` | int \| None |  |  |  |
| `lagDays` | int \| None |  |  |  |
| `lagNonworkingDaysFlag` | bool \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `opportunity` | OpportunityReference \| None |  |  |  |
| `owner` | MemberReference \| None |  |  |  |
| `phase` | ProjectPhaseReference \| None |  |  |  |
| `predecessorClosedFlag` | bool \| None |  |  |  |
| `predecessorId` | int \| None |  |  |  |
| `predecessorType` | `Ticket` \| `Phase` |  |  |  |
| `priority` | PriorityReference \| None |  |  |  |
| `processNotifications` | bool \| None |  |  | Can be set to false to skip notification processing when adding or updating a ticket (D… |
| `project` | ProjectReference \| None |  |  |  |
| `requiredDate` | datetime \| None |  |  |  |
| `resources` | str \| None |  |  |  |
| `serviceLocation` | ServiceLocationReference \| None |  |  |  |
| `site` | SiteReference \| None |  |  |  |
| `siteName` | str \| None |  | 50 |  |
| `skipCallback` | bool \| None |  |  |  |
| `source` | ServiceSourceReference \| None |  |  |  |
| `stateIdentifier` | str \| None |  | 50 |  |
| `status` | ServiceStatusReference \| None |  |  |  |
| `subBillingAmount` | float \| None |  |  |  |
| `subBillingMethod` | `ActualRates` \| `FixedFee` \| `NotToExceed` \| `OverrideRate` |  |  |  |
| `subDateAccepted` | str \| None |  |  |  |
| `subType` | ServiceSubTypeReference \| None |  |  |  |
| `summary` | str | **y** | 100 |  |
| `type` | ServiceTypeReference \| None |  |  |  |
| `wbsCode` | str \| None |  | 50 |  |
| `workRole` | WorkRoleReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |
| `zip` | str \| None |  | 12 |  |

### Time and expense

#### `TimeAccrual` — 19 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `holidayAvailableType` | `AnniversaryYear` \| `CalendarYear` |  |  |  |
| `holidayCarryoverAllowedFlag` | bool \| None |  |  |  |
| `holidayCarryoverLimit` | float \| None |  |  |  |
| `holidayFlag` | bool \| None |  |  | if holidayFlag is set to false, system will clear out or ignore the values of holidayAv… |
| `id` | int \| None |  |  |  |
| `location` | SystemLocationReference \| None |  |  |  |
| `ptoAvailableType` | `AnniversaryYear` \| `CalendarYear` |  |  |  |
| `ptoCarryoverAllowedFlag` | bool \| None |  |  |  |
| `ptoCarryoverLimit` | float \| None |  |  |  |
| `ptoFlag` | bool \| None |  |  | if ptoFlag is set to false, system will clear out or ignore the values of ptoAvailableT… |
| `sickAvailableType` | `AnniversaryYear` \| `CalendarYear` |  |  |  |
| `sickCarryoverAllowedFlag` | bool \| None |  |  |  |
| `sickCarryoverLimit` | float \| None |  |  |  |
| `sickFlag` | bool \| None |  |  | if sickFlag is set to false, system will clear out or ignore the values of sickAvailabl… |
| `vacationAvailableType` | `AnniversaryYear` \| `CalendarYear` |  |  |  |
| `vacationCarryoverAllowedFlag` | bool \| None |  |  |  |
| `vacationCarryoverLimit` | float \| None |  |  |  |
| `vacationFlag` | bool \| None |  |  | if vacationFlag is set to false, system will clear out or ingore the values of vacation… |

#### `TimeEntry` — 41 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `actualHours` | float \| None |  |  |  |
| `addToDetailDescriptionFlag` | bool \| None |  |  |  |
| `addToInternalAnalysisFlag` | bool \| None |  |  |  |
| `addToResolutionFlag` | bool \| None |  |  |  |
| `agreement` | AgreementReference \| None |  |  |  |
| `agreementAmount` | float \| None |  |  |  |
| `agreementHours` | float \| None |  |  |  |
| `billableOption` | `Billable` \| `DoNotBill` \| `NoCharge` \| `NoDefault` |  |  | Required On Updates; |
| `businessUnitId` | int \| None |  |  |  |
| `chargeToId` | int \| None |  |  | If chargeToId is not specified, we asume you enter time against the company specified |
| `chargeToType` | `ServiceTicket` \| `ProjectTicket` \| `ChargeCode` \| `Activity` |  |  | If chargeToId is not specified, we asume you enter time against the company specified |
| `company` | CompanyReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `dateEntered` | datetime \| None |  |  |  |
| `emailCc` | str \| None |  |  | To update this value use the /service/tickets endpoint automaticEmailCc field |
| `emailCcFlag` | bool \| None |  |  | This is an action flag. To update this value use the /service/tickets endpoint automati… |
| `emailContactFlag` | bool \| None |  |  | This is an action flag. To update this value use the /service/tickets endpoint automati… |
| `emailResourceFlag` | bool \| None |  |  | This is an action flag. To update this value use the /service/tickets endpoint automati… |
| `enteredBy` | str \| None |  |  |  |
| `hourlyRate` | float \| None |  |  | This field may only be Updated, it is defaulted on Create |
| `hoursBilled` | float \| None |  |  |  |
| `hoursDeduct` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `internalNotes` | str \| None |  |  |  |
| `invoice` | InvoiceReference \| None |  |  |  |
| `invoiceHours` | float \| None |  |  |  |
| `locationId` | int \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `mobileGuid` | UUID \| None |  |  |  |
| `notes` | str \| None |  |  |  |
| `overageRate` | float \| None |  |  |  |
| `phase` | ProjectPhaseReference \| None |  |  |  |
| `project` | ProjectReference \| None |  |  |  |
| `status` | `Open` \| `Rejected` \| `PendingApproval` \| `ErrorsCorrected` \| `PendingProjectApproval` \| `ApprovedByTierOne` \| `RejectBySecondTier` \| `ApprovedByTierTwo` \| `ReadyToBill` \| `Billed` \| `WrittenOff` \| `BilledAgreement` |  |  |  |
| `ticket` | TicketReference \| None |  |  |  |
| `timeEnd` | datetime \| None |  |  |  |
| `timeSheet` | TimeSheetReference \| None |  |  |  |
| `timeStart` | datetime | **y** |  |  |
| `workRole` | WorkRoleReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |

#### `TimeSheet` — 10 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `dateEnd` | datetime \| None |  |  |  |
| `dateStart` | datetime \| None |  |  |  |
| `deadline` | datetime \| None |  |  |  |
| `hours` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `member` | MemberReference \| None |  |  |  |
| `period` | int \| None |  |  |  |
| `status` | `Open` \| `Rejected` \| `PendingApproval` \| `ErrorsCorrected` \| `PendingProjectApproval` \| `ApprovedByTierOne` \| `RejectBySecondTier` \| `ApprovedByTierTwo` \| `ReadyToBill` \| `Billed` \| `WrittenOff` \| `BilledAgreement` |  |  |  |
| `year` | int \| None |  |  |  |

### Members, security and system

#### `AuditTrailEntry` — 6 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `auditSource` | str \| None |  |  |  |
| `auditSubType` | str \| None |  |  |  |
| `auditType` | str \| None |  |  |  |
| `enteredBy` | str \| None |  |  |  |
| `enteredDate` | str \| None |  |  |  |
| `text` | str \| None |  |  |  |

#### `Member` — 123 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `adminFlag` | bool \| None |  |  |  |
| `agreementInvoicingDisplayOptions` | `RemainOnInvoicingScreen` \| `ShowRecentInvoices` | **y** |  |  |
| `allowExpensesEnteredAgainstCompaniesFlag` | bool \| None |  |  |  |
| `allowInCellEntryOnTimeSheet` | bool \| None |  |  |  |
| `authenticationServiceType` | `AuthAnvil` \| `GoogleAuthenticator` \| `Email` |  |  |  |
| `autoPopupQuickNotesWithStopwatch` | bool \| None |  |  |  |
| `autoStartStopwatch` | bool \| None |  |  |  |
| `billableForecast` | float \| None |  |  |  |
| `calendar` | CalendarReference \| None |  |  |  |
| `calendarSyncIntegrationFlag` | bool \| None |  |  |  |
| `clientId` | str \| None |  |  |  |
| `companyActivityTabFormat` | `SummaryList` \| `DetailList` |  |  |  |
| `copyColumnLayoutsAndFilters` | bool \| None |  |  |  |
| `copyPodLayouts` | bool \| None |  |  |  |
| `copySharedDefaultViews` | bool \| None |  |  |  |
| `country` | CountryReference \| None |  |  |  |
| `customFields` | list[CustomFieldValue] \| None |  |  |  |
| `dailyCapacity` | float \| None |  |  |  |
| `daysTolerance` | int \| None |  |  |  |
| `defaultDepartment` | SystemDepartmentReference \| None |  |  |  |
| `defaultEmail` | `Office` \| `Mobile` \| `Home` | **y** |  |  |
| `defaultLocation` | SystemLocationReference \| None |  |  |  |
| `defaultPhone` | `Office` \| `Mobile` \| `Home` | **y** |  |  |
| `disableOnlineFlag` | bool \| None |  |  |  |
| `employeeIdentifer` | str \| None |  | 10 |  |
| `enableLdapAuthenticationFlag` | bool \| None |  |  |  |
| `enableMobileFlag` | bool \| None |  |  |  |
| `enableMobileGpsFlag` | bool \| None |  |  |  |
| `enterTimeAgainstCompanyFlag` | bool \| None |  |  |  |
| `excludedProjectBoardIds` | list[int] \| None |  |  |  |
| `excludedServiceBoardIds` | list[int] \| None |  |  |  |
| `expenseApprover` | MemberReference \| None |  |  |  |
| `firstName` | str | **y** | 30 |  |
| `fromMemberRecId` | int \| None |  |  |  |
| `globalSearchDefaultSort` | `None` \| `LastUpdatedDesc` \| `LastUpdatedAsc` \| `CreatedDesc` \| `CreatedAsc` |  |  |  |
| `globalSearchDefaultTicketFilter` | `OpenRecords` \| `ClosedRecords` \| `AllRecords` |  |  |  |
| `hideMemberInDispatchPortalFlag` | bool \| None |  |  |  |
| `hireDate` | datetime \| None |  |  |  |
| `homeEmail` | str \| None |  | 250 |  |
| `homeExtension` | str \| None |  | 10 |  |
| `homePhone` | str \| None |  | 15 |  |
| `hourlyCost` | float \| None |  |  |  |
| `hourlyRate` | float \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `identifier` | str | **y** | 15 |  |
| `inactiveDate` | datetime \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `includeInUtilizationReportingFlag` | bool \| None |  |  |  |
| `invoiceScreenDefaultTabFormat` | `ShowInvoicingTab` \| `ShowAgreementInvoicingTab` | **y** |  |  |
| `invoiceTimeTabFormat` | `SummaryList` \| `DetailList` |  |  |  |
| `invoicingDisplayOptions` | `RemainOnInvoicingScreen` \| `ShowRecentInvoices` | **y** |  |  |
| `lastLogin` | str \| None |  |  |  |
| `lastName` | str \| None |  | 30 |  |
| `ldapConfiguration` | LdapConfigurationReference \| None |  |  |  |
| `ldapUserName` | str \| None |  | 50 |  |
| `licenseClass` | `A` \| `C` \| `F` \| `X` | **y** |  | F = Full Member, A = API Member, C = StreamlineIT Member, X = Subcontractor Member |
| `mapiName` | str \| None |  |  |  |
| `memberPersonas` | list[int] \| None |  |  |  |
| `middleInitial` | str \| None |  | 1 |  |
| `minimumHours` | float \| None |  |  |  |
| `mobileEmail` | str \| None |  | 250 |  |
| `mobileExtension` | str \| None |  | 10 |  |
| `mobilePhone` | str \| None |  | 15 |  |
| `notes` | str \| None |  |  |  |
| `office365` | MemberOffice365 \| None |  |  |  |
| `officeEmail` | str \| None |  | 250 |  |
| `officeExtension` | str \| None |  | 10 |  |
| `officePhone` | str \| None |  | 15 |  |
| `partnerPortalFlag` | bool \| None |  |  |  |
| `password` | str \| None |  | 60 | ConditionallyRequired. API Member will get random password generated |
| `phoneIntegrationType` | `TAPI` \| `SKYPE` \| `NONE` |  |  |  |
| `phoneSource` | str \| None |  |  |  |
| `photo` | DocumentReference \| None |  |  |  |
| `primaryEmail` | str \| None |  | 250 |  |
| `projectDefaultBoard` | ProjectBoardReference \| None |  |  |  |
| `projectDefaultDepartment` | SystemDepartmentReference \| None |  |  |  |
| `projectDefaultLocation` | SystemLocationReference \| None |  |  |  |
| `reportCard` | ReportCardReference \| None |  |  |  |
| `reportsTo` | MemberReference \| None |  |  |  |
| `requireExpenseEntryFlag` | bool \| None |  |  |  |
| `requireStartAndEndTimeOnTimeEntryFlag` | bool \| None |  |  |  |
| `requireTimeSheetEntryFlag` | bool \| None |  |  |  |
| `restrictDefaultSalesTerritoryFlag` | bool \| None |  |  |  |
| `restrictDefaultWarehouseBinFlag` | bool \| None |  |  |  |
| `restrictDefaultWarehouseFlag` | bool \| None |  |  |  |
| `restrictDepartmentFlag` | bool \| None |  |  |  |
| `restrictLocationFlag` | bool \| None |  |  |  |
| `restrictProjectDefaultDepartmentFlag` | bool \| None |  |  |  |
| `restrictProjectDefaultLocationFlag` | bool \| None |  |  |  |
| `restrictScheduleFlag` | bool \| None |  |  |  |
| `restrictServiceDefaultDepartmentFlag` | bool \| None |  |  |  |
| `restrictServiceDefaultLocationFlag` | bool \| None |  |  |  |
| `salesDefaultLocation` | SystemLocationReference \| None |  |  |  |
| `scheduleCapacity` | float \| None |  |  |  |
| `scheduleDefaultDepartment` | SystemDepartmentReference \| None |  |  |  |
| `scheduleDefaultLocation` | SystemLocationReference \| None |  |  |  |
| `securityLocation` | SystemLocationReference \| None |  |  |  |
| `securityRole` | SecurityRoleReference \| None |  |  |  |
| `serviceBoardTeamIds` | list[int] \| None |  |  |  |
| `serviceDefaultBoard` | BoardReference \| None |  |  |  |
| `serviceDefaultDepartment` | SystemDepartmentReference \| None |  |  |  |
| `serviceDefaultLocation` | SystemLocationReference \| None |  |  |  |
| `serviceLocation` | ServiceLocationReference \| None |  |  |  |
| `signature` | str \| None |  |  |  |
| `ssoSettings` | MemberSsoSettingsReference \| None |  |  |  |
| `structureLevel` | StructureReference \| None |  |  |  |
| `stsUserAdminUrl` | str \| None |  |  |  |
| `timeApprover` | MemberReference \| None |  |  |  |
| `timeReminderEmailFlag` | bool \| None |  |  |  |
| `timeSheetStartDate` | datetime \| None |  |  |  |
| `timeZone` | TimeZoneSetupReference \| None |  |  |  |
| `timebasedOneTimePasswordActivated` | bool \| None |  |  |  |
| `title` | str \| None |  | 50 |  |
| `toastNotificationFlag` | bool \| None |  |  |  |
| `token` | str \| None |  |  |  |
| `type` | MemberTypeReference \| None |  |  |  |
| `useBrowserLanguageFlag` | bool \| None |  |  |  |
| `vendorNumber` | str \| None |  |  |  |
| `warehouse` | WarehouseReference \| None |  |  |  |
| `warehouseBin` | WarehouseBinReference \| None |  |  |  |
| `workRole` | WorkRoleReference \| None |  |  |  |
| `workType` | WorkTypeReference \| None |  |  |  |

#### `SecurityRole` — 5 fields

| Field | Type | Req | Max | Note |
|---|---|---|---|---|
| `adminFlag` | bool \| None |  |  |  |
| `id` | int \| None |  |  |  |
| `inactiveFlag` | bool \| None |  |  |  |
| `name` | str | **y** | 30 |  |

## Full inventory

Every entity in the model, by domain. Names only.

**Service delivery — the board** (29)

`Board`, `BoardAutoAssignResource`, `BoardAutoTemplate`, `BoardCopy`, `BoardDefault`, `BoardExcludedMember`, `BoardItem`, `BoardItemAssociation`, `BoardNotification`, `BoardStatus`, `BoardStatusNotification`, `BoardSubType`, `BoardTeam`, `BoardType`, `BoardTypeSubTypeItemAssociation`, `Impact`, `Priority`, `Service`, `ServiceEmailTemplate`, `ServiceLocation`, `ServiceNote`, `ServiceSignoff`, `ServiceSurvey`, `ServiceSurveyQuestion`, `ServiceSurveyQuestionOption`, `ServiceTeam`, `ServiceTemplate`, `Severity`, `Source`

**Service delivery — the ticket** (21)

`Activity`, `ActivityStatus`, `ActivityStopwatch`, `ActivityType`, `BundleRequestsCollection`, `BundleResultsCollection`, `ScheduleColor`, `ScheduleDetail`, `ScheduleEntry`, `ScheduleEntryDetail`, `ScheduleReminderTime`, `ScheduleStatus`, `ScheduleStopwatch`, `ScheduleType`, `Ticket`, `TicketBundle`, `TicketMerge`, `TicketNote`, `TicketStopwatch`, `TicketSync`, `TicketTask`

**SLA and calendars** (9)

`Calendar`, `Holiday`, `HolidayList`, `SLA`, `SLAPriority`, `WorkRole`, `WorkRoleExemption`, `WorkRoleLocation`, `WorkType`

**Workflow — the rules engine** (10)

`Workflow`, `WorkflowAction`, `WorkflowActionAutomateParameter`, `WorkflowActionUserDefinedField`, `WorkflowAttachment`, `WorkflowEvent`, `WorkflowNotifyType`, `WorkflowTableType`, `WorkflowTrigger`, `WorkflowTriggerOption`

**Commercial — agreements and billing** (51)

`AccountingBatch`, `AccountingPackage`, `Addition`, `AdjustmentDetail`, `AdjustmentType`, `Agreement`, `AgreementAdjustment`, `AgreementSite`, `AgreementType`, `AgreementTypeBoardDefault`, `AgreementTypeWorkRole`, `AgreementTypeWorkRoleExclusion`, `AgreementTypeWorkType`, `AgreementTypeWorkTypeExclusion`, `AgreementWorkRole`, `AgreementWorkRoleExclusion`, `AgreementWorkType`, `AgreementWorkTypeExclusion`, `BillingCycle`, `BillingSetupRouting`, `BillingStatus`, `BillingTerm`, `ChargeCode`, `ChargeCodeExpenseType`, `CurrencyCode`, `ExpenseEntry`, `ExpenseEntryAudit`, `ExpenseReport`, `ExpenseReportAudit`, `ExpenseTax`, `ExpenseType`, `ExpenseTypeExemption`, `Invoice`, `InvoiceEmailTemplate`, `InvoiceTemplate`, `Payment`, `PaymentType`, `TaxCode`, `TaxCodeLevel`, `TaxCodeXRef`, `TaxIntegration`, `TaxableExpenseTypeLevel`, `TaxableProductTypeLevel`, `TaxableWorkRoleLevel`, `TaxableXRefLevel`, `UnpostedExpense`, `UnpostedExpenseTaxableLevel`, `UnpostedInvoice`, `UnpostedInvoiceTaxableLevel`, `UnpostedProcurement`, `UnpostedProcurementTaxableLevel`

**Procurement** (30)

`CatalogComponent`, `CatalogInventory`, `CatalogItem`, `CatalogPricing`, `InventoryOnHand`, `Manufacturer`, `Order`, `OrderStatus`, `OrderStatusEmailTemplate`, `OrderStatusNotification`, `PricingBreak`, `PricingDetail`, `PricingSchedule`, `ProductComponent`, `ProductDemand`, `ProductDetach`, `ProductItem`, `ProductPickingShippingDetail`, `ProductRecurring`, `ProductType`, `ProductTypeExemption`, `PurchaseOrder`, `PurchaseOrderLineItem`, `PurchaseOrderStatus`, `PurchaseOrderStatusEmailTemplate`, `PurchaseOrderStatusNotification`, `ShipmentMethod`, `UnitOfMeasure`, `Warehouse`, `WarehouseBin`

**Configurations — the CMDB** (5)

`ConfigurationQuestion`, `ConfigurationStatus`, `ConfigurationType`, `ConfigurationTypeQuestion`, `ConfigurationTypeQuestionValue`

**Companies, contacts and sites** (42)

`AddressFormat`, `Company`, `CompanyCompanyTypeAssociation`, `CompanyCompanyTypeAssociationCompanyTypeAssociation`, `CompanyConfiguration`, `CompanyContactTypeAssociation`, `CompanyCustomNote`, `CompanyFinance`, `CompanyGroup`, `CompanyManagementSummary`, `CompanyMerge`, `CompanyNote`, `CompanyNoteType`, `CompanyPickerItem`, `CompanySite`, `CompanyStatus`, `CompanyTeam`, `CompanyType`, `Contact`, `ContactCommunication`, `ContactCommunicationItem`, `ContactContactTypeAssociationContactTypeAssociation`, `ContactDepartment`, `ContactGroup`, `ContactNote`, `ContactRelationship`, `ContactTrack`, `ContactType`, `Country`, `Department`, `DepartmentLocation`, `Group`, `Location`, `LocationDepartment`, `LocationWorkRole`, `PortalCalendar`, `PortalConfiguration`, `PortalConfigurationPaymentProcessor`, `PortalReport`, `PortalSecurity`, `PortalSecurityLevel`, `State`

**Projects** (12)

`Project`, `ProjectBoardTeam`, `ProjectBoardTeamMember`, `ProjectContact`, `ProjectNote`, `ProjectPhase`, `ProjectSecurityRole`, `ProjectStatus`, `ProjectTeamMember`, `ProjectTicket`, `ProjectTicketNote`, `ProjectType`

**Sales and marketing** (27)

`Campaign`, `CampaignAudit`, `CampaignCampaignSubType`, `CampaignStatus`, `CampaignType`, `Forecast`, `ForecastItem`, `MarketingCompany`, `MarketingContact`, `Opportunity`, `OpportunityContact`, `OpportunityNote`, `OpportunityRating`, `OpportunityStage`, `OpportunityStatus`, `OpportunityToAgreementConversion`, `OpportunityToProjectConversion`, `OpportunityToSalesOrderConversion`, `OpportunityToServiceTicketConversion`, `OpportunityType`, `QuoteLink`, `SalesProbability`, `SalesQuota`, `SalesTeam`, `SalesTeamMember`, `Track`, `TrackAction`

**Time and expense** (10)

`TimeAccrual`, `TimeAccrualDetail`, `TimeEntry`, `TimeEntryAudit`, `TimeExpense`, `TimePeriod`, `TimePeriodSetupDefaults`, `TimeSheet`, `TimeSheetAudit`, `TimeSheetTierUpdate`

**Finance — general ledger and accounting** (30)

`ClosedInvoice`, `Code`, `Commission`, `Conversion`, `DeliveryMethod`, `EPayConfiguration`, `FinanceCurrency`, `GLAccount`, `GLCaption`, `GLExport`, `GLExportAdjustmentTransaction`, `GLExportAdjustmentTransactionDetail`, `GLExportCustomer`, `GLExportCustomerTaxLevel`, `GLExportExpense`, `GLExportExpenseBill`, `GLExportExpenseBillDetail`, `GLExportExpenseOffset`, `GLExportInventoryTransfer`, `GLExportInventoryTransferOffset`, `GLExportPurchaseTransaction`, `GLExportPurchaseTransactionDetail`, `GLExportPurchaseTransactionDetailTax`, `GLExportPurchaseTransactionTaxLevel`, `GLExportTransaction`, `GLExportTransactionDetail`, `GLExportTransactionDetailTaxLevel`, `GLExportTransactionTaxLevel`, `GLExportVendor`, `GLPath`

**Members, security and system** (93)

`AllowedFileType`, `AllowedOrigin`, `ApiMember`, `AuditTrailEntry`, `AuthAnvil`, `AutoSyncTime`, `ConnectWiseHostedScreen`, `Count`, `CustomFieldValue`, `CustomReport`, `CustomReportParameter`, `CwTimeZone`, `DocumentFormData`, `EmailConnector`, `EmailConnectorParsingRule`, `EmailConnectorParsingStyle`, `EmailExclusion`, `EmailOpened`, `EmailToken`, `EntityType`, `ErrorResponseMessage`, `Experiment`, `FormSubmitted`, `IRestIdentifiedItem`, `ImportMassMaintenance`, `KPI`, `KPICategory`, `KnowledgeBaseArticle`, `KnowledgeBaseCategory`, `KnowledgeBaseSubCategory`, `Link`, `LinkClicked`, `ManagedDeviceAccount`, `ManagedDevicesIntegration`, `ManagedDevicesIntegrationLogin`, `ManagedDevicesIntegrationNotification`, `ManagedInformation`, `Member`, `MemberAccrual`, `MemberCertification`, `MemberDeactivation`, `MemberDeactivationCompanyTeam`, `MemberDeactivationDepartmentMananager`, `MemberDeactivationDispatchMember`, `MemberDeactivationDutyManager`, `MemberDeactivationKnowledgebaseArticle`, `MemberDeactivationMyCompanyCOORole`, `MemberDeactivationMyCompanyControllerRole`, `MemberDeactivationMyCompanyDispatchRole`, `MemberDeactivationMyCompanyDutyManagerRole`, `MemberDeactivationMyCompanyPresidentRole`, `MemberDeactivationMyCompanyServiceManagerRole`, `MemberDeactivationOpportunity`, `MemberDeactivationProjectManager`, `MemberDeactivationSalesActivity`, `MemberDeactivationSalesTeam`, `MemberDeactivationSendFromEmailNotify`, `MemberDeactivationServiceManger`, `MemberDeactivationServiceTeam`, `MemberDeactivationServiceTemplate`, `MemberDeactivationStatusWorkflow`, `MemberDeactivationWorkflow`, `MemberDelegation`, `MemberLinkSsoUser`, `MemberOffice365`, `MemberPersona`, `MemberSkill`, `MemberSsoToken`, `MemberType`, `MenuEntry`, `MenuEntryLocation`, `MyAccount`, `MyMember`, `MySecurity`, `MySecurityCustomizeItem`, `NotificationRecipient`, `OwnershipType`, `Report`, `ReportCard`, `ReportCardDetail`, `ReportColumnDefinition`, `ReportingService`, `Role`, `SecurityRole`, `Survey`, `SurveyOption`, `SurveyQuestion`, `SurveyQuestionValue`, `SurveyResultDetail`, `TemplateGeneratedCountsModel`, `UserDefinedField`, `UserDefinedFieldOption`, `ValidationError`

**Classification and reference data** (9)

`Category`, `Certification`, `Classification`, `CommunicationType`, `CorporateStructure`, `CorporateStructureLevel`, `Crm`, `StatusIndicator`, `TypeCampaignSubType`

**Reference and transport shapes** (341)

`AccountingPackageReference`, `AccountingPackageSetup`, `ActivityReference`, `ActivityStatusInfo`, `ActivityStatusReference`, `ActivityTypeReference`, `AddressFormatInfo`, `AddressFormatReference`, `AdjustmentDetailReference`, `AdjustmentReference`, `AdjustmentTypeInfo`, `AdjustmentTypeReference`, `AgreementBatchSetup`, `AgreementBillingInfo`, `AgreementReference`, `AgreementRevenueReference`, `AgreementTypeInfo`, `AgreementTypeReference`, `AgreementTypeWorkRoleInfo`, `ApiRequest`, `AuditTrailEntryGetRequest`, `AutomateScriptReference`, `BatchEntry`, `BillingCycleInfo`, `BillingCycleReference`, `BillingDeliveryReference`, `BillingSetup`, `BillingSetupInfo`, `BillingSetupReference`, `BillingStatusInfo`, `BillingStatusReference`, `BillingTermInfo`, `BillingTermsReference`, `BoardInfo`, `BoardReference`, `BoardStatusInfo`, `BoardSubTypeInfo`, `BoardTeamInfo`, `BoardTypeInfo`, `BulkResult`, `BundleRequest`, `BundleResult`, `CalendarInfo`, `CalendarReference`, `CalendarSetupReference`, `CampaignReference`, `CampaignStatusReference`, `CampaignSubTypeReference`, `CampaignTypeInfo`, `CampaignTypeReference`, `CatalogItemInfo`, `CatalogItemReference`, `CategoryInfo`, `CertificationReference`, `ChargeCodeInfo`, `ChargeCodeReference`, `ClassificationReference`, `ClearPickerRequest`, `CommunicationTypeInfo`, `CommunicationTypeReference`, `CompanyNoteTypeInfo`, `CompanyReference`, `CompanyStatusReference`, `CompanyTypeInfo`, `CompanyTypeReference`, `ConfigurationReference`, `ConfigurationStatusInfo`, `ConfigurationStatusReference`, `ConfigurationTypeInfo`, `ConfigurationTypeQuestionInfo`, `ConfigurationTypeQuestionReference`, `ConfigurationTypeQuestionValueInfo`, `ConfigurationTypeReference`, `ConnectWiseHostedSetup`, `ContactDepartmentInfo`, `ContactDepartmentReference`, `ContactReference`, `ContactTypeInfo`, `ContactTypeReference`, `ConvertItem`, `ConvertToProject`, `CorporateStructureInfo`, `CorporateStructureLevelReference`, `CountryInfo`, `CountryReference`, `CreateAccountingBatchRequest`, `CrmInfo`, `CurrencyCodeReference`, `CurrencyInfo`, `CurrencyReference`, `CustomReportReference`, `DepartmentInfo`, `DepartmentLocationInfo`, `DocumentInfo`, `DocumentReference`, `DocumentSetup`, `EmailConnectorInfo`, `EmailConnectorParsingStyleReference`, `EmailConnectorParsingTypeReference`, `EmailConnectorParsingVariableReference`, `EmailConnectorReference`, `EmailTemplateReference`, `EntityTypeInfo`, `EntityTypeReference`, `ExpenseDetailReference`, `ExpenseReportReference`, `ExpenseRevenueReference`, `ExpenseTaxTypeInfo`, `ExpenseTaxTypeReference`, `ExpenseTypeInfo`, `ExpenseTypeReference`, `ExportAccountingBatchRequest`, `FileUploadSetting`, `FilterValues`, `ForecastRevenueReference`, `GLExportSettings`, `GenericBoardTeamReference`, `GenericIdIdentifierReference`, `GoogleEmailSetup`, `GoogleEmailSetupReference`, `GroupInfo`, `GroupReference`, `HolidayInfo`, `HolidayListInfo`, `HolidayListReference`, `ImapInfo`, `ImapSetupReference`, `InOutTypeInfo`, `InOutTypeReference`, `InclusiveRevenueReference`, `Info`, `IntegratorLoginReference`, `InvoiceEmailTemplateInfo`, `InvoiceGroupingReference`, `InvoiceInfo`, `InvoiceReference`, `InvoiceTemplateDetailReference`, `InvoiceTemplateReference`, `InvoiceTemplateSetup`, `IvItemReference`, `KBCategoryReference`, `KPICategoryReference`, `KPIReference`, `KnowledgeBaseSettings`, `LdapConfigurationInfo`, `LdapConfigurationReference`, `LegacySubCategoryInfo`, `LinkInfo`, `LinkResolveUrlInfo`, `LocaleInfo`, `LocaleReference`, `LocationInfo`, `LostRevenueReference`, `ManagedDevicesIntegrationCrossReference`, `ManagedDevicesIntegrationInfo`, `ManagedDevicesIntegrationReference`, `ManagementLogDocumentInfo`, `ManagementReportSetup`, `ManagementSolutionReference`, `ManufacturerInfo`, `ManufacturerReference`, `MappedRecordReference`, `MappedTypeReference`, `MarketDescriptionInfo`, `MarketDescriptionReference`, `MemberInfo`, `MemberNotificationSetting`, `MemberReference`, `MemberSsoSettingsReference`, `MemberTypeInfo`, `MemberTypeReference`, `MenuLocationReference`, `MyMemberInfo`, `NoteTypeReference`, `NotificationRecipientReference`, `NotifyTypeReference`, `Office365EmailSetup`, `Office365EmailSetupReference`, `OnHandSerialNumberReference`, `OpenRevenueReference`, `OpportunityPriorityReference`, `OpportunityProbabilityReference`, `OpportunityRatingInfo`, `OpportunityRatingReference`, `OpportunityReference`, `OpportunitySalesRoleReference`, `OpportunityStageInfo`, `OpportunityStageReference`, `OpportunityStatusInfo`, `OpportunityStatusReference`, `OpportunityTypeInfo`, `OpportunityTypeReference`, `OrderStatusEmailTemplateReference`, `OrderStatusInfo`, `OrderStatusReference`, `Other1RevenueReference`, `Other2RevenueReference`, `OwnershipTypeInfo`, `OwnershipTypeReference`, `PaymentMethodReference`, `PaymentTypeInfo`, `PersonasInfo`, `PhaseStatusReference`, `PortalConfigurationInvoiceSetup`, `PortalConfigurationOpportunitySetup`, `PortalConfigurationPasswordEmailSetup`, `PortalConfigurationPaymentProcessorReference`, `PortalConfigurationProjectSetup`, `PortalConfigurationReference`, `PortalConfigurationServiceSetup`, `PortalSecuritySetting`, `PricingScheduleReference`, `PriorityInfo`, `PriorityReference`, `ProcurementSetting`, `ProductCategoryReference`, `ProductItemReference`, `ProductReference`, `ProductRevenueReference`, `ProductSubCategoryReference`, `ProductTypeInfo`, `ProductTypeReference`, `ProjectBoardReference`, `ProjectBoardTeamInfo`, `ProjectPhaseReference`, `ProjectReference`, `ProjectRoleReference`, `ProjectSecurityRoleSetting`, `ProjectStatusInfo`, `ProjectStatusReference`, `ProjectTypeInfo`, `ProjectTypeReference`, `PurchaseOrderLineItemReference`, `PurchaseOrderReference`, `PurchaseOrderStatusEmailTemplateReference`, `PurchaseOrderStatusReference`, `RelationshipReference`, `ReminderReference`, `ReportCardInfo`, `ReportCardReference`, `ReportDataResponse`, `RequestPasswordRequest`, `ResultInfo`, `RmaActionInfo`, `RmaActionReference`, `RmaDispositionInfo`, `RmaDispositionReference`, `RmaStatusEmailTemplateReference`, `RmaStatusInfo`, `RmaStatusReference`, `SLAInfo`, `SLAReference`, `SalesOrderReference`, `SalesProbabilityInfo`, `SalesTeamReference`, `ScheduleEntryReference`, `ScheduleSpanReference`, `ScheduleStatusReference`, `ScheduleTypeInfo`, `ScheduleTypeReference`, `SchedulingMemberInfo`, `SecurityRoleInfo`, `SecurityRoleReference`, `SecurityRoleSetting`, `ServiceCodeReference`, `ServiceEmailTemplateReference`, `ServiceInfo`, `ServiceItemReference`, `ServiceLocationInfo`, `ServiceLocationReference`, `ServiceRevenueReference`, `ServiceSignoffInfo`, `ServiceSignoffReference`, `ServiceSourceReference`, `ServiceStatusReference`, `ServiceSubTypeReference`, `ServiceSurveyReference`, `ServiceTeamReference`, `ServiceTemplateInfo`, `ServiceTemplateReference`, `ServiceTicketLinkInfo`, `ServiceTypeReference`, `ShipmentMethodInfo`, `ShipmentMethodReference`, `SicCodeReference`, `SiteReference`, `SkillCategoryReference`, `SkillInfo`, `SkillReference`, `SourceInfo`, `StandardNoteInfo`, `StateInfo`, `StateReference`, `StatusIndicatorReference`, `StructureReference`, `SubCategoryInfo`, `SuccessResponse`, `SurveyInfo`, `SurveyQuestionReference`, `SurveyReference`, `SurveyResult`, `SystemDepartmentReference`, `SystemLocationReference`, `SystemMenuEntryReference`, `SystemSetting`, `TaxCodeInfo`, `TaxCodeLevelReference`, `TaxCodeReference`, `TaxIntegrationInfo`, `TeamRoleInfo`, `TeamRoleReference`, `TicketInfo`, `TicketReference`, `TimeAccrualReference`, `TimeEntryReference`, `TimePeriodSetup`, `TimePeriodSetupReference`, `TimeRevenueReference`, `TimeSheetReference`, `TimeZoneReference`, `TimeZoneSetup`, `TimeZoneSetupInfo`, `TimeZoneSetupReference`, `TrackReference`, `UnitOfMeasureReference`, `UserDefinedFieldInfo`, `UserDefinedFieldReference`, `ValidatePortalRequest`, `ValidatePortalResponse`, `WarehouseBinInfo`, `WarehouseBinReference`, `WarehouseInfo`, `WarehouseReference`, `WonRevenueReference`, `WorkRoleInfo`, `WorkRoleReference`, `WorkTypeInfo`, `WorkTypeReference`, `WorkflowNotifyTypeInfo`, `WorkflowTableTypeInfo`, `WorkflowTableTypeReference`

**Unclassified** (54)

`CallbackEntry`, `IdCollection`, `Imap`, `InOutBoard`, `InOutType`, `IntegratorLogin`, `IntegratorTag`, `IntegratorTagCollection`, `LdapConfiguration`, `LdapConfigurationTestLink`, `LegacySubCategory`, `LicenseBit`, `Management`, `ManagementBackup`, `ManagementItSolution`, `ManagementItSolutionAgreementInterfaceParameter`, `ManagementNetworkSecurity`, `ManagementReportNotification`, `MappedType`, `MarketDescription`, `MarketplaceImport`, `MinimumStockByWarehouse`, `OnHandSerialNumber`, `OsGradeWeight`, `Other`, `PageValues`, `ParsingType`, `ParsingVariable`, `PatchOperation`, `PhaseStatus`, `ProcurementAdjustment`, `PurchasingDemand`, `RmaAction`, `RmaDisposition`, `RmaStatus`, `RmaStatusEmailTemplate`, `RmaStatusNotification`, `RmaTag`, `ServiceTicketLink`, `ServiceTicketNote`, `SetupScreen`, `Skill`, `SkillCategory`, `SsoConfiguration`, `SsoUser`, `StandardNote`, `SubCategory`, `Task`, `Team`, `TeamMember`, `TeamRole`, `TodayPageCategory`, `Token`, `Usage`

