# Azure DevOps — Gated Approval Flows with Work Item Status Updates

---

## Overview

Azure DevOps pipelines support **environment-level approval gates** that pause a deployment until one or more reviewers explicitly approve or reject it. Combined with the **Azure DevOps REST API** and the built-in `Update Work Items` task, you can automatically transition work item states (e.g. `Active → In Review → Done`) at each stage of the pipeline — giving you a traceable audit trail that ties deployment progress directly to your board.

---

## Architecture

```
Feature Branch PR
      │
      ▼
CI Pipeline (Build + Unit Tests)
      │  ── on success ──▶  Work Item: Active → "In Review"
      │
      ▼
CD Pipeline: Deploy to DEV
      │  ── on success ──▶  Work Item: "In Review" → "Testing"
      │
      ▼
┌─────────────────────────────┐
│  GATE: QA Approval          │  ◀── Manual approval required
│  Approver: QA Lead          │      (timeout: 48h, reject = pipeline fails)
└─────────────────────────────┘
      │  ── on approval ──▶  Work Item: "Testing" → "Approved"
      │
      ▼
CD Pipeline: Deploy to STAGING
      │
      ▼
┌─────────────────────────────┐
│  GATE: Release Manager      │  ◀── Manual approval required
│  Approver: Release Manager  │      (timeout: 24h)
└─────────────────────────────┘
      │  ── on approval ──▶  Work Item: "Approved" → "Done"
      │
      ▼
CD Pipeline: Deploy to PRODUCTION
      │  ── on success ──▶  Work Item: "Done"
```

---

## Part 1 — Environment Approval Gates

Approvals in ADO are configured on **Environments**, not directly on pipelines. A pipeline stage targets an environment; the environment's approval rules are evaluated before the stage runs.

### Create an Environment with Approvals

1. Go to **Pipelines → Environments → New environment**
2. Name it (e.g. `staging`, `production`)
3. Open the environment → **Approvals and checks → +**
4. Select **Approvals**
5. Configure:

| Setting | Recommended value |
|---|---|
| Approvers | Specific users or AAD groups |
| Instructions | Shown to approvers in the approval notification |
| Timeout | 48h (pipeline fails after this if no response) |
| Allow approvers to approve their own runs | Off (enforces separation of duties) |
| Require all approvers | On / Off depending on your process |

### Reference the Environment in a Pipeline Stage

```yaml
# azure-pipelines.yml

stages:

  - stage: Deploy_Staging
    displayName: Deploy to Staging
    jobs:
      - deployment: DeployStaging
        displayName: Deploy to Staging Environment
        environment: staging          # ← references the environment with approval gate
        strategy:
          runOnce:
            deploy:
              steps:
                - script: echo "Deploying to staging..."

  - stage: Deploy_Production
    displayName: Deploy to Production
    dependsOn: Deploy_Staging
    jobs:
      - deployment: DeployProduction
        displayName: Deploy to Production Environment
        environment: production       # ← separate environment with its own approval gate
        strategy:
          runOnce:
            deploy:
              steps:
                - script: echo "Deploying to production..."
```

When the pipeline reaches `Deploy_Staging`, it pauses and sends email/Teams notifications to the configured approvers. The stage only proceeds once approved.

---

## Part 2 — Additional Gate Types

Beyond manual approvals, ADO environments support these gate checks that run automatically:

| Gate type | Use case |
|---|---|
| **Approvals** | Human sign-off before a stage runs |
| **Branch control** | Only allow deployments from specific branches (e.g. `main`) |
| **Business hours** | Block deployments outside working hours |
| **Exclusive lock** | Prevent concurrent deployments to the same environment |
| **Query-based gates** (Classic) | Block if an ADO work item query returns results (e.g. open P1 bugs) |
| **Invoke Azure Function** | Call a custom function for external validation |
| **Invoke REST API** | Query any external system for a pass/fail signal |

### Example: Block If Open P1 Bugs Exist (Query Gate — Classic Release Pipelines)

In a Classic release pipeline → Pre-deployment gate → **Query Work Items**:

```
Query: [Team Project]\P1 Bugs - Open
Maximum threshold: 0    ← gate fails if any open P1 bug exists
```

For YAML pipelines, replicate this with an **Invoke REST API** gate that calls the ADO Work Items Query API.

