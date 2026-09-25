# platform/imaging — the Path A platform

**Status, 24 Sep 2026: M1 (the engine), M2.1 (the front door and the viewer),
M2.2 (sign-in), the first part of M2.3 (the worklist) and M3 (the BizBox
connector, backups with a disaster drill, and the feed watch and alerts) are
built and proven off-prem. Nothing is deployed.** Dada's rule
(23 Sep): nothing goes on-prem until the whole platform is built, and the
on-prem go is his. Deployment also stays gated on ADR-001 (still *Proposed*)
and on the safety work in [`../README.md`](../README.md), "What it is gated
on".

This replaces the 6 Sep skeleton in `platform/`, which was never run.

## What is built

```
            edge                         engine network (no route out)
person ─ HTTPS 443 ─▶ front (nginx) ─┬─▶ oauth2-proxy ─▶ sessions (Valkey)
                                     ├─▶ keycloak ─▶ pg-platform (keycloak); and, by LDAPS, ─▶ PMC's AD
                                     ├─▶ viewer (OHIF, static files)
                                     ├─▶ app (the worklist) ─┬─▶ pg-platform (platform)
                                     └─▶ orthanc ◀───────────┘
modality ─ DICOM 4242 ─────────────────▶   │
                                           ├─▶ auth-service ─▶ keycloak
                                           ├─▶ pg-index         the index
                                           └─▶ orthanc-storage  the images
```

- **M1, the engine:** Orthanc and its PostgreSQL index, on a network with no
  route out.
- **M2.1, the front door and the viewer:** one origin over TLS and HTTP/2.
  `/viewer?StudyInstanceUIDs=…` is OHIF; `/dicom-web/` is the engine's DICOMweb,
  read-only and never cached. Nothing else of the engine is routed.
