# CyberArk for Database Credentials: On-Prem/VMware Setup & COTS Products

## Part 1: Leveraging CyberArk in an On-Prem, VMware-Based Environment

### Core Deployment Model

On-prem CyberArk typically runs as a set of VMs within the same VMware environment: **Digital Vault**, **Central Policy Manager (CPM)**, **Password Vault Web Access (PVWA)**, and **Privileged Session Manager (PSM)** — each usually hardened and isolated on its own VM/network segment, often with the Vault server locked down with minimal OS footprint per CyberArk's hardening guide.

### Database Credential Management Specifics

**Discovery** — CyberArk's Discovery and Audit (DNA) tool or Auto-Detection scans the network/domain to find database instances and existing service accounts that need onboarding, so you're not manually hunting down every DB credential across the estate.

**Onboarding into the Vault** — Each database account (Oracle SYS/SYSTEM, SQL Server sa, MySQL root, PostgreSQL admin, etc.) gets stored as a Safe object with an associated **Platform** — a CyberArk-provided or custom policy defining rotation logic, connection method, and password complexity rules for that DB engine.

**Rotation via CPM** — The Central Policy Manager connects directly to the database (using native drivers — Oracle OCI, JDBC/ODBC for SQL Server, etc.) to change passwords on a schedule or on-demand. Because this is on-prem, CPM needs line-of-sight network access to every DB host/VM, so firewall rules and port access between the CPM VM and DB VMs are a key design point.

**Application credential retrieval — Central Credential Provider (CCP) / Application Server Credential Provider (AAM)** — An application server (running on a VM or in a VMware Tanzu/vSphere environment) calls the CCP's REST API or uses the local AIM agent to fetch the DB credential at runtime instead of storing it in a config file or app server's password store.

**Privileged Session Manager (PSM)** — For interactive DBA access, PSM proxies the actual database session (e.g., via SQL*Plus, SSMS, or a web-based portal) so the DBA never sees the plaintext password, and CyberArk records the full session for audit — keystrokes, screen recording depending on config.

### VMware-Specific Integration Points

