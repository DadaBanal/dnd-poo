"""SQL Server Reporting Services, as the desk reads it (082, 13 Oct 2026).

Dada: "printing out reports for MMS". SQL01 measured the estate: 164 reports
already under /BizBox MMS Reports on the host's report server, which answers
at http://dnd-sql01/ReportServer. So the desk writes no report. It asks the
server three things, and nothing else:

1. what the folder holds (ListChildren, the SOAP endpoint every SSRS since
   2008 R2 serves at /ReportService2010.asmx);
2. a report's own parameters, with the valid values the server computes for
   the values chosen so far, so a cascading dropdown refreshes from the
   server's truth (GetItemParameters with ForRendering);
3. the report rendered as PDF or Excel (URL access, rs:Command=Render).

How the desk signs in (Dada, 13 Oct 2026: as its own service account). On
the host the request goes through Windows' own HTTP stack (WinHttpRequest,
through pywin32) with the identity PSA-Desk runs under; SQL01 gives that
account the Browser role on the folder. No password exists for this
anywhere. Off the host, or without pywin32, a plain request goes out and the
server's 401 is reported in a sentence. The tests use a transport of their
own that answers from canned XML.

The server's address comes from the environment (PSA_SSRS_URL, and
PSA_SSRS_FOLDER for the folder), never from the repo: a hostname is fine in
a handoff, and nothing here holds an address.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

NS = "http://schemas.microsoft.com/sqlserver/2010/06/30/reporting/reportingservices"
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
DEFAULT_FOLDER = "/BizBox MMS Reports"
FORMATS = {"PDF": ("application/pdf", "pdf"), "EXCELOPENXML": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx")}
TIMEOUT = 120


class Refused(ValueError):
    """A sentence for the person; nothing was fetched."""


class ServerError(RuntimeError):
    """What the report server answered, in a sentence, with its status."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- transport

class Transport:
    """One HTTP request. Returns (status, content_type, body bytes)."""
    name = "none"

    def request(self, method: str, url: str, *, headers: dict | None = None, body: bytes | None = None):  # pragma: no cover
        raise NotImplementedError


class UrllibTransport(Transport):
    """Python's own client: no Windows sign-in. Enough for a server that lets
    the desk's network identity through, and for saying 401 plainly."""
    name = "urllib"

    def request(self, method, url, *, headers=None, body=None):
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:        # noqa: S310 - the host's own report server
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", exc.read() or b""
        except (urllib.error.URLError, OSError) as exc:
            raise ServerError(0, f"The report server could not be reached: {exc.reason if hasattr(exc, 'reason') else exc}") from None


class WinHttpTransport(Transport):
    """Windows' HTTP stack with the process's own identity (pywin32): the
    desk signs in to SSRS as the account PSA-Desk runs under."""
    name = "winhttp"

    def __init__(self):
        import win32com.client                                       # the host has pywin32; elsewhere ImportError
        self._client = win32com.client

    def request(self, method, url, *, headers=None, body=None):
        import pywintypes
        req = self._client.Dispatch("WinHttp.WinHttpRequest.5.1")
        req.SetAutoLogonPolicy(0)                                     # always: send the current Windows identity
        req.SetTimeouts(15000, 15000, 30000, TIMEOUT * 1000)
        try:
            req.Open(method, url, False)
            for k, v in (headers or {}).items():
                req.SetRequestHeader(k, v)
            req.Send(body if body is not None else "")
            ctype = ""
            try:
                ctype = req.GetResponseHeader("Content-Type")
            except pywintypes.com_error:
                pass
            return int(req.Status), ctype, bytes(req.ResponseBody)
        except pywintypes.com_error as exc:
            raise ServerError(0, f"The report server could not be reached: {exc}") from None


