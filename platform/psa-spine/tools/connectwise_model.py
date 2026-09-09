"""Extract the ConnectWise PSA entity model into a reference we can design against.

    git clone --depth 1 https://github.com/HealthITAU/pyconnectwise <path>
    python3 tools/connectwise_model.py --source <path> --write

Why this exists. ConnectWise's own documentation sits behind ConnectWise
University authentication, so it cannot be read from a build. `pyconnectwise` is
code-generated from ConnectWise's **own OpenAPI schemas** and is public, which
makes it the only machine-readable statement of the PSA entity model available to
us. Reading it settled several design questions and falsified one claim this
programme had recorded as VERIFIED — see WS36-psa-build-scope §2.2.1.

What this is NOT. It is not ConnectWise's documentation, it is a third party's
generation of ConnectWise's schema, and it carries no behaviour: an enum tells you
the values a field accepts, never what the product does with them. Field names and
types are ConnectWise's; the grouping below is ours.

The output is committed because the source is an external clone that CI does not
have. There is therefore **no drift gate on it** — unlike sqlserver/, which is
generated from this repository and is gated. Regenerate deliberately, and say in
the commit which upstream commit it came from.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT.parent.parent / "docs" / "WS36-connectwise-model-20260909.md"

MODELS = "src/pyconnectwise/models/manage/__init__.py"

# Our grouping, not ConnectWise's. Ordered: the first pattern that matches wins,
# so put the specific before the general.
# Roughly a third of the model is not entities at all: `XReference` and `XInfo`
# are the trimmed shapes ConnectWise returns when an entity is embedded in
# another, and request/response wrappers are transport. Separating them is the
# difference between "a PSA is 773 objects" and a number that means something.
WRAPPER = re.compile(r"(Reference|Info)$|^(Bulk|Clear|Create|Convert|Batch)\w*(Request|Result|Item)?$"
                     r"|(Request|Response|Result|Settings?|Setup|Filter\w*|Callback)$")

DOMAINS: list[tuple[str, str, str]] = [
    ("Service delivery — the board", r"^(Board|ServiceTeam|ServiceStatus|ServiceType|ServiceSubType|ServiceItem|ServiceSource|ServiceLocation|ServiceSignoff|ServiceEmailTemplate|ServiceSurvey|ServiceTemplate|ServiceNote|ServiceCode|ServiceRevenue|Service$|ServiceInfo|Priority|Source|Impact|Urgency|Severity)",
     "The unit of configuration. A board owns its statuses, types, teams and rules."),
    ("Service delivery — the ticket", r"^(Ticket|Activity|Schedule|Reminder|Merge|Bundle|Stopwatch)",
     "The work itself, and everything that hangs off it."),
    ("SLA and calendars", r"^(SLA|Calendar|Holiday|BusinessUnit|WorkRole|WorkType)",
     "Three clocks, four calendar kinds, and the working week as data."),
    ("Workflow — the rules engine", r"^Workflow",
     "Scope, condition, execution policy and typed actions, all as rows."),
    ("Commercial — agreements and billing", r"^(Agreement|Invoice|Billing|Payment|Adjustment|Tax|Currency|Accounting|Unposted|Expense|Cost|Rate|Markup|Charge|Credit|Deposit|Subscription|Addition|Batch)",
     "Where a PSA turns work into money. The half the spine already models differently."),
    ("Procurement", r"^(Purchase|Order|Product|Catalog|Inventory|Warehouse|Shipment|Manufacturer|Vendor|Supplier|Pricing|Unit)",
     "A module Dada asked for. Every one of these extends the same base record."),
    ("Configurations — the CMDB", r"^Configuration",
     "What a ticket is ABOUT. Medical devices become configuration items."),
    ("Companies, contacts and sites", r"^(Company|Contact|Site|Address|Country|State|Territory|Relationship|Department|Location|Group|Portal)",
     "Who asks, and where they are."),
    ("Projects", r"^Project",
     "The other work type extending the same base. Phases, tasks, budgets."),
    ("Sales and marketing", r"^(Opportunity|Sales|Campaign|Lead|Forecast|Quote|Marketing|Track)",
     "Not PMC's problem this year. Listed so the omission is a decision."),
    ("Time and expense", r"^(Time|Expense|Timesheet|Accrual)",
     "The numerator of any capacity claim."),
    ("Finance — general ledger and accounting", r"^(GL|Commission|Conversion|DeliveryMethod|EPay|FinanceCurrency|ClosedInvoice|Code$)",
     "The export into an accounting system. Out of scope, and it is here so that is a decision."),
    ("Members, security and system", r"^(Member|Security|Audit|System|Api|Auth|Login|Password|Role|Permission|Setting|Integration|Managed|Report|KPI|Document|Attachment|Note|Custom|UserDefined|Error|Validation|Count|Link|Menu|Template|Email|Notification|Survey|Knowledge|My|Owner|Sync|Import|Export|Delete|Allowed|Auto|ConnectWiseHosted|CwTimeZone|Experiment|FileUpload|FormSubmitted|Google|IRest|Entity)",
     "The plumbing. Note the audit trail is a first-class entity."),
    ("Classification and reference data", r"^(Category|Certification|Classification|CorporateStructure|CommunicationType|Crm|Currency|Unit|Status|Type|State|Level)",
     "The lookup tables every module hangs off."),
]


def _literal_values(node: ast.AST) -> list[str] | None:
    """Pull the values out of a Literal[...] annotation, however it is nested."""
    found: list[str] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Subscript) and getattr(n.value, "id", "") == "Literal":
            sl = n.slice
            elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
            for e in elts:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    found.append(e.value)
            return
        for child in ast.iter_child_nodes(n):
            walk(child)

    walk(node)
    return found or None


def _alias(node: ast.AST) -> str | None:
    """The wire name, from Field(alias="...")."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Field":
            for kw in n.keywords:
                if kw.arg == "alias" and isinstance(kw.value, ast.Constant):
                    return kw.value.value
    return None


