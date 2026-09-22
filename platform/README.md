# platform — Path A, engine as code

**Status: SKELETON. Never run, never deployed, nothing here is validated.**

Dada chose Path A on 6 Sep 2026 — *"Path A now; Path B evaluation in parallel;
decision point at week 12."* Path A is: OHIF v3 as the only viewer, sign-in via
Keycloak brokering to Entra ID, the engine as `orthancteam/orthanc` container
images with env-var config, **configuration as versioned code**, and DICOMweb
everywhere so the engine stays swappable.

The roadmap puts *"engine as code (Linux VM, containers, PostgreSQL index inside,
config in Git)"* at **weeks 2–5**. No work on it had started anywhere. This is
the start: the shape of the target, reviewable in a diff instead of living in one
person's head.

## What is verified, and what is not

**VERIFIED** (from the record, read from primary sources on 6 Sep 2026):
`orthancteam/orthanc` publishes container images configured by environment
variables; the PostgreSQL index plugin 10.3 (19 Aug 2026) is the documented
reference backend; OHIF v3 documents OpenID Connect sign-in via Keycloak;
Keycloak 26.7.3 brokers to any OIDC or SAML 2.0 IdP and lists Microsoft as an
identity provider — so OHIF → Keycloak → Entra ID is documented end to end.

**NOT VERIFIED** — everything about *this* compose file. It has never been run.
No image digest is pinned. No Keycloak realm, no OHIF data-source config and no
reverse proxy is written yet. Nothing here has been tested against PMC's estate.

## What it is gated on

1. **ADR-001** — move the index from SQL Server/ODBC to PostgreSQL. Status is
   still *Proposed*, not approved. The ADR argued the cost was lowest "while the
   archive holds two studies"; the archive now holds real patient studies, so
   that window has already narrowed.
2. **A Linux host.** There is one Hyper-V host, it runs the only domain
   controller, and it has no host-level backup. The record's own accepted risk
   says a Windows-service Orthanc stays for now, to be revisited when a second
   host exists.
3. **Weeks 1–2 safety work** — archive and index backups, a patch window, the
   internet port-forwards closed. None of that is done. The index has never been
   backed up.

Do not deploy any of this until those are true. It is here to be reviewed and
argued with, not run.

## Files

```
compose.yaml        Orthanc + PostgreSQL index + OHIF + Keycloak
orthanc/orthanc.json  config as code; site values come from the environment
.env.example        copy to .env (git-ignored); no real value is committed
```