class CurlTransport(Transport):
    """Windows' own curl.exe with --negotiate: SSPI sends the process's
    identity, so the desk signs in as the account PSA-Desk runs under with
    nothing installed (SQL01, Part 81, proven end to end: the list, a PDF, an
    Excel). `exe` is the program, or a command prefix as a list (the tests
    run a stub through the interpreter)."""
    name = "curl"

    def __init__(self, exe=None):
        exe = exe or os.environ.get("PSA_SSRS_CURL", "").strip() or _find_curl()
        if not exe:
            raise ImportError("no curl.exe")
        self.cmd = list(exe) if isinstance(exe, (list, tuple)) else [exe]

    def request(self, method, url, *, headers=None, body=None):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "answer.bin")
            args = self.cmd + ["--negotiate", "-u", ":", "-sS", "--max-time", str(TIMEOUT), "-X", method,
                               "-o", out, "-w", "%{http_code}\n%{content_type}"]
            for k, v in (headers or {}).items():
                args += ["-H", f"{k}: {v}"]
            if body is not None:
                sent = os.path.join(tmp, "request.bin")
                with open(sent, "wb") as fh:
                    fh.write(body)
                args += ["--data-binary", f"@{sent}"]
            args.append(url)
            try:
                run = subprocess.run(args, capture_output=True, timeout=TIMEOUT + 15)    # noqa: S603 - the host's own curl, fixed arguments
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ServerError(0, f"The report server could not be reached: {exc}") from None
            if run.returncode != 0:
                said = (run.stderr.decode("utf-8", "replace").strip().splitlines() or ["curl failed"])[-1][:200]
                raise ServerError(0, f"The report server could not be reached: {said}")
            lines = run.stdout.decode("utf-8", "replace").strip().splitlines()
            status = int(lines[0].strip()) if lines and lines[0].strip().isdigit() else 0
            ctype = lines[1].strip() if len(lines) > 1 else ""
            data = b""
            if os.path.exists(out):
                with open(out, "rb") as fh:
                    data = fh.read()
            return status, ctype, data


def _find_curl() -> str:
    """Windows ships curl.exe in System32 (8.x, Schannel, SSPI). Elsewhere a
    curl has no Windows identity to send, so it is not picked up by itself."""
    if os.name == "nt":
        p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
        if os.path.exists(p):
            return p
        return shutil.which("curl.exe") or ""
    return ""


def transport() -> Transport:
    """Windows' stack where pywin32 is there; else Windows' curl.exe, which
    needs nothing installed; else Python's, which has no identity to send."""
    try:
        return WinHttpTransport()
    except ImportError:
        pass
    try:
        return CurlTransport()
    except ImportError:
        return UrllibTransport()


# --------------------------------------------------------------- the client

@dataclass
class Param:
    name: str
    prompt: str
    type: str = "String"                    # String, Integer, Float, DateTime, Boolean
    nullable: bool = False
    allow_blank: bool = False
    multi: bool = False
    prompt_user: bool = True
    query_based: bool = False
    dependencies: list = field(default_factory=list)
    valid_values: list = field(default_factory=list)      # [(label, value)]
    defaults: list = field(default_factory=list)
    state: str = ""                          # HasValidValue, MissingValidValue, HasOutstandingDependencies, DynamicValuesUnavailable

    @property
    def required(self) -> bool:
        return not self.nullable and not self.allow_blank

    def as_dict(self) -> dict:
        return {"name": self.name, "prompt": self.prompt, "type": self.type, "nullable": self.nullable,
                "allow_blank": self.allow_blank, "multi": self.multi, "prompt_user": self.prompt_user,
                "query_based": self.query_based, "dependencies": list(self.dependencies),
                "has_list": bool(self.valid_values), "defaults": list(self.defaults)}


@dataclass
class Report:
    path: str
    name: str
    description: str = ""
    hidden: bool = False


def base_url(raw: str | None = None) -> str:
    url = (raw if raw is not None else os.environ.get("PSA_SSRS_URL", "")).strip().rstrip("/")
    if not url:
        raise Refused("PSA_SSRS_URL is not set: the report server's address lives on the host, never in the repo.")
    if not re.match(r"^https?://[A-Za-z0-9.-]+(:\d+)?(/[^\s?#]*)?$", url):
        raise Refused("PSA_SSRS_URL must be http(s)://<host>/ReportServer, nothing else.")
    return url


