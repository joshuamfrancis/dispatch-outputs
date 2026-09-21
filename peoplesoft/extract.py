#!/usr/bin/env python3
"""
ps_customization_report.py

Extracts customization metadata and custom PeopleCode from a PeopleSoft HCM
database (no vanilla baseline required) and writes a Markdown report.

Detection heuristics (no baseline):
  1. LASTUPDOPRID <> 'PPLSOFT'  (Oracle-delivered objects are stamped PPLSOFT)
  2. Object names matching your custom prefixes (e.g. XX_, Z_)
  3. Customer-reserved ranges: message sets >= 20000, GP/Absence PINs >= 50,000,000

Requirements:
  PeopleTools 8.52+ (PeopleCode plain text stored in PSPCMTXT.PCTEXT)
  pip install oracledb        # Oracle
  pip install pyodbc          # SQL Server

Environment variables:
  PS_DB_TYPE          oracle | mssql              (default: oracle)
  PS_DB_USER / PS_DB_PASSWORD
  PS_DB_DSN           Oracle only, e.g. dbhost:1521/HCMPRD
  PS_DB_CONNSTR       SQL Server only, full ODBC connection string
  PS_SCHEMA           e.g. SYSADM (Oracle) or dbo (SQL Server); optional
  PS_CUSTOM_PREFIXES  comma-separated, e.g. "XX_,Z_"; optional

Usage (Git Bash / Ubuntu):
  python ps_customization_report.py --out customization_report.md --include-source
"""
import argparse
import datetime as dt
import os
import re
import sys
from collections import defaultdict

# PSPCMPROG.OBJECTID1 -> object type
OBJECT_TYPES = {1: "Record", 3: "Menu", 9: "Page", 10: "Component",
                60: "Message", 66: "App Engine", 74: "Component Interface",
                104: "App Package"}

PCODE_FLAGS = {
    "Errors": re.compile(r"^\s*Error\b", re.I | re.M),
    "Warnings": re.compile(r"^\s*Warning\b", re.I | re.M),
    "SQL": re.compile(r"\b(SQLExec|CreateSQL|GetSQL|SQL\.[A-Z_0-9]+)\b", re.I),
    "AE": re.compile(r"\bCallAppEngine\b", re.I),
    "CI": re.compile(r"\bGetCompIntfc\b", re.I),
    "IB": re.compile(r"%IntBroker\b", re.I),
    "Workflow": re.compile(r"\b(TriggerBusinessEvent|EOAW_CORE|PTAF_CORE)\b", re.I),
}
RULE_LINE_RE = re.compile(r"^\s*(Error|Warning)\b.*$", re.I | re.M)
MSG_RE = re.compile(r"\bMsgGet(?:Text|ExplainText)?\s*\(\s*(\d+)\s*,\s*(\d+)", re.I)


def env(name, required=True):
    val = os.getenv(name, "").strip()
    if required and not val:
        sys.exit(f"Missing required environment variable: {name}")
    return val


def connect(db_type):
    if db_type == "oracle":
        import oracledb
        oracledb.defaults.fetch_lobs = False  # return CLOBs (PCTEXT) as str
        return oracledb.connect(user=env("PS_DB_USER"), password=env("PS_DB_PASSWORD"),
                                dsn=env("PS_DB_DSN"))
    if db_type == "mssql":
        import pyodbc
        return pyodbc.connect(env("PS_DB_CONNSTR"))
    sys.exit(f"Unsupported PS_DB_TYPE: {db_type}")


def custom_cond(name_col, prefixes, oprid_col="LASTUPDOPRID"):
    parts = [f"{oprid_col} <> 'PPLSOFT'"] if oprid_col else []
    for p in prefixes:
        esc = p.replace("_", "\\_")
        parts.append(f"{name_col} LIKE '{esc}%' ESCAPE '\\'")
    return "(" + " OR ".join(parts) + ")" if parts else "(1=1)"