def _type_name(node: ast.AST) -> str:
    text = ast.unparse(node)
    text = re.sub(r"Annotated\[\s*", "", text)
    text = re.sub(r",\s*Field\(.*?\)\s*\]", "", text, flags=re.S)
    text = re.sub(r"\s+", " ", text).strip().rstrip("]").strip()
    return text


class Field:
    def __init__(self, name: str, node: ast.AnnAssign, doc: str | None) -> None:
        self.name = name
        self.alias = _alias(node.annotation)
        self.type = _type_name(node.annotation)
        self.values = _literal_values(node.annotation)
        self.required = node.value is None
        self.max_length = None
        if doc:
            m = re.search(r"Max length:\s*(\d+)", doc)
            if m:
                self.max_length = int(m.group(1))
            self.note = re.sub(r"\s*Max length:\s*\d+;?", "", doc).strip() or None
        else:
            self.note = None


class Entity:
    def __init__(self, name: str) -> None:
        self.name = name
        self.fields: list[Field] = []

    @property
    def is_wrapper(self) -> bool:
        return bool(WRAPPER.search(self.name))

    @property
    def domain(self) -> str:
        if self.is_wrapper:
            return "Reference and transport shapes"
        for title, pattern, _ in DOMAINS:
            if re.match(pattern, self.name):
                return title
        return "Unclassified"


def parse(models: Path) -> list[Entity]:
    tree = ast.parse(models.read_text(encoding="utf-8"))
    entities: list[Entity] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        entity = Entity(node.name)
        body = node.body
        for i, stmt in enumerate(body):
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            doc = None
            nxt = body[i + 1] if i + 1 < len(body) else None
            if (isinstance(nxt, ast.Expr) and isinstance(nxt.value, ast.Constant)
                    and isinstance(nxt.value.value, str)):
                doc = " ".join(nxt.value.value.split())
            entity.fields.append(Field(stmt.target.id, stmt, doc))
        entities.append(entity)
    return entities


