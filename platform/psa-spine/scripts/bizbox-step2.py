"""The desk's four read-only views in BizBox's database (LiveDB_PMC), schema psa.

BizBox step 2 (docs/handoffs/HANDOFF-cloud-sql01-WS36-20260929-bizbox.md). SQL01 created them on DND-SQL01 on
29 Sep 2026 at 11:20 (Reply, part 2) and added psa.vw_invoice's SupplierInvoiceNo after schema 044. This file
holds the views as they stand, so a rebuilt host can be made from the repository. Run it as the operator's own
Windows login (sysadmin), never as the desk.

Dada's decision, 29 Sep 2026 ("b"): the supplier's name comes from BizBox's own dbo.udf_GetFullName, keyed by the
vendor only, doctors included. No agreement view: BizBox holds no supplier agreements (Reply, part 1).

What it deliberately does NOT do:
  - read or join any table outside iw* and dbo.udf_GetFullName (which reads psDatacenter, by vendor key only);
  - make the views schema-bound. No BizBox upgrade is ever blocked by them: if one renames a column, the view
    fails and the desk's sync says so, while BizBox is untouched;
  - grant anything. The desk's login and its one grant are New-PsaBizboxLogin.ps1's;
  - print a row's content. It prints counts and names only.

PREVIEW BY DEFAULT.
    python bizbox-step2.py            (or: preview) no DDL: each view's SELECT run as a query, row counts only;
                                      the map the views fit, checked by the desk's own check_map and printed;
                                      every column name checked by the desk's patient-word fence
    python bizbox-step2.py apply      CREATE SCHEMA psa AUTHORIZATION dbo if it is missing, then CREATE OR ALTER
                                      each view, in one transaction (running it again changes nothing)
    python bizbox-step2.py verify     the views exist, are not schema-bound, answer the desk's exact query shape,
                                      and read only the approved objects; names pass the fence
    python bizbox-step2.py reverse    DROP the four views, then the schema if it holds nothing else
"""
import io, json, os, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pyodbc

SPINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # platform/psa-spine
sys.path.insert(0, SPINE)
from psaspine.bizbox import PATIENT_WORDS, check_map, MAX_ROWS   # the desk's own fence

CS = ("Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\\PMC_SS;Database=LiveDB_PMC;"
      "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes")

