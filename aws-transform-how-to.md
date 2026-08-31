# Importing AWS Transform Discovery Tool Data (from S3) into AWS Transform

**Scenario:** The AWS Transform discovery tool OVA ran on-premises against vCenter, the export
(`discovery_tool_export.zip`) was downloaded, and it now sits in an Amazon S3 bucket you own.
Goal: get that inventory into an AWS Transform **VMware migration** job.

---

## 1. The key point about "importing from S3"

AWS Transform does **not** have a "point at my S3 bucket and ingest" control for on-premises
discovery data. Ingestion happens in the **AWS Transform web experience**, in the
**Discover on-premises data** step of the Job Plan, by **uploading the export file** into the job.

Two different S3 buckets are involved — don't confuse them:

| Bucket | Who owns it | Purpose |
|---|---|---|
| Your staging bucket | You created it | Where you parked `discovery_tool_export.zip`. Not read directly by AWS Transform. |
| Discovery-account bucket | Created **by AWS Transform** when you set up the discovery connector | Where AWS Transform stores inventory data, dependency mappings, wave plans, and application groupings. |

So the practical flow is: **S3 → local workstation → upload into the AWS Transform job**.
Your bucket remains useful as the archive/system-of-record copy and for re-uploads.

---

## 2. Accepted data formats

AWS Transform accepts:

- **AWS Transform discovery tool** export — CSV + JSON inside a **ZIP**
- AWS Migration Evaluator collector output
- **RVTools** — Excel (`.xlsx`) or a ZIP of CSVs
- **modelizeIT** — CSV in ZIP
- **AWS Migration Portfolio Assessment (MPA)** format exports (e.g. Cloudamize)

Rules that bite people:

- The **primary server file** can be uploaded on its own.
- **Supplementary files** (network connections, performance, database) are only processed when
  they are inside the **ZIP with the server files** — do not unzip and upload loose CSVs unless
  you only care about the server list.
- Upload the **whole ZIP**. The export holds up to **30 days** of collected data.
- Re-uploading is safe: AWS Transform **de-duplicates records across uploads** and merges updates.

---

## 3. Prerequisites

- AWS Transform enabled, with an **IAM Identity Center** user/group assigned to the AWS Transform
  web experience.
- A **workspace** in AWS Transform.
- Permission to create the **discovery connector** (or an admin who can approve the connection
  request for the discovery account).
- KMS: AWS Transform needs `kms:DescribeKey`, `kms:GenerateDataKey`, `kms:Decrypt` if you use a
  customer-managed key for the discovery bucket.
- Local: AWS CLI v2 + credentials with `s3:GetObject` / `s3:ListBucket` on your staging bucket.

---

## 4. Step-by-step

### Step 1 — Pull the export down from your S3 bucket

Git Bash on Windows 11 (or Ubuntu/WSL):

```bash
export BUCKET="my-discovery-staging-bucket"
export PREFIX="vmware/discovery/"
export DEST="$HOME/aws-transform-import"

mkdir -p "$DEST"

# See what's there
aws s3 ls "s3://${BUCKET}/${PREFIX}" --human-readable

# Pull the export
aws s3 cp "s3://${BUCKET}/${PREFIX}discovery_tool_export.zip" "$DEST/" 
```

If the object is SSE-KMS encrypted, your principal also needs `kms:Decrypt` on that key.

### Step 2 — Validate the ZIP before uploading

```bash
cd "$DEST"
unzip -l discovery_tool_export.zip | head -50
```

You should see the CSV/JSON payload plus an `mpa_exports/` directory containing
`vmware_data_mpa.csv`. **Do not repackage or rename anything** — format auto-detection keys off
the file names and structure. Confirm the data reflects the current estate; a stale or partial
export produces poor application grouping and wave plans.

Optional Python validation (boto3 + zipfile), useful if you want to script this in a pipeline:

```python
#!/usr/bin/env python3
"""Fetch and sanity-check an AWS Transform discovery tool export from S3."""
import zipfile
from pathlib import Path

import boto3

BUCKET = "my-discovery-staging-bucket"
KEY = "vmware/discovery/discovery_tool_export.zip"
DEST = Path.home() / "aws-transform-import" / "discovery_tool_export.zip"

DEST.parent.mkdir(parents=True, exist_ok=True)
boto3.client("s3").download_file(BUCKET, KEY, str(DEST))

with zipfile.ZipFile(DEST) as zf:
    bad = zf.testzip()
    if bad:
        raise SystemExit(f"Corrupt entry in archive: {bad}")
    names = zf.namelist()

print(f"{DEST} OK — {len(names)} entries, {DEST.stat().st_size / 1e6:.1f} MB")
for expected in ("mpa_exports/vmware_data_mpa.csv",):
    print(f"  {expected}: {'found' if any(n.endswith(expected) for n in names) else 'MISSING'}")
```

