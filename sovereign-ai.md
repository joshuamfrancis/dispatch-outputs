# Local Sovereign AI — Build Plan, Cost Projection & Setup Guide

**Budget target:** AUD $2,500 · **Parts reference:** [centrecom.com.au](https://www.centrecom.com.au) · **Date:** July 2026
**Workload:** 33B-class LLMs for coding assistance, technical documentation, and financial data processing, self-hosted and reachable from the internet with proper AuthN/AuthZ.

> **Pricing note:** Centre Com prices move weekly with stock and specials. Figures below are anchored to prices observed at Centre Com and other AU retailers in July 2026 (e.g. RTX 5060 Ti 16GB ≈ $730–800). Re-check each line via Centre Com's [PC Builder](https://www.centrecom.com.au/buildpc) before ordering — treat this as a shopping list, not a quote.

---

## 1. Why this architecture

A 33B model needs roughly this much memory depending on quantization:

| Quant | Approx. size (33B) | Quality |
|---|---|---|
| Q4_K_M (GGUF) | ~20 GB | Very good, standard choice |
| Q5_K_M | ~23 GB | Near-lossless |
| Q3_K_M | ~15 GB | Usable, some degradation |

A single 16GB GPU can't hold a full Q4 33B model, so the recommended build uses **partial GPU offload** (most layers on GPU, remainder + KV cache spillover on fast DDR5 RAM) via `llama.cpp`/Ollama, or drops to Q3/Q4_K_S to fit fully in VRAM. The "up" tier below removes this compromise entirely with 32GB of VRAM across two GPUs.

---

## 2. Recommended build (~AUD $2,470) — target tier

| Component | Item | Est. price (AUD) |
|---|---|---|
| GPU | ASUS/Gigabyte/MSI **RTX 5060 Ti 16GB** GDDR7 | $750 |
| CPU | AMD **Ryzen 5 7600** (AM5, 6c/12t) | $290 |
| Motherboard | AM5 B650 mATX/ATX (e.g. Gigabyte B650 Eagle) | $230 |
| RAM | **64GB DDR5-6000** (2×32GB) | $290 |
| Storage (OS) | 1TB NVMe Gen4 SSD | $85 |
| Storage (models) | 2TB NVMe Gen4 SSD | $150 |
| Case | Mid-tower ATX, good airflow | $120 |
| PSU | 750W 80+ Gold, modular | $140 |
| CPU cooler | Tower air cooler | $70 |
| UPS | Line-interactive UPS (600VA+, protects an always-on box) | $150 |
| Cables/fans/thermal paste | Misc. | $40 |
| **Subtotal** | | **≈ $2,115** |
| **Contingency / shipping** (~15%) | | **≈ $355** |
| **Total** | | **≈ $2,470** |

**Category links to build from:** [RTX 5000 series](https://www.centrecom.com.au/rtx-5000-series) · [AMD AM5 CPUs](https://www.centrecom.com.au/amd-am5-9000-series) · [AM5 motherboards](https://www.centrecom.com.au/amd-socket-am5-2) · [DDR5 RAM](https://www.centrecom.com.au/ddr5-desktop-ram) · [NVMe SSDs](https://www.centrecom.com.au/nvme-ssd) · [ATX PSUs](https://www.centrecom.com.au/atx-power-supplies) · [Mid-tower cases](https://www.centrecom.com.au/mid-tower)

**Expected performance:** Qwen2.5-Coder-32B or DeepSeek-Coder-33B at Q4_K_M, ~12–18 tokens/sec generation with partial offload; comfortable for interactive coding/doc/finance-analysis use, not for high-concurrency serving.

---

## 3. One option down (~AUD $1,650) — budget tier

Cuts VRAM headroom and RAM to reduce cost; still runs 33B models, just slower and at a lower quant.

| Component | Item | Est. price (AUD) |
|---|---|---|
| GPU | **RTX 4060 Ti 16GB** (previous gen, still 16GB VRAM) | $700 |
| CPU | AMD **Ryzen 5 5600** (AM4) | $150 |
| Motherboard | AM4 B550 | $140 |
| RAM | **32GB DDR4-3200** (2×16GB) | $90 |
| Storage | 1TB NVMe Gen3 SSD | $70 |
| Case | Budget mid-tower | $90 |
| PSU | 650W 80+ Bronze | $100 |
| CPU cooler | Stock/basic air cooler | $40 |
| Misc. | Cables/fans/paste | $30 |
| **Subtotal** | | **≈ $1,410** |
| **Contingency/shipping** | | **≈ $210** |
| **Total** | | **≈ $1,620** |

**Trade-off:** 33B runs at Q3_K_M/Q4_K_S with heavier CPU offload — expect 5–9 tokens/sec, and DDR4 bandwidth becomes the bottleneck. No UPS included. Fine for occasional use; frustrating for daily driving.

---

## 4. One option up (~AUD $3,650) — headroom tier

Removes the offload compromise: 32GB VRAM fits 33B at Q5/Q6 fully on GPU, plus room to run a second smaller model (e.g. an embedding model for RAG) concurrently.

| Component | Item | Est. price (AUD) |
|---|---|---|
| GPU ×2 | **2× RTX 5060 Ti 16GB** (32GB VRAM combined) | $1,500 |
| CPU | AMD **Ryzen 7 7700** (AM5, 8c/16t) | $430 |
| Motherboard | AM5 X670E (dual PCIe x16 physical slots, x8/x8 electrical) | $320 |
| RAM | **96GB DDR5-5600** (2×48GB) | $450 |
| Storage | 2TB NVMe Gen4 SSD | $150 |
| Case | Full-tower, dual-GPU airflow | $180 |
| PSU | 850W 80+ Gold, modular | $190 |
| CPU cooler | 240mm AIO liquid cooler | $150 |
| UPS | Higher-capacity line-interactive UPS | $220 |
| Misc. | Cables/fans/paste | $60 |
| **Subtotal** | | **≈ $3,650** |

**Note on dual-GPU inference:** `llama.cpp`/Ollama split model layers across both GPUs via tensor-split; this isn't NVLink-fast multi-GPU scaling, but it fully removes CPU offload, roughly doubling throughput to ~25–35 tokens/sec and enabling longer context windows.

---

## 5. Software stack

| Layer | Choice | Why |
|---|---|---|
| OS | **Ubuntu Server 24.04 LTS** | Matches your standard OS; best NVIDIA driver/CUDA support |
| GPU drivers | NVIDIA driver 550+ / CUDA 12.4+ | Required for GGUF/vLLM GPU offload |
| Containers | **Docker + NVIDIA Container Toolkit** | Matches your Docker-first preference |
| Model runtime | **Ollama** (primary) — OpenAI-compatible API, easy GGUF model management | Simple to run in Docker, good default |
| Alt. runtime | **vLLM** | Higher throughput if you outgrow Ollama; more setup |
| Models | Qwen2.5-Coder-32B-Instruct (coding), Qwen2.5-32B-Instruct (docs/finance), DeepSeek-Coder-33B (alt. coding) | Best-in-class 30–33B class for these three tasks |
| Reverse proxy | **Caddy** (in Docker) | Auto-TLS, simple config, sits in front of Ollama's API |
| Secure exposure | **WireGuard tunnel → small AWS EC2 (ap-southeast-2)** relay, or **Cloudflare Tunnel** | See §6 |
| Authoritative authZ | **Authelia** (self-hosted OIDC/2FA) fronting Caddy, or **Cloudflare Access** | See §6 |
| Source control | GitHub repo for docker-compose, Caddyfile, Authelia config | Matches your DevOps preference |
| Image registry | Docker Hub, for any custom images you build | Matches your preference |
| Monitoring | `nvidia-smi` exporter + Prometheus/Grafana (optional) | Track VRAM/thermal headroom |

---

## 6. Exposing it to the internet with authoritative authorization

Two credible approaches — pick based on how much you want to depend on a third party for the "authority" in authorization.

### Option A — Self-sovereign (recommended, matches "sovereign AI" intent)
Your home ISP almost certainly has CGNAT, so you need a public rendezvous point — this is the one piece that isn't purely local, but it carries no model weights or data, only encrypted tunnel traffic.

1. Spin up a **cheap AWS EC2 t4g.micro** in `ap-southeast-2` (Sydney) — matches your AWS preference, ~AUD $10–12/month.
2. Run **WireGuard** on both the EC2 instance and the home server; EC2 forwards ports 443 → home server over the tunnel.
3. On the home server, **Caddy** terminates TLS (Let's Encrypt) and reverse-proxies to Ollama's API.
4. **Authelia** sits in front as an OIDC/forward-auth provider — enforces username+password+TOTP (or WebAuthn) before any request reaches Caddy/Ollama. This is your "authoritative" authorization layer: centrally defined access policy, MFA-backed, fully under your control.
5. No inbound ports opened on your home router at all — only the EC2 box is internet-facing, and it only relays WireGuard-encrypted traffic.

### Option B — Fastest to stand up
- **Cloudflare Tunnel** (`cloudflared`) from the home server — no open ports, no separate cloud VM needed.
- **Cloudflare Zero Trust Access** in front of it — policy-based auth via Google/GitHub SSO or one-time email codes, with device posture checks if wanted.
- Trade-off: your authorization boundary is now a US-headquartered third party rather than fully self-hosted — worth flagging given the "sovereign" goal, but it's genuinely fast and well-hardened.

Either way: put the model API behind an API key *in addition to* the auth layer (defence in depth), and never expose Ollama's raw port (11434) directly.

---

## 7. Installation outline

```bash
# 1. OS
# Install Ubuntu Server 24.04 LTS, enable OpenSSH during setup.

# 2. NVIDIA driver + CUDA
sudo ubuntu-drivers install
sudo reboot
nvidia-smi   # confirm GPU(s) detected

# 3. Docker + NVIDIA Container Toolkit
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 4. Ollama (containerized, GPU-enabled)
docker run -d --gpus=all -v ollama:/root/.ollama -p 127.0.0.1:11434:11434 \
  --name ollama --restart unless-stopped ollama/ollama

docker exec -it ollama ollama pull qwen2.5-coder:32b
docker exec -it ollama ollama pull qwen2.5:32b

# 5. Caddy (reverse proxy, TLS) — run via docker-compose (repo below)
# 6. Authelia (authZ) — run via docker-compose (repo below)
# 7. WireGuard — install on both EC2 relay and home server; configure peers
#    sudo apt install wireguard; wg genkey | tee privatekey | wg pubkey > publickey

# 8. Verify end-to-end
curl -H "Authorization: Bearer <api-key>" https://ai.yourdomain.com/api/generate ...
```

Keep `docker-compose.yml`, `Caddyfile`, and `authelia/configuration.yml` in a private GitHub repo (not `dispatch-outputs` — keep secrets/configs separate from generated outputs) with a `.env.example` for secrets, and use GitHub Actions (self-hosted runner on the box, or SSH deploy) to redeploy on push.

---

## 8. Minimum OS/software requirements summary

- Ubuntu Server 24.04 LTS, kernel ≥ 6.8
- NVIDIA driver ≥ 550, CUDA ≥ 12.4
- Docker Engine ≥ 26, NVIDIA Container Toolkit
- WireGuard (or `cloudflared`) for tunnel
- Ollama ≥ 0.5 (or vLLM ≥ 0.6 for the "up" tier)
- Caddy ≥ 2.7, Authelia ≥ 4.38 (Option A) — or a Cloudflare Zero Trust account (Option B)
- 100Mbps+ upload from your ISP recommended if serving larger contexts remotely; otherwise usable at lower speeds since inference is compute-, not bandwidth-, bound