# Each view: name -> SELECT body. Only the columns the desk maps; renamed so none trips the fence.
VIEWS = {
    "vw_product": """
SELECT CAST(i.PK_iwItems AS nvarchar(64))          AS ItemCode,
       i.itemdesc                                  AS ItemName,
       CAST(i.FK_mscItemCategory AS nvarchar(20))  AS Category,
       i.unit                                      AS Unit,
       i.avgcost                                   AS UnitCost
FROM dbo.iwItems AS i
WHERE i.isInventory = 1
  AND (i.isactive = 1 OR EXISTS (SELECT 1 FROM dbo.iwPOitem AS l WHERE l.FK_iwItems = i.PK_iwItems))""",
    "vw_purchase_order": """
SELECT CAST(p.docno AS nvarchar(20))               AS PONo,
       dbo.udf_GetFullName(p.FK_faVendors)         AS VendorName,
       p.docdate                                   AS PODate,
       CASE WHEN p.cancelflag = 1 THEN N'Cancelled'
            WHEN ISNULL(p.postflag, 0) = 0 AND p.approvalflag = 1 THEN N'Approved'
            WHEN ISNULL(p.postflag, 0) = 0 THEN N'Draft'
            WHEN p.postatus = N'FS' THEN N'Received'
            WHEN p.postatus = N'PS' THEN N'Partly received'
            ELSE N'Ordered' END                    AS Status,
       p.netcurramt                                AS TotalAmount,
       p.FK_mscCurrencies                          AS Currency
FROM dbo.iwPOinv AS p
WHERE ISNULL(p.deleteflag, 0) = 0""",
    "vw_purchase_order_line": """
SELECT CAST(l.PK_iwPOitem AS nvarchar(20))         AS LineID,
       CAST(p.docno AS nvarchar(20))               AS PONo,
       CAST(ROW_NUMBER() OVER (PARTITION BY l.FK_TRXNO ORDER BY l.PK_iwPOitem) AS int) AS [LineNo],
       CAST(l.FK_iwItems AS nvarchar(64))          AS ItemCode,
       COALESCE(NULLIF(LTRIM(RTRIM(l.itemSpec)), N''), i.itemdesc) AS Description,
       l.qty                                       AS QtyOrdered,
       l.servqty                                   AS QtyReceived,
       l.price                                     AS UnitCost
FROM dbo.iwPOitem AS l
JOIN dbo.iwPOinv AS p ON p.PK_TRXNO = l.FK_TRXNO
LEFT JOIN dbo.iwItems AS i ON i.PK_iwItems = l.FK_iwItems
WHERE ISNULL(p.deleteflag, 0) = 0""",
    # BizBox's receiving report, which carries the supplier's invoice; refno is that invoice's own number.
    "vw_invoice": """
SELECT CAST(a.docno AS nvarchar(20)) AS ReceivingNo, a.refno AS SupplierInvoiceNo,
       dbo.udf_GetFullName(a.FK_faVendors) AS VendorName,
       COALESCE(a.refdate, a.docdate) AS InvoiceDate,
       DATEADD(day, ISNULL(a.terms, 0), COALESCE(a.refdate, a.docdate)) AS DueDate,
       CASE WHEN a.cancelflag = 1 THEN N'Cancelled' WHEN a.postflag = 1 THEN N'Posted' ELSE N'Draft' END AS Status,
       a.netlocamt AS TotalAmount, a.FK_mscCurrency AS Currency
FROM dbo.iwApinv AS a
WHERE ISNULL(a.deleteflag, 0) = 0""",
}
ALLOWED_REFS = {"iwitems", "iwpoitem", "iwpoinv", "iwapinv", "udf_getfullname"}

# The map these views fit: D:\psa\bizbox-map.json on the host (never in the repo).
MAP = {"objects": {
    "product": {"view": "psa.vw_product", "columns": {
        "ext_ref": "ItemCode", "name": "ItemName", "category": "Category", "unit": "Unit", "unit_cost": "UnitCost"}},
    "purchase_order": {"view": "psa.vw_purchase_order", "columns": {
        "ext_ref": "PONo", "vendor": "VendorName", "ordered_on": "PODate", "status": "Status",
        "total": "TotalAmount", "currency": "Currency"}},
    "po_line": {"view": "psa.vw_purchase_order_line", "columns": {
        "ext_ref": "LineID", "po_ref": "PONo", "line_no": "LineNo", "product_ref": "ItemCode",
        "description": "Description", "quantity": "QtyOrdered", "received_qty": "QtyReceived", "unit_cost": "UnitCost"}},
    "invoice": {"view": "psa.vw_invoice", "columns": {
        "ext_ref": "ReceivingNo", "supplier_ref": "SupplierInvoiceNo", "party": "VendorName",
        "invoiced_on": "InvoiceDate", "due_on": "DueDate", "status": "Status", "total": "TotalAmount",
        "currency": "Currency"}},
}}


def conn(autocommit=True):
    return pyodbc.connect(CS, autocommit=autocommit)


def fence(names):
    bad = [n for n in names if PATIENT_WORDS.search(n)]
    return "PASS" if not bad else f"FAIL {bad}"


def clean(exc):
    return re.sub(r"^(\s*\[[^\]]*\])+", "", str(exc))


mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
if mode == "preview":
    check_map(json.loads(json.dumps(MAP)))
    print("the map these views fit: accepted by the desk's check_map (4 kinds; no agreement)")
    c = conn(); cur = c.cursor()
    print("schema psa exists now:", bool(cur.execute("SELECT 1 FROM sys.schemas WHERE name = 'psa'").fetchone()))
    for v, body in VIEWS.items():
        cur.execute(f"SELECT TOP 0 * FROM ({body}) AS x")
        cols = [d[0] for d in cur.description]
        n = cur.execute(f"SELECT COUNT_BIG(*) FROM ({body}) AS x").fetchone()[0]
        kind = next(k for k, s in MAP["objects"].items() if s["view"] == "psa." + v)
        missing = [col for col in MAP["objects"][kind]["columns"].values() if col not in cols]
        print(f"psa.{v}: {n} rows; columns {cols}; fence {fence(cols + [v])}; map columns missing: {missing or 'none'}")
    c.close()
    print("the map, for D:\\psa\\bizbox-map.json:")
    print(json.dumps(MAP, indent=2))
    print("preview only: nothing was created (python bizbox-step2.py apply)")
