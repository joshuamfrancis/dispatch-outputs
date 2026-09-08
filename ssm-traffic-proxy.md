# Connecting to Oracle RDS via AWS SSM Port Forwarding

A practical guide to reaching a private Oracle RDS instance from a local DB client, tunnelling through an EC2 jump host with AWS Systems Manager. No bastion SSH keys, no public IPs, no inbound security group rules.

**Conventions used below**

Every command block is labelled with where it runs:

- **laptop** — Windows 11 + gitbash
- **jump host** — the EC2 instance, reached via an SSM shell session

Placeholder values to replace throughout:

| Placeholder | Example | Where to find it |
|---|---|---|
| `i-0abc123def4567890` | jump host instance ID | EC2 console, or `aws ec2 describe-instances` |
| `mydb.abc123.ap-southeast-2.rds.amazonaws.com` | RDS endpoint | Step 1 below |
| `ORCL` | SID or service name | Step 1 below (`DBName`) |
| `sg-rds0123456789` | RDS security group | Step 1 below |
| `sg-jumphost987654` | jump host security group | EC2 console |

---

## Architecture

```
laptop                          AWS
------                          ---
DB client
   |
   v
localhost:11521
   |
   | SSM session (outbound 443 only)
   v
Systems Manager  ---->  EC2 jump host  ---->  Oracle RDS :1521
                        (SSM Agent)          (private subnet)
```

SSM cannot target RDS directly — RDS is not an SSM managed instance. The jump host is what SSM connects to; it then opens a plain TCP connection onward to the database.

---

## Prerequisites

### Jump host

A `t4g.nano` is more than enough.

- SSM Agent running. Preinstalled on Amazon Linux 2023 and recent Ubuntu AMIs; on Ubuntu it is a snap: `sudo snap install amazon-ssm-agent --classic`
- Instance profile with the `AmazonSSMManagedInstanceCore` managed policy attached
- Outbound 443 to the SSM endpoints — via NAT gateway, or via VPC interface endpoints for `ssm`, `ssmmessages`, and `ec2messages` if the subnet has no NAT
- Its security group referenced as a source in the RDS security group (Step 2)

No inbound rules and no public IP are required on the jump host.

### Laptop

- AWS CLI v2
- **Session Manager plugin** — a separate install, and the most commonly missed prerequisite. The Windows installer places it in `C:\Program Files\Amazon\SessionManagerPlugin\bin` and adds it to PATH, which gitbash inherits.

**Run on: laptop**

```bash
aws --version
session-manager-plugin --version
```

### IAM permissions

The calling principal needs the following. Scoping `StartSession` to the instance alone is not enough — the document ARN must also be permitted, and omitting it produces an `AccessDenied` that looks like an instance permissions problem.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ssm:StartSession",
      "Resource": [
        "arn:aws:ec2:ap-southeast-2:123456789012:instance/i-0abc123def4567890",
        "arn:aws:ssm:ap-southeast-2::document/AWS-StartPortForwardingSessionToRemoteHost"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["ssm:TerminateSession", "ssm:ResumeSession"],
      "Resource": "arn:aws:ssm:*:*:session/${aws:username}-*"
    }
  ]
}
```

---

## Step 1 — Gather the connection facts

**Run on: laptop**

```bash
aws rds describe-db-instances \
  --db-instance-identifier my-oracle-db \
  --region ap-southeast-2 \
  --query 'DBInstances[0].{
      Endpoint:Endpoint.Address,
      Port:Endpoint.Port,
      DBName:DBName,
      Engine:Engine,
      EngineVersion:EngineVersion,
      SG:VpcSecurityGroups[*].VpcSecurityGroupId,
      Subnets:DBSubnetGroup.Subnets[*].SubnetIdentifier
    }' \
  --output json
```

Interpreting `DBName`:

- **Non-CDB instance** — this is the **SID**, often `ORCL`
- **19c CDB or 21c+** — this is the PDB name, which you connect to as a **service name**

The distinction determines the connect string separator in Step 5. Port is `1521` unless the SSL option is on the option group, in which case an encrypted listener also exists on `2484`.

---

## Step 2 — Allow the jump host through the DB security group

**Run on: laptop**

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-rds0123456789 \
  --protocol tcp --port 1521 \
  --source-group sg-jumphost987654 \
  --region ap-southeast-2
```

Referencing the source security group rather than a CIDR keeps the rule valid if the jump host is ever replaced.

---

## Step 3 — Verify the jump host can reach Oracle

Worth doing once. Skipping it means a later failure shows up as a client-side timeout, which sends you looking in the wrong place.

**Run on: laptop** — open an interactive shell on the jump host:

```bash
aws ssm start-session \
  --target i-0abc123def4567890 \
  --region ap-southeast-2
```

**Run on: jump host**

