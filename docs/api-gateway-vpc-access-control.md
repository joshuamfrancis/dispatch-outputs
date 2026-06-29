# AWS API Gateway — VPC Access Restriction for HTTP APIs and WebSocket APIs

## Overview

This document covers the mechanisms available to restrict access to AWS API Gateway **HTTP APIs** (v2) and **WebSocket APIs** (v2) so that only traffic originating from within a VPC can reach them.

> **Critical distinction before you start**
>
> The "private API" feature — where an API is only reachable via a VPC Interface Endpoint (PrivateLink) — exists **only for REST APIs (v1)**. HTTP APIs and WebSocket APIs do **not** support the private endpoint type or API-level resource policies. This means there is no single native "flip a switch to make it VPC-only" mechanism for these API types. Instead, you combine the mechanisms below to enforce VPC-origin access.

---

## Mechanism 1 — AWS WAF IP-Based Rules (Recommended for Network-Layer Restriction)

AWS WAF (Web Application Firewall) can be attached directly to an HTTP API or WebSocket API stage. You create an **IP set** containing your VPC's CIDR ranges (or the Elastic IPs of your NAT Gateways) and configure a Web ACL rule to **block all traffic not matching that set**.

**How it works:**

1. Create an IP set in WAF with your allowed VPC CIDRs or NAT Gateway EIPs.
2. Create a Web ACL with a rule: allow if source IP is in the set, otherwise block (default action: `Block`).
3. Associate the Web ACL with your API Gateway HTTP API or WebSocket API stage.

**Example Web ACL rule logic:**

```
IF source IP NOT IN [10.0.0.0/8, 172.16.0.0/12, <NAT-GW-EIP>]
THEN Block (403)
```

**Considerations:**

- Traffic from EC2 instances in a VPC exits through either the instance's public IP (if it has one) or the NAT Gateway Elastic IP. WAF sees the **public IP**, not the private RFC-1918 address. You must allow-list your NAT Gateway EIPs rather than private CIDRs for internet-egress flows.
- If clients call the API from within the VPC using a VPC Endpoint for API Gateway execute-api, the source IP seen by WAF is the **private IP** of the VPC endpoint ENI. In that case, you can allow-list the private subnet CIDRs.
- WAF rules are evaluated per-request and incur per-request cost beyond the free tier.
- WAF supports HTTP APIs and WebSocket APIs in all commercial regions.

**Terraform snippet:**

```hcl
resource "aws_wafv2_ip_set" "vpc_ips" {
  name               = "vpc-allowed-ips"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"
  addresses          = ["<NAT-GW-EIP>/32", "10.0.0.0/16"]
}

resource "aws_wafv2_web_acl" "api_acl" {
  name  = "api-vpc-only"
  scope = "REGIONAL"

  default_action { block {} }

  rule {
    name     = "allow-vpc"
    priority = 1
    action { allow {} }
    statement {
      ip_set_reference_statement {
        arn = aws_wafv2_ip_set.vpc_ips.arn
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "allow-vpc"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "api-vpc-only-acl"
    sampled_requests_enabled   = true
  }
}

resource "aws_apigatewayv2_stage" "default" {
  # ... your stage config
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_apigatewayv2_stage.default.arn
  web_acl_arn  = aws_wafv2_web_acl.api_acl.arn
}
```

---

## Mechanism 2 — Lambda Authorizer with Source IP Inspection

A **Lambda authorizer** runs before your integration on every request. It receives the full request context, including `requestContext.http.sourceIp` (HTTP APIs) or `requestContext.identity.sourceIp` (WebSocket APIs), and returns an IAM policy or a simple allow/deny response.

You can use this to enforce VPC-origin access at the application layer by checking the caller's IP against an allowed range.

**Lambda authorizer flow:**

```
Client → API Gateway → Lambda Authorizer (IP check) → Integration (if allowed)
                                    ↓ 403 if denied
```

**Python example (HTTP API simple response mode):**

```python
import ipaddress

ALLOWED_CIDRS = [
    ipaddress.ip_network("10.0.0.0/16"),       # VPC CIDR
    ipaddress.ip_network("203.0.113.5/32"),     # NAT Gateway EIP
]

def lambda_handler(event, context):
    source_ip = event["requestContext"]["http"]["sourceIp"]

    try:
        addr = ipaddress.ip_address(source_ip)
    except ValueError:
        return {"isAuthorized": False}

    for cidr in ALLOWED_CIDRS:
        if addr in cidr:
            return {"isAuthorized": True}

    return {"isAuthorized": False}
```