def run(cur, sql, max_rows=None):
    cur.execute(sql)
    cols = [d[0].upper() for d in cur.description]
    rows = []
    while True:
        batch = cur.fetchmany(1000)
        if not batch:
            break
        rows.extend(dict(zip(cols, r)) for r in batch)
        if max_rows and len(rows) > max_rows:
            return cols, rows[:max_rows], True
    return cols, rows, False


def md_cell(v, limit=200):
    if v is None:
        return ""
    s = str(v).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()
    return s if len(s) <= limit else s[:limit] + "…"


def md_table(cols, rows):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(md_cell(r.get(c)) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def build_categories(t, cc, db_type, schema):
    cats = [
        ("Records (tables/views)", f"SELECT RECNAME, RECDESCR, RECTYPE, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSRECDEFN')} WHERE {cc('RECNAME')} ORDER BY RECNAME"),
        ("Fields", f"SELECT FIELDNAME, FIELDTYPE, LENGTH, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSDBFIELD')} WHERE {cc('FIELDNAME')} ORDER BY FIELDNAME"),
        ("Pages", f"SELECT PNLNAME, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSPNLDEFN')} WHERE {cc('PNLNAME')} ORDER BY PNLNAME"),
        ("Components", f"SELECT PNLGRPNAME, MARKET, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSPNLGRPDEFN')} WHERE {cc('PNLGRPNAME')} ORDER BY PNLGRPNAME"),
        ("Menus", f"SELECT MENUNAME, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSMENUDEFN')} WHERE {cc('MENUNAME')} ORDER BY MENUNAME"),
        ("Application Engine programs", f"SELECT AE_APPLID, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSAEAPPLDEFN')} WHERE {cc('AE_APPLID')} ORDER BY AE_APPLID"),
        ("Application Packages", f"SELECT PACKAGEROOT, QUALIFYPATH, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSPACKAGEDEFN')} WHERE {cc('PACKAGEROOT')} ORDER BY PACKAGEROOT"),
        ("Component Interfaces", f"SELECT BCNAME, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSBCDEFN')} WHERE {cc('BCNAME')} ORDER BY BCNAME"),
        ("SQL objects", f"SELECT SQLID, SQLTYPE, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSSQLDEFN')} WHERE {cc('SQLID')} ORDER BY SQLID"),
        ("Public queries", f"SELECT QRYNAME, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSQRYDEFN')} WHERE OPRID = ' ' AND {cc('QRYNAME')} ORDER BY QRYNAME"),
        ("Integration Broker service operations", f"SELECT IB_OPERATIONNAME, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSOPERATION')} WHERE {cc('IB_OPERATIONNAME')} ORDER BY IB_OPERATIONNAME"),
        ("Permission lists", f"SELECT CLASSID, CLASSDEFNDESC, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSCLASSDEFN')} WHERE {cc('CLASSID')} ORDER BY CLASSID"),
        ("Roles", f"SELECT ROLENAME, DESCR, LASTUPDOPRID, LASTUPDDTTM FROM {t('PSROLEDEFN')} WHERE {cc('ROLENAME')} ORDER BY ROLENAME"),
        ("Message catalog (customer sets >= 20000)", f"SELECT MESSAGE_SET_NBR, MESSAGE_NBR, MSG_SEVERITY, MESSAGE_TEXT FROM {t('PSMSGCATDEFN')} WHERE MESSAGE_SET_NBR >= 20000 ORDER BY MESSAGE_SET_NBR, MESSAGE_NBR"),
        ("Global Payroll / Absence elements (customer PINs >= 50,000,000)", f"SELECT PIN_NUM, PIN_NM, PIN_TYPE, COUNTRY, DESCR FROM {t('PS_GP_PIN')} WHERE PIN_NUM >= 50000000 ORDER BY PIN_TYPE, PIN_NM"),
    ]
    if db_type == "oracle" and schema:
        cats.append(("Database triggers", f"SELECT TRIGGER_NAME, TABLE_NAME, TRIGGERING_EVENT, STATUS FROM ALL_TRIGGERS WHERE OWNER = '{schema.upper()}' ORDER BY TABLE_NAME"))
    elif db_type == "mssql":
        cats.append(("Database triggers", "SELECT t.name AS TRIGGER_NAME, OBJECT_NAME(t.parent_id) AS TABLE_NAME, t.is_disabled AS IS_DISABLED FROM sys.triggers t ORDER BY 2"))
    return cats


def extract_peoplecode(cur, t, prefixes):
    keys = [f"OBJECTID{i}" for i in range(1, 8)] + [f"OBJECTVALUE{i}" for i in range(1, 8)]
    join = " AND ".join(f"P.{k} = T.{k}" for k in keys)
    where = custom_cond("T.OBJECTVALUE1", prefixes, "P.LASTUPDOPRID")
    sql = (f"SELECT {', '.join('T.' + k for k in keys)}, P.LASTUPDOPRID, P.LASTUPDDTTM, T.PCTEXT "
           f"FROM {t('PSPCMTXT')} T JOIN {t('PSPCMPROG')} P ON {join} AND P.PROGSEQ = 0 "
           f"WHERE {where}")
    _, rows, _ = run(cur, sql)
    programs = {}
    for r in rows:
        vals = [str(r[f"OBJECTVALUE{i}"]).strip() for i in range(1, 8)
                if r[f"OBJECTVALUE{i}"] and str(r[f"OBJECTVALUE{i}"]).strip()]
        path = ".".join(vals)
        prog = programs.setdefault(path, {
            "path": path,
            "type": OBJECT_TYPES.get(int(r["OBJECTID1"] or 0), f"ObjectID {r['OBJECTID1']}"),
            "event": vals[-1] if vals else "",
            "oprid": r["LASTUPDOPRID"], "updated": r["LASTUPDDTTM"], "chunks": []})
        prog["chunks"].append(r["PCTEXT"] or "")
    for p in programs.values():
        p["text"] = "".join(p.pop("chunks"))
        p["lines"] = p["text"].count("\n") + 1
        for flag, rx in PCODE_FLAGS.items():
            p[flag] = len(rx.findall(p["text"]))
        p["rule_lines"] = [m.group(0).strip()[:200] for m in RULE_LINE_RE.finditer(p["text"])]
        p["msg_refs"] = sorted({(int(a), int(b)) for a, b in MSG_RE.findall(p["text"])})
    return sorted(programs.values(), key=lambda x: x["path"])


def resolve_messages(cur, t, programs):
    sets = sorted({s for p in programs for s, _ in p["msg_refs"]})
    msgs = {}
    for i in range(0, len(sets), 500):
        chunk = ",".join(str(s) for s in sets[i:i + 500])
        _, rows, _ = run(cur, f"SELECT MESSAGE_SET_NBR, MESSAGE_NBR, MESSAGE_TEXT FROM {t('PSMSGCATDEFN')} WHERE MESSAGE_SET_NBR IN ({chunk})")
        for r in rows:
            msgs[(int(r["MESSAGE_SET_NBR"]), int(r["MESSAGE_NBR"]))] = r["MESSAGE_TEXT"]
    return msgs


def main():
    ap = argparse.ArgumentParser(description="PeopleSoft customization inventory -> Markdown")
    ap.add_argument("--out", default="customization_report.md")
    ap.add_argument("--max-rows", type=int, default=500, help="row cap per category table")
    ap.add_argument("--include-source", action="store_true", help="append custom PeopleCode source")
    ap.add_argument("--max-source-lines", type=int, default=300)
    args = ap.parse_args()

    db_type = os.getenv("PS_DB_TYPE", "oracle").lower()
    schema = os.getenv("PS_SCHEMA", "").strip()
    prefixes = [p.strip().upper() for p in os.getenv("PS_CUSTOM_PREFIXES", "").split(",") if p.strip()]
    for p in prefixes:
        if not re.fullmatch(r"[A-Z0-9_]+", p):
            sys.exit(f"Invalid prefix (letters, digits, underscore only): {p}")

    t = lambda n: f"{schema}.{n}" if schema else n
    cc = lambda col: custom_cond(col, prefixes)

    conn = connect(db_type)
    cur = conn.cursor()
    summary, sections = [], []

    for title, sql in build_categories(t, cc, db_type, schema):
        try:
            cols, rows, truncated = run(cur, sql, args.max_rows)
            note = f"truncated at {args.max_rows}" if truncated else ""
            summary.append({"Category": title, "Rows": f"{len(rows)}{'+' if truncated else ''}", "Note": note})
            sections.append(f"## {title}\n\n" + (md_table(cols, rows) if rows else "_None found._"))
            print(f"[ok]   {title}: {len(rows)}{'+' if truncated else ''}")
        except Exception as e:  # table/column may not exist on this release
            summary.append({"Category": title, "Rows": "-", "Note": f"skipped: {str(e)[:120]}"})
            print(f"[skip] {title}: {e}")

    programs, msgs = [], {}
    try:
        programs = extract_peoplecode(cur, t, prefixes)
        msgs = resolve_messages(cur, t, programs)
        summary.append({"Category": "Custom PeopleCode programs", "Rows": str(len(programs)), "Note": ""})
        print(f"[ok]   PeopleCode programs: {len(programs)}")
    except Exception as e:
        summary.append({"Category": "Custom PeopleCode programs", "Rows": "-", "Note": f"skipped: {str(e)[:120]}"})
        print(f"[skip] PeopleCode: {e}")
    conn.close()

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# PeopleSoft Customization Inventory\n",
          f"Generated {now} · DB type: {db_type} · Schema: {schema or '(default)'} · "
          f"Prefixes: {', '.join(prefixes) or '(none)'}\n",
          "> Detection is heuristic (no vanilla baseline): LASTUPDOPRID <> 'PPLSOFT', custom name "
          "prefixes, and customer-reserved number ranges. Delivered objects re-saved by an admin "
          "appear as customized; customizations migrated under PPLSOFT may be missed.\n",
          "## Summary\n", md_table(["Category", "Rows", "Note"], summary), ""]
    md += [s + "\n" for s in sections]

    if programs:
        cols = ["Program", "Type", "Updated by", "Updated", "Lines"] + list(PCODE_FLAGS)
        rows = [{"Program": p["path"], "Type": p["type"], "Updated by": p["oprid"],
                 "Updated": p["updated"], "Lines": p["lines"], **{f: p[f] for f in PCODE_FLAGS}}
                for p in programs]
        md += ["## Custom PeopleCode: business-rule signals\n", md_table(cols, rows), ""]

        md.append("## Validation rules and messages found in PeopleCode\n")
        for p in programs:
            if not (p["rule_lines"] or p["msg_refs"]):
                continue
            md.append(f"### {p['path']}\n")
            md += [f"- `{md_cell(line)}`" for line in p["rule_lines"]]
            for s, n in p["msg_refs"]:
                md.append(f"- Message ({s},{n}): {md_cell(msgs.get((s, n), '(text not found)'))}")
            md.append("")

        if args.include_source:
            md.append("## Appendix: Custom PeopleCode source\n")
            for p in programs:
                lines = p["text"].splitlines()
                body = "\n".join(lines[:args.max_source_lines])
                if len(lines) > args.max_source_lines:
                    body += f"\n/* … truncated, {len(lines) - args.max_source_lines} more lines */"
                md += [f"### {p['path']}\n", "```text", body, "```", ""]

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\nReport written to {args.out}")


if __name__ == "__main__":
    main()