def folder(raw: str | None = None) -> str:
    f = (raw if raw is not None else os.environ.get("PSA_SSRS_FOLDER", "")).strip() or DEFAULT_FOLDER
    if not f.startswith("/") or ".." in f:
        raise Refused("PSA_SSRS_FOLDER is a report-server path starting with /.")
    return f.rstrip("/") or "/"


class Ssrs:
    def __init__(self, url: str | None = None, folder_path: str | None = None, transport_: Transport | None = None):
        self.url = base_url(url)
        self.folder = folder(folder_path)
        self.transport = transport_ or transport()

    def _refused(self) -> ServerError:
        """A 401 in words that name the right fix (SQL01, Part 81: the old
        sentence sent the reader to a Browser role that was already granted).
        The server speaks only Negotiate and NTLM, so Python's own client,
        which offers neither, is refused whatever the roles say."""
        if self.transport.name == "urllib":
            return ServerError(401, "The report server refused the desk's sign-in: the desk could not present a Windows identity "
                                    "to it (neither curl.exe nor pywin32 is available to the desk's Python). SQL01 confirms "
                                    "C:\\Windows\\System32\\curl.exe exists on the host, or names a curl in PSA_SSRS_CURL.")
        return ServerError(401, "The report server refused the sign-in of the account PSA-Desk runs under. SQL01 gives that "
                                "account the Browser role on the reports folder.")

    # ---- SOAP
    def _soap(self, action: str, body_xml: str) -> ET.Element:
        envelope = (f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="{SOAP_ENV}">'
                    f'<soap:Body>{body_xml}</soap:Body></soap:Envelope>').encode("utf-8")
        status, ctype, data = self.transport.request(
            "POST", f"{self.url}/ReportService2010.asmx",
            headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{NS}/{action}"'}, body=envelope)
        if status == 401:
            raise self._refused()
        if status != 200:
            raise ServerError(status, f"The report server answered {status} to {action}: {_fault(data)}")
        try:
            return ET.fromstring(data)
        except ET.ParseError:
            raise ServerError(status, f"The report server's answer to {action} was not XML.") from None

    def list_reports(self) -> list[Report]:
        root = self._soap("ListChildren", f'<ListChildren xmlns="{NS}"><ItemPath>{_x(self.folder)}</ItemPath>'
                                          f'<Recursive>true</Recursive></ListChildren>')
        out = []
        for item in root.iter(f"{{{NS}}}CatalogItem"):
            kind = _t(item, "TypeName")
            if kind not in ("Report", "LinkedReport"):
                continue
            out.append(Report(path=_t(item, "Path"), name=_t(item, "Name"), description=_t(item, "Description"),
                              hidden=_t(item, "Hidden").lower() == "true"))
        out.sort(key=lambda r: r.path.lower())
        return out

    def parameters(self, path: str, values: dict | None = None) -> list[Param]:
        """The report's parameters as the server sees them for the values
        chosen so far: a child dropdown's choices follow its parents."""
        vals = "".join(f"<ParameterValue><Name>{_x(k)}</Name><Value>{_x(v)}</Value></ParameterValue>"
                       for k, vs in (values or {}).items() for v in (vs if isinstance(vs, list) else [vs]) if v is not None)
        root = self._soap("GetItemParameters",
                          f'<GetItemParameters xmlns="{NS}"><ItemPath>{_x(path)}</ItemPath><ForRendering>true</ForRendering>'
                          f'<Values>{vals}</Values></GetItemParameters>')
        out = []
        for p in root.iter(f"{{{NS}}}ItemParameter"):
            out.append(Param(
                name=_t(p, "Name"), prompt=_t(p, "Prompt") or _t(p, "Name"), type=_t(p, "ParameterTypeName") or "String",
                nullable=_b(p, "Nullable"), allow_blank=_b(p, "AllowBlank"), multi=_b(p, "MultiValue"),
                prompt_user=_t(p, "PromptUser").lower() != "false", query_based=_b(p, "ValidValuesQueryBased"),
                dependencies=[d.text or "" for d in p.iter(f"{{{NS}}}Dependency")],
                valid_values=[(_t(v, "Label") or _t(v, "Value"), _t(v, "Value")) for v in p.iter(f"{{{NS}}}ValidValue")],
                defaults=[d.text or "" for dv in p.iter(f"{{{NS}}}DefaultValues") for d in dv.iter(f"{{{NS}}}Value")],
                state=_t(p, "State")))
        return out

    # ---- URL access
    def render_url(self, path: str, values: dict, fmt: str) -> str:
        if fmt not in FORMATS:
            raise Refused("A report comes out as PDF or Excel.")
        q = [("rs:Command", "Render"), ("rs:Format", fmt), ("rc:Toolbar", "false")]
        for k, vs in values.items():
            if vs is None:
                q.append((f"{k}:isnull", "true"))
                continue
            for v in (vs if isinstance(vs, list) else [vs]):
                q.append((k, str(v)))
        return f"{self.url}?{urllib.parse.quote(path, safe='/')}&{urllib.parse.urlencode(q)}"

    def render(self, path: str, values: dict, fmt: str) -> tuple[bytes, str, str]:
        """(bytes, content type, file extension). The server's own error page
        becomes a sentence; a 401 names what SQL01 grants."""
        started = time.monotonic()
        status, ctype, data = self.transport.request("GET", self.render_url(path, values, fmt))
        if status == 401:
            raise self._refused()
        if status != 200:
            raise ServerError(status, f"The report server answered {status}: {_fault(data)}")
        want, ext = FORMATS[fmt]
        if (ctype or "").split(";")[0].strip().lower() not in (want, "application/octet-stream"):
            raise ServerError(status, f"The report server sent {ctype or 'no content type'} instead of a {ext.upper()}: {_fault(data)}")
        self.last_millis = int((time.monotonic() - started) * 1000)
        return data, want, ext


# ----------------------------------------------------------------- helpers

def _x(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _t(el, tag: str) -> str:
    c = el.find(f"{{{NS}}}{tag}")
    return (c.text or "").strip() if c is not None and c.text else ""


def _b(el, tag: str) -> bool:
    return _t(el, tag).lower() == "true"


def _fault(data: bytes) -> str:
    """The sentence inside a SOAP fault or an SSRS error page, never the page."""
    text = (data or b"")[:20000].decode("utf-8", "replace")
    for pat in (r"<faultstring>(.*?)</faultstring>", r"<Message>(.*?)</Message>", r"<title>(.*?)</title>",
                r"rsErrorCode[^<]*<[^>]*>([^<]{0,300})"):
        m = re.search(pat, text, re.S | re.I)
        if m:
            words = re.sub(r"<[^>]+>", " ", m.group(1))
            return " ".join(words.split())[:300]
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())[:200] or "no detail"


def humanise(name: str) -> str:
    """A report's title from its item name: MMS_PurcSum_ByVendor -> Purchase
    summary by vendor. A person reads words, never a code (Dada, 13 Oct)."""
    words = {"purc": "purchase", "sum": "summary", "summ": "summary", "rep": "report", "del": "delivery",
             "tran": "transaction", "adj": "adjustment", "inv": "inventory", "dept": "department", "qty": "quantity",
             "recv": "receiving", "rr": "receiving", "po": "purchase order", "mms": "", "per": "per", "by": "by",
             "unposted": "unposted", "amt": "amount", "cat": "category", "wh": "warehouse", "whse": "warehouse",
             "jour": "journal", "crit": "critical", "bal": "balance", "iss": "issued", "mat": "materials"}
    s = re.sub(r"^MMS_?", "", name, flags=re.I)
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    parts = [w for w in re.split(r"[_\s]+", s) if w]
    out = []
    for w in parts:
        lw = w.lower()
        out.append(words.get(lw, w if w.isupper() and len(w) > 1 else lw))
    text = " ".join(x for x in out if x).strip()
    return (text[:1].upper() + text[1:]) if text else name