- **M2.2, sign-in:** see [Sign-in](#sign-in) below. People sign in with
  their PMC Windows logon, checked against PMC's Active Directory, and five
  AD groups give the roles. Every page and every image request needs a
  session, and the engine decides, per role, what each person may see.
- **M2.3, the front door app, first part:** see
  [The front door app](#the-front-door-app) below. The site's address opens
  the PMC worklist at `/pmc/`, which opens the viewer.
- **M3.2, the BizBox connector:** see
  [The BizBox connector](#the-bizbox-connector) below. Orders placed in
  BizBox reach the consoles' worklists, read-only from one agreed view.
- **M3.1, backups:** see [Backups](#backups) below. Every database change is
  kept as it happens; every night the images and the database backups go to
  the R740xd, which the primary can add to but never delete from, and from
  there off-site. A disaster drill rebuilds the platform from the off-site
  copy alone.
- **M3.3, the feed watch and alerts:** see
  [Feed watch and alerts](#feed-watch-and-alerts) below. ICT hears by email
  or Teams when a modality goes quiet, the engine or sign-in is down, space
  runs low, a certificate is about to expire, or a backup is late.
- **M5, the reading experience:** the viewer opens fast and stays cached
  (M5.1, see Measured); its reading tools are configured for PMC (M5.2, see
  [The viewer's tools](#the-viewers-tools)); the reading list carries each
  study's first image, a preview with its series and the patient's earlier
  studies, read and unread, totals, and never lags, in PMC's look with
  motion that explains (M5.3, see [The reading list](#the-reading-list));
  the reading room holds the list and the viewer together, with the next
  study already loaded (M5.4, see [The reading room](#the-reading-room)).
- **PMC's identity:** see [Branding](#branding) below. The sign-in page, the
  app, the viewer, the signed-out page and the alert email wear the 2026
  identity as the portal proposal applied it: PMC Blue, the four-segment
  bar, the white lock-up, Aptos, *Better Care. For Every Life.*

No port is published to the host in the build. The tests run in containers:
one on the engine network plays the modalities, and one on the edge network is
a person at a PC, with Chromium, who can reach the front door and nothing else.
Nothing is mocked, except PMC's Active Directory and Azure themselves: the
tests sign in against a stand-in AD (Samba's AD domain controller,
`identity/test/ad/`, with invented people and groups) and copy off-site to a
stand-in Azure (Azurite). Neither is ever deployed.

## Sign-in

**Dada's decision, 24 Sep 2026: people sign in with their PMC Windows logon,
checked against PMC's own Active Directory, and AD groups decide the roles.
Not Entra ID.** The Entra ID version (23 Sep) is in git history.

People type the Windows username and password they already use at PMC.
Nobody has a separate imaging password, and the platform stores none: AD
checks every one.

How a sign-in goes. Each step is MEASURED by the tests, against a stand-in
AD (Samba's AD domain controller, `identity/test/ad/`), unless marked:

1. A person opens a link, say a study in the viewer. The front door asks
   oauth2-proxy whether the request carries a session. It does not, so the
   person is sent to sign in. A request a page makes in the background (a
   script, an image) gets a plain 401 instead and can never start a sign-in.
2. oauth2-proxy sends them to PMC's sign-in page (Keycloak), which asks for
   their Windows username and password.
3. Keycloak finds the person in AD with a read-only account, and checks
   their password with a domain controller, over LDAPS. It trusts the domain
   controller's certificate only through the CA ICT names. A disabled
   account is refused.
4. Keycloak asks AD which of the five imaging groups the person is in,
   directly or through nested groups, and turns them into PMC roles (below).
   Someone in none of them gets no role, and oauth2-proxy refuses them a
   session.
5. oauth2-proxy keeps the session in Valkey and gives the browser one cookie,
   `__Host-pmc-session`: HttpOnly, Secure, SameSite=Lax. It holds a ticket,
   not a token, and the page's scripts cannot read it. The person lands on the
   page they asked for.
6. On every request the front door hands the engine the person's own access
   token. It lasts 5 minutes, and oauth2-proxy renews it once it is 4 minutes
   old, so a person keeps working past it. Each renewal asks AD again, so
   someone taken out of their group loses access at the next renewal
   (MEASURED: after 40–42 s in the tests, in three runs, where tokens renew at 40 s; on
   site within about 4 minutes, INFERRED). The engine's authorization plugin
   asks orthanc-auth-service what the person's role may do, and matches the
   route against the engine's permission table (`orthanc/orthanc.json`). A
   route the table does not name is refused, whoever asks. An expired token
   is refused too, though up to a minute late (see Found while building it).

Signing out (`/oauth2/sign_out`) ends the session, and the viewer's own
requests cannot revive it.

Two more things the tests prove:

- **Guessing at the sign-in cannot lock someone out of Windows.** After five
  wrong passwords Keycloak stops asking AD for a while (1 minute, doubling up
  to 15), so AD's own lockout, which would lock the person out of Windows as
  well, is never reached (MEASURED: AD counted five bad passwords, short of
  the stand-in's lockout at ten, and the Windows account still worked).
- **Nothing on the platform needs the internet.** Keycloak talks to the
  domain controllers and nothing else.

### Roles

| Role | AD group (site value) | May | Sees |
|---|---|---|---|
| `pmc-radiologist` | `PMC_AD_GROUP_RADIOLOGISTS` | search, view, download | every study |
| `pmc-cardiologist` | `PMC_AD_GROUP_CARDIOLOGISTS` | search, view, download | every study |
| `pmc-technologist` | `PMC_AD_GROUP_TECHNOLOGISTS` | search, view | every study |
| `pmc-referrer` | `PMC_AD_GROUP_REFERRERS` | search, view | only studies shared with referrers |
| `pmc-ict-admin` | `PMC_AD_GROUP_ICT_ADMINS` | as a radiologist, plus worklists, modalities, upload, labels, delete | every study |
| `pmc-service` | none: the platform's own services, by API key | as ICT, except delete | every study |

The roles and the group behind each are in `identity/realm-pmc.json`, and
what each may do is in `identity/auth-service/permissions.json`. Two things
the table does not say:

- **Viewing is copying.** A viewer works by fetching a study's DICOM through
  DICOMweb, so anyone who may view a study can, with some effort, save it
  (INFERRED from the permission table, which allows exactly that). The
  download right (a whole study as a zip) is not routed from the front door
  yet.
- **ICT's extra rights are not reachable yet.** The front door routes only
  DICOMweb reads. The admin rights take effect when an admin screen arrives
  (M2.3).

Sharing with a referrer is a label on the study, `referrer-shared`. Only the
ICT and service roles may set it, and a share does not expire.

### Decisions for Dada

The design works either way on each of these; the build has a placeholder.

- **Who is in each group**, and whether these five roles are the right ones.
- **How long a session lasts.** Now: signed out after 1 hour idle, and after
  12 hours at most (a shift). Set in `identity/realm-pmc.json`.
- **Who may share a study with referrers, and for how long.** The front door
  app (M2.3) carries the answer.
- **A second factor.** AD on its own is a password. Keycloak can add an
  authenticator app or a passkey, for everyone or only from outside PMC's
  network. Not built.
- **Windows single sign-on.** On domain-joined PCs people could skip the
  password prompt altogether (Kerberos). It needs a service account and a
  keytab from ICT. Not built.
- **Referring doctors from outside PMC** need an AD account to sign in.
- **OHIF's investigational-use notice** (see Choices).

### What ICT provides at go-live

None of it goes in git. Keycloak refuses to start if any of it is missing.

1. **A read-only AD account** for the sign-in. A plain domain user will do:
   AD lets any user read the directory. Its password goes in
   `secrets/ad-bind-password`, and its DN in `PMC_AD_BIND_DN`.
2. **LDAPS on the domain controllers**, and the certificate of the CA that
   signed theirs, in `secrets/tls/ad-ca.crt`. `PMC_AD_URL` names the domain
   controllers, as `ldaps://<name>:636`, space-separated; Keycloak tries them
   in turn.
3. **Five security groups**, one per role, in one OU (`PMC_AD_GROUPS_DN`),
   with their names (`cn`) in `PMC_AD_GROUP_RADIOLOGISTS`,
   `_CARDIOLOGISTS`, `_TECHNOLOGISTS`, `_REFERRERS` and `_ICT_ADMINS`. People
   may be members directly or through other groups.
4. **Where the people are**, in `PMC_AD_USERS_DN`: searched with everything
   below it.
5. **An account lockout threshold above five** wrong passwords, or Keycloak's
   `failureFactor` is lowered to stay below it. PMC's threshold is NOT
   VERIFIED.
6. **One firewall rule** (M4): the platform may reach the domain controllers
   on port 636, and nothing else outside.

### Found while building it

MEASURED, 23 and 24 Sep 2026, unless marked.

- **orthanc-auth-service 26.8.1 writes the tokens it checks to its log** at
  INFO level. Here it runs at WARNING (`identity/auth-service/pmc_quiet.py`),
  so no token reaches a log.
- **Its permission names are a fixed list.** The engine's table uses
  `api-view` for search, `view` to read a study and `admin-permissions` for
  administration.
- **Keycloak reports itself ready before it has imported the realm.** Its
  health check therefore waits for the `pmc` realm itself, and the auth
  service waits for Keycloak.
- **A new share takes about a minute to reach a referrer**, because the
  engine's authorization plugin caches what it knows about a study. See
  Measured.
- **Sign-out used to undo itself.** The viewer's requests still in flight
  followed the sign-in redirect straight back in. Now only a page load can
  start a sign-in.
- **The engine dropped idle connections after 1 s** (its default), racing
  clients that reused them. Its `KeepAliveTimeout` is now 10 s, and the front
  door lets go after 5 s.
- **The realm is imported only at Keycloak's first start.** A later change to
  `identity/realm-pmc.json`, including the AD settings, does not reach a
  running platform. See Open.
- **There is no Keycloak administrator.** When ICT needs one, `kc.sh
  bootstrap-admin` creates a temporary one (NOT VERIFIED here).
- **Keycloak asks AD every time.** It keeps a record of each person after
  their first sign-in, but reads their groups and whether their account is
  enabled from AD on every sign-in and every renewal (its cache is off).
  That is what makes a leaver's access end at the next renewal.
- **AD counts every wrong password** (`badPwdCount`), including those typed
  at PMC's sign-in page, which is why Keycloak's own limit sits below AD's.
- **Samba 4.22 runs as a domain controller in an ordinary container**, once
  it keeps Windows ACLs in `user.NTACL` (an option since Samba 4.18), with no
  extra privilege.
- **The tests' LDAP client is old.** ldap3 2.9.1 (2021) is its latest
  release, and it imports two pyasn1 names that pyasn1 has deprecated (two
  warnings in every run). The runner pins pyasn1 0.6.4 by hash, so nothing
  changes under it; a pyasn1 that drops the names would need ldap3 replaced.
  Only the tests use it.
- **An expired token is still accepted for up to a minute.** The engine
  refused one 63 s after it expired. orthanc-auth-service 26.8.1 tells the
  authorization plugin to keep a person's profile for 60 s, and that figure
  is fixed in its code (MEASURED from its source). The token only ever sits
  inside the platform (oauth2-proxy, the front door, the engine), never in a
  browser, so this is a one-minute window for a token stolen from inside, not
  for a person at a PC.

## The front door app

The site's address, `https://imaging.pmcne.ph/`, now opens the PMC worklist
at `/pmc/`, not the viewer. It is PMC's own code (`app/`): a page in React
and a small server in Node, in one container. OHIF is the viewer only.

What a person gets. Each point is MEASURED by the tests unless marked:

- **The worklist:** every study they may see, newest first. When it was taken
  and how long ago; the patient's name, ID, sex and age; the kinds of image;
  the description; the accession number; the image count; and whether images
  are still arriving.
- **Filters and search:** the kind of study (X-ray, CT, MR, ultrasound, cath
  lab), how far back, and one box for a name, a patient ID or an accession
  number. The filters are part of the address, so a view is a link.
- **Opening a study:** Enter or a double-click opens the viewer in one named
  window, and the next study opens in that same window. On two screens the
  list stays on one and the viewer on the other.
- **Live:** a new study appears on every open worklist without a reload. The
  page heard of one 1.6–1.7 s after the modality started sending it (two
  runs).
- **Claiming a study:** a radiologist or cardiologist presses `A` (or
  Claim) and the study is theirs to read; everyone's worklist shows who has
  it within seconds. Nobody else can take or release it. "Claimed by me"
  lists just their own.
- **An audit trail:** every study opened from the worklist, and every claim
  and release, is recorded with who and when. ICT can read it; nobody can
  change it (the app's database role may only add to it).
- **The keyboard:** `/` finds, `J` and `K` move, `Enter` opens, `A` claims,
  `R` marks read, `Esc` closes the preview. A row the keyboard reaches at the
  top of the list lands below the column headings, not under them (M5.4:
  `scroll-padding-top` on the list, which the browser and React Aria both
  honour when they scroll a row into view).
- **Since M5.3:** each row's first image, a preview pane, read and unread,
  totals, compact rows, and a list that does not lag: see
  [The reading list](#the-reading-list).
- **Light and dark**, both designed; the page follows the PC unless the person
  picks one. PMC's 2026 identity, as in the sample Dada saw. On a phone the
  worklist narrows to when, who and what.
- **Accessibility:** WCAG 2.2 AA, checked by axe-core in both themes on every
  run.

How it keeps the engine in charge:

- **The engine decides what each person sees.** The app asks the engine for a
  worklist with the person's own token. A referrer's worklist therefore comes
  back cut to the studies shared with referrers, whatever the app asks for,
  and at once: a search is filtered by label in the index, not cached.
- **It believes only tokens Keycloak signed.** It checks each token against
  Keycloak's signing keys, so nothing else on the engine network can pose as
  a person. An unsigned or tampered token gets 401.
- **Its own key reads only the change log.** The app polls the engine's
  change log with the platform's key, and all it passes on is "the studies
  changed". Each open page then asks again with its own person's token.
- **It sorts only where the engine can.** OrderBy goes only to an engine that
  reports `HasExtendedFind` (the PostgreSQL index). Pointed at the legacy
  ODBC index, which answers OrderBy with HTTP 500, it would sort each page
  itself instead (INFERRED: the code path exists; that index is not in the
  build).

Not there yet, and where each part comes from:

| Missing | Comes with |
|---|---|
| Priority and STAT, from the BizBox order | M3, the BizBox connector |
| Assigning a study to someone else; a claim that expires | M2.3, with ICT's admin screens |
| A report marking its study read by itself | after the reporting decision; today a reader marks a study read (M5.3) |
| Sharing a study with referrers from the page | M2.3, after Dada decides who may share and for how long |
| ICT's admin screens | M2.3 |
| Reports | after the reporting decision (the record's open question) |
| Filipino, for anything a patient sees | with the first patient-facing page |

### Found while building the app

- **The router read numbers as numbers.** TanStack Router's own address
  parser turns `?q=12345` into the number 12345, which the page's filter
  rules then dropped, so a search for a numeric patient ID (PMC's are
  numbers) silently vanished (MEASURED: `?mine=1` failed the same way in a
  test). The page now reads its address as text only, and a test searches
  for a number.

### PMC's platform database

What no archive holds lives in PMC's own database, `platform`, on the
`pg-platform` cluster beside Keycloak's. Studies are named there only by
their DICOM identifiers, never by the engine's own IDs, so the engine stays
swappable.

- **Schemas:** `reading` (claims, and since M5.3 `reading.done`: studies
  marked read), `ris` (orders from BizBox) and `audit` (the audit trail,
  append-only). Reports and shares join as those parts are built.
- **Two roles.** `platform_owner` owns every object and runs the migrations;
  `platform_app` is what the front door app logs in as, with only the grants
  the migrations give it. Neither can reach Keycloak's database, nor
  Keycloak's role this one.
- **Schema as code.** `db/migrations/` holds plain SQL, applied by dbmate as
  a one-shot container (`migrate`) before the app starts. `db/schema.sql` is
  the schema those migrations produce; `ci/run.sh` dumps the live database
  on every run and fails if the two differ.

## Backups

M3.1, built and proven off-prem. Nothing runs on site yet.

```
primary (the platform)                         R740xd (second building)                off-site
pg-index ────┐ every log segment,
pg-platform ─┴─ as written ─▶ pgbackrest-repo ─┐
orthanc-storage (the images) ──────────────────┴─ nightly, add-only ─▶ kopia-server ─ nightly, new blobs only ─▶ Azure
```

- **Every change to either database is kept as it happens.** Both PostgreSQL
  clusters hand each finished write-ahead log segment to pgBackRest, and
  close one at least once a minute (`archive_timeout`). So a database can be
  put back to any moment since its oldest kept full backup, not only to last
  night. The database containers stay on the engine network, with no route
  out: their backups leave the host inside the nightly snapshot.
- **Every night** (`tools/backup.sh`): pgBackRest backs up both clusters
  (full on Sundays, differential on other days, two full backups kept) and
  checks each. Then Kopia snapshots the engine's files and pgBackRest's
  repository to the Kopia server on the R740xd.
- **The primary can add to the R740xd's copy, never remove from it.** It
  connects as its own Kopia user, allowed to add snapshots and nothing else.
  Expiry and maintenance run on the R740xd, as the repository's owner. So
  ransomware on the primary, or a mistake there, cannot delete what the
  R740xd already holds. `tools/backup.sh full --prove-append-only` tries to
  delete a snapshot and fails if it can; `ci/run.sh` runs it that way.
- **Then off-site** (`tools/offsite.sh`, on the R740xd): `kopia repository
  sync-to azure` copies new blobs to an Azure Blob Storage container and never
  deletes one. Only the R740xd holds the storage key. Kopia encrypts every
  blob before it leaves (AES256-GCM-HMAC-SHA256, MEASURED from the
  repository's status), with a key made from the repository password.
- **Off-site stays off until it is decided.** On site,
  `tools/make-secrets.sh` leaves the storage key empty, and `tools/offsite.sh`
  then does nothing. A cloud copy waits on the DPO's answers and on Dada
  (the record's open decision). ICT placing the key switches it on.
- **The disaster drill** (`ci/restore-drill.sh`, which refuses any compose
  project but the test one): delete both hosts' volumes, meaning both
  clusters, the engine's files, the database backups and the R740xd's copy.
  Then rebuild from the off-site copy alone: verify every file of every
  snapshot, restore the engine's files and pgBackRest's repository, restore
  both clusters from it (replaying every archived segment), start the
  platform, and check that archiving works again. The after-restart tests then
  run once more.

What that gives, INFERRED from the design:

| | |
|---|---|
| 3 copies | the live data; the R740xd's copy; the off-site copy |
| 2 kinds of storage | disks in two buildings; object storage in Azure |
| 1 off site | Azure, once switched on |
| 1 the primary cannot change | the R740xd's copy (add-only, MEASURED on every run). On Azure, immutability is ICT's to set; the stand-in does not enforce it, so NOT VERIFIED here |
| 0 errors | every drill verifies every file it restores. pgBackRest checks every database page against its checksum as it backs up; a bad page is logged and noted in the backup, not fatal (MEASURED from its own help), so the alerts (M3) must watch for it |

How much could be lost, INFERRED from the schedule:

- **a database mistake, the primary intact:** up to about a minute (a
  point-in-time restore from the primary's own repository);
- **the primary lost, the R740xd intact:** up to one night;
- **both buildings lost:** up to one night, from off-site.

Studies sent since the last snapshot are likely still on the modalities that
sent them and can be sent again (INFERRED; how long each modality keeps its
studies is NOT VERIFIED). M4 can make the R740xd pgBackRest's repository host
too, which brings the second case down to about a minute for the databases,
though not for the images.

### What ICT provides for backups

- **The R740xd**, running `compose.r740xd.yaml` (M4 packages it), with disks
  for the Kopia repository: at least the archive (6.3 TB after the
  migration), its growth, and what the retention keeps. Sizing is NOT
  VERIFIED.
- **An Azure storage account and container** for the off-site copy, with
  immutability set, once Dada and the DPO agree.
- **Escrow, away from both hosts:** the Kopia repository password and the
  storage key. Without the password nobody can read the copy, including PMC.
- **The schedule:** `tools/backup.sh` nightly on the primary, then
  `tools/offsite.sh` on the R740xd. M4 installs both as timers.

### Found while building the backups

- **Kopia never makes the Azure container.** `sync-to` into a missing one
  fails with `ContainerNotFound` (MEASURED). That is kept: ICT makes the
  container, with its immutability policy, and a missing one stops the copy
  rather than sending it somewhere unprotected. The tests make it in the
  stand-in (`ci/azure-standin-container.mjs`).
- **Compose's `--wait` counts a container without a health check as ready as
  soon as it runs.** The stand-in was running but not yet listening (MEASURED:
  connection refused), so it has a health check now.
- **A restore logs `unknown group 'root' in backup manifest`.** The official
  image leaves the data directory's group as root; the restore gives it the
  postgres group. Harmless (MEASURED: both clusters start, archive and pass
  every check).
- **The snapshot's order matters.** The database backups are snapshotted
  before the engine's files, so a restored index never names a file the
  snapshot missed. The first version got that order from the alphabet;
  `backup/kopia/snapshot.sh` now names it.

## The BizBox connector

M3.2, built and proven off-prem against a stand-in BizBox. BizBox's own view
does not exist yet: it needs PMC's DBA and the vendor (see below).

- **Orders reach the consoles.** An order placed in BizBox appears on the
  worklist of every console of its section within one poll (30 s on site),
  with the patient's name, ID, birth date and sex, the procedure and its
  priority as BizBox has them. A change in BizBox updates the waiting entry;
  a cancellation withdraws it. When the console sends the study under the
  order's identifiers, the engine takes the entries off, and the connector
  marks the order performed.
- **Read-only.** It reads one view in BizBox's database through a login
  allowed SELECT on that view and nothing else (MEASURED: every table, and
  every write, is refused). Nothing is ever written to BizBox.
- **Nothing lost, nothing held up.** A row's change marker (`change_seq`) is
  SQL Server's rowversion, a database-wide counter rather than a clock. It is
  taken when a row is written, not when it commits, so the connector reads
  only below `MIN_ACTIVE_ROWVERSION()` and passes over rows another
  transaction holds (`READCOMMITTEDLOCK, READPAST`) instead of waiting on
  them. MEASURED here: an order whose transaction commits after a later one
  is not lost, and an open BizBox transaction holds nothing up.
- **One worklist entry per console.** DICOM allows one entry to name several
  consoles, but the engine's worklist then reaches none of them (MEASURED by
  the research proof). All of an order's entries share its StudyInstanceUID,
  which the order number fixes (`2.25.` and a UUID), so the images land on the
  study the order expects, whichever console does the exam.
- **After the exam, a person decides.** A BizBox change to an order already
  performed is never applied to the images by itself: the order is marked
  for review, and ICT is told (`OrderNeedsReview`).
- **Its record** is the `ris` schema of the platform database: each order's
  worklist entries and state, where it is in BizBox and in the engine's
  change feed, and what it did (`ris.event`, append-only by grant).

The view's contract, one row per imaging order:

| Column | What it is |
|---|---|
| `order_no` | BizBox's order number: the accession number, 1 to 16 characters |
| `hospital_no`, `last_name`, `first_name`, `middle_name`, `birth_date`, `sex` | the patient |
| `encounter_no` | the admission or visit |
| `section`, `procedure_code`, `procedure_desc`, `priority`, `scheduled_at` | what is ordered, where, and when |
| `referring_doctor` | who ordered it |
| `status` | `ORDERED` or `CANCELLED` |
| `change_seq` | the larger rowversion of the order and its patient, as bigint |

MEASURED here, polling every 2 s: an order reached both X-ray consoles
1.2–2.3 s after BizBox committed it, and 100 orders placed at once reached both
consoles within 3.8–3.9 s (two runs).

### What ICT and PMC's DBA provide

1. **The view** (`dbo.v_pmc_imaging_orders`, or another name in
   `PMC_BIZBOX_VIEW`), mapping BizBox's tables onto the contract, with the
   vendor. The stand-in (`orders/test/bizbox/schema.sql`) shows its shape.
   BizBox's own tables, and whether its orders carry all of this, are NOT
   VERIFIED: no cloud session reaches DND-SQL01, so the SQL01 row maps them.
2. **A SQL Server login** with SELECT on that view and nothing else, and its
   password in `secrets/bizbox-password`.
3. **The site values:** `PMC_BIZBOX_SERVER` (host,port), `PMC_BIZBOX_DATABASE`,
   `PMC_BIZBOX_USER`, and `PMC_ORDERS_STATIONS`: which consoles (AE titles)
   take each BizBox section's orders, as JSON. Without a server the connector
   idles.
4. **A certificate the connector can check** on SQL Server's connection
   (`PMC_BIZBOX_TRUST_SERVER_CERT` stays `no` on site). What DND-SQL01
   presents is NOT VERIFIED.
5. **Each console set to ask the engine for its worklist**, with its own AE
   title. Which of PMC's consoles can is NOT VERIFIED (the record's open
   question on the Azurion and the CT consoles).
6. **One firewall rule** (M4): the connector may reach SQL Server's port and
   nothing else.

### Not built yet

The research proof went further, and those parts wait on decisions:

- **MPPS**, a console's "exam started, exam done" messages. The engine does not
  accept them (MEASURED by the proof), so the proof's connector received them
  itself. Built when ICT confirms which consoles send them.
- **A study done without an order, and a BizBox correction to images already
  stored.** The proof reconciled both through a journal, because the engine's
  own modify call, used one way, deletes the study it was asked to correct
  (MEASURED by the proof). Nothing on the platform calls it.
- **Reports** (the proof signed them as DICOM SR, HL7 ORU and FHIR) wait for
  Dada's decision on where reporting lives.

## Feed watch and alerts

M3.3, built and proven off-prem. What ICT hears about, and how:

- **The watch** (`watch/src/main.mjs`: Node 24, one file, no packages) only
  reads. It follows the engine's change feed and notes, for each registered
  modality, when it last sent a study (once the engine holds it stable). It
  checks that the engine answers, that each domain controller answers LDAPS
  with a certificate the platform trusts, and how much space is free where
  the images are. It reads when the site's and the domain controllers'
  certificates expire, the newest backup of each database cluster (from
  pgBackRest's own record), and when the newest snapshot to the R740xd
  finished.
- **Prometheus 3.14** reads the watch every 15 s, keeps 90 days, and
  evaluates the alert rules (`monitor/rules.yml`).
- **Alertmanager 0.34** sends what fires to ICT: by email through PMC's mail
  relay, to a Teams channel through a Workflows webhook, or both. Neither is
  set until ICT sets it; until then alerts show only in Alertmanager.

| Alert | Fires when | Severity |
|---|---|---|
| `FeedSilent` | a modality has sent nothing for longer than its limit: 24 h, unless ICT sets another for it | warning |
| `EngineDown` | the engine has not answered for 2 minutes | critical |
| `SignInDown` | no domain controller has answered LDAPS for 5 minutes: nobody can sign in | critical |
| `DomainControllerDown` | one domain controller has not, for 15 minutes | warning |
| `StorageLow`, `StorageCritical` | under 15%, then under 5%, free where the images are | warning, critical |
| `CertificateExpiring`, `DirectoryCertificateExpiring` | the site's, or a domain controller's, certificate has under 21 days left | warning |
| `DatabaseBackupStale`, `DatabaseBackupMissing` | no backup of a cluster for 26 hours; or none at all, a day after the start | critical |
| `SnapshotStale` | no snapshot to the R740xd for 26 hours | critical |
| `WatchDown` | Prometheus cannot read the watch for 5 minutes, so nothing else can fire | critical |

The tests register a modality allowed 20 s of silence, have it send one
study, and wait: the `FeedSilent` email reached ICT's inbox at the stand-in
relay 65–75 s after that study, in four runs (MEASURED). After the nightly backup,
the watch showed both clusters' backups and the snapshot within seconds.

### What ICT provides for alerts

- **Where alerts go:** `PMC_ALERT_EMAIL_TO` and `PMC_ALERT_EMAIL_FROM`, and
  the mail relay as `PMC_ALERT_SMTP` (host:port) with `PMC_ALERT_SMTP_TLS`;
  and/or a Teams Workflows webhook URL in `secrets/alert-teams-webhook`.
- **Each modality's limit**, where a day is wrong: a cathlab idle over a
  weekend, say. `PMC_FEED_SILENCE_OVERRIDES`, by registered name:
  `cathlab-qfr=72h,mr-sempra=48h`.
- **One firewall rule** (M4): Alertmanager may reach the relay, and Teams if
  it is used, and nothing else.

## The reading list

M5.3 (25 Sep 2026): the worklist grew into a reading list, on Dada's two
asks of that day, *no lag on the GUI* and *a modern GUI with effects, not a
simple app*. Each point is MEASURED by `tests/test_app.py` or
`browser/tests/home.spec.js` unless marked.

What a reader has:

- **Each study's first image**, small, in its row: the engine renders it
  (`/dicom-web/studies/{uid}/thumbnail`) through the front door, on the
  person's own session, never cached on the PC. A row that scrolls into view
  fetches its image then, not before.
- **A preview pane** for the selected row (a click, or `J`/`K`): the patient,
  the study, its series each with its own image and count, and the same
  patient's earlier studies, newest first. **Compare** opens the current
  study beside a prior in the viewer's compare layout (a 2×2 grid, the
  current study left and the prior right; the lower row fills when each
  study has more than one series; OHIF's own `@ohif/hpCompare`). `Esc`
  closes the pane.
- **Read and unread.** `R` (or *Mark read*) says the reader has finished
  with a study, once it is reported where PMC's reports live today
  (BizBox). A read study drops its claim, shows who read it and when, and
  leaves the **Unread** list. Only the reader who marked it can unmark it;
  a study someone else holds cannot be marked read past them; only
  radiologists and cardiologists mark. Both go into the audit trail. When
  reports come to the platform, a signed report will mark its study read by
  itself.
- **Totals:** "142 studies" for the filters in force, counted by the engine
  (`/tools/count-resources`). Not for a search (three questions merged),
  nor for *claimed by me*, and never for a referrer: the engine's count
  ignores the labels its search respects (INFERRED from the authorization
  plugin's source), so it would count studies they cannot see.
- **Waiting:** an unread, unclaimed study's "ago" turns Care Orange after
  two hours and bold after eight (INFERRED thresholds; see Open). STAT and
  priority come with the BizBox order (M3).
- **Compact rows** (the button at the right of the filters): no images,
  closer rows; remembered on the PC.
- **State in words, never colour alone:** Arriving, Unread, Claimed, Read.

No lag (the numbers are in Measured):

- **Only the rows on screen exist.** The table is virtualized (React Aria's
  `Virtualizer`), so a page of 50, or 500 after *Show more*, costs the
  browser the same fifteen rows. The list is a table on a phone, where three
  columns and few rows need none of this.
- **The table re-renders only when what it shows changes.** It is memoized
  apart from the page: a fetch in progress, a notice, or the clock never
  re-render the rows; the "8 min" in each row ticks from one shared clock
  that re-renders those words alone; the rows are drawn at a lower priority
  than a keystroke (`useDeferredValue`).
- **A filter keeps the rows on screen until the new ones arrive**
  (`keepPreviousData`): no empty list, no "loading" flash, ever.
- **The preview follows the keyboard once it settles** (120 ms): holding
  `J` never asks the engine fifty times.
- **The page arrives compressed and in parts:** the front door now
  compresses scripts and stylesheets too (MEASURED before: the 652 KB
  script went out as it was), and the page's own code (35 KB) is built apart
  from its libraries, each part named by its content and kept on the PC for
  a year, so an update to the page costs a PC only the page's own file. The
  theme is applied before the first paint (no flash of the other theme).
- **Every image is a fixed box**: a row never moves when its image arrives.
- **Every animation is a transform or an opacity**, so it runs off the main
  thread (tested: the page's animations are read back and checked).
- **The test:** `home.spec.js` opens the page in a browser with nothing
  cached, records the time to the rows and to every image, the filter
  switch, the second visit, every task that held the main thread past 50
  ms, and fails on a loading flash, an uncached second visit, or a long
  task.

Look and motion (Dada, 25 Sep: "modern GUI and effects"). What was read
first, VERIFIED 25 Sep 2026:

- The 2026 direction is *calm interfaces* and *motion that explains, not
  performs*, with reduced-motion support as infrastructure
  ([Envato](https://elements.envato.com/learn/ux-ui-design-trends),
  [Pixelmatters](https://www.pixelmatters.com/insights/7-UI-design-trends-to-watch-in-2026):
  motion as a UI language, depth by layering, glass only where it keeps
  content readable).
- Fluent's timing: 83, 167 and 250 ms, entering on *fast out, slow in*
  (`cubic-bezier(0, 0, 0, 1)`) and leaving on the reverse
  ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/apps/design/motion/timing-and-easing));
  Material 3's rule that enters decelerate and exits accelerate
  ([m3.material.io](https://m3.material.io/styles/motion/easing-and-duration/tokens-specs)).
- Springs in plain CSS with `linear()`
  ([Josh Comeau](https://www.joshwcomeau.com/animation/linear-timing-function/)),
  same-document view transitions with `flushSync` for React and a
  reduced-motion rule
  ([Chrome for Developers](https://developer.chrome.com/docs/web-platform/view-transitions/same-document)),
  scroll-state container queries for a header that casts a shadow once the
  list has scrolled under it, Chromium 133+
  ([Chrome for Developers](https://developer.chrome.com/blog/css-scroll-state-queries)),
  and `@starting-style` / scroll-driven animations as the 2026 baseline
  ([Chrome for Developers](https://developer.chrome.com/docs/css-ui/scroll-driven-animations)).
- Radiology worklists mark STAT and urgent in reds and flag the ageing of
  what waits ([AJR](https://ajronline.org/doi/pdf/10.2214/AJR.22.28949),
  [RAD365](https://www.rad365.com/blogs/best-radiology-workflow-management-systems)).
  PMC's attention colour is Care Orange, so waiting is orange here, and STAT
  will be too when the order carries it.

What moves, and why (each a transform or an opacity; all of it off when the
PC asks for reduced motion, view transitions included):

- **Arriving:** the four-segment bar draws itself in (420 ms), the title,
  the filters and the list rise in turn (250 ms, 50 ms apart), the first
  dozen rows rise one after another (22 ms apart), and a row that later
  scrolls or arrives into view fades in (167 ms). Eight quiet, shimmering
  rows stand in for the first page while it is on its way; an empty list
  says so with a small drawing rather than a blank.
- **Images** shimmer faintly in their black box until they arrive, then fade
  in (250 ms).
- **Selection:** the accent bar on a row's edge springs into place; a hover
  answers in 83 ms; anything pressable settles under the finger (scale
  0.96).
- **The preview pane** slides in from the right (250 ms) and crossfades
  from study to study; the list and the pane sit a little above the page
  (one shadow token, both themes).
- **The header** of the list casts a shadow once rows have scrolled beneath
  it (Chromium 133+; elsewhere it simply stays put).
- **Live** breathes: a ring around the green dot grows and fades every 2.6 s.
- **Light and dark:** the new theme spreads from the button in a circle (a
  view transition; a plain switch elsewhere).
- **Sign-in:** the bar draws, the card rises, the panel's words follow; a
  field glows with the focus; the button settles when pressed.

Choices:

- **No glass.** A translucent header over scrolling rows would need a blur
  on every frame; the trend itself asks for it only where it keeps content
  readable, and PMC's header is solid PMC Blue.
- **No motion on the images themselves** beyond the fade: a radiologist's
  eye should never be drawn by movement that is not the image.
- **The rows carry plain buttons and links**, not React Aria's: four
  interactive components a row across fifty rows was most of the render
  cost (MEASURED: the render of 31 rows fell with them).

## The reading room

M5.4 (25 Sep 2026): one screen for reading through a list. Each point is
MEASURED by `browser/tests/room.spec.js` unless marked.

- **The list and the viewer together.** *Reading room* on the list page (or
  `/pmc/read`, with the same filters in the address) opens a rail of studies
  on the left and the viewer on the right. The rail is the same virtualized
  table as the list, one column, each study a card: its image, the patient
  and hospital number, when, what, and its state.
- **The next study is already loaded.** Two viewers sit on the stage: the
  one in front shows the current study; the one behind, unseen, has already
  opened the study after it. `J` swaps them, so the next study is on screen
  at once, and the viewer that was in front turns to the study after that.
  `K` goes back (that study loads again). The viewer is OHIF in a frame of
  this same origin, so the front door's session and rules apply unchanged,
  and every opening goes into the audit trail as before.
- **The keyboard, end to end.** On the rail: `J`/`K` next and previous,
  `Enter` (or a double-click) into the images, `A` claim, `R` mark read and
  move on, `/` find. In the images, the viewer's own keys apply, and `Esc`
  returns to the rail; `J` and `K` work from there too (OHIF does not use
  them: MEASURED from its hotkeys). The buttons above the images do the same
  by mouse.
- **A phone gets no room:** the button is not offered below 721 px.

Choices:

- **The viewer is framed, not rebuilt.** OHIF stays exactly the stock image
  the standalone window uses; the room is 300 lines of the front door app.
  Its header's PMC mark leaves the room (a top-level link) rather than
  loading the list inside the frame.
- **Two viewers, not more.** One study ahead is what a reader's next
  keystroke needs; each viewer is its own OHIF, so memory doubles (NOT
  VERIFIED on PMC's PCs; see Open).

Decisions for Dada (not built):

- Whether opening a study in the room should claim it for the reader.
- Whether `R` should always move on to the next study (it does), and whether
  the room should skip studies someone else has claimed.

## The viewer's tools

The viewer is OHIF 3.13 as shipped, configured (`viewer/app-config.js`),
never forked, so every release of it is a digest change and a test run. What a
reader has (each MEASURED by `browser/tests/viewer.spec.js` where marked):

- **Window and level**, by dragging, by menu, and by number key for CT:
  1 soft tissue, 2 lung, 3 bone, 4 brain, 5 liver, 6 mediastinum, 7 stroke
  (tested: 2 then 1). MR and X-ray windows are relative to the image, so
  they have no fixed presets.
- **Zoom, pan, magnify, invert, rotate, flip, reset, reference lines,
  crosshairs**, from the toolbar and its More menu.
- **Cine** for cath lab, fluoroscopy and ultrasound runs, on by itself at the
  run's own frame rate (tested: 12–15 frames a second on the cloud host).
- **Layouts:** 1×1, 1×2, 2×2, 3×1, and the volume layouts MPR, 3D four up,
  3D main, axial primary, 3D only and 3D primary (tested: the CT stack in
  three planes).
- **Measurements:** length, bidirectional, angle, Cobb angle, arrow, ellipse,
  rectangle, circle, freehand and spline regions with statistics, probe,
  calibration (tested: a length, listed in millimetres). They live in the
  page and can be exported; saving them into the archive as DICOM SR is a
  decision (below).
- **Priors:** the study browser lists the patient's other studies, newest
  first, so an earlier study is a drag away and the compare layouts can hold
  both (tested: a year-older chest plate offered beside the current one).
- **Capture** a viewport as an image; the **tag browser** for any instance;
  **segmentation** panel for SEG objects; **the patient's name, ID, sex and
  age** stay in the header while reading.
- **Keyboard:** arrows scroll images and viewports, Page Up/Down change
  series, Home/End first and last image, Space resets, Esc cancels, 1–7
  window presets, and OHIF's other defaults, listed in its user preferences.
- **Decoders** run in web workers, one fewer than the PC's cores (2 to 7).

Choices:

- **No first-visit tour.** A ward PC is shared; every new Windows profile
  would have started it again. The reading list's help carries the keys.
- **Measurements are tracked without questions** (OHIF's simplified tracking
  mode): no "start tracking?" prompts between a reader and the image.

Decisions for Dada:

- **Saving measurements and annotations into the archive** as DICOM
  structured reports. Modern reading keeps them with the study; it means the
  first write to the archive by a reader, through the front door, for SR
  objects only. Not built until decided.
- **OHIF's investigational-use notice**, once a session, stays until the
  regulatory answer the record asks for (§10 of the redesign) is in.

## Branding

The platform wears PMC's 2026 identity as the portal proposal applied it to
the old archive. The source is the record: `docs/pmc-imaging-portal-built-20260906.md`
("taken from `rebranding_1.pdf`, not from memory") and
`deliverables/PMC_Imaging_GUI_Presentation_20260906` (the design-system
slide), both MEASURED on 24 Sep 2026. The old portal (`apps/imaging-portal`)
carries the same, and its logo files are the ones in `brand/`.

| | Value | Where it is used here |
|---|---|---|
| PMC Blue | `#0B3F8A`; `#062449` in the reading room, as the portal's rail | the app's header, the sign-in panel, the one button, the email's header |
| Renewal Green | `#69B52C` | healthy states: *Live*, the rule-and-dot, *Recovered* |
| Care Orange | `#F06423` (text `#B4450F`) | attention only: Caps Lock, a wrong password, an alert. Never alarm red |
| Clinical Black / Support Grey | `#101820` / `#E7E9ED` | text / surfaces |
| Type | Aptos Display, Aptos | already on every PMC computer, so nothing is downloaded |
| The bar | blue 40, orange 22, green 22, black 16 (%) | the top edge of every page and email: the letterhead's device |
| The logo | the white lock-up on blue; the loop alone on a phone | `brand/`, served by the front door at `/brand/` |
| The tagline | *Better Care. For Every Life.* | the sign-in page, the signed-out page, the email |

What wears it:

- **The sign-in page** is Keycloak's own v2 page with PMC's theme
  (`identity/theme/pmc`): a stylesheet, one script, the footer and a few
  words. The brand panel is the realm's `displayNameHtml`. The form, its fields
  and what it does stay Keycloak's, so an upgrade keeps working and so do the
  tests. Like Voyager's sign-in, it says when Caps Lock is on: a Windows
  password is case-sensitive, and five wrong tries make it wait.
- **The app's header, the viewer's header** (OHIF's `whiteLabeling`, which
  also links back to the reading list), **the signed-out page and each tab's
  icon.**
- **The alert email** (`monitor/templates/pmc.tmpl`), in HTML and plain text.
  Its subject stays Alertmanager's own (`[FIRING:1] FeedSilent ...`), so ICT's
  mail rules keep matching. It has no images, because mail programs block
  them. Times are Manila time.
- **`brand/` is the one source** of the logo files. The front door serves them
  at `/brand/` without a session: the sign-in page shows them before anyone has
  signed in, and they are on the hospital's signage. Keycloak serves a tab
  icon only from its theme, so the theme holds one copy of the mark, and
  `ci/run.sh` checks it matches.

Choices:

- ***For Every Life.* is pale blue, not Renewal Green** as in the portal's
  rail: green on PMC Blue is 3.9:1, under WCAG AA for text this size
  (INFERRED from the two colours; axe checks the pages that carry it).
- **Errors are Care Orange, not red.** The proposal keeps orange for
  attention; a sign-in error or a failed backup is exactly that.

Open:

- **The Teams message** is Alertmanager's own card, not PMC-styled.
- **A realm change after the first start** (the brand panel and the theme are
  realm settings) reaches a running Keycloak only through M4's tool, as for any
  realm change (see [Open](#open)).

## Pinned

| Component | Version | Pinned by | Evidence |
|---|---|---|---|
| Engine: `orthancteam/orthanc:26.9.1` | Orthanc 1.13.0; DICOMweb 1.24; PostgreSQL index 11.0 (schema revision 11); Worklists 0.9.2; Housekeeper 1.13.0; GDCM plugin 1.8 (GDCM 3.0.24); DCMTK 3.7.0 | image digest | MEASURED from the running engine's `/system` and `/plugins`, 23 Sep 2026 |
| Index: `postgres:18.6-trixie` | 18.6. Data checksums on; built-in `C.UTF-8` collation, which no glibc update can reorder | image digest | MEASURED by `ci/run.sh` on every run |
| Viewer: `ohif/app:v3.13.10` | OHIF 3.13.10, served only through the front door | image digest | MEASURED: the option names in `viewer/app-config.js` were read from this image's bundle |
| Front door: `nginx:1.30.5` (trixie) | nginx 1.30.5, TLS 1.3, HTTP/2 | image digest | MEASURED by the browser tests |
| Sign-in: `quay.io/keycloak/keycloak:26.7.4` | Keycloak 26.7.4, on its own PostgreSQL 18.6 cluster (`pg-platform`), reading AD over LDAPS | image digest | MEASURED: it starts, imports the realm and signs the test people in against the stand-in AD |
| Session: `quay.io/oauth2-proxy/oauth2-proxy:v7.15.4` | oauth2-proxy 7.15.4, sessions in `valkey/valkey:9.2-trixie` (Valkey 9.2.0) | image digests | MEASURED by the browser tests |
| Permissions: `orthancteam/orthanc-auth-service:26.8.1` | orthanc-auth-service 26.8.1, with the engine's authorization plugin 0.12.0 | image digest | MEASURED: `/plugins`, and the access tests |
| Front door app: `pmc-imaging/app`, built here from `app/` | Node 24.21.0 LTS (`node:24.21.0-trixie-slim`). The page: React 19.3.0, TanStack Router 1.170.39 and Query 5.103.2, React Aria Components 1.21.1, Tailwind CSS 4.3.3, lucide-react 1.47.0; built by Vite 8.3.0 and type-checked by TypeScript 7.0.2. The server: Hono 4.13.8 with @hono/node-server 2.1.1, and zod 4.6.5 on both sides | base image digest, and an integrity hash for every package | MEASURED: built and run by `ci/run.sh`. Versions VERIFIED on registry.npmjs.org, 23 Sep 2026. The base digest was read from the mirror (Docker Hub answered 429 that day) |
| Schema migrations: `ghcr.io/amacneil/dbmate:2.36.0` | dbmate 2.36.0, with pg_dump 18.6 inside | image digest | MEASURED: the digest pulled matched the one the research recorded; `--version` and `pg_dump --version` read from the image |
| Database backups: pgBackRest, in `pmc-imaging/postgres`, built here from `backup/postgres/` on `postgres:18.6-trixie` | pgBackRest 2.59.1 (`2.59.1-1.pgdg13+1`, from the PostgreSQL project's Debian repository) | base image digest, and the exact package version | MEASURED: `pgbackrest version` at build, and the backups and the drill on every run |
| Nightly copy and off-site: `kopia/kopia:0.23.1` | Kopia 0.23.1. Repository format 3, AES256-GCM-HMAC-SHA256, BLAKE2B-256-128 | image digest | MEASURED: `kopia --version` and `kopia repository status`, 24 Sep 2026 |
| Off-site stand-in, tests only: `mcr.microsoft.com/azure-storage/azurite:3.37.0` | Azurite 3.37.0, blob service only, over TLS | image digest | MEASURED: `azurite-blob --version`, 24 Sep 2026 |
| Stand-in Active Directory, tests only: `pmc-imaging/ad-standin`, built here from `identity/test/ad/` on `debian:trixie-slim` | Samba 4.22.11 (`2:4.22.11+dfsg-0+deb13u1`) as an AD domain controller | base image digest, and the exact package version | MEASURED: `samba --version`, 24 Sep 2026 |
| BizBox connector: `pmc-imaging/orders`, built here from `orders/` | Python 3.14.7 (`python:3.14-slim-trixie`), mssql-python 1.15.0 (with Microsoft's ODBC driver 18.6.2.1 inside), psycopg 3.3.6, requests 2.34.2 | base image digest, a hash for every package, exact system library versions | MEASURED: built and run by `ci/run.sh`. Both drivers publish Python 3.14 wheels (VERIFIED on pypi.org, 24 Sep 2026). mssql-python's licence is not in its package metadata: NOT VERIFIED |
| BizBox stand-in, tests only: `mcr.microsoft.com/mssql/server:2022-latest` | SQL Server 2022 CU27 (16.0.4295.3), Developer edition | image digest | MEASURED by the research proof, which used the same digest |
| Feed watch: `pmc-imaging/watch`, built here from `watch/` | Node 24.21.0 (`node:24.21.0-trixie-slim`), no packages | base image digest | MEASURED: built and run by `ci/run.sh` |
| Alerts: `quay.io/prometheus/prometheus:v3.14.0` and `quay.io/prometheus/alertmanager:v0.34.1` | Prometheus 3.14.0, Alertmanager 0.34.1 | image digests | MEASURED: `--version` from each image. Both are the latest releases (VERIFIED on GitHub, 24 Sep 2026) |
| Mail relay stand-in, tests only: `ghcr.io/axllent/mailpit:v1.31.2` | Mailpit 1.31.2 | image digest | VERIFIED as the latest release on GitHub, 24 Sep 2026 |
| Test runner: `python:3.14-slim-trixie` | Python 3.14.7, pydicom 3.0.2, pynetdicom 3.0.4, pylibjpeg-libjpeg 2.4.0, pytest 9.1.1, ldap3 2.9.1 | image digest, and a hash for every package | MEASURED. ldap3 2.9.1 is its latest release (VERIFIED on pypi.org, 24 Sep 2026) |
| Browser runner: `mcr.microsoft.com/playwright:v1.63.0-noble` | Playwright 1.63.0, Chromium | image digest, and an integrity hash for every package | MEASURED |

The digests are in `compose.yaml`, `compose.r740xd.yaml`, `compose.test.yaml`
and the Dockerfiles (`app/`, `backup/postgres/`, `identity/test/ad/`,
`tests/`, `browser/`). Each
was pulled on 23 or 24 Sep 2026 (MEASURED). The official images (`postgres`,
`nginx`) gave the same digest from Docker Hub and from its public mirror, so
`PMC_LIBRARY` can point at a mirror without changing what runs.

## What the tests prove

`ci/run.sh` runs 119 tests. All passed on 25 Sep 2026 (MEASURED, cloud build,
16 minutes). It starts from empty volumes, checks the platform database's
schema and grants and that the logo files have one source, and runs 61
engine, API, sign-in, watch, orders and brand tests and 41 browser tests. It then removes the containers, starts new ones
from the same volumes, and runs 6 engine tests and 2 browser tests again: the
radiologist signs in afresh, and a cathlab run still opens playing. Then it
takes the nightly backup, proves the primary cannot delete from the R740xd's
copy, checks the watch saw it, copies it off-site, deletes every volume of
both hosts, rebuilds the platform from the off-site copy alone, and runs the
same 6 and 2 once more.

The test overlay shortens three clocks so the tests can wait them out: a
study is stable after 5 s (60 s on site), worklist housekeeping runs every
5 s, and a person's token lives 60 s and is renewed at 40 s (5 min and 4 min
on site).

| Property | Test |
|---|---|
| The engine is the configured one: versions, PostgreSQL index, no SQLite index file, exact plugin set, JPEG-LS ingest, never overwrite, never recycle. It logs in to its index as a role that owns its database and is no superuser | `test_engine.py`, `ci/run.sh` |
| Nothing on the engine network can reach the internet | `ci/run.sh` |
| A modality is admitted only if its AE title is registered, it calls this engine's AE title, and it connects from its registered address. A store-only modality cannot search | `test_engine.py` |
| The engine's REST API refuses a caller with no credentials or a wrong API key. A route the permission table does not name is refused even to the platform's own service account | `test_engine.py` |
| Every uncompressed arrival (XA cine, signed 16-bit CT, MR, CR, DR, RGB ultrasound) is stored as JPEG-LS and decodes identical to what was sent, every pixel of every frame | `test_ingest.py` |
| An arrival that is already lossy (JPEG ultrasound) is kept byte for byte, not re-encoded | `test_ingest.py` |
| A resend is accepted and leaves one copy. Six modalities sending at once all succeed | `test_ingest.py` |
| Server-side sorting (`OrderBy`) works, which the legacy ODBC index answers with HTTP 500 | `test_dicomweb.py` |
| QIDO-RS finds by modality and patient. WADO-RS returns cine frames as stored (JPEG-LS) or uncompressed, both pixel-exact. Series metadata is cached once the series is stable | `test_dicomweb.py` |
| An order reaches only its own modality's worklist and leaves it once the study has arrived and is stable. A cancelled order is withdrawn | `test_worklists.py` |
| After the restart, every study, every file (MD5), every registered modality, a pending order and the audit trail are still there, and the engine still takes studies | `test_after_restart.py` |
| Both clusters archive every log segment as it is written. The nightly backup takes both clusters and checks them, then snapshots them and the engine's files to the R740xd's Kopia server, which copies its repository off-site. The primary cannot delete a snapshot, even its own | `ci/run.sh`, `tools/backup.sh`, `tools/offsite.sh` |
| A BizBox login may read its view and nothing else. An order reaches every console of its section and no other, with its own StudyInstanceUID; a Filipino name arrives intact; a change in BizBox updates the waiting entry; a cancellation withdraws it; the exam takes it off the worklist and marks it performed; an order whose transaction commits late is neither lost nor holding anything up; 100 orders at once all arrive | `tests/test_orders.py` |
| The watch sees the engine, the domain controller, the images' free space and the certificates. Every registered modality has a feed and a limit. A modality that goes quiet past its limit reaches ICT's inbox as a `FeedSilent` email. After the nightly backup the watch shows both clusters' backups and the snapshot | `tests/test_watch.py` |
| Disaster: with both hosts' volumes deleted, the platform is rebuilt from the off-site copy alone. Every file is verified, both clusters are restored and their logs replayed, and archiving works again. Then every study, every file (MD5), every modality, a pending order and the audit trail are back, the radiologist signs in, and a cathlab run opens playing | `ci/restore-drill.sh`, then `test_after_restart.py` and `browser/tests/viewer.spec.js` |
| The front door answers only for the site name, over TLS 1.3 and HTTP/2, and sends plain HTTP to HTTPS | `browser/tests/viewer.spec.js` |
| A cathlab run opens already playing, and opened again it costs no download of the viewer (its content-hashed files come from the PC's cache) while no image ever does. A CT series opens and every slice arrives. An ultrasound run that arrived as JPEG plays as sent. No console errors. The time to the first image is recorded, cold and warm | `browser/tests/viewer.spec.js`, `browser/measure/open-study.mjs` |
| Every request the viewer makes goes to the front door and nowhere else, and every DICOMweb answer says `no-store` | `browser/tests/viewer.spec.js` |
| From where people sit, the engine cannot be reached by name. Its REST API is not routed. DICOMweb refuses writes | `browser/tests/viewer.spec.js` |
| A link opened without a session goes straight to PMC's sign-in page, with no image request first, and comes back to the same page after the Windows logon. The session cookie is HttpOnly, Secure and SameSite=Lax | `browser/tests/access.spec.js` |
| Someone in AD but in no PMC group gets no session and no images | `browser/tests/access.spec.js` |
| A role can come through a nested AD group. A disabled AD account cannot sign in. Five wrong passwords stop Keycloak asking AD, so AD's own lockout is never reached and the Windows account still works. Someone taken out of their AD group loses access at their token's next renewal | `tests/test_directory.py` |
| The engine is handed the person's own short-lived token. A session outlives its first token, and the engine refuses the expired one | `tests/test_session.py` |
| The site's address opens the front door app, whose pages run only their own scripts. Its API needs a session, believes only tokens Keycloak signed, and answers the engine's own view of each person: newest first, sorted by the index, filtered and searched; a referrer's list holds only shared studies. A new study reaches an open page within seconds | `tests/test_app.py` |
| A radiologist claims a study and a cardiologist sees who has it; nobody else can take or release it; "claimed by me" is exactly one's own. Only readers claim, only studies the engine shows them, and only from this site's pages (Origin). ICT reads who opened, claimed and released a study | `tests/test_app.py` |
| The platform database is exactly `db/schema.sql`, and the app's role cannot change or delete the audit record | `ci/run.sh` |
| The worklist lists every study, live; Enter opens the selected study in the viewer's own window, playing, and the next study reuses that window. Filters live in the address. The keyboard finds and moves. A referrer sees only shared studies. It passes WCAG 2.2 AA (axe-core) in light and dark. `A` claims a study, and a colleague's open worklist shows it within seconds | `browser/tests/home.spec.js` |
| A referrer opens a study shared with referrers. A search finds only shared studies, and an unshared study is refused even by its UID | `browser/tests/access.spec.js` |
| A cardiologist opens a cathlab run and it plays | `browser/tests/access.spec.js` |
| Without a session, DICOMweb answers 401: never data, never a sign-in page. Keycloak's admin console and master realm are not reachable. Signing out ends the session | `browser/tests/access.spec.js` |
| The viewer's tools on the stored images: window presets by key, the CT in three planes (MPR), a length measured and listed in millimetres, the patient's earlier study offered in the study browser | `browser/tests/viewer.spec.js` |
| The reading list is counted for readers and never for referrers; a reader marks a study read, which drops the claim, leaves the unread list and can be unmarked only by them; a study someone else holds cannot be marked read; only readers mark; the trail shows claim, read and unread. A study's preview lists its series and the patient's earlier studies; its first image comes through the front door as a JPEG, never cached, and a browser's own image request gets one too; a referrer gets neither for a study not shared | `tests/test_app.py` |
| A row carries its first image; selecting it previews the series and the earlier study, and `Esc` closes the preview; *Compare* opens the earlier study beside the current one and both draw; `R` marks a study read, *Unread* hides it, and the reader can unmark it; compact rows drop the images and are remembered; the list does not lag (compressed parts, cached second visit, no flash on a filter, no long task); the page moves with purpose (transforms and opacities only), the theme switches, and nothing moves with reduced motion; the accessibility check covers the open preview | `browser/tests/home.spec.js` |
| The reading room shows the study beside the list with the next one already loading behind; `J` shows the next study within a second and `K` goes back; `Enter` takes the keyboard to the images and `Esc` (pressed in the viewer) brings it back to the rail; `R` marks the study read and moves on; the room passes WCAG 2.2 AA in light and dark (the viewer's own page excluded) | `browser/tests/room.spec.js` |
| PMC's identity: the logo files need no session, are only read, and nothing else under `/brand/` is served. The sign-in page carries PMC's theme, the lock-up and tagline on PMC Blue and PMC's words, keeps Keycloak's own form, says when Caps Lock is on, and passes axe's contrast check in light and dark. The app's header, the viewer's header and the signed-out page show the lock-up or mark. The alert email is PMC's, in HTML and plain text | `tests/test_brand.py`, `browser/tests/access.spec.js`, `home.spec.js`, `viewer.spec.js`, `tests/test_watch.py` |

All test data is synthetic (`tests/synth.py`). Pixels are drawn from formulas,
patients are invented, and each file carries `PatientIdentityRemoved=YES`.
The AE titles the tests play are PMC's own, as MEASURED in the record.

## Measured on synthetic data (cloud build host, 4 CPU)

- **JPEG-LS saving:** synthetic images were stored at 38–61% of their raw pixel
  size. That figure says nothing about PMC's images. The record MEASURED 30–37%
  smaller on PMC's own files.
- **A 59-frame cathlab run (512×512)**, straight from the engine, in two runs:
  - whole instance, one request: 52–54 ms;
  - all frames, one request: 42–47 ms;
  - frame by frame, 59 requests: 881–1,030 ms in total.

  INFERRED: a viewer should fetch a cine run in one request, or in a few large
  batches, and never frame by frame. The fix for the live portal's cine
  complaint starts from this.
- **Opening a study in the viewer** (`browser/measure/open-study.mjs`:
  headless Chromium, software rendering, same host, no test tracing; 24 Sep,
  after the viewer's files became cacheable):
  - the 59-frame cathlab run: first image **3.8–3.9 s on the PC's first
    visit** (two runs), of which about 2.5 s is the viewer's own 5.0 MB of
    scripts, then **0.8–1.0 s** once the PC has them, playing at 12–15
    frames a second;
  - the 40-slice CT: 1.8–1.9 s, then 1.1–1.2 s;
  - the engine and the front door are not the limit: the 59 frames came
    through the front door, session check and permission check included, in
    172 ms with 16 in flight (2.9 ms a frame), one at a time in 344 ms, and
    the whole run as one instance in 47 ms. What remains is the browser's
    own: fetching, decoding and drawing.
  - **JPEG-LS to the browser beats uncompressed.** Asked for uncompressed
    frames, the viewer took 2–4 times longer on the run (frames 2.1–3.5 s
    against 1.1–1.3 s) and the first cold cine ran at 8 frames a second: the
    extra bytes cost more than the decode saves, even on one host. The
    configuration asks for the images as stored.

  Earlier figures in this section (6–11 s) were the tests waiting up to 25 s
  for OHIF dialogs that were not there; they are withdrawn. All of these
  include OHIF's own start-up on a CPU-rendered canvas, so a ward PC with a
  GPU should do better: NOT VERIFIED until measured on PMC hardware.
- **A new share reached a referrer after 60–64 s**, in three runs: the
  engine's authorization plugin caches what it knows about a study.
- **An expired token was refused 63 s after it expired**, in two runs (the
  same cache; see Sign-in).
- **A new study reached an open worklist 1.6–1.7 s** after the modality began
  sending it, in two runs.
- **The reading list** (`home.spec.js`, a browser with nothing cached,
  software rendering, 25 Sep 2026): rows on screen 603 ms after
  the link on a first visit, every row's image by 708 ms, a filter switch in
  265 ms (the rows on screen never left), a second visit to rows in 453 ms
  with none of the page's files downloaded again; no task held the main
  thread past 84 ms (79, 84 and 59 ms on the first visit: the scripts'
  evaluation, the first rows, the filtered rows; 71 ms on the second), and
  nothing moved the layout. One run; the assertion allows one task over
  100 ms and none over 300 ms, seen once at 106 ms in a dev-loop run.
- **The reading room** (`room.spec.js`, software rendering, 25 Sep 2026):
  `J` put the next study's image on screen 17 ms after the key (the
  viewers swapped in 17 ms; that study had been opened behind the
  current one), timed inside the page. `K` went back in 5,289 ms: the cost
  of opening a study that is no longer held, on this host's software
  rendering. Timed from the test runner instead, the same `J` reads about
  3 s: each of the runner's own actions snapshots the page for its trace,
  and two viewer documents make that cost more than what is being timed
  (MEASURED both ways), so the room's numbers are taken inside the page.
- **The reading list's API** (`test_app.py`): a study's preview (three
  questions to the engine) answered in 18 ms; a first image
  rendered by the engine and passed through the front door in
  55 ms (2.7 KB).
- **The worklist page** is 7 files, 258 KB on the wire
  (722 KB uncompressed): the page's own 35 KB script apart from its
  libraries, and a 27 KB stylesheet; Vite 8.3 builds it in about 1.1 s.
  Before M5.3 it was one 646 KB script, sent uncompressed (MEASURED: the
  front door compressed JSON only).
- **The nightly backup** of both clusters in full, then the snapshot to the
  R740xd, took 9.3 s (one run). pgBackRest's zstd kept the index's 33.4 MB as
  3.9 MB, and the platform database's 51.7 MB as 5.9 MB. These are small
  synthetic databases; real ones will compress less. The images are not
  compressed again: they are already JPEG-LS.
- **The off-site copy** of the whole 60 MB repository took 1.4 s (one run, to
  the stand-in on the same host).
- **The disaster drill**, in five runs: verifying every file of the off-site
  copy and restoring the engine's files and the database backups took
  9.8–10.1 s; restoring both clusters from those backups, 3.8–4.3 s; starting
  the platform on them, 49–50 s.
- **Someone taken out of their AD group lost access 40–42 s later** (three
  runs; the tests renew a token at 40 s, the site at 4 minutes).
- **A BizBox order reached both X-ray consoles 1.2–2.3 s after BizBox committed
  it**, and 100 at once reached both within 3.8–3.9 s (two runs, polling every
  2 s; every 30 s on site).

## Run it

```sh
tools/make-secrets.sh        # once: generates secrets/ (git-ignored); never overwrites.
                             # ICT adds secrets/ad-bind-password, the site's
                             # certificate and the AD's CA in secrets/tls/, and
                             # the PMC_AD_* values in .env beside compose.yaml
                             # (git-ignored)
docker compose up -d --wait  # the platform, as project pmc-imaging
tools/backup.sh              # the nightly backup: both databases, then the
                             # snapshot to the R740xd (M4 runs it on a timer)
tools/offsite.sh             # on the R740xd: its copy, off-site; does nothing
                             # until the storage key is placed
ci/run.sh                    # the tests, as project pmc-imaging-test, then removes it
KEEP=1 ci/run.sh             # the same, but leaves the test stack running
```

`ci/run.sh` runs as its own compose project, with its own volumes, its own
throwaway secrets (`.test-secrets/`) and a test hostname (`imaging.pmcne.test`,
from the reserved `.test` domain). So it can never touch a real platform's data,
secrets or certificate. The same script runs in GitHub Actions
(`.github/workflows/imaging-platform.yml`). Where Docker Hub rate-limits
anonymous pulls, run it with `PMC_LIBRARY=public.ecr.aws/docker/library`.

## Where things live

- `orthanc/orthanc.json`: the engine's configuration. Each block says why.
- `compose.yaml`: images by digest, the network, volumes and secrets.
- `compose.test.yaml`: the test overlay. Stable age and worklist housekeeping
  drop to 5 s, the edge network is sealed, and it adds the two test runners.
- `front/`: the front door. `nginx.conf` logs paths only, never query strings,
  because a DICOMweb query can carry a patient ID or name.
  `templates/front.conf.template` holds the routes, TLS and security headers.
- `viewer/`: OHIF's configuration (`app-config.js`) and the server block that
  serves its files inside its own container.
- `identity/`: sign-in. `realm-pmc.json` is the Keycloak realm: the roles,
  the two clients, the connection to PMC's AD and the group behind each role,
  with every site value and secret as a placeholder Keycloak fills in at
  import. `keycloak-start.sh` refuses to start without them.
  `pg-platform-init.sh` makes Keycloak's database. `auth-service/` holds what
  each role may do (`permissions.json`) and how the auth service starts.
  `test/ad/` is the stand-in AD, for tests only. `theme/pmc/` is PMC's
  sign-in page (see [Branding](#branding)).
- `app/`: the front door app. `src/web/` is the page (the worklist),
  `src/server/` its server, `src/shared/api.ts` the schemas both sides check.
  `Dockerfile` type-checks, builds and packs it.
- `browser/`: the browser tests (Playwright), and `measure/open-study.mjs`,
  which times a study's open phase by phase. `tests/people.js` is who signs
  in, `tests/access.spec.js` what each person may see, `tests/home.spec.js`
  the worklist.
- `db/`: PMC's platform database. `migrations/` is its schema as plain SQL,
  one file per change, applied in order; `schema.sql` is the result, which
  CI checks against the live database.
- `tests/frontdoor.py`: signing in at the front door from Python, as a
  person would, for the tests that look behind it (`test_session.py`,
  `test_app.py`).
- `backup/`: backups. `postgres/Dockerfile` adds pgBackRest to the official
  PostgreSQL image, which both clusters run; `pg-start.sh` writes its
  configuration at each start, `initdb-stanza.sh` creates a new cluster's
  stanza, and `pg-restore.sh` restores a cluster from its repository.
  `kopia/` holds the Kopia server's start (`server.sh`: the repository, the
  primary's add-only user, retention), the nightly snapshot
  (`snapshot.sh`), the copy off-site (`sync-offsite.sh`) and the restore from
  off-site (`restore.sh`).
- `compose.r740xd.yaml`: the R740xd's part, the Kopia server. On site it runs
  on the R740xd; in the tests, beside the primary.
- `tools/backup.sh` and `tools/offsite.sh`: the nightly backup, and the copy
  off-site. `ci/restore-drill.sh`: the disaster drill, for the test project
  only.
- `orders/`: the BizBox connector (`pmcorders/`), and the stand-in BizBox for
  the tests (`test/bizbox/`: a synthetic schema, the read-only login).
- `watch/`: the feed watch. `monitor/`: Prometheus's configuration, the alert
  rules, Alertmanager's start, which writes its configuration from the
  site's values, and PMC's alert email (`templates/pmc.tmpl`).
- `brand/`: PMC's logo files, the one source: the white lock-up, the white
  loop and the coloured loop, from the old portal (see [Branding](#branding)).
- `secrets/`: generated by `tools/make-secrets.sh`, git-ignored, never
  overwritten. It holds the passwords of both PostgreSQL clusters and of
  Keycloak's database, the front door's client and cookie secrets, the auth
  service's password and signing key, admin-cli's secret, the platform's API
  key, the Kopia repository's password and its three users' passwords, the
  off-site storage key (empty on site until ICT places it), the BizBox
  connector's platform database password and its BizBox login's password
  (empty until ICT places it), and the TLS certificate. `ad-bind-password` and `tls/ad-ca.crt` come from ICT. The
  containers read them all as Docker secrets; none is in any file in git.
- **Modality addresses** live in the engine's database, registered at runtime
  (`PUT /modalities/{name}`), never in git (CLAUDE.md). The tests register
  their own container's address. A registration tool that reads the private
  inventory comes with M3.
- **Site values** are compose variables with safe defaults, none of them
  secret:
  - `PMC_HOSTNAME`: the front door's name (default `imaging.pmcne.ph`);
  - `PMC_DICOM_AET`: the engine's AE title (default `PMC-IMAGING`);
  - `PMC_SECRETS`: where the secrets are (default `./secrets`);
  - `PMC_LIBRARY`: where the official images come from (default Docker Hub);
  - `PMC_AD_*`: PMC's Active Directory: the domain controllers, where the
    people and the five groups are, the read-only account, and the group
    behind each role. These have no default (see [Sign-in](#sign-in)); they
    go in the site's env file;
  - `PMC_KOPIA_SERVER_URL` and `PMC_KOPIA_SERVER_FINGERPRINT`: the R740xd's
    Kopia server, by name, and the SHA-256 fingerprint of its certificate,
    which the primary pins. The nightly snapshot refuses to run without them;
  - `PMC_BACKUP_AZURE_ACCOUNT` and `PMC_BACKUP_AZURE_KOPIA_CONTAINER`: the
    off-site storage account and container, set on the R740xd once the cloud
    copy is decided;
  - `PMC_BIZBOX_SERVER`, `_DATABASE`, `_USER`, `_VIEW` and
    `PMC_ORDERS_STATIONS`: BizBox's SQL Server, the connector's login and
    view, and which consoles take each section's orders. No server, no
    connector;
  - `PMC_FEED_SILENCE` and `PMC_FEED_SILENCE_OVERRIDES`: how long a modality
    may stay silent (default 24h), and the exceptions;
  - `PMC_ALERT_EMAIL_TO`, `_FROM`, `PMC_ALERT_SMTP`, `PMC_ALERT_SMTP_TLS`:
    where alerts are emailed, and through which relay.
- **The TLS certificate** is the site's own; for PMC, the existing `*.pmcne.ph`
  wildcard. It goes in `secrets/tls/` as `tls.crt` and `tls.key`.
  `tools/make-test-tls.sh` makes a throwaway one for tests and never replaces
  an existing certificate.

## Choices made here

These are INFERRED, not decided by anyone but this build. Argue with them.

- **An AE title alone is not an identity.** `DicomCheckModalityHost` is on, so
  a modality must connect from its registered address. On-prem this needs Docker
  to pass through each modality's real source address. Docker's default port
  publishing does that (INFERRED), but it is NOT VERIFIED on the R740xd; M4
  checks it.
- **C-ECHO is open to anyone**, so a technologist can test a link without ICT.
- **A resend never replaces what is stored** (`OverwriteInstances: Never`, the
  default).
- **The extra index tags are fixed now**, before the first study. Changing them
  later makes the Housekeeper re-read every file: 6.3 TB after the migration.
- **PostgreSQL `Lock` is off.** A lock held by a killed container's dead session
  can block the very restart that would recover it. Compose runs one engine.
- **Explorer 2 is off.** ICT's admin screens come with the front door app
  (M2.3). Nothing of the engine's REST API is routed from the front door.
- **No local accounts.** Everyone signs in with their AD account. The `pmc`
  realm holds no passwords for people, only the platform's two service
  accounts, so a leaver is handled where ICT already handles leavers: in
  AD.
- **The engine decides, not the front door.** The front door checks only that
  a session exists. What a person may see is decided by the engine on every
  request, so any later client (the front door app, a report tool) gets the
  same rules.
- **Default deny.** The engine's permission table lists every route anyone may
  use, and refuses the rest (MEASURED: its script endpoint is refused even to
  the platform's own service account).
- **Nothing reaches the internet.** Keycloak reaches only the domain
  controllers. Its admin console and the master realm are never routed.
- **Keycloak reads AD, never writes to it**, and keeps no copy of anyone's
  groups: it asks AD at every sign-in and every renewal.
- **Sessions are kept in memory only.** A restart of the session store signs
  everyone out, and they sign in again (INFERRED).
- **A worklist entry nobody performs is removed after 72 h.** A performed one
  goes as soon as its study is stable.
- **The Housekeeper runs on weekday nights and weekends**, Manila time.
- **The viewer's files are kept on the PC for a year, the images never.**
  OHIF names every script, stylesheet, decoder and font by its content hash,
  so those are served `immutable`; the page and its configuration are
  `no-cache` with an ETag, so a new viewer image reaches every PC at its next
  open. Without this, every open of a study fetched 5.2 MB of viewer again
  (MEASURED, 24 Sep). Images stay `no-store` at the front door.
- **The test browser trusts the test CA** (`browser/tests/trust-ca.js`, in
  Chromium's own store), instead of ignoring certificate errors: Chromium
  caches nothing from an origin whose certificate it rejects (MEASURED), so
  the old setting hid the viewer's caching, and it let the tests skip the
  check a ward PC makes. The test runner's own requests trust it through
  `NODE_EXTRA_CA_CERTS`.
- **The tests never wait for a dialog that is not there.** OHIF's
  investigational-use notice and first-visit tour are met once, at the
  sign-in that every viewer test reuses; a helper clears them wherever they
  can still appear and returns as soon as an image is on screen. The fixed
  waits it replaces (5 s and 20–30 s) were most of every earlier open time.
- **Cathlab runs open playing.** OHIF 3.13 turns the cine player on by itself
  only for `OT` and `US` (MEASURED from its bundle). `viewer/app-config.js`
  adds `XA` and `RF` and sets `autoPlayCine`, so a coronary run plays the
  moment it opens, which answers Dada's 1 Sep search for playback.
- **The browser may talk to the front door and nothing else**
  (`connect-src 'self'`). The policy also allows `'unsafe-eval'`, because the
  viewer's image decoders fail without it (MEASURED: every frame failed to
  decode).
- **Images stay off disks on the way through.** DICOMweb answers carry
  `Cache-Control: no-store`, and the front door is barred from spilling a
  response to a temp file.
- **OHIF is the viewer only.** Its study list is off; the worklist is the
  front door app, and OHIF's home link lands on `/`, which the front door
  sends to `/pmc/`.
- **The front door app runs no script but its own.** Its pages get a
  stricter content security policy than the viewer's: no `'unsafe-eval'`, no
  inline scripts, no framing. Inline style attributes are allowed, because
  the table component positions things with them.
- **The front door app's server is TypeScript run as it is.** Node 24 strips
  the types at start, so there is no server build step and nothing compiled
  to drift from its source. The page is built once, in the image, and served
  as hashed files.
- **No second viewer.** The worklist shows no image previews yet; opening a
  study is one keystroke away, in the one viewer.
- **Claims live in PMC's platform database, not in the engine.** The
  front-door research suggested the engine's metadata. The platform database
  gives one transaction for a claim and its audit entry, an audit trail the
  app cannot rewrite, and nothing to redo if the engine is ever swapped.
- **A change must come from this site's own pages.** The app refuses a POST
  or DELETE whose Origin is not the site's; with the SameSite session
  cookie, another site's page cannot act in a signed-in person's name.
- **OHIF's "investigational use" notice** is left at OHIF's default: once per
  browser session. Whether PMC keeps it is a governance decision for Dada.
- **The engine owns its database and nothing more.** The official image makes
  its `POSTGRES_USER` a superuser, and until 24 Sep the engine logged in as
  that user (MEASURED). A superuser can run programs inside the database's
  container, where the index's own backups also live. Now the superuser is
  `pmc`, for backups and ICT, and the engine's `orthanc` role only owns the
  `orthanc` database (`orthanc/pg-index-init.sh`). `ci/run.sh` checks both on
  every run.
- **A database is backed up by pgBackRest, never by copying its files.** A
  copy of a running cluster's files is not a database. pgBackRest takes a
  consistent backup and every log segment needed to replay it, and keeps
  archiving between backups, so a restore can stop at any moment.
- **Kopia takes the copy off the host**, for three things it does that a plain
  copy does not: a server whose users can be allowed to add snapshots but not
  delete them; encryption before anything leaves; and `sync-to`, which copies
  the whole repository to Azure without the primary ever holding the key.
- **The watch reads the record, not a report.** It reads pgBackRest's own
  record of each backup, and the engine's own change feed, so a job that never
  ran cannot claim it did. Only the snapshot to the R740xd is noted by the
  job itself, when it succeeds.
- **Alerts leave by one door.** Only Alertmanager reaches outside the
  platform, and only to the mail relay and Teams. Prometheus and the watch
  sit on a network with no route out.
- **The drill restores from off-site only.** The R740xd's copy would be
  quicker, but the case worth proving is the one where both buildings are
  gone.

## Open

- **The AE title the modalities call today** is NOT VERIFIED here. Migration
  either sets `PMC_DICOM_AET` to it or re-points every modality.
- **The DICOMweb plugin in this image logs a warning** (MEASURED): "compiled
  against Orthanc SDK <= 1.5.6. STOW and WADO chunked transfers will be entirely
  stored in RAM". That matters for large STOW uploads, which is how migration
  may load studies. M4 measures memory under a large STOW before relying on it.
- **Orthanc's performance options are at their defaults**, which it logs at
  start. Tune them after measuring at PMC's volume (about 82 studies a day; CT
  up to about 1,700 images a study), not before.
- **Concurrency:** `DicomThreadsCount` is 4 (the default). Six simultaneous
  senders passed; larger bursts are not measured.
- **DICOM from the modalities on-prem:** the engine sits on a network with no
  route out, which also means port 4242 cannot be published from it. M4 gives
  the engine a second, DICOM-only network for the modalities.
- **The viewer's first visit costs 5 MB and 2.5 s** on each PC (see
  Measured); every later open is under a second. The reading room (M5.4)
  keeps the viewer loaded between studies, and the worklist can fetch it
  ahead of the first click.
- **A realm change after the first start does not reach a running platform.**
  M4 adds a tool that applies `identity/realm-pmc.json` to a running Keycloak.
- **Cutting someone off at once.** Removing a person from a group, or
  disabling them in AD, takes effect at their next token renewal (within
  about 4 minutes on site). The runbook (M4) gets a step that ends a person's
  sessions straight away.
- **A password AD says must be changed** (a new account, or after a reset)
  cannot be changed at PMC's sign-in page, which only reads AD: the person
  changes it in Windows first (INFERRED; not tested).
- **People type their Windows username**, not `PMC\name` or an email
  address. What the sign-in page does with those is NOT VERIFIED.
- **How long a study may wait unread** before its "ago" turns orange (two
  hours here) and bold (eight) is Dada's to set, with the radiologists; STAT
  and priority come with the BizBox order (M3).
- **Compare** opens OHIF's own compare protocol, a 2×2 grid whose lower row
  is empty for single-series studies (a chest plate against a chest plate).
  A one-by-two compare for those is a hanging-protocol change in the
  viewer's configuration, once the readers have seen this one.
- **A phone gets the plain table**, not the virtualized one: fine for the
  few rows a phone shows, not measured with hundreds.
- **Two viewers in the reading room** double the viewer's memory on the PC
  (each is its own OHIF). NOT VERIFIED on PMC's reading-room PCs; the
  standalone window remains for a PC that struggles.
- **Going back in the room loads the study again** (`K`: 5.3 s on the cloud
  host, while the study after the new current one loads behind at the same
  time). Keeping the previous study too would mean a third viewer; loading
  the two in turn rather than at once is the cheaper first step. Measured on
  4 CPUs with software rendering; a reading-room PC is faster.
- **The page's chunks are cached for a year by name;** a library update
  changes the library's file only. Not measured on a phone.
- **Node 24 leaves active support in October 2026**, when Node 26 becomes the
  LTS line (the date is from the front-door research, NOT VERIFIED here). The
  move is a base-image change plus a test run.
- **The audit trail is append-only by permission, not yet tamper-evident.**
  The research suggested monthly partitions and a hash chain; how long PMC
  keeps it is a Data Privacy Act question for the DPO.
- **A claim never lapses.** A reader who goes home keeps it until they
  release it; ICT's release comes with the admin screens.
- **`secrets/` after a disaster.** The drill keeps the test secrets, so it
  proves the data comes back, not the credentials. On site, losing the
  primary loses `secrets/` too. Either ICT escrows the whole directory with
  the two backup keys, or the nightly snapshot takes it too (encrypted like
  everything else), leaving only the two keys to escrow. M4 decides, with the
  host layout.
- **After a disaster, the R740xd's own copy** is gone as well. The runbook
  (M4) re-seeds it from Azure before the next night's backup.
- **Azure immutability with Kopia's `sync-to`** is NOT VERIFIED: the stand-in
  does not enforce immutability. It is tested against a real container, with
  ICT, before the copy counts as the one the primary cannot change.
- **Putting back one study**, not the whole site, needs the engine's index to
  find its files. The runbook (M4) restores a copy into a scratch engine and
  sends the study from there.
- **The off-site copy's freshness** is watched on the R740xd, which the
  primary cannot see into: M4 puts a watch there too.
- **Nobody looks at Prometheus or Alertmanager directly yet.** The front door
  does not route them. ICT's admin screens (M2.3) can show what is firing.
- **The host itself** (its CPU, memory and system disk) is not watched yet:
  M4, or PMC's existing monitoring if it has one.
- **A modality refused for a wrong AE title** is in the engine's log, but not
  counted yet.
- **The drill's times are for a few synthetic studies.** Restoring 6.3 TB is
  measured on PMC hardware in M4.

## Regenerating `db/schema.sql`

After adding a migration, run `ci/run.sh`. It fails at the schema check and
leaves the live schema in `.results/schema.sql`. Read it, then copy it over
`db/schema.sql` and commit both. Never edit a migration that has run
anywhere; add a new one.

## Regenerating `tests/requirements.txt`

It is generated from `tests/requirements.in` with a hash for every package.
The image installs with `--require-hashes`. To change a version, edit
`requirements.in`, then regenerate:

```sh
uv pip compile --generate-hashes --python-version 3.14 \
  --python-platform x86_64-manylinux_2_28 --no-header --no-annotate \
  -o requirements.txt requirements.in
```

## Next

- **M2.3, the rest:** assigning a reader; sharing with referrers from the
  page, once Dada decides who may share and for how long; ICT's admin
  screens. See [The front door app](#the-front-door-app).
- **M2.4:** the cine fix for the live WS23 portal, prepared and tested in
  `apps/imaging-portal`. It is deployed only on Dada's go.
- **M4:** migration tooling, the runbook, and the on-prem package for the
  R740xd.