```bash
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/mydb.abc123.ap-southeast-2.rds.amazonaws.com/1521' \
  && echo "listener reachable" || echo "blocked"
exit
```

If this reports `blocked`, revisit Step 2 before going further.

---

## Step 4 — Start the tunnel

**Run on: laptop.** Leave this terminal open for the duration of your session; `Ctrl+C` closes the tunnel.

```bash
aws ssm start-session \
  --target i-0abc123def4567890 \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["mydb.abc123.ap-southeast-2.rds.amazonaws.com"],"portNumber":["1521"],"localPortNumber":["11521"]}' \
  --region ap-southeast-2 \
  --profile myprofile
```

Two details that matter:

- The document must be `AWS-StartPortForwardingSessionToRemoteHost`. The similarly named `AWS-StartPortForwardingSession` forwards only to a port on the instance itself, not onward to a remote host.
- The local port is arbitrary. `11521` avoids clashing with a local Oracle XE install or container already holding 1521.

The single-quoted JSON works in gitbash. From PowerShell or `cmd` the quoting breaks, so use the shorthand form instead:

```
--parameters host="mydb.abc123.ap-southeast-2.rds.amazonaws.com",portNumber="1521",localPortNumber="11521"
```

**Run on: laptop, second terminal** — confirm the listener is up:

```bash
netstat -an | grep 11521
```

---

## Step 5 — Connect the client

### sqlplus

**Service name** (CDB/PDB) — note the `//` prefix and `/` separator:

```bash
sqlplus 'admin/YourPassword@//localhost:11521/ORCL'
```

**SID** (non-CDB) — `:` separator, no `//`:

```bash
sqlplus 'admin/YourPassword@localhost:11521:ORCL'
```

If the short SID form misbehaves, the explicit descriptor is unambiguous:

```bash
sqlplus 'admin/YourPassword@(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=localhost)(PORT=11521))(CONNECT_DATA=(SID=ORCL)(SERVER=DEDICATED)))'
```

### Python — python-oracledb thin mode

The least painful option, and no Oracle Instant Client to install.

**Run on: laptop**

```bash
pip install oracledb
```

```python
import os
import oracledb

conn = oracledb.connect(
    user="admin",
    password=os.environ["ORACLE_PASSWORD"],
    dsn="localhost:11521/ORCL",  # service name form
)

with conn.cursor() as cur:
    cur.execute(
        "SELECT sys_context('USERENV','DB_NAME'), sys_context('USERENV','SERVER_HOST') FROM dual"
    )
    print(cur.fetchone())

conn.close()
```

For the SID form, build the DSN with `oracledb.makedsn("localhost", 11521, sid="ORCL")`.

One caveat: if the option group enforces Oracle Native Network Encryption, older thin-mode releases refuse the connection. Pin a current `oracledb` release, or switch to thick mode with Instant Client.

### SQL Developer / DBeaver

Host `localhost`, port `11521`, then select **Service name** or **SID** to match Step 1. In SQL Developer, the *Advanced* tab accepts the full descriptor above if the simple form gives trouble.

### Clients running in Docker

`localhost` inside a container is the container, not your host. Use `host.docker.internal:11521`, and on Linux add `--add-host=host.docker.internal:host-gateway`.

---

## Is a hosts file entry needed?

**For a standard connection on 1521, no.**

The concern is listener redirection — the listener handing the client back a different address to connect to. That happens with **shared server** (dispatcher) configurations and with RAC/SCAN listeners. RDS for Oracle is single-instance, has no SCAN listener, and defaults to **dedicated server**, where the listener hands off the existing socket in place and no hostname is returned to the client. So the redirect path does not arise.

Confirm once connected:

```sql
SELECT server FROM v$session WHERE sid = SYS_CONTEXT('USERENV','SID');
```

`DEDICATED` means you are clear.

**Where it does matter: TLS on port 2484.** The RDS server certificate is issued for the real endpoint name, and `SSL_SERVER_DN_MATCH` defaults to ON, so connecting to `localhost` fails certificate validation. A hosts entry is one fix. Pinning the expected DN is better, because it keeps identity verification intact rather than weakening it — see the SSL section below.

**Why not add one just in case:** a hosts entry is machine-wide and permanent until removed. If you later gain VPN or Direct Connect access to that VPC, the entry silently blackholes the real endpoint to loopback, and the resulting failure is genuinely confusing to diagnose. It also requires an elevated editor each time you change it.

If you do decide you need one, add to `C:\Windows\System32\drivers\etc\hosts` as Administrator:

```
127.0.0.1  mydb.abc123.ap-southeast-2.rds.amazonaws.com
```

and set `localPortNumber` to `1521` so the port matches too. From gitbash, open an elevated editor with:

```bash
powershell.exe -Command "Start-Process notepad -Verb RunAs -ArgumentList 'C:\Windows\System32\drivers\etc\hosts'"
```