# Entities written out in full. Everything else is inventoried by name only —
# a reference nobody can finish reading is not a reference.
IN_FULL = {
    "Board", "BoardStatus", "BoardStatusNotification", "BoardTeam", "BoardType",
    "BoardSubType", "BoardItem", "BoardTypeSubTypeItemAssociation",
    "BoardAutoAssignResource", "BoardAutoTemplate", "BoardExcludedMember",
    "BoardNotification", "BoardDefault",
    "Ticket", "TicketNote", "TicketTask", "TicketMerge", "TicketBundle",
    "ServiceTeam", "ServiceTemplate", "ServiceSignoff", "ServiceSurvey",
    "ServiceSurveyQuestion", "ServiceLocation", "ServiceNote", "ServiceTicketLink",
    "SLA", "SLAPriority", "Calendar", "Holiday", "HolidayList",
    "Priority", "Source", "WorkRole", "WorkType", "BusinessUnit",
    "Workflow", "WorkflowEvent", "WorkflowAction", "WorkflowTrigger",
    "WorkflowNotifyType", "WorkflowTableType", "WorkflowTriggerOption",
    "Agreement", "AgreementAddition", "AgreementAdjustment", "AgreementType",
    "AgreementSite", "AgreementWorkRole", "AgreementWorkType",
    "Invoice", "InvoiceTemplate", "BillingSetup", "BillingStatus",
    "TimeEntry", "TimeSheet", "TimeAccrual", "ScheduleEntry",
    "CompanyConfiguration", "ConfigurationType", "ConfigurationStatus",
    "ConfigurationTypeQuestion", "ConfigurationQuestion",
    "PurchaseOrder", "PurchaseOrderLineItem", "ProductItem", "CatalogItem",
    "AgreementAddition", "BillingSetup", "Document",
    "Company", "CompanySite", "CompanyTeam", "Contact", "ContactDepartment",
    "Member", "SecurityRole", "AuditTrailEntry", "Document",
    "Project", "ProjectPhase", "ProjectTicket",
}


