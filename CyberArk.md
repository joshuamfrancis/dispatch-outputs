# Handling Credential Retrieval with COTS Products (CyberArk, On-Prem/VMware)

## The Core Challenge

Most COTS products expect a credential in a config file, connection string, registry key, or database, and weren't built with an external secrets API in mind. CyberArk offers a few integration tiers depending on how flexible the product is.

## 1. Native/Plugin Support (Best Case)

Some major COTS platforms have CyberArk-certified integrations already:

- **SAP** — CyberArk has a dedicated SAP platform/plugin for rotating and retrieving credentials used by SAP application servers.
- **ServiceNow, Splunk, Tanium** and similar enterprise platforms often have CyberArk Marketplace connectors.
- Check the **CyberArk Marketplace** first — if the COTS vendor or CyberArk has already built a connector, this saves significant custom work.

## 2. Central Credential Provider (CCP) — REST-Callable

If the COTS product supports **any kind of pre-connection script, startup hook, or custom authentication module**, you can have it (or a wrapper script) call the CCP's REST API to pull the credential just before connecting:

- CCP returns the credential over HTTPS, authenticated via client certificate, OS user, or allowed machine IP.
- Works well for products that read credentials from an external file at startup — you generate that file dynamically from a CCP call in a pre-start script, then have the COTS app read it.

## 3. Application Password SDK / AIM (Credential Provider Agent)

For Windows or Linux COTS apps that can execute local commands or scripts (e.g., in startup configs, service wrappers, or scheduled tasks):

- The **CyberArk AIM agent** sits locally on the host and exposes a local API/CLI (`CLIPasswordSDK`) that scripts can call to retrieve a credential without any network round-trip to the vault directly — the agent handles that.
- Common pattern: a wrapper batch/shell script calls `CLIPasswordSDK GetPassword`, injects the result into an env variable or temp config, then launches the COTS service.

## 4. Credential File/Connection-String Patching (Common Fallback)

Many COTS products (older ERPs, legacy DB-backed apps, some monitoring tools) only support a static credential in a config/ini/XML file or a DB connection string field:

- CyberArk **CPM plugin with "dependent file" or "linked account" logic** can push the rotated password directly into that config file after each rotation — CyberArk edits the file in place (or a designated field within it) so the app's next restart/reconnect picks up the new credential automatically.
- This is the standard approach for things like IIS app pools, Windows services, and scheduled tasks with embedded credentials — CyberArk's **Windows Service Credential** and **Scheduled Task** plugins handle exactly this pattern.

## 5. Session-Based Access Instead of Credential Injection

If the COTS product only supports interactive login (a GUI admin console, for example) and there's no way to inject credentials programmatically:

- Use **Privileged Session Manager (PSM)** so admins log in through CyberArk, which auto-fills the credential into the login screen (via PSM's "auto-logon" connection component) — the human never sees or types the password, and the session is recorded.

## Decision Framework

| COTS Behavior | CyberArk Approach |
|---|---|
| Has native CyberArk/vendor connector | Use the marketplace plugin |
| Supports pre-start scripting/hooks | CCP REST call or AIM agent (CLIPasswordSDK) |
| Reads static config file only | CPM "dependent account" — auto-push rotated password into file |
| Windows service/scheduled task | Built-in CyberArk plugin for service/task credential update |
| GUI-only admin console, no scripting | PSM auto-logon connection component |

## Practical On-Prem Considerations

- **Restart requirements** — Many COTS products don't hot-reload credentials, so rotation needs to be paired with a controlled service restart (CyberArk can trigger a post-rotation script/service bounce as part of the CPM process).
- **Vendor support boundaries** — Pushing CyberArk-modified credentials into a vendor's config file sometimes falls outside vendor support agreements; worth confirming with the vendor if it's a supported customization point.
- **Testing rotation in lower environments first** — COTS products are more prone to breaking silently on unexpected credential changes than custom apps, so a staged rollout (dev → test → prod) for any new dependent-account mapping is standard practice.
