# PeopleSoft HCM Customization & Business Rules Inventory

A guide to identifying the customizations and business rules in a PeopleSoft HCM system when no vanilla (delivered) baseline instance is available. It covers the approach, prerequisites, how to run the extraction script, and how to turn the output into a business-rules catalog.

---

## 1. Approach

Without a vanilla instance, you can't run a direct object compare. Instead, customizations are detected with three signals read from PeopleTools metadata:

| Signal | Logic | Why it works |
|---|---|---|
| Last updated by | `LASTUPDOPRID <> 'PPLSOFT'` | Oracle stamps delivered objects with the `PPLSOFT` operator ID |
| Custom prefix | Object names such as `XX_%` or `Z_%` | Most organizations use a naming convention for custom objects |
| Customer-reserved ranges | Message sets `>= 20000`; Global Payroll/Absence PINs `>= 50,000,000` | Oracle reserves these ranges for customers |

Business rules are then found in three places:

1. **Code-based rules** in PeopleCode (SaveEdit, FieldEdit, and similar events), Application Engine, Application Packages, and Component Interfaces.
2. **Configuration-based rules** stored as setup data, such as Absence and Global Payroll rules, Time and Labor rules, Benefits eligibility, and approval workflow (AWE).
3. **Non-metadata objects** that PeopleTools doesn't track, such as SQR, COBOL, report templates, and database triggers.

---

## 2. Prerequisites

- **PeopleTools 8.52 or later.** PeopleCode is stored as plain text in `PSPCMTXT.PCTEXT`. On earlier releases it exists only in binary form.
- **A read-only database account** with SELECT access to PeopleTools tables (`PS*`) and, optionally, application tables (`PS_*`).
- **Python 3.9 or later.** Install the database driver:
  - Oracle: `pip install oracledb`
  - SQL Server: `pip install pyodbc`, plus the Microsoft ODBC Driver 18
- **Approval** from your security team before extracting source code or sharing it outside the organization.

---

## 3. Identify your versions first

The PeopleTools release determines which customization features exist in your system and which tables the script can read.

**How to check:**
- In the browser, press **Ctrl+J** on any PeopleSoft page.
- Or run these queries:

```sql
SELECT TOOLSREL FROM PSSTATUS;                            -- PeopleTools release
SELECT * FROM PSRELEASE ORDER BY RELEASEDTTM DESC;        -- application release history
SELECT * FROM PS_MAINTENANCE_LOG;                         -- applied updates and images
```

**Release reference (as of September 2026):**

| Item | Status |
|---|---|
| HCM application | 9.2, updated through PUM images (image 54 posted January 2026; check the PUM home page for newer) |
| PeopleTools 8.62 | Available on-premises since July 2025 (patch 8.62.03) |
| PeopleTools 8.63 | Released on OCI in July 2026; on-premises availability to follow |
| Support | Oracle has committed to supporting PeopleSoft through at least 2036 |

**PeopleTools features that affect customization discovery:**

| Release | Feature | Impact on the inventory |
|---|---|---|
| 8.52 | Plain-text PeopleCode (`PSPCMTXT`) | Required for source extraction |
| 8.54 | Fluid UI | Check for custom Fluid pages, tiles, and homepages |
| 8.55 | PUM Customization Repository and Change Impact Analyzer | Use them if customizations were registered there |
| 8.56 | Event Mapping | Custom code attached without modifying delivered objects; not caught by compares |
| 8.62 | Customization Insights Dashboard | Delivered analysis of customization usage and cost; use it alongside the script |

---

## 4. Run the extraction script

The script `ps_customization_report.py` queries PeopleTools metadata and writes a Markdown report.

### 4.1 Configure (Git Bash on Windows or Ubuntu)

**Oracle:**
```bash
export PS_DB_TYPE=oracle
export PS_DB_DSN=dbhost:1521/HCMPRD
export PS_DB_USER=ro_user
export PS_DB_PASSWORD='********'
export PS_SCHEMA=SYSADM
export PS_CUSTOM_PREFIXES="XX_,Z_"      # your naming conventions
```

**SQL Server:**
```bash
export PS_DB_TYPE=mssql
export PS_DB_CONNSTR="DRIVER={ODBC Driver 18 for SQL Server};SERVER=dbhost,1433;DATABASE=HCMPRD;UID=ro_user;PWD=********;TrustServerCertificate=yes"
export PS_SCHEMA=dbo
export PS_CUSTOM_PREFIXES="XX_,Z_"
```

To keep the password out of your shell history, put these variables in an `.env` file that is listed in `.gitignore`, and load it with `set -a; source .env; set +a`.

### 4.2 Run

```bash
python ps_customization_report.py --out customization_report.md --include-source
```