**WebSocket API authorizer note:** Lambda authorizers for WebSocket APIs run only on the `$connect` route. Once a connection is established, it is not re-evaluated per message. This is important — an IP-based authorizer prevents the initial connection from non-VPC sources but does not disconnect an existing session if its IP changes.

**Considerations:**

- Lambda authorizer adds latency to every request (typical p99: 5–20 ms cold start with Provisioned Concurrency).
- Use **response caching** (TTL up to 3600s) where appropriate to reduce Lambda invocations and latency.
- The source IP seen is still the **public** IP unless the caller is going through a VPC Endpoint. Plan accordingly.
- Combine with WAF for defence in depth — WAF blocks at the network layer before Lambda is even invoked.

---

## Mechanism 3 — IAM Authorization with `aws:SourceVpc` / `aws:SourceVpce` Conditions

HTTP APIs and WebSocket APIs support **IAM authorization** (`AWS_IAM`). When enabled, callers must sign requests with SigV4 using valid AWS credentials. You can scope down permissions using IAM policies on the calling principal with condition keys.

**Relevant condition keys:**

| Condition Key | What it checks |
|---|---|
| `aws:SourceVpc` | Request originated from a specific VPC ID |
| `aws:SourceVpce` | Request came through a specific VPC endpoint ID |
| `aws:VpcSourceIp` | Source private IP within the VPC (available when calling via VPC endpoint) |

**Example IAM policy attached to the calling role:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "execute-api:Invoke",
      "Resource": "arn:aws:execute-api:us-east-1:123456789012:abc123/*",
      "Condition": {
        "StringEquals": {
          "aws:SourceVpc": "vpc-0a1b2c3d4e5f"
        }
      }
    }
  ]
}
```

**How to route the call through the VPC for this to work:**

The `aws:SourceVpc` and `aws:SourceVpce` condition keys are only populated when the API is called **through a VPC Interface Endpoint** for `execute-api`. Without the endpoint, the condition context is absent and the policy evaluates to a deny.

Steps:
1. Create an Interface VPC Endpoint for `com.amazonaws.<region>.execute-api` in your VPC.
2. Enable private DNS on the endpoint so `<api-id>.execute-api.<region>.amazonaws.com` resolves to the endpoint's private IPs within the VPC.
3. Callers within the VPC hit the private DNS name; the condition keys are populated.
4. Callers from outside the VPC use the public DNS name; the condition keys are absent and the policy denies.

> **Note:** Even though HTTP APIs and WebSocket APIs don't support *private endpoint type* (REST API concept), they can still be called *through* a VPC endpoint for `execute-api`. The difference is that the public URL remains reachable unless you also apply WAF or a deny-by-default resource policy (the latter requires REST API; for HTTP APIs, use WAF as the network-layer block).

**Considerations:**

- IAM authorization requires callers to implement SigV4 signing, which adds SDK complexity for browser-based clients.
- Suitable for service-to-service calls within a VPC (e.g., ECS task calling an HTTP API) where the calling service has an IAM role.
- Not suitable as the sole VPC restriction if you need to support unauthenticated or third-party clients.

---

## Mechanism 4 — VPC Link (Private Integration — Controls Egress, Not Ingress)

A **VPC Link V2** connects API Gateway to backend resources inside your VPC — an NLB, ALB, or ECS service — without traversing the public internet. This is about where the API *routes traffic to*, not who can *access* the API.

```
Internet → HTTP API → VPC Link → NLB (private) → ECS / EC2 in VPC
```

VPC Link does **not** restrict who can call the API from the outside. It only ensures the backend integration is private.

Where VPC Link becomes relevant for access restriction is in an **architecture pattern**:

- Deploy your HTTP API with a VPC Link to a private NLB.
- Do **not** advertise the API Gateway URL externally.
- Internal services call the API via its public URL, but you add WAF + IAM auth (Mechanisms 1 & 3) to block non-VPC callers.
- The backend integration never leaves the AWS network.

**Setting up VPC Link V2 (AWS CLI):**

```bash
aws apigatewayv2 create-vpc-link \
  --name my-vpc-link \
  --subnet-ids subnet-abc123 subnet-def456 \
  --security-group-ids sg-0123456789abcdef0