- **vCenter/ESXi credential management** — CyberArk can also vault and rotate the vCenter and ESXi host root/admin credentials themselves, using its VMware platform plugin, which is often bundled into the same rollout as DB credential management.
- **Network segmentation** — Since everything is on-prem VMs, you'd typically place the Vault in its own isolated VLAN/port group with tightly controlled firewall rules — only PVWA and CPM allowed to talk to it directly.
- **High availability** — On-prem HA is usually done via a Distributed Vault Cluster or a passive/active DR vault replicated to a secondary VMware cluster/datacenter, rather than relying on cloud-native failover.
- **Backup integration** — Vault backups often get orchestrated with existing VMware backup tooling (e.g., snapshot-based or CyberArk's own PAVault utility) rather than cloud snapshotting.

### Typical On-Prem Flow for a DB-Connected App

```
App VM (e.g., WebLogic/Tomcat on a VMware guest)
   → CCP Provider or AIM Agent installed locally
   → authenticates via OS user / client certificate / app identity
   → requests credential from CCP over HTTPS
   → CCP validates against Vault policy
   → returns current DB password
   → app connects to Oracle/SQL Server VM
```

### Practical Considerations for a VMware Shop

- **Network latency/segmentation** between CPM and DB VMs matters more here than in cloud, since there's no managed service abstraction — you're relying on internal firewall/VLAN design.
- **Windows vs Linux DB hosts** — CPM plugins differ slightly depending on whether SQL Server is on Windows VMs vs Oracle/PostgreSQL on Linux VMs, so plugin selection and connection method (Windows auth vs native DB auth) needs to be planned per platform.
- **Change windows** — Password rotation for production DB service accounts usually needs coordination with app restart/reconnect logic, since on-prem apps are less likely to have the elastic reconnect patterns common in cloud-native apps.

## Part 2: Handling Credential Retrieval with COTS Products

### The Core Challenge

Most COTS products expect a credential in a config file, connection string, registry key, or database, and weren't built with an external secrets API in mind. CyberArk offers a few integration tiers depending on how flexible the product is.

### 1. Native/Plugin Support (Best Case)

Some major COTS platforms have CyberArk-certified integrations already:

- **SAP** — CyberArk has a dedicated SAP platform/plugin for rotating and retrieving credentials used by SAP application servers.
- **ServiceNow, Splunk, Tanium** and similar enterprise platforms often have CyberArk Marketplace connectors.
- Check the **CyberArk Marketplace** first — if the COTS vendor or CyberArk has already built a connector, this saves significant custom work.

### 2. Central Credential Provider (CCP) — REST-Callable

If the COTS product supports **any kind of pre-connection script, startup hook, or custom authentication module**, you can have it (or a wrapper script) call the CCP's REST API to pull the credential just before connecting:

- CCP returns the credential over HTTPS, authenticated via client certificate, OS user, or allowed machine IP.
- Works well for products that read credentials from an external file at startup — you generate that file dynamically from a CCP call in a pre-start script, then have the COTS app read it.

### 3. Application Password SDK / AIM (Credential Provider Agent)

For Windows or Linux COTS apps that can execute local commands or scripts (e.g., in startup configs, service wrappers, or scheduled tasks):

- The **CyberArk AIM agent** sits locally on the host and exposes a local API/CLI (`CLIPasswordSDK`) that scripts can call to retrieve a credential without any network round-trip to the vault directly — the agent handles that.
- Common pattern: a wrapper batch/shell script calls `CLIPasswordSDK GetPassword`, injects the result into an env variable or temp config, then launches the COTS service.

### 4. Credential File/Connection-String Patching (Common Fallback)

Many COTS products (older ERPs, legacy DB-backed apps, some monitoring tools) only support a static credential in a config/ini/XML file or a DB connection string field:

- CyberArk **CPM plugin with "dependent file" or "linked account" logic** can push the rotated password directly into that config file after each rotation — CyberArk edits the file in place (or a designated field within it) so the app's next restart/reconnect picks up the new credential automatically.
- This is the standard approach for things like IIS app pools, Windows services, and scheduled tasks with embedded credentials — CyberArk's **Windows Service Credential** and **Scheduled Task** plugins handle exactly this pattern.

### 5. Session-Based Access Instead of Credential Injection

If the COTS product only supports interactive login (a GUI admin console, for example) and there's no way to inject credentials programmatically:

- Use **Privileged Session Manager (PSM)** so admins log in through CyberArk, which auto-fills the credential into the login screen (via PSM's "auto-logon" connection component) — the human never sees or types the password, and the session is recorded.

### Decision Framework

| COTS Behavior | CyberArk Approach |
|---|---|
| Has native CyberArk/vendor connector | Use the marketplace plugin |
| Supports pre-start scripting/hooks | CCP REST call or AIM agent (CLIPasswordSDK) |
| Reads static config file only | CPM "dependent account" — auto-push rotated password into file |
| Windows service/scheduled task | Built-in CyberArk plugin for service/task credential update |
| GUI-only admin console, no scripting | PSM auto-logon connection component |

### Practical On-Prem Considerations

- **Restart requirements** — Many COTS products don't hot-reload credentials, so rotation needs to be paired with a controlled service restart (CyberArk can trigger a post-rotation script/service bounce as part of the CPM process).
- **Vendor support boundaries** — Pushing CyberArk-modified credentials into a vendor's config file sometimes falls outside vendor support agreements; worth confirming with the vendor if it's a supported customization point.
- **Testing rotation in lower environments first** — COTS products are more prone to breaking silently on unexpected credential changes than custom apps, so a staged rollout (dev → test → prod) for any new dependent-account mapping is standard practice.