| Option | Default | Purpose |
|---|---|---|
| `--out` | `customization_report.md` | Output file |
| `--max-rows` | 500 | Row cap per category table |
| `--include-source` | off | Append custom PeopleCode source |
| `--max-source-lines` | 300 | Line cap per PeopleCode program |

If a table or column doesn't exist on your release, that section is marked **skipped** and the rest of the report still runs.

### 4.3 What the report contains

- **Summary** of customized object counts by category.
- **Object inventories** for records, fields, pages, components, menus, Application Engine programs, Application Packages, Component Interfaces, SQL objects, public queries, Integration Broker service operations, permission lists, roles, and database triggers.
- **Custom message catalog** (sets 20000 and up), which is often the plainest statement of your business rules.
- **Global Payroll/Absence custom elements** (PIN numbers 50,000,000 and up).
- **PeopleCode business-rule signals.** Every custom program is listed with its event (SaveEdit, SavePreChange, FieldChange, RowInit, and so on) and counts of `Error`/`Warning` validations, SQL calls, App Engine and Component Interface calls, Integration Broker calls, and workflow triggers.
- **Validation rules**, meaning the extracted `Error`/`Warning` lines, with `MsgGet` references resolved to their message text.
- **PeopleCode source appendix**, if `--include-source` is set.

The program path ends with the event name. For example:
- `JOB.EMPLID.SaveEdit` is record field PeopleCode.
- `JOB_DATA.GBL.JOB.SavePreChange` is component record PeopleCode.
- `JOB_DATA.GBL.SavePostChange` is component-level PeopleCode.

---

## 5. Validate the output

Check these before trusting the results:

1. **Completeness of PeopleCode text.** Compare the row counts of `PSPCMTXT` and `PSPCMPROG` (where `PROGSEQ = 0`). A large gap means some programs have no text on upgraded systems.
2. **False positives.** Delivered objects that an administrator opened and re-saved will appear as customized. Look for delivered names with no real change in logic.
3. **False negatives.** Customizations migrated under the `PPLSOFT` ID will be missed. Cross-check against project lists in `PSPROJECTITEM` and your change-management records.
4. **Prefix coverage.** Confirm that all historical naming conventions are listed in `PS_CUSTOM_PREFIXES`.

---

## 6. Manual checks the script doesn't cover

| Area | Where to look |
|---|---|
| Event Mapping (8.56+) | PeopleTools > Portal > Related Content Service > Manage Related Content Service (Event Mapping tab) |
| Page and Field Configurator | Enterprise Components > Page and Field Configurator |
| Drop Zones, Activity Guides, Fluid homepages and tiles | PeopleTools > Portal structure and content, and component configuration pages |
| Approval workflow (AWE) | Enterprise Components > Approvals > Approval Process Setup |
| Absence, Global Payroll, Time and Labor, and Benefits rules | Module setup pages, or export setup tables with PS Query |
| SQR, COBOL, and report templates | Diff `PS_CUST_HOME` against the delivered `PS_HOME` (see below) |
| Database views, triggers, and stored procedures | The database data dictionary (triggers are included in the report) |
| Integration handlers and routings | PeopleTools > Integration Broker > Integration Setup |

**Diffing file-system objects with Git:**
```bash
mkdir ps-baseline && cd ps-baseline && git init
cp -r /path/to/PS_HOME/sqr /path/to/PS_HOME/src/cbl .   # delivered files
git add . && git commit -m "delivered baseline"
cp -r /path/to/PS_CUST_HOME/sqr /path/to/PS_CUST_HOME/src/cbl .   # customized files
git diff --stat
```

---

## 7. Build the business-rules catalog

1. Review `customization_report.md` for sensitive data, such as hard-coded employee IDs, credentials, or personal information in PeopleCode or messages. Remove it before sharing.
2. Upload the report to Claude and ask for a business-rules catalog grouped by module. For each rule, the catalog can include:
   - the rule in plain English
   - the triggering component or page and the event
   - its enforcement type (hard error, warning, default, or derivation)
   - its dependencies (tables, App Engine programs, integrations)
   - its upgrade risk and whether it could be replaced by delivered functionality
3. Validate the catalog with functional owners for HR, Benefits, Payroll, and Absence.
4. Store the report, catalog, and script in a GitHub repository so the inventory can be rerun and compared after each PUM image or PeopleTools upgrade.

---

## 8. Limitations

- Detection is heuristic. It gives a strong starting inventory, not a certified list of every customization.
- Configuration-based rules require functional review. Metadata alone doesn't explain intent.
- Table and column names can vary slightly between PeopleTools releases. Skipped sections indicate where the queries need adjusting for your release.