elif mode == "apply":
    c = conn(autocommit=False); cur = c.cursor()
    try:
        if not cur.execute("SELECT 1 FROM sys.schemas WHERE name = 'psa'").fetchone():
            cur.execute("CREATE SCHEMA psa AUTHORIZATION dbo")
            print("schema psa created (owner dbo)")
        for v, body in VIEWS.items():
            cur.execute(f"CREATE OR ALTER VIEW psa.{v}\nAS{body}")
        c.commit()
        print("in one transaction: CREATE OR ALTER " + ", ".join(f"psa.{v}" for v in VIEWS))
    except pyodbc.Error as exc:
        c.rollback()
        raise SystemExit("FAILED, rolled back, nothing changed: " + clean(exc))
    finally:
        c.close()
elif mode == "verify":
    c = conn(); cur = c.cursor()
    views = [r[0] for r in cur.execute(
        "SELECT v.name FROM sys.views v JOIN sys.schemas s ON s.schema_id = v.schema_id WHERE s.name = 'psa' ORDER BY v.name")]
    print(f"views in psa: {views}; schema owner: "
          f"{cur.execute('SELECT USER_NAME(principal_id) FROM sys.schemas WHERE name = ?', 'psa').fetchone()[0]}")
    other = cur.execute("SELECT COUNT(*) FROM sys.objects o JOIN sys.schemas s ON s.schema_id = o.schema_id "
                        "WHERE s.name = 'psa' AND o.type <> 'V'").fetchone()[0]
    print(f"other objects in psa: {other}")
    for kind, spec in MAP["objects"].items():
        v = spec["view"].split(".")[1]
        bound = cur.execute("SELECT is_schema_bound FROM sys.sql_modules WHERE object_id = OBJECT_ID(?)", spec["view"]).fetchone()[0]
        refs = sorted({r[0].lower() for r in cur.execute(
            "SELECT DISTINCT referenced_entity_name FROM sys.sql_expression_dependencies WHERE referencing_id = OBJECT_ID(?)",
            spec["view"])})
        cols = [r[0] for r in cur.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID(?) ORDER BY column_id", spec["view"])]
        sel = ", ".join(f"[{col}]" for col in spec["columns"].values())
        rows = cur.execute(f"SELECT TOP ({MAX_ROWS + 1}) {sel} FROM [psa].[{v}]").fetchall()   # the desk's exact shape
        extra = sorted(set(refs) - ALLOWED_REFS)
        print(f"{spec['view']} ({kind}): {len(rows)} rows by the desk's query; schema-bound {bool(bound)}; "
              f"reads {refs}{' NOT APPROVED: ' + str(extra) if extra else ''}; fence {fence(cols + [v])}")
    c.close()
elif mode == "reverse":
    c = conn(autocommit=False); cur = c.cursor()
    try:
        for v in reversed(list(VIEWS)):
            cur.execute(f"DROP VIEW IF EXISTS psa.{v}")
        left = cur.execute("SELECT COUNT(*) FROM sys.objects o JOIN sys.schemas s ON s.schema_id = o.schema_id WHERE s.name = 'psa'").fetchone()[0]
        if left:
            raise SystemExit(f"psa still holds {left} other object(s); the views were NOT dropped either (rolled back)")
        cur.execute("DROP SCHEMA IF EXISTS psa")
        c.commit()
        print("dropped: the four views and schema psa")
    except pyodbc.Error as exc:
        c.rollback()
        raise SystemExit("FAILED, rolled back: " + clean(exc))
    finally:
        c.close()
else:
    print(__doc__)