---

## Part 3 — Updating Work Item Status from a Pipeline

### Method A — `Update Work Items` Built-in Task

ADO has a native mechanism to link pipeline runs to work items via the **commit messages**. If your commit message or PR description contains `#<work-item-id>`, ADO automatically links the run. You can then use the REST API to transition the work item state.

### Method B — Azure DevOps REST API via Script Task

This is the most flexible approach. Use a `script` or `PowerShell` task with the pipeline's built-in `$(System.AccessToken)` to call the Work Items REST API.

#### PowerShell task — update work item state

```yaml
- task: PowerShell@2
  displayName: 'Update Work Item: Active → In Review'
  inputs:
    targetType: inline
    script: |
      param()
      $workItemId  = "$(workItemId)"         # pipeline variable or extracted from PR
      $org         = "$(System.TeamFoundationCollectionUri)"
      $project     = "$(System.TeamProject)"
      $token       = "$(System.AccessToken)"
      $newState    = "In Review"

      $base64Token = [Convert]::ToBase64String(
                       [Text.Encoding]::ASCII.GetBytes(":$token"))
      $headers = @{
        Authorization  = "Basic $base64Token"
        'Content-Type' = 'application/json-patch+json'
      }

      $body = @(
        @{
          op    = "add"
          path  = "/fields/System.State"
          value = $newState
        }
      ) | ConvertTo-Json -AsArray

      $uri = "${org}${project}/_apis/wit/workitems/${workItemId}?api-version=7.1"
      Invoke-RestMethod -Uri $uri -Method PATCH -Headers $headers -Body $body
      Write-Host "Work item $workItemId updated to state: $newState"
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

> **Important:** In pipeline settings, enable **Allow scripts to access the OAuth token** (Project Settings → Pipelines → Settings, or set `env: SYSTEM_ACCESSTOKEN` on the task).

#### Bash equivalent

```yaml
- task: Bash@3
  displayName: 'Update Work Item State'
  inputs:
    targetType: inline
    script: |
      WORK_ITEM_ID="$(workItemId)"
      ORG="$(System.TeamFoundationCollectionUri)"
      PROJECT="$(System.TeamProject)"
      NEW_STATE="Testing"

      curl -s -X PATCH \
        "${ORG}${PROJECT}/_apis/wit/workitems/${WORK_ITEM_ID}?api-version=7.1" \
        -H "Authorization: Basic $(echo -n :$(System.AccessToken) | base64)" \
        -H "Content-Type: application/json-patch+json" \
        -d "[{\"op\":\"add\",\"path\":\"/fields/System.State\",\"value\":\"${NEW_STATE}\"}]"
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

---

## Part 4 — Extracting Work Item IDs from the Pipeline

### From a Pipeline Variable

Pass the work item ID as a pipeline variable at queue time or from a variable group:

```yaml
parameters:
  - name: workItemId
    displayName: Work Item ID
    type: string
    default: ''

variables:
  workItemId: ${{ parameters.workItemId }}
```

### From PR Description (auto-detect linked work items)

Use the ADO REST API to read the PR's linked work items:

```yaml
- task: PowerShell@2
  displayName: 'Get Linked Work Item IDs from PR'
  inputs:
    targetType: inline
    script: |
      $org          = "$(System.TeamFoundationCollectionUri)"
      $project      = "$(System.TeamProject)"
      $repoId       = "$(Build.Repository.ID)"
      $prId         = "$(System.PullRequest.PullRequestId)"
      $token        = "$(System.AccessToken)"

      $base64Token  = [Convert]::ToBase64String(
                        [Text.Encoding]::ASCII.GetBytes(":$token"))
      $headers = @{ Authorization = "Basic $base64Token" }

      $uri = "${org}${project}/_apis/git/repositories/${repoId}/pullRequests/${prId}/workitems?api-version=7.1"
      $result = Invoke-RestMethod -Uri $uri -Headers $headers

      $ids = ($result.value | Select-Object -ExpandProperty id) -join ","
      Write-Host "Linked work items: $ids"
      Write-Host "##vso[task.setvariable variable=linkedWorkItemIds;isOutput=true]$ids"
  name: getWorkItems
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

Then reference `$(getWorkItems.linkedWorkItemIds)` in downstream tasks.

---

## Part 5 — Full End-to-End Pipeline Example

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main

parameters:
  - name: workItemId
    displayName: Work Item ID to track
    type: string
    default: ''

variables:
  workItemId: ${{ parameters.workItemId }}

stages:

  # ── CI ────────────────────────────────────────────────────────
  - stage: Build
    displayName: Build & Test
    jobs:
      - job: BuildJob
        pool:
          vmImage: ubuntu-latest
        steps:
          - script: echo "Running build and tests..."
            displayName: Build

          - task: PowerShell@2
            displayName: 'Work Item: Active → In Review'
            condition: and(succeeded(), ne(variables['workItemId'], ''))
            inputs:
              targetType: inline
              script: |
                $id      = "$(workItemId)"
                $org     = "$(System.TeamFoundationCollectionUri)"
                $project = "$(System.TeamProject)"
                $b64     = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$(System.AccessToken)"))
                $headers = @{ Authorization="Basic $b64"; 'Content-Type'='application/json-patch+json' }
                $body    = '[{"op":"add","path":"/fields/System.State","value":"In Review"}]'
                Invoke-RestMethod "${org}${project}/_apis/wit/workitems/${id}?api-version=7.1" -Method PATCH -Headers $headers -Body $body
            env:
              SYSTEM_ACCESSTOKEN: $(System.AccessToken)

  # ── Deploy to DEV ─────────────────────────────────────────────
  - stage: Deploy_Dev
    displayName: Deploy to Dev
    dependsOn: Build
    jobs:
      - deployment: DeployDev
        environment: dev              # no approval gate on dev
        strategy:
          runOnce:
            deploy:
              steps:
                - script: echo "Deploying to dev..."

                - task: PowerShell@2
                  displayName: 'Work Item: In Review → Testing'
                  condition: and(succeeded(), ne(variables['workItemId'], ''))
                  inputs:
                    targetType: inline
                    script: |
                      $id      = "$(workItemId)"
                      $org     = "$(System.TeamFoundationCollectionUri)"
                      $project = "$(System.TeamProject)"
                      $b64     = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$(System.AccessToken)"))
                      $headers = @{ Authorization="Basic $b64"; 'Content-Type'='application/json-patch+json' }
                      $body    = '[{"op":"add","path":"/fields/System.State","value":"Testing"}]'
                      Invoke-RestMethod "${org}${project}/_apis/wit/workitems/${id}?api-version=7.1" -Method PATCH -Headers $headers -Body $body
                  env:
                    SYSTEM_ACCESSTOKEN: $(System.AccessToken)

  # ── QA Approval Gate + Staging ────────────────────────────────
  - stage: Deploy_Staging
    displayName: Deploy to Staging (QA Approval)
    dependsOn: Deploy_Dev
    jobs:
      - deployment: DeployStaging
        environment: staging          # ← QA approval gate configured here in ADO UI
        strategy:
          runOnce:
            preDeploy:
              steps:
                - task: PowerShell@2
                  displayName: 'Work Item: Testing → Approved'
                  condition: ne(variables['workItemId'], '')
                  inputs:
                    targetType: inline
                    script: |
                      $id      = "$(workItemId)"
                      $org     = "$(System.TeamFoundationCollectionUri)"
                      $project = "$(System.TeamProject)"
                      $b64     = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$(System.AccessToken)"))
                      $headers = @{ Authorization="Basic $b64"; 'Content-Type'='application/json-patch+json' }
                      $body    = '[{"op":"add","path":"/fields/System.State","value":"Approved"}]'
                      Invoke-RestMethod "${org}${project}/_apis/wit/workitems/${id}?api-version=7.1" -Method PATCH -Headers $headers -Body $body
                  env:
                    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
            deploy:
              steps:
                - script: echo "Deploying to staging..."

  # ── Release Manager Approval Gate + Production ────────────────
  - stage: Deploy_Production
    displayName: Deploy to Production (Release Manager Approval)
    dependsOn: Deploy_Staging
    jobs:
      - deployment: DeployProd
        environment: production       # ← Release Manager approval gate configured here
        strategy:
          runOnce:
            preDeploy:
              steps:
                - task: PowerShell@2
                  displayName: 'Work Item: Approved → Done'
                  condition: ne(variables['workItemId'], '')
                  inputs:
                    targetType: inline
                    script: |
                      $id      = "$(workItemId)"
                      $org     = "$(System.TeamFoundationCollectionUri)"
                      $project = "$(System.TeamProject)"
                      $b64     = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$(System.AccessToken)"))
                      $headers = @{ Authorization="Basic $b64"; 'Content-Type'='application/json-patch+json' }
                      $body    = '[{"op":"add","path":"/fields/System.State","value":"Done"}]'
                      Invoke-RestMethod "${org}${project}/_apis/wit/workitems/${id}?api-version=7.1" -Method PATCH -Headers $headers -Body $body
                  env:
                    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
            deploy:
              steps:
                - script: echo "Deploying to production..."
```

