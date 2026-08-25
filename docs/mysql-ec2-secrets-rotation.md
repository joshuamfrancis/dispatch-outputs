# Windows EC2 MySQL — Secrets Manager Rotation & Audit Logging

CloudFormation template: [`cloudformation/mysql-rotation.yaml`](../cloudformation/mysql-rotation.yaml)

---

## Architecture

```
Pre-existing VPC
│
├── EC2 Subnet (any)
│   └── Windows EC2  ──── EC2 Security Group (3306 from Lambda SG only)
│
└── Private Subnets (x2, different AZs)
    ├── Lambda (VPC-attached) ──── Lambda Security Group
    │     │  egress: 3306 → EC2 SG
    │     │  egress: 443  → Endpoint SG
    │     │
    └── Secrets Manager Interface Endpoint ──── Endpoint Security Group
          (private DNS: secretsmanager.<region>.amazonaws.com)
          ingress: 443 from Lambda SG

          ↕ HTTPS (stays inside VPC — no NAT Gateway, no internet)

AWS Secrets Manager (regional service)
    │
    ├── Rotation trigger (schedule every N days)
    │     createSecret → setSecret → testSecret → finishSecret
    │
    └── CloudTrail → S3 audit bucket → Glacier (90d) → expire (7yr)
        CloudWatch Logs → /aws/lambda/<stack>-secret-rotation (90d)
```

---

## What Gets Deployed

The template assumes a **pre-existing VPC and subnets**. It does not create or modify any VPC resources.

| Resource | Purpose |
|---|---|
| EC2 Security Group | Allows MySQL on configured port from Lambda SG only |
| Lambda Security Group | Egress to EC2 SG (MySQL) and Endpoint SG (HTTPS) |
| Endpoint Security Group | Allows HTTPS 443 from Lambda SG to the VPC endpoint |
| **Secrets Manager VPC Interface Endpoint** | Private path from Lambda to Secrets Manager — no NAT required |
| EC2 IAM Role + Instance Profile | SSM access + read the secret |
| Windows EC2 (Server 2022) | Host for MySQL — **MySQL must be installed manually post-launch** |
| Secrets Manager Secret | JSON: username, password, host, port, dbname, engine |
| Rotation Schedule | Triggers Lambda every N days (default 30) |
| Lambda Execution Role | Scoped to read/write/stage-update the specific secret only |
| Lambda Function (VPC-attached) | Four-step rotation using PyMySQL |
| CloudWatch Log Group | Lambda logs, 90-day retention |
| CloudTrail Trail | All Secrets Manager management events to S3 |
| S3 Audit Bucket | Encrypted, versioned, 90d → Glacier, 7yr expiry |
| CloudWatch Alarm | Fires on any Lambda rotation error |

---

## VPC Endpoint — Why It Matters

The Lambda function is in private subnets with no internet route. Without a VPC endpoint for Secrets Manager, the function cannot reach the `secretsmanager` API.

The **Interface Endpoint** (`com.amazonaws.<region>.secretsmanager`) with `PrivateDnsEnabled: true` means the standard SDK endpoint (`https://secretsmanager.us-east-1.amazonaws.com`) resolves to a private ENI IP inside your VPC. All Secrets Manager calls from the Lambda stay entirely within the AWS network — no NAT Gateway cost, no internet exposure.

**Traffic flow:**
```
Lambda → Lambda SG (egress 443) → Endpoint SG (ingress 443) → Interface Endpoint ENIs → Secrets Manager
```

---

## Prerequisites

### 1. Existing VPC Requirements

You need:
- A VPC with DNS resolution and DNS hostnames enabled
- One subnet for the EC2 instance
- **Two private subnets in different AZs** for the Lambda function and the VPC endpoint ENIs (interface endpoints require at least one subnet; two provides AZ redundancy)

### 2. MySQL on EC2 — Manual Setup

The EC2 instance is launched with no MySQL installation. After the stack deploys:

1. RDP into the EC2 instance (Public IP in Outputs)
2. Download and install [MySQL Community Server 8.0](https://dev.mysql.com/downloads/mysql/)
3. Create the application database and user:

```sql
CREATE DATABASE appdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'appadmin'@'%' IDENTIFIED BY 'YourInitialPassword123!';
GRANT ALL PRIVILEGES ON appdb.* TO 'appadmin'@'%';
FLUSH PRIVILEGES;
```

4. Edit `my.ini` to set `bind-address=0.0.0.0` so MySQL accepts remote connections
5. Open port 3306 in Windows Firewall
6. Restart the MySQL service

### 3. PyMySQL Lambda Layer

```bash
mkdir -p pymysql-layer/python
pip install pymysql -t pymysql-layer/python/
cd pymysql-layer && zip -r ../pymysql-layer.zip python/ && cd ..

aws lambda publish-layer-version \
  --layer-name pymysql \
  --compatible-runtimes python3.12 \
  --zip-file fileb://pymysql-layer.zip \
  --query 'LayerVersionArn' --output text
```

Copy the returned ARN for the `PyMySQLLayerArn` parameter.

---

## Deploy the Stack

```bash
aws cloudformation deploy \
  --template-file cloudformation/mysql-rotation.yaml \
  --stack-name mysql-rotation \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    VpcId=vpc-0abc123456 \
    EC2SubnetId=subnet-0pub111 \
    LambdaSubnetId1=subnet-0priv111 \
    LambdaSubnetId2=subnet-0priv222 \
    DBUsername=appadmin \
    DBPassword="YourInitialPassword123!" \
    DBName=appdb \
    MySQLPort=3306 \
    PyMySQLLayerArn="arn:aws:lambda:us-east-1:123456789012:layer:pymysql:1" \
    RotationIntervalDays=30
```

### Trigger an Immediate Rotation (optional)

```bash
SECRET_ARN=$(aws cloudformation describe-stacks \
  --stack-name mysql-rotation \
  --query "Stacks[0].Outputs[?OutputKey=='SecretARN'].OutputValue" \
  --output text)

aws secretsmanager rotate-secret --secret-id $SECRET_ARN
```

---

## Four-Step Rotation Protocol

| Step | What happens |
|---|---|
| `createSecret` | Generates a new 32-char random password. Stores it as `AWSPENDING`. Skipped if `AWSPENDING` already exists (safe retry). |
| `setSecret` | Connects to MySQL using `AWSCURRENT` credentials. Runs `ALTER USER ... IDENTIFIED BY` with the new password. Both old and new passwords are valid at this point. |
| `testSecret` | Connects to MySQL using the `AWSPENDING` credentials. Fails the rotation if connection is refused. |
| `finishSecret` | Calls `UpdateSecretVersionStage` to promote `AWSPENDING` → `AWSCURRENT`. Old version becomes `AWSPREVIOUS` for emergency rollback. |

---

## Audit Logging

### CloudTrail — Secrets Manager Events

CloudTrail captures every Secrets Manager API call as a management event. Logs land in `s3://<stack>-audit-<account>-<region>/AWSLogs/<account>/CloudTrail/`.

#### Events on Secret Rotation

| Event | Triggered by |
|---|---|
| `RotateSecret` | Scheduled trigger or manual call |
| `DescribeSecret` | Lambda (all four steps) |
| `GetSecretValue` | Lambda reads AWSCURRENT and AWSPENDING |
| `PutSecretValue` | Lambda writes new password as AWSPENDING |
| `UpdateSecretVersionStage` | Lambda promotes AWSPENDING → AWSCURRENT |

#### Events on Secret Retrieval

| Event | Triggered by |
|---|---|
| `GetSecretValue` | Any application or EC2 role reading the secret |
| `DescribeSecret` | Any principal inspecting secret metadata |

Each CloudTrail log entry includes: `eventTime`, `eventName`, `sourceIPAddress`, `userIdentity.arn`, `requestParameters.secretId`. **The secret value is never written to the log.**

#### Example — GetSecretValue log entry

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
    "arn": "arn:aws:sts::123456789012:assumed-role/mysql-rotation-ec2-role/i-0abc123",
    "principalId": "AROA...:i-0abc123"
  },
  "requestParameters": {
    "secretId": "mysql-rotation/mysql/credentials"
  },
  "responseElements": null
}
```

### CloudWatch Logs — Lambda Rotation

Log group: `/aws/lambda/<stack>-secret-rotation` (90-day retention)

**Successful rotation output:**
```
[INFO] Executing step: createSecret for secret: arn:aws:secretsmanager:...
[INFO] createSecret: AWSPENDING version stored.
[INFO] Executing step: setSecret ...
[INFO] setSecret: MySQL password updated for user 'appadmin'.
[INFO] Executing step: testSecret ...
[INFO] testSecret: new credentials verified — connection successful.
[INFO] Executing step: finishSecret ...
[INFO] finishSecret: AWSCURRENT promoted to version abc123.
```

**On failure:**
```
[ERROR] setSecret: Can't connect to MySQL server — check security group port 3306.
```

The `RotationFailureAlarm` CloudWatch Alarm fires within 5 minutes of any Lambda error.

### Querying Audit Logs with Athena

```sql
SELECT
  eventtime,
  useridentity.arn        AS caller,
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

- **RDP (3389)** in the EC2 security group defaults to `0.0.0.0/0`. Change to your admin IP before deploying.
- Lambda reaches Secrets Manager via the **VPC Interface Endpoint** — traffic never leaves the AWS network and no NAT Gateway is required.
- The **EC2 role** can only `GetSecretValue` and `DescribeSecret` on the specific secret — it cannot rotate, delete, or list others.
- The **Lambda role** can only read, write, and stage-update the specific secret.
- `AWSPREVIOUS` version is retained after each rotation for emergency rollback.
- CloudTrail log file validation is enabled — tampered files are detectable.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `setSecret` times out | Lambda SG egress 3306 or EC2 SG ingress misconfigured | Verify SG rules reference each other correctly |
| `setSecret` auth error | MySQL user not created or bind-address still localhost | Confirm `'appadmin'@'%'` user exists; `bind-address=0.0.0.0` in my.ini |
| Lambda can't reach Secrets Manager | VPC endpoint not available or endpoint SG missing ingress | Verify endpoint state is `available`; check endpoint SG allows 443 from Lambda SG |
| PyMySQL import error | Layer ARN wrong or layer not compatible with python3.12 | Republish layer with `--compatible-runtimes python3.12` |
| Rotation not triggering | `LambdaInvokePermission` missing | Template creates it — check `DependsOn` on `SecretRotationSchedule` |

---

## References

- [Secrets Manager rotation — AWS Docs](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [Secrets Manager VPC endpoint — AWS Docs](https://docs.aws.amazon.com/secretsmanager/latest/userguide/vpc-endpoint-overview.html)
- [CloudTrail Secrets Manager events — AWS Docs](https://docs.aws.amazon.com/secretsmanager/latest/userguide/monitoring-cloudtrail.html)
- [Lambda VPC networking — AWS Docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html)