### Step 3 — Open (or create) the VMware migration job

1. Sign in to the **AWS Transform web experience** with your IAM Identity Center credentials.
2. Open your **workspace**.
3. Start a job and choose the **VMware migration** job type (or open the existing job).

### Step 4 — Connect the discovery account

In the **Job Plan** pane, expand **Connect discovery account** → **Create or select connectors**.

- Reuse an existing connector from the **Collaboration** tab (**Use connector**), or create a new
  one for the target account/Region.
- If a connector is greyed out, its version is incompatible with the job type you selected.
- Choose **Send to AWS Transform**. For a new connector, copy the verification link, have an
  administrator of the discovery account approve it, then send.

AWS Transform creates an S3 bucket in that account for the job artifacts.

> **Security note:** that bucket is created **without SecureTransport (TLS-only) enforcement**.
> If your controls require `aws:SecureTransport` denial of plaintext access, add that statement to
> the bucket policy yourself after creation.

### Step 5 — Upload the discovery data

1. In the **Job Plan**, expand **Discover on-premises data**.
2. Choose the option to share/upload your on-premises data and select
   `discovery_tool_export.zip` from `$DEST`.
3. Confirm the upload. AWS Transform then auto-detects the format, parses and extracts entity
   records, de-duplicates across files, and validates data quality.

For a **directional migration business case only**, you can instead upload the ZIP to
**Migration assessment**, or unzip and upload `mpa_exports/vmware_data_mpa.csv`.

### Step 6 — Verify the ingest

1. Expand **Discover on-premises data** → **Inventory readiness summary**.
2. Check server counts against what the discovery tool reported on-prem.
3. Use the **chat** to interrogate the data, e.g.:
   - "How many servers were ingested, and from which source files?"
   - "Break down the inventory by operating system and version."
   - "Which servers are missing performance or network connection data?"
4. Fix problems by **re-uploading** corrected data — records are merged automatically. You can also
   remove a previously uploaded file if you no longer want that inventory in scope.

### Step 7 — Continue the job

Once the inventory is accepted, move on through the Job Plan: application grouping, wave planning,
network conversion (VMware → Amazon VPC), and EC2 instance recommendations.

---

## 5. Incremental / ongoing collection

The discovery tool keeps running after the first collection: **VMware discovery hourly at :00 UTC**,
**Hyper-V hourly at :20 UTC**. Practical pattern:

1. Let it run **at least 2 weeks** so performance data supports right-sizing (a run of only a few
   hours gives you an inventory, not a sizing recommendation).
2. Download a fresh `discovery_tool_export.zip`, push it to S3 with a dated key, e.g.
   `s3://bucket/vmware/discovery/2026-09-01/discovery_tool_export.zip`.
3. Re-upload into the job. De-duplication handles the overlap.

Suggested archival helper:

```bash
STAMP=$(date -u +%Y-%m-%d)
aws s3 cp discovery_tool_export.zip \
  "s3://${BUCKET}/vmware/discovery/${STAMP}/discovery_tool_export.zip" \
  --sse aws:kms --sse-kms-key-id alias/transform-discovery
```

Enable S3 versioning and a lifecycle rule on the staging prefix — these exports contain hostnames,
IPs, credentials metadata and topology, so treat them as sensitive.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Servers appear but no network dependency or performance data | Loose CSVs were uploaded instead of the ZIP. Supplementary files are only processed inside the ZIP. |
| Format not recognised | ZIP was repackaged or files renamed. Re-download the original export and upload untouched. |
| `AccessDenied` on `aws s3 cp` | Missing `s3:GetObject`, or SSE-KMS key policy doesn't grant `kms:Decrypt` to your principal. |
| Connector greyed out | Connector version incompatible with the selected job type — create a new connector. |
| Connector stuck pending | The discovery-account administrator hasn't approved the verification link. |
| Server count lower than expected | vCenter account lacks Read/View on parts of the inventory, or OS credentials failed for some VMs — check the discovery tool's collection status per module. |
| Sizing recommendations look generic | Not enough performance history collected; let the tool run longer and re-upload. |

---

## 7. Reference

- Discover source data — <https://docs.aws.amazon.com/transform/latest/userguide/transform-vmware-discover-source-data.html>
- Discovery tool overview — <https://docs.aws.amazon.com/transform/latest/userguide/discovery-tool.html>
- Discovery tool data collection — <https://docs.aws.amazon.com/transform/latest/userguide/discovery-tool-data-collection.html>
- Connect discovery account — <https://docs.aws.amazon.com/transform/latest/userguide/transform-vmware-connect-discovery-account.html>
- Guidance for automated setup of AWS Transform for VMware — <https://github.com/aws-solutions-library-samples/guidance-for-automated-setup-of-aws-transform>
