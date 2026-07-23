# Appian Cloud — Source Control, CI/CD Pipelines & Testing Guide
**Appian 26.6**

---

## Overview

Appian Cloud supports a full DevOps lifecycle through a combination of **deployment packages**, a **REST-based Deployment API** (v3 in 26.6), **connected environment pipelines**, and built-in **testing frameworks**. This document details what can be version-controlled, how to structure CI/CD pipelines, and what testing strategies are available across Development, Test, and Production environments.

> **Reference:** [Deploy to Target Environments — Appian Docs 26.6](https://docs.appian.com/suite/help/26.6/Deploy_to_Target_Environments.html)

---

## What Can Be Source Controlled

Appian does not natively push individual design objects to Git on save — instead, artefacts are grouped into **packages** (ZIP files) that are exported via GUI or API and then committed to a version control system such as GitHub. The following table lists everything that can be packaged and source-controlled.

### Design Objects (inside packages)

| Object Type | Description | Source-Controllable |
|---|---|---|
| **Expression Rules** | Reusable logic functions; the primary unit of testable code in Appian | ✅ Yes |
| **Interfaces** | UI components and form templates built with SAIL | ✅ Yes |
| **Process Models** | Workflow definitions (BPMN-style automated and human tasks) | ✅ Yes |
| **Record Types** | Data model definitions with sync, views, and relationships | ✅ Yes |
| **Web APIs** | RESTful API objects published from Appian | ✅ Yes |
| **Connected Systems** | Integration definitions (REST, JDBC, SFTP, SAP, etc.) | ✅ Yes |
| **Constants** | Named values used across the application | ✅ Yes |
| **Custom Data Types (CDTs)** | Structured data type definitions | ✅ Yes |
| **Groups** | User groups used in role maps and security | ✅ Yes |
| **Document Types** | Document metadata templates | ✅ Yes |
| **Reports / Record List Views** | Configured report and grid definitions | ✅ Yes |
| **Sites & Pages** | Navigation and portal configuration | ✅ Yes |
| **Query Rules** | Saved query definitions | ✅ Yes |
| **Decision Tables** | Rule logic expressed as tables | ✅ Yes |
| **Robotic Task Objects** | RPA task definitions | ✅ Yes |

### Application-Level Artefacts

| Artefact | Description | Source-Controllable |
|---|---|---|
| **Application Configurations** | App-level settings: groups, data stores, record type associations | ✅ Yes (toggle per deployment) |
| **Database Scripts** | DDL/DML SQL files for schema changes | ✅ Yes (bundled into packages, ordered) |
| **Plug-ins** | Third-party or custom Java plug-ins (.jar) | ✅ Yes (bundled into packages) |
| **Import Customization Files (ICF)** | `.properties` files overriding environment-specific values | ✅ Yes (stored in Git alongside packages) |
| **Admin Console Settings** | Infrastructure, deployment config, data sources | ✅ Partial (export manually; import via GUI or API) |

### What Cannot Be Source-Controlled or Deployed Automatically

| Item | Reason |
|---|---|
| API Keys | Security-sensitive; environment-specific |
| SSL/TLS Certificates | Environment-specific; managed in Admin Console |
| User passwords / credentials | Never exported |
| Transactional database data | Not part of packages |
| Environment-specific constants (passwords, URLs) | Must be overridden via ICF per environment |
| Log files / audit trails | Environment-specific runtime data |

---

## Object Types in Depth

### Form Templates (Interfaces / SAIL)

Interfaces are SAIL components — the building blocks of Appian forms, portals, and embedded UIs. They are first-class design objects that are:

- Fully packaged and exported in ZIP format
- Version-controlled at the object level (Appian maintains an internal version history)
- Diffable during Compare & Deploy (changes highlighted field-by-field)
- Testable indirectly via expression rules that populate their inputs

When deploying interfaces, include any dependent expression rules, constants, CDTs, and record types in the same package to avoid missing-precedent errors.

### Workflows (Process Models)

Process models define automated business workflows — task routing, approvals, integrations, subprocess calls. They are:

- Packaged as objects within an application package
- Versioned internally (each deployment creates a new version)
- Compared during inspection to detect structural changes
- Deployed with full role maps (administrator group assignments carry over)

**Important:** In-flight process instances in the target environment continue running on their current process model version. Only new instances started after deployment pick up the new model.

### Configurations (Application Configurations)

Application configurations are non-object settings applied at the app level:

- Primary groups, viewer groups
- Data stores associated with the application
- Record type data sync configuration references
- Portal configuration

They can be selectively included or excluded per deployment using the **Include app configurations** toggle in Compare & Deploy. Changes appear highlighted (green = added, red = removed) during review.

### Custom Components (Plug-ins)

Custom plug-ins extend Appian's function library with Java-based components:

- Uploaded to the source environment via the Admin Console
- Added to deployment packages from the Plug-ins tab during Compare & Deploy
- Deployed to target environments with connectivity and permission checks
- Require the `Allow deployments with plug-ins` setting enabled on the target environment

Plug-ins are not included in ZIP exports — they must be deployed separately via Compare & Deploy or the Deployment API, or pre-installed on the target environment directly.

---

## Import Customization Files (ICF) — Environment-Specific Overrides

ICFs are `.properties` files that override object values that vary between environments. They are the primary mechanism for keeping packages environment-agnostic while still applying the right values at deployment time.

Common ICF uses:

```properties
# Override a constant value for the target environment
/applications/MyApp/design/constants/API_BASE_URL.value=https://api.prod.example.com

# Override a connected system URL
/applications/MyApp/design/connectedSystems/PaymentGateway.baseUrl=https://payments.prod.example.com

# Trigger a record type sync after a database script changes the underlying table
/applications/MyApp/design/recordTypes/CustomerRecord.triggerSync=true
```

ICFs are generated as templates by Appian during export. The template is environment-agnostic; you fill in environment-specific values and store one ICF per environment in Git:

```
/iac/
  dev.properties
  test.properties
  prod.properties
packages/
  MyApp-sprint-42.zip
database/
  V42__add_customer_table.sql
```

---

## Promoting Across Environments: Dev → Test → Prod

### Connected Environments

Before any pipeline can work, environments must be connected in the Admin Console:

1. In the **source** environment Admin Console → Infrastructure → Add target environment (URL + service account credentials).
2. Enable **incoming deployments** on each target environment.
3. Optionally enable **deployment review** on Test and Production (creates an approval gate).

### Deployment Paths

```
Development ──────────────────────▶ Test ──────────────────────▶ Production
   │                                  │                               │
   │  Compare & Deploy (GUI)          │  Reuse deployed package       │  Requires reviewer approval
   │  or Deployment API (CI/CD)       │  or Deployment API            │  (configured in Admin Console)
   │                                  │                               │
   └── Package exported to Git ───────┴── Same ZIP reused ───────────┘
```

**Key principle:** The same package ZIP deployed to Test is the exact one promoted to Production — no re-export. This guarantees environment parity. Only the ICF changes per environment.

### Compare and Deploy — GUI Workflow

For ad-hoc or release deployments from within Appian:

1. Go to Build view → **COMPARE AND DEPLOY**
2. Select target environment
3. Select package(s) or entire application
4. Review object statuses (New / Changed / Conflict / Unchanged)
5. Inspect — check for security warnings, failing test cases, missing precedents
6. Upload appropriate ICF for the target environment
7. Deploy (or Export if no direct deployment permission)

### Reusing a Package Across Environments

Once a package is successfully deployed to Test, it can be promoted to Production from the **Deploy view** without re-exporting:

1. In Test environment → **Deploy** view → Incoming tab → select the deployment
2. Click **DEPLOY TO ANOTHER ENVIRONMENT**
3. Select Production
4. Upload Production ICF
5. Deploy (subject to reviewer approval if configured)

---

## CI/CD Pipeline with the Deployment REST API

The Deployment REST API (v3 in Appian 26.6) enables fully automated pipelines via Jenkins, GitHub Actions, or any CI/CD tool.

### API Base URL

```
https://<your-appian-domain>/suite/deployment-management/v3
```

### Authentication

All calls require an API key tied to a service account with Administrator role:

```bash
-H "appian-api-key: <your-api-key>"
```

### Full Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline                           │
│                                                                 │
│  1. EXPORT from Dev                                             │
│     POST /deployments  (Action-Type: export)                    │
│     → package UUID returned                                     │
│                                                                 │
│  2. POLL for export completion                                  │
│     GET /deployments/{uuid}                                     │
│     → status: SUCCEEDED                                         │
│                                                                 │
│  3. DOWNLOAD package ZIP                                        │
│     GET /deployments/{uuid}/package                             │
│     → commit ZIP + ICF templates to Git                         │
│                                                                 │
│  4. INSPECT against Test environment                            │
│     POST /inspections  (upload ZIP)                             │
│     → inspection UUID                                           │
│                                                                 │
│  5. POLL inspection results                                     │
│     GET /inspections/{uuid}                                     │
│     → check for WARNINGS / ERRORS / failing test cases         │
│     → fail pipeline if blocking issues found                    │
│                                                                 │
│  6. DEPLOY to Test                                              │
│     POST /deployments  (Action-Type: import, upload ZIP + ICF)  │
│     → deployment UUID                                           │
│                                                                 │
│  7. POLL deployment status                                      │
│     GET /deployments/{uuid}                                     │
│     → SUCCEEDED                                                 │
│                                                                 │
│  8. RUN post-deployment tests (smoke tests, rule tests)         │
│                                                                 │
│  9. APPROVAL GATE (manual or automated)                         │
│                                                                 │
│  10. DEPLOY to Production                                       │
│      POST /deployments  (Action-Type: import, same ZIP + prod ICF) │
│      → deployment UUID                                          │
│                                                                 │
│  11. POLL + verify Production deployment                        │
│      GET /deployments/{uuid}                                    │
└─────────────────────────────────────────────────────────────────┘
```

### GitHub Actions Pipeline Example

```yaml
# .github/workflows/appian-deploy.yml
name: Appian Deploy Pipeline

on:
  push:
    branches: [release]

jobs:
  export:
    runs-on: ubuntu-latest
    outputs:
      deployment_uuid: ${{ steps.export.outputs.uuid }}
    steps:
      - name: Export package from Dev
        id: export
        run: |
          RESPONSE=$(curl -s -X POST \
            "https://${{ secrets.APPIAN_DEV_DOMAIN }}/suite/deployment-management/v3/deployments" \
            -H "appian-api-key: ${{ secrets.APPIAN_DEV_API_KEY }}" \
            -H "Action-Type: export" \
            -H "Content-Type: multipart/form-data" \
            -F "json={\"packageUUIDs\":[\"${{ secrets.PACKAGE_UUID }}\"]};type=application/json")
          UUID=$(echo $RESPONSE | jq -r '.uuid')
          echo "uuid=$UUID" >> $GITHUB_OUTPUT

      - name: Wait for export and download
        run: |
          UUID=${{ steps.export.outputs.uuid }}
          for i in {1..20}; do
            STATUS=$(curl -s \
              "https://${{ secrets.APPIAN_DEV_DOMAIN }}/suite/deployment-management/v3/deployments/$UUID" \
              -H "appian-api-key: ${{ secrets.APPIAN_DEV_API_KEY }}" | jq -r '.status')
            [ "$STATUS" == "SUCCEEDED" ] && break
            sleep 15
          done
          curl -o package.zip \
            "https://${{ secrets.APPIAN_DEV_DOMAIN }}/suite/deployment-management/v3/deployments/$UUID/package" \
            -H "appian-api-key: ${{ secrets.APPIAN_DEV_API_KEY }}"

      - name: Commit package to Git
        run: |
          git config user.email "ci@example.com"
          git config user.name "CI Bot"
          cp package.zip packages/latest.zip
          git add packages/latest.zip
          git commit -m "ci: export package from Dev [skip ci]"
          git push

  deploy-test:
    needs: export
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Inspect package against Test
        run: |
          RESPONSE=$(curl -s -X POST \
            "https://${{ secrets.APPIAN_TEST_DOMAIN }}/suite/deployment-management/v3/inspections" \
            -H "appian-api-key: ${{ secrets.APPIAN_TEST_API_KEY }}" \
            -F "package=@packages/latest.zip")
          INSPECT_UUID=$(echo $RESPONSE | jq -r '.uuid')
          # Poll for results
          for i in {1..10}; do
            RESULT=$(curl -s \
              "https://${{ secrets.APPIAN_TEST_DOMAIN }}/suite/deployment-management/v3/inspections/$INSPECT_UUID" \
              -H "appian-api-key: ${{ secrets.APPIAN_TEST_API_KEY }}")
            STATUS=$(echo $RESULT | jq -r '.status')
            [ "$STATUS" == "COMPLETED" ] && break
            sleep 10
          done
          # Fail if inspection found errors
          ERRORS=$(echo $RESULT | jq '.errors | length')
          [ "$ERRORS" -gt 0 ] && echo "Inspection errors found" && exit 1

      - name: Deploy to Test
        run: |
          curl -s -X POST \
            "https://${{ secrets.APPIAN_TEST_DOMAIN }}/suite/deployment-management/v3/deployments" \
            -H "appian-api-key: ${{ secrets.APPIAN_TEST_API_KEY }}" \
            -H "Action-Type: import" \
            -F "package=@packages/latest.zip" \
            -F "icf=@iac/test.properties"

  deploy-prod:
    needs: deploy-test
    runs-on: ubuntu-latest
    environment: production   # requires manual approval in GitHub Environments
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Production
        run: |
          curl -s -X POST \
            "https://${{ secrets.APPIAN_PROD_DOMAIN }}/suite/deployment-management/v3/deployments" \
            -H "appian-api-key: ${{ secrets.APPIAN_PROD_API_KEY }}" \
            -H "Action-Type: import" \
            -F "package=@packages/latest.zip" \
            -F "icf=@iac/prod.properties"
```

### Jenkins Pipeline (Declarative)

```groovy
pipeline {
    agent any
    environment {
        DEV_DOMAIN  = credentials('appian-dev-domain')
        DEV_KEY     = credentials('appian-dev-api-key')
        TEST_DOMAIN = credentials('appian-test-domain')
        TEST_KEY    = credentials('appian-test-api-key')
        PROD_DOMAIN = credentials('appian-prod-domain')
        PROD_KEY    = credentials('appian-prod-api-key')
        PACKAGE_UUID = credentials('appian-package-uuid')
    }
    stages {
        stage('Export from Dev') {
            steps {
                sh '''
                  curl -X POST \
                    "https://${DEV_DOMAIN}/suite/deployment-management/v3/deployments" \
                    -H "appian-api-key: ${DEV_KEY}" \
                    -H "Action-Type: export" \
                    -H "Content-Type: application/json" \
                    -d "{\"packageUUIDs\":[\"${PACKAGE_UUID}\"]}" \
                    -o export_response.json
                  cat export_response.json
                '''
            }
        }
        stage('Inspect for Test') {
            steps {
                sh 'curl -X POST "https://${TEST_DOMAIN}/suite/deployment-management/v3/inspections" ...'
            }
        }
        stage('Deploy to Test') {
            steps {
                sh 'curl -X POST "https://${TEST_DOMAIN}/suite/deployment-management/v3/deployments" ...'
            }
        }
        stage('Smoke Tests') {
            steps {
                sh 'python3 tests/smoke_tests.py --env test'
            }
        }
        stage('Approval') {
            steps {
                input message: 'Approve deployment to Production?', ok: 'Deploy'
            }
        }
        stage('Deploy to Production') {
            steps {
                sh 'curl -X POST "https://${PROD_DOMAIN}/suite/deployment-management/v3/deployments" ...'
            }
        }
    }
}
```

---

## Testing in Appian

### 1. Expression Rule Unit Tests (Built-In)

Expression rules — the core logic units in Appian — have a native test case framework. Test cases are stored with the rule object and travel with the package through environments.

**Capabilities:**
- Define named test cases with specific inputs and expected outputs
- Three assertion types: match output value, expression evaluates to true, completes without errors
- Test cases flagged as failing or outdated block deployment via inspection warnings
- AI Copilot (Appian 26.x) generates up to 15 test cases automatically using rule context

**Testing strategy for expression rules:**

```
Rule: validateEmailAddress(address: Text) → Boolean

Test cases:
  ✅ valid_standard_email        input: "user@example.com"   → true
  ✅ valid_plus_address          input: "user+tag@example.com" → true
  ❌ missing_at_sign             input: "userexample.com"    → false
  ❌ double_at_sign              input: "user@@example.com"  → false
  ❌ null_input                  input: null                 → false
  ❌ empty_string                input: ""                   → false
  ❌ spaces_in_address           input: "user @example.com"  → false
  ✅ output_type_is_boolean      assert: typeof(result) = "Boolean"
```

**Running tests in bulk (pre-deployment):**

Inside Appian Designer: Settings → **Manage Test Cases** → Run All Rules.

Programmatically via smart service in a process model:
- **Start All Rule Tests** smart service — runs all test cases across the application
- **Start Application Rule Tests** smart service — scoped to a specific application

Results are surfaced during Compare & Deploy inspection and will raise warnings for failing or outdated test cases.

---

### 2. Pre-Deployment Inspection

The inspection step in Compare & Deploy (and in the API `/inspections` endpoint) performs automated checks before every deployment:

| Check | What it catches |
|---|---|
| **Security warnings** | Objects with overly permissive role maps (e.g., Everyone group has edit access) |
| **Missing precedents** | Objects in the package that reference design objects not present in the package or target environment |
| **Failing test cases** | Expression rules in the package with one or more test cases that currently fail |
| **Outdated test cases** | Test cases that haven't been run since the rule last changed |
| **Deployment errors** | Breaking issues in object definitions that would cause import failure |

Warnings are non-blocking (informational). Errors block deployment until resolved.

---

### 3. Post-Deployment Process

You can attach a **post-deployment process model** to an application. It runs automatically after every successful deployment and can orchestrate any post-deployment validation logic.

Common uses:

```
Post-deployment process:
  ├── Trigger record type sync (for any updated synced record types)
  ├── Send Slack/email notification to the team
  ├── Run a set of smoke test Web API calls and assert responses
  ├── Warm up caches or pre-populate lookup tables
  └── Update a deployment registry (e.g., write to a tracking database)
```

Configure via: Application Settings → Post-Deployment Process.

---

### 4. Smoke Testing via External HTTP Calls

Appian Web APIs are RESTful endpoints exposed from Appian. You can invoke them as part of a CI/CD pipeline to verify the application is functioning post-deployment.

```python
# tests/smoke_tests.py
import requests
import sys

BASE_URL = f"https://{sys.argv[2]}.appian.com/suite/webapi"
API_KEY = sys.argv[3]
HEADERS = {"appian-api-key": API_KEY}

def test_health_check():
    r = requests.get(f"{BASE_URL}/health", headers=HEADERS)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"

def test_lookup_returns_data():
    r = requests.get(f"{BASE_URL}/customers?limit=1", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert len(data["customers"]) > 0, "No customers returned"

def test_submit_creates_process():
    payload = {"name": "CI Test Case", "email": "ci@example.com"}
    r = requests.post(f"{BASE_URL}/onboarding/submit", json=payload, headers=HEADERS)
    assert r.status_code == 201, f"Submit failed: {r.status_code}"

if __name__ == "__main__":
    test_health_check()
    test_lookup_returns_data()
    test_submit_creates_process()
    print("All smoke tests passed ✅")
```

---

### 5. Process Model Testing

Process models don't have a native unit test framework equivalent to expression rule test cases. Testing strategies include:

- **Start a test instance** manually in Dev/Test using known input data and trace execution in the Process Modeler
- **Use test record data** in Test environment populated by a separate test data setup script
- **Post-deployment process** can start a process model with known inputs and assert on the outcome via a follow-up Web API call
- **Audit logs** in the Admin Console capture process instance errors that can be checked post-deployment

---

### 6. Interface / Form Testing

SAIL interfaces are tested primarily through:

- **Manual testing** in the Appian Designer preview pane during development
- **Expression rule test cases** for any expression rules powering the interface inputs, validations, and display logic
- **User acceptance testing (UAT)** in the Test environment before production promotion
- **Appian RPA** (if licensed) can be configured to drive browser-based form interactions as automated regression tests

---

## Recommended Repository Structure

```
appian-my-application/
├── README.md
├── packages/
│   ├── sprint-42-feature-x.zip        # exported application package
│   └── sprint-43-hotfix-y.zip
├── database/
│   ├── V42__add_customer_table.sql
│   └── V43__add_customer_email_index.sql
├── iac/
│   ├── dev.properties                 # ICF for Development
│   ├── test.properties                # ICF for Test
│   └── prod.properties                # ICF for Production
├── plugins/
│   └── my-custom-plugin-1.0.0.jar
├── admin-console/
│   └── admin-settings-export.zip      # exported manually; imported via Admin Console
├── tests/
│   ├── smoke_tests.py
│   └── integration_tests.py
└── .github/
    └── workflows/
        └── appian-deploy.yml
```

---

## Environment Promotion Summary

| Stage | Method | ICF | Approval | Test Gates |
|---|---|---|---|---|
| **Dev → Test** | Deployment API (automated on push to `release` branch) | `test.properties` | None | Inspection + expression rule tests |
| **Test → Prod** | Deployment API with reused package | `prod.properties` | Manual (GitHub Environments gate or Admin Console reviewer group) | Smoke tests post-Test deploy |
| **Hotfix → Dev** | Manual Compare & Deploy or API | `dev.properties` | None | Inspection |
| **Hotfix → Prod** | Reuse deployed package from hotfix pipeline | `prod.properties` | Manual | Expedited smoke tests |

---

## Key Limitations to Be Aware Of

- Plug-ins and database scripts are **not included** in ZIP exports — they must be managed and deployed separately.
- Admin Console settings can be imported programmatically but must still be **exported manually**.
- API keys, certificates, and environment credentials are never exported — manage these out-of-band (e.g., AWS Secrets Manager for credentials passed at deploy time).
- In-flight process instances do **not** migrate to a new process model version; they continue on the previous version.
- ICF files are environment-specific and must never be reused from one environment on another without review.
- Multiple-package deployments require a **manually reconciled single ICF** — Appian does not merge them automatically.

---

## References

- [Deploy to Target Environments — Appian 26.6](https://docs.appian.com/suite/help/26.6/Deploy_to_Target_Environments.html)
- [Deployment REST API — Appian 26.6](https://docs.appian.com/suite/help/26.6/Deployment_Rest_API.html)
- [Expression Rule Testing — Appian 26.6](https://docs.appian.com/suite/help/26.6/Expression_Rule_Testing.html)
- [Automated Testing for Expression Rules](https://docs.appian.com/suite/help/26.6/Automated_Testing_for_Expression_Rules.html)
- [Managing Import Customization Files](https://docs.appian.com/suite/help/26.6/Managing_Import_Customization_Files.html)
- [Post-Deployment Process](https://docs.appian.com/suite/help/26.6/post-deployment-process.html)
- [Inspect Deployment Packages](https://docs.appian.com/suite/help/26.6/inspect-deployment-packages.html)
- [DevOps Infrastructure Setup](https://docs.appian.com/suite/help/26.6/admin-infrastructure.html)
- [Deployment Automation — Appian MAX Community](https://community.appian.com/success/w/guide/3328/deployment-automation)

---

*Based on Appian 26.6 documentation. Last updated: 2026-07-23.*