def render(entities: list[Entity], upstream: str, source: Path) -> str:
    by_domain: dict[str, list[Entity]] = {}
    for e in entities:
        by_domain.setdefault(e.domain, []).append(e)

    real = [e for e in entities if not e.is_wrapper]
    total_fields = sum(len(e.fields) for e in real)
    vocab: dict[str, list[str]] = {}
    for e in entities:
        for f in e.fields:
            if f.values:
                vocab.setdefault(f"{e.name}.{f.alias or f.name}", f.values)

    out: list[str] = []
    w = out.append
    w("# WS36 — the ConnectWise PSA entity model, extracted")
    w("")
    w("**9 September 2026. GENERATED FILE — do not hand-edit.**")
    w("")
    w("```")
    w("git clone --depth 1 https://github.com/HealthITAU/pyconnectwise <path>")
    w("python3 tools/connectwise_model.py --source <path> --write")
    w("```")
    w("")
    w(f"**[VERIFIED 9 Sep 2026]** Extracted from `HealthITAU/pyconnectwise` at "
      f"commit `{upstream}`, file `{MODELS}`.")
    w("")
    w(f"**{len(real)} entities and {total_fields} fields**, once the "
      f"{len(entities) - len(real)} `Reference`/`Info`/transport wrappers are set "
      f"aside. {len(vocab)} closed vocabularies. {len(entities)} classes in all.")
    w("")
    w("## What this is, and what it is not")
    w("")
    w("ConnectWise's own documentation is behind ConnectWise University "
      "authentication and cannot be read from a build. `pyconnectwise` is "
      "code-generated from **ConnectWise's own OpenAPI schemas**, so the entity "
      "names, field names and types below are ConnectWise's. The generation is a "
      "third party's and the grouping is ours.")
    w("")
    w("**It carries no behaviour.** An enum tells you the values a field accepts "
      "and never what the product does with them. Every design claim drawn from "
      "this file is INFERRED unless it is also stated in ConnectWise's "
      "documentation.")
    w("")
    w("**It has already earned its place.** Reading it falsified a claim this "
      "programme had recorded as VERIFIED — that ConnectWise cannot derive "
      "priority from impact and urgency. It can; the matrix is on `SLA`, not on "
      "`Priority`. See `WS36-psa-build-scope-20260909.md` §2.2.1 and the "
      "correction block in `WS36-psa-recommendation-20260909.md`.")
    w("")
    w("**There is no drift gate on this file.** It is generated from an external "
      "clone that CI does not have, unlike `sqlserver/`, which is generated from "
      "this repository and is gated. Regenerate deliberately and name the upstream "
      "commit when you do.")
    w("")

    w("## The shape of a complete PSA")
    w("")
    w("| Domain | Entities | Why it is here |")
    w("|---|---|---|")
    for title, _, why in DOMAINS + [
            ("Reference and transport shapes", "", "Not entities: embedded shapes and request wrappers."),
            ("Unclassified", "", "Did not match a group.")]:
        group = by_domain.get(title)
        if group:
            w(f"| **{title}** | {len(group)} | {why} |")
    w("")
    w("**[INFERRED]** The count is the point. A PSA that a hospital would call "
      "complete is not a ticket table with some columns; it is roughly this many "
      "objects, and the ones Dada asked for later — procurement, finance — are "
      "already whole domains here. That is the argument for the base class in "
      "`WS36-psa-build-scope` §5.1: each of these arrives as a table extending "
      "`work_item`, or it arrives as a rewrite.")
    w("")

    w("## Closed vocabularies")
    w("")
    w("Every enumerated field in the model. These are the ones worth arguing "
      "with, because each is a decision somebody at ConnectWise made and had to "
      "live with.")
    w("")
    for key in sorted(vocab):
        values = " · ".join(f"`{v}`" for v in vocab[key])
        w(f"- **{key}** — {values}")
    w("")

    w("## Entities in full")
    w("")
    w("The ones a board engine, an SLA engine, a rules engine, a CMDB, "
      "procurement or billing would be built against.")
    w("")
    for title, _, _ in DOMAINS:
        group = [e for e in by_domain.get(title, []) if e.name in IN_FULL]
        if not group:
            continue
        w(f"### {title}")
        w("")
        for e in sorted(group, key=lambda x: x.name):
            w(f"#### `{e.name}` — {len(e.fields)} fields")
            w("")
            w("| Field | Type | Req | Max | Note |")
            w("|---|---|---|---|---|")
            for f in e.fields:
                name = f.alias or f.name
                if name == "_info":
                    continue
                typ = f.type.replace("|", "\\|")
                if f.values:
                    typ = " \\| ".join(f"`{v}`" for v in f.values)
                elif len(typ) > 60:
                    typ = typ[:57] + "…"
                note = (f.note or "").replace("|", "\\|")
                if len(note) > 90:
                    note = note[:87] + "…"
                w(f"| `{name}` | {typ} | {'**y**' if f.required else ''} "
                  f"| {f.max_length or ''} | {note} |")
            w("")

    w("## Full inventory")
    w("")
    w("Every entity in the model, by domain. Names only.")
    w("")
    for title, _, _ in DOMAINS + [("Reference and transport shapes", "", ""),
                                  ("Unclassified", "", "")]:
        group = by_domain.get(title)
        if not group:
            continue
        w(f"**{title}** ({len(group)})")
        w("")
        w(", ".join(f"`{e.name}`" for e in sorted(group, key=lambda x: x.name)))
        w("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", required=True, help="path to a pyconnectwise clone")
    p.add_argument("--write", action="store_true")
    p.add_argument("--out", default=str(OUTPUT))
    a = p.parse_args(argv)

    source = Path(a.source)
    models = source / MODELS
    if not models.exists():
        print(f"REFUSED: {models} not found. Clone pyconnectwise first.", file=sys.stderr)
        return 2
    try:
        upstream = subprocess.run(["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        upstream = "unknown"

    text = render(parse(models), upstream, source)
    if a.write:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out} from pyconnectwise@{upstream}")
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