```

Then reference the VPC link in your integration:

```bash
aws apigatewayv2 create-integration \
  --api-id <api-id> \
  --integration-type HTTP_PROXY \
  --integration-uri arn:aws:elasticloadbalancing:...:listener/... \
  --connection-type VPC_LINK \
  --connection-id <vpc-link-id> \
  --payload-format-version 1.0
```

---

## Mechanism 5 — Mutual TLS (mTLS)

HTTP APIs and WebSocket APIs support **mutual TLS authentication**. You configure a custom domain with a truststore (an S3 object containing trusted CA certificates). Clients must present a valid certificate signed by a trusted CA.

Since certificates are only issued to known clients (e.g., services within your VPC), this effectively restricts callers to those with valid client certificates.

```
VPC Client (with cert) → HTTPS + mTLS → API Gateway Custom Domain → HTTP API
External Client (no cert) → 403 Forbidden
```

**How to configure:**

1. Upload a truststore bundle (PEM-encoded CA certificates) to S3.
2. Configure a custom domain name with mTLS:

```bash
aws apigatewayv2 create-domain-name \
  --domain-name api.internal.example.com \
  --domain-name-configurations CertificateArn=arn:aws:acm:...:certificate/... \
  --mutual-tls-authentication TruststoreUri=s3://my-bucket/truststore.pem
```

3. Issue client certificates from your internal CA only to services within the VPC.

**Considerations:**

- mTLS requires a **custom domain name** — it does not work with the default `execute-api` URL.
- Certificate management (issuance, rotation, revocation) adds operational overhead. Use AWS Private CA for internal cert management.
- mTLS can be layered with any other mechanism (IAM, Lambda authorizer, WAF).

---

## Comparison Summary

| Mechanism | API Types | Blocks at Layer | Requires VPC Endpoint | Client Impact |
|---|---|---|---|---|
| **WAF IP Rules** | HTTP, WebSocket | Network (before auth) | No | None |
| **Lambda Authorizer + IP check** | HTTP, WebSocket | Application | No | None |
| **IAM Auth + SourceVpc condition** | HTTP, WebSocket | IAM policy | Yes (for condition to populate) | Must sign with SigV4 |
| **VPC Link** | HTTP, WebSocket | Integration (egress only) | No | None — this controls routing, not access |
| **Mutual TLS** | HTTP, WebSocket | TLS handshake | No | Must present client certificate |
| **Private Endpoint (REST only)** | REST API only | Network | Yes | DNS resolution only within VPC |

---

## Recommended Combination for Strict VPC-Only Access

For HTTP APIs and WebSocket APIs where you need to ensure **only VPC traffic can reach the API**:

1. **WAF Web ACL** → block all IPs not matching your NAT Gateway EIPs or VPC endpoint private CIDRs. This is your primary network-layer gate.
2. **IAM authorization + Interface VPC Endpoint** → service-to-service calls within the VPC use SigV4. The `aws:SourceVpc` condition in the calling role's policy ensures only that VPC can invoke the API.
3. **Lambda authorizer** (optional, for non-IAM clients) → validates source IP or a custom header/token that only VPC-internal services can obtain.
4. **mTLS** (optional, for high-assurance environments) → add certificate-based client identity on top of the above.

WAF alone is the minimum viable control. IAM + VPC endpoint is the most native AWS control. The combination of both is defence-in-depth.

---

## References

- [Control and manage access to HTTP APIs — AWS Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control.html)
- [Control and manage access to WebSocket APIs — AWS Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api-control-access.html)
- [Set up VPC links V2 in API Gateway — AWS Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vpc-links.html)
- [Control HTTP APIs with Lambda authorizers — AWS Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-lambda-authorizer.html)
- [Private REST APIs in API Gateway — AWS Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-private-apis.html)
- [Best Practices for Designing API Gateway Private APIs and Private Integration — AWS Whitepaper](https://docs.aws.amazon.com/whitepapers/latest/best-practices-api-gateway-private-apis-integration/websocket-api.html)
- [Evaluating access control methods to secure API Gateway APIs — AWS Compute Blog](https://aws.amazon.com/blogs/compute/evaluating-access-control-methods-to-secure-amazon-api-gateway-apis/)
- [VPC endpoint policies — AWS Docs](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-access.html)

---

*Last updated: 2026-06-29*