---

## Part 6 — Updating State on Rejection / Failure

Use a `condition: failed()` step or a separate pipeline job to handle rollback state transitions when an approval is rejected or a stage fails.

```yaml
- task: PowerShell@2
  displayName: 'Work Item: Revert to Active on Failure'
  condition: failed()
  inputs:
    targetType: inline
    script: |
      $id      = "$(workItemId)"
      $org     = "$(System.TeamFoundationCollectionUri)"
      $project = "$(System.TeamProject)"
      $b64     = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$(System.AccessToken)"))
      $headers = @{ Authorization="Basic $b64"; 'Content-Type'='application/json-patch+json' }
      $body    = '[{"op":"add","path":"/fields/System.State","value":"Active"},
                   {"op":"add","path":"/fields/System.History","value":"Pipeline failed or approval rejected — state reverted."}]'
      Invoke-RestMethod "${org}${project}/_apis/wit/workitems/${id}?api-version=7.1" -Method PATCH -Headers $headers -Body $body
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

---

## Part 7 — Adding a Comment to the Work Item

Log the pipeline run URL directly onto the work item as a comment for full traceability:

```yaml
- task: PowerShell@2
  displayName: 'Add Pipeline Run Link to Work Item'
  inputs:
    targetType: inline
    script: |
      $id       = "$(workItemId)"
      $org      = "$(System.TeamFoundationCollectionUri)"
      $project  = "$(System.TeamProject)"
      $runUrl   = "$(System.TeamFoundationCollectionUri)$(System.TeamProject)/_build/results?buildId=$(Build.BuildId)"
      $b64      = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$(System.AccessToken)"))
      $headers  = @{ Authorization="Basic $b64"; 'Content-Type'='application/json' }
      $comment  = "Pipeline run: <a href='$runUrl'>$(Build.BuildNumber)</a> — Stage: $(System.StageName)"
      $body     = @{ text = $comment } | ConvertTo-Json

      $uri = "${org}${project}/_apis/wit/workItems/${id}/comments?api-version=7.1-preview.3"
      Invoke-RestMethod -Uri $uri -Method POST -Headers $headers -Body $body
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

---

## Part 8 — Required Permissions

| Setting | Where to configure |
|---|---|
| Allow scripts to access OAuth token | Pipeline → Edit → ... → Triggers → (or task-level `env: SYSTEM_ACCESSTOKEN`) |
| Work item edit permission for Build Service | Project Settings → Boards → Area permissions → grant `Edit work items in this node` to `<Project> Build Service` |
| Environment approval configuration | Pipelines → Environments → select env → Approvals and checks |
| Approver group membership | Project Settings → Teams or Azure AD groups |

---

## Work Item State Transition Reference (Agile Process)

| Board column | State value in API |
|---|---|
| New | `New` |
| Active / In Progress | `Active` |
| Resolved | `Resolved` |
| Closed | `Closed` |
| Custom states | Exact string as defined in process customization |

> State names are case-sensitive in the REST API. Use the exact string shown in your process template (check via: **Project Settings → Boards → Process → Work item types → States**).

---

## References

- [ADO Environment Approvals and Checks](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/approvals)
- [ADO Work Items REST API](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update)
- [ADO Work Item Comments API](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-item-comments)
- [Pipeline OAuth token access](https://learn.microsoft.com/en-us/azure/devops/pipelines/build/variables#systemaccesstoken)
- [Deployment jobs and environments](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/deployment-jobs)
- [Query-based gates (Classic)](https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/gates)

---

*Last updated: 2026-08-26*