---

## SSL-enabled instances (port 2484)

If the `SSL` option is attached to the option group, forward the encrypted listener instead:

**Run on: laptop**

```bash
aws ssm start-session \
  --target i-0abc123def4567890 \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["mydb.abc123.ap-southeast-2.rds.amazonaws.com"],"portNumber":["2484"],"localPortNumber":["12484"]}' \
  --region ap-southeast-2
```

Then pin the certificate DN rather than disabling the check:

```
(DESCRIPTION=(ADDRESS=(PROTOCOL=TCPS)(HOST=localhost)(PORT=12484))
 (CONNECT_DATA=(SERVICE_NAME=ORCL))
 (SECURITY=(SSL_SERVER_CERT_DN="CN=mydb.abc123.ap-southeast-2.rds.amazonaws.com,OU=RDS,O=Amazon.com,L=Seattle,ST=Washington,C=US")))
```

In python-oracledb thin mode this is the `ssl_server_cert_dn` parameter. There is also `ssl_server_dn_match=False`, but that disables verification entirely — prefer the DN.

You will also need the Amazon RDS CA bundle in your client wallet or trust store. It is available from the RDS documentation's certificate bundle page for your region.

---

## Reusable wrapper script

Save as `~/bin/db-tunnel.sh` and `chmod +x` it.

```bash
#!/usr/bin/env bash
set -euo pipefail

INSTANCE_ID="${INSTANCE_ID:-i-0abc123def4567890}"
DB_HOST="${DB_HOST:-mydb.abc123.ap-southeast-2.rds.amazonaws.com}"
DB_PORT="${DB_PORT:-1521}"
LOCAL_PORT="${LOCAL_PORT:-11521}"
REGION="${AWS_REGION:-ap-southeast-2}"
PROFILE="${AWS_PROFILE:-default}"

if netstat -an 2>/dev/null | grep -q "[:.]${LOCAL_PORT}[[:space:]].*LISTEN"; then
  echo "Port ${LOCAL_PORT} is already in use. Set LOCAL_PORT to something else." >&2
  exit 1
fi

echo "Tunnel: localhost:${LOCAL_PORT} -> ${DB_HOST}:${DB_PORT}"
echo "Ctrl+C to close."

aws ssm start-session \
  --target "$INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"${DB_HOST}\"],\"portNumber\":[\"${DB_PORT}\"],\"localPortNumber\":[\"${LOCAL_PORT}\"]}" \
  --region "$REGION" \
  --profile "$PROFILE"
```

Override per-invocation without editing the file:

```bash
LOCAL_PORT=12484 DB_PORT=2484 ./db-tunnel.sh
```

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `session-manager-plugin: command not found` | Plugin not installed, or PATH not refreshed — restart gitbash |
| `TargetNotConnected` | SSM Agent not running, missing instance profile, or no route to the SSM endpoints |
| `AccessDeniedException` on StartSession | IAM policy missing the **document** ARN, not just the instance ARN |
| ORA-12541 — no listener | Tunnel not running, or client pointed at the wrong local port |
| ORA-12514 — service not known | Service name wrong, or you are using the SID form for a PDB. Recheck `DBName` |
| ORA-12505 — SID not known | Reverse of the above — using SID form where a service name is needed |
| ORA-12170 — timeout | Jump host security group not permitted into the RDS security group (Step 2) |
| ORA-01017 — invalid credentials | Network path is working; this is purely a username/password issue |
| ORA-28759 / certificate errors | TLS DN mismatch on 2484 — pin `SSL_SERVER_CERT_DN` |
| Connection drops after ~20 min idle | SSM `idleSessionTimeout`. A running query counts as traffic, so it will not drop mid-query |

### Raising the idle timeout

Edit the `SSM-SessionManagerRunShell` session preferences document and set `idleSessionTimeout` (in minutes, up to 60). Alternatively, most GUI clients have a keep-alive setting — in SQL Developer it is *Preferences → Database → Advanced*.

### Reading session logs

**Run on: laptop**

```bash
aws ssm describe-sessions \
  --state History \
  --region ap-southeast-2 \
  --query 'Sessions[0:5].{Id:SessionId,Target:Target,Start:StartDate,Reason:Reason}' \
  --output table
```

---

## Alternatives considered

**EC2 Instance Connect Endpoint** — removes the need for the SSM agent, but EIC endpoints only target EC2, so a jump host is still required. No real saving.

**RDS Proxy** — helps with connection pooling and IAM auth, but does not solve network reachability from a laptop; you would still tunnel to it.

**VPN / Direct Connect** — the right long-term answer for a team that needs routine access. SSM port forwarding is better suited to occasional or break-glass access, and to environments where you would rather not run a VPN.

A permanently running `t4g.nano` jump host is a few dollars a month and is usually the simplest option for individual developer access.
