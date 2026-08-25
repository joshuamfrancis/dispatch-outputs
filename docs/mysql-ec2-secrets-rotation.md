# Windows EC2 MySQL — Secrets Manager Rotation & Audit Logging

CloudFormation template: [`cloudformation/mysql-rotation.yaml`](../cloudformation/mysql-rotation.yaml)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  VPC  (10.0.0.0/16)                                              │
│                                                                  │
│  ┌─────────────────────┐      ┌──────────────────────────────┐  │
│  │  Public Subnet       │      │  Private Subnet              │  │
│  │  10.0.1.0/24         │      │  10.0.2.0/24                 │  │
│  │                      │      │                              │  │
│  │  ┌───────────────┐   │      │  ┌────────────────────────┐  │  │
│  │  │ Windows EC2   │   │      │  │ Lambda (VPC-attached)  │  │  │
│  │  │ MySQL 8.0     │◀──┼──────┼──│ Rotation Function      │  │  │
│  │  │ Port 3306     │   │TCP   │  │ Port 3306 egress only  │  │  │
│  │  └───────────────┘   │      │  └──────────┬─────────────┘  │  │
│  │                      │      │             │ HTTPS           │  │
│  │  ┌───────────────┐   │      │  ┌──────────▼─────────────┐  │  │
│  │  │  NAT Gateway  │◀──┼──────┼──│ Private Route Table    │  │  │
│  │  └───────────────┘   │      │  └────────────────────────┘  │  │
│  └─────────────────────┘      └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
          │ HTTPS
          ▼
  AWS Secrets Manager
  (secret: <stack>/mysql/credentials)
          │
          │ Rotation trigger (schedule or manual)
          ▼
  Lambda invoked with 4 steps:
  createSecret → setSecret → testSecret → finishSecret
          │
          ▼
  CloudTrail → S3 audit bucket (90d → Glacier → 7yr expiry)
  CloudWatch Logs → /aws/lambda/<stack>-secret-rotation
```

---

## What Gets Deployed

| Resource | Purpose |
|---|---|
| VPC + public/private subnets | Network isolation |
| NAT Gateway | Allows Lambda in private subnet to reach Secrets Manager HTTPS |
| EC2 Security Group | Allows MySQL 3306 only from Lambda SG; RDP from admin IP |
| Lambda Security Group | Egress: 3306 to EC2, 443 to internet (NAT) |
| Windows EC2 (Server 2022) | Hosts MySQL 8.0; configured via UserData PowerShell |
| Secrets Manager Secret | JSON: username, password, host, port, dbname, engine |
| Rotation Schedule | Triggers Lambda every N days (default 30) |
| Lambda Function (VPC) | Four-step rotation; requires PyMySQL layer |
| CloudTrail Trail | Captures all Secrets Manager management events to S3 |
| CloudWatch Log Group | Lambda logs retained 90 days |
| CloudWatch Alarm | Fires on any Lambda rotation error |

---

## Prerequisites

### 1. PyMySQL Lambda Layer

The rotation Lambda requires `pymysql`. Create a layer before deploying:

```bash
mkdir -p pymysql-layer/python
pip install pymysql -t pymysql-layer/python/
cd pymysql-layer
zip -r ../pymysql-layer.zip python/
cd ..

# Publish the layer
aws lambda publish-layer-version \
  --layer-name pymysql \
  --compatible-runtimes python3.12 \
  --zip-file fileb://pymysql-layer.zip \
  --query 'LayerVersionArn' --output text
```

Copy the returned ARN — you'll pass it as the `PyMySQLLayerArn` parameter.

### 2. Deploy the Stack

```bash
aws cloudformation deploy \
  --template-file cloudformation/mysql-rotation.yaml \
  --stack-name mysql-rotation-lab \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    DBPassword="YourInitialPassword123!" \
    PyMySQLLayerArn="arn:aws:lambda:us-east-1:123456789012:layer:pymysql:1" \
    RotationIntervalDays=30
```

### 3. Trigger an Immediate Rotation (optional)

```bash
SECRET_ARN=$(aws cloudformation describe-stacks \
  --stack-name mysql-rotation-lab \
  --query "Stacks[0].Outputs[?OutputKey=='SecretARN'].OutputValue" \
  --output text)

aws secretsmanager rotate-secret --secret-id $SECRET_ARN
```

---

## Four-Step Rotation Protocol

Secrets Manager calls the Lambda four times with a different `Step` value each rotation cycle. All four steps must succeed for the rotation to complete.

### Step 1 — `createSecret`
Generates a cryptographically random 32-character password (upper, lower, digit, special chars). Stores it as a new version in `AWSPENDING` stage alongside the existing `AWSCURRENT` version. If `AWSPENDING` already exists (e.g. retry after failure), this step is skipped.

### Step 2 — `setSecret`
Opens a MySQL connection using the current (`AWSCURRENT`) credentials. Issues `ALTER USER ... IDENTIFIED BY` with the new pending password. Both old and new passwords are valid simultaneously at this point.

### Step 3 — `testSecret`
Opens a MySQL connection using the `AWSPENDING` credentials to verify the new password works. Fails the rotation if the connection is refused.

### Step 4 — `finishSecret`
Calls `UpdateSecretVersionStage` to move `AWSCURRENT` to the new version and demote the old version to `AWSPREVIOUS`. Previous version is retained temporarily in case of rollback need.

```
Version lifecycle during rotation:

Before:   v1[AWSCURRENT]
Step 1:   v1[AWSCURRENT]  v2[AWSPENDING]
Step 2:   v1[AWSCURRENT]  v2[AWSPENDING]  ← MySQL accepts both passwords
Step 3:   v1[AWSCURRENT]  v2[AWSPENDING]  ← verified
Step 4:   v1[AWSPREVIOUS] v2[AWSCURRENT]
```

---

## Audit Logging

### CloudTrail — Secrets Manager Management Events

Every Secrets Manager API call is a **management event** captured by CloudTrail automatically. No additional configuration is needed beyond enabling a trail (included in the template).

Logs are written to: `s3://<stack>-audit-<account>-<region>/AWSLogs/<account>/CloudTrail/<region>/YYYY/MM/DD/`

#### Events Generated on Secret Rotation

| CloudTrail Event | When it fires | Who calls it |
|---|---|---|
| `RotateSecret` | Manual or scheduled rotation triggered | User / EventBridge scheduler |
| `DescribeSecret` | Lambda reads secret metadata in each step | Lambda execution role |
| `GetSecretValue` | Lambda reads AWSCURRENT and AWSPENDING values | Lambda execution role |
| `PutSecretValue` | Lambda stores the new password as AWSPENDING | Lambda execution role |
| `UpdateSecretVersionStage` | Lambda promotes AWSPENDING → AWSCURRENT | Lambda execution role |

#### Events Generated on Secret Retrieval (application access)

| CloudTrail Event | When it fires | Who calls it |
|---|---|---|
| `GetSecretValue` | Any time an application reads the secret | EC2 instance role, application code |
| `DescribeSecret` | Any time secret metadata is read | Any IAM principal with permission |

#### Example CloudTrail log entry (GetSecretValue)

```json
{
  "eventTime": "2026-08-25T14:32:01Z",
  "eventSource": "secretsmanager.amazonaws.com",
  "eventName": "GetSecretValue",
  "awsRegion": "us-east-1",
  "sourceIPAddress": "10.0.1.50",
  "userAgent": "aws-sdk-python/1.34.0",
  "userIdentity": {
    "type": "AssumedRole",
    "arn": "arn:aws:sts::123456789012:assumed-role/mysql-rotation-lab-ec2-role/i-0abc123",
    "principalId": "AROA....:i-0abc123"
  },
  "requestParameters": {
    "secretId": "mysql-rotation-lab/mysql/credentials"
  },
  "responseElements": null,
  "errorCode": null
}
```

> `responseElements` is always `null` for `GetSecretValue` — the secret value itself is never written to CloudTrail logs.

### CloudWatch Logs — Lambda Rotation Function

The rotation Lambda logs every step to `/aws/lambda/<stack>-secret-rotation` with 90-day retention.

**What is logged per rotation:**

```
[INFO]  Executing step: createSecret for secret: arn:aws:secretsmanager:...
[INFO]  createSecret: AWSPENDING version stored.
[INFO]  Executing step: setSecret for secret: arn:aws:secretsmanager:...
[INFO]  setSecret: MySQL password updated for user 'appadmin'.
[INFO]  Executing step: testSecret for secret: arn:aws:secretsmanager:...
[INFO]  testSecret: new credentials verified — connection successful.
[INFO]  Executing step: finishSecret for secret: arn:aws:secretsmanager:...
[INFO]  finishSecret: AWSCURRENT promoted to version abc123.
```

**On failure:**
```
[ERROR] setSecret: Lost connection to MySQL server — check security group port 3306.
```

The CloudWatch Alarm (`<stack>-rotation-failure`) fires if the Lambda error count ≥ 1 in any 5-minute window.

### Querying Audit Logs with CloudTrail Lake or Athena

To search who retrieved the secret in the last 7 days using Athena:

```sql
SELECT
  eventtime,
  useridentity.arn AS caller,
  sourceipaddress,
  requestparameters
FROM cloudtrail_logs
WHERE eventsource = 'secretsmanager.amazonaws.com'
  AND eventname   = 'GetSecretValue'
  AND requestparameters LIKE '%mysql/credentials%'
  AND eventtime   > date_add('day', -7, now())
ORDER BY eventtime DESC;
```

---

## Security Notes

- **RDP port 3389** in the EC2 security group is open to `0.0.0.0/0` in this template. Change the `CidrIp` to your IP before deploying to production.
- The **EC2 instance role** can only read the specific secret — not list or rotate it.
- The **Lambda role** can only read and write the specific secret — not delete or list others.
- Secrets Manager secret value is **never written to CloudTrail** — only the API call metadata is logged.
- The S3 audit bucket has **log file validation enabled** — tampered log files are detectable.
- The **previous version** of the secret (`AWSPREVIOUS`) is retained after rotation for emergency rollback.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `setSecret` fails with connection timeout | Lambda SG egress or EC2 SG ingress misconfigured | Verify SG rules allow TCP 3306 between Lambda SG and EC2 SG |
| `setSecret` fails with auth error | Initial DB user not created during EC2 UserData | RDP into EC2, verify user exists: `SELECT user, host FROM mysql.user;` |
| Lambda fails to start | PyMySQL layer missing or wrong ARN | Re-check `PyMySQLLayerArn` parameter value |
| CloudTrail not capturing events | Trail not logging or wrong region | Verify `IsLogging: true` and trail is in the same region as the secret |
| Rotation not triggering on schedule | `RotationSchedule` resource not created | Check `LambdaInvokePermission` exists — required before schedule resource |

---

## References

- [Secrets Manager rotation templates — AWS Docs](https://docs.aws.amazon.com/secretsmanager/latest/userguide/reference_available-rotation-templates.html)
- [CloudTrail Secrets Manager events — AWS Docs](https://docs.aws.amazon.com/secretsmanager/latest/userguide/monitoring-cloudtrail.html)
- [Lambda VPC networking — AWS Docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html)
- [Secrets Manager rotation best practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
