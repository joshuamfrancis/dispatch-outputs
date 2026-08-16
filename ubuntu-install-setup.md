# Ubuntu 26.04 LTS "Resolute Raccoon" — Workstation Build Run Sheet

**Target OS:** Ubuntu Desktop 26.04 LTS (codename `resolute`, released 23 Apr 2026)
**Goal:** Bring a freshly installed desktop to a known-good developer baseline, then capture a Timeshift snapshot of that baseline.
**Packaging preference:** native `.deb` via APT (Canonical archive first, then vendor APT repos, then vendor `.deb`, then AppImage as last resort). No Flatpak. Snap is avoided except for Thunderbird and Firefox, which use Ubuntu's defaults — see §10.

---

## 0. Read this first — release-specific notes

| Item | Note |
|---|---|
| Codename | `resolute` — verify with `lsb_release -cs`. Vendor repo lines below derive this automatically. |
| Python | 26.04 ships **Python 3.14** as `python3`. Do not remove or replace the system Python. |
| Java | `default-jdk` now points at **OpenJDK 25** (previous LTS default was 21). |
| Display server | 26.04 is **Wayland-only**. Affects OBS (use PipeWire capture) and global-hotkey apps. |
| Snap reality check | Ubuntu Desktop 26.04 uses Snap for App Center, Firefox and Thunderbird. This run sheet accepts the Mozilla defaults (§10) and routes around Snap everywhere else. Do **not** purge `snapd` on this build — it would break Thunderbird, Firefox and App Center. §10.6 covers switching Mozilla to `.deb` later if you want the option back. |
| APT keyring dir | Use `/etc/apt/keyrings/` for all third-party keys. Create it once: `sudo install -m 0755 -d /etc/apt/keyrings` |
| Source format | Prefer the modern deb822 `.sources` format over legacy `.list`. Both work; deb822 is the direction Debian/Ubuntu are moving. |

### Run order (do not reorder 1 → 12)

1. Baseline system update & essential tools
2. Timeshift (install only — snapshot comes last)
3. Git
4. SSH keys + GitHub
5. Python toolchain
6. OpenJDK
7. VS Code
8. Docker Engine + Compose
9. Claude Desktop
10. Thunderbird + Firefox (Ubuntu defaults)
11. Arduino IDE, draw.io, balenaEtcher, OBS Studio
12. Proton VPN + RoboForm extension
13. Verify everything → **take the Timeshift baseline snapshot**

---

## 1. Baseline system update and essential tools

```bash
sudo apt update && sudo apt full-upgrade -y

sudo apt install -y \
  ca-certificates curl wget gnupg apt-transport-https \
  build-essential pkg-config \
  software-properties-common \
  git-lfs unzip zip xz-utils \
  htop tree jq net-tools \
  gnome-tweaks gir1.2-ayatanaappindicator3-0.1

sudo install -m 0755 -d /etc/apt/keyrings
```

GNOME has had no system tray since 3.26. Ubuntu rebuilds one from two independent pieces, and both must be present:

- **Host** — `gnome-shell-extension-appindicator`, shown in the Extensions app as **Ubuntu AppIndicators**. It watches D-Bus for StatusNotifierItem registrations and draws them in the top bar. Ships enabled on Ubuntu Desktop, but confirm it — a GNOME version bump can silently mark extensions incompatible, and the symptom is identical to not having it.
- **Provider typelib** — `gir1.2-ayatanaappindicator3-0.1`, the GObject Introspection metadata that lets Python/GTK apps call the appindicator library at runtime.

The typelib is only needed by **Proton VPN** (§12.1), whose GUI is Python and does `gi.require_version('AyatanaAppIndicator3', '0.1')` — without it that import raises and the tray icon silently never appears, though the app itself runs fine. OBS uses Qt's `QSystemTrayIcon`, which speaks the D-Bus protocol directly, and Timeshift's `.deb` pulls its own dependencies; for both, only the *extension* matters.

Since StatusNotifierItem is a D-Bus protocol rather than the old X11 XEmbed one, it survives 26.04 being Wayland-only.

```bash
gnome-extensions list --enabled | grep -i appindicator
gnome-extensions enable ubuntu-appindicators@ubuntu.com   # if missing
```

Confirm your codename before adding any vendor repo:

```bash
lsb_release -cs     # expect: resolute
```

Reboot if the upgrade pulled a new kernel:

```bash
sudo reboot
```

---

## 2. Timeshift (install now, snapshot later)

Timeshift is in Ubuntu's `universe` component — plain APT, no third-party repo.

```bash
sudo apt install -y timeshift
```

**Do not create the snapshot yet.** Configure it now, snapshot in §13.

### Configuration

Launch Timeshift (`sudo timeshift-gtk`) and set:

| Setting | Recommendation |
|---|---|
| **Snapshot type** | `RSYNC` unless your root filesystem is Btrfs with `@`/`@home` subvolumes — then choose `BTRFS` (instant, near-zero space). Check with `findmnt -no FSTYPE /`. |
| **Snapshot location** | A **separate disk or partition** from `/`. A snapshot on the same disk does not protect you from disk failure. |
| **Schedule** | Weekly ×3, Monthly ×2 is a sane desktop default. Disable hourly. |
| **User home dirs** | Default is *exclude*. Keep it excluded — your home belongs in a separate data backup (Déjà Dup / restic / rsync to NAS), not in system snapshots. |

### Recommended extra exclusions

Add these under **Settings → Filters** so snapshots stay small:

```
/var/lib/docker/**
/var/lib/containerd/**
/var/cache/apt/archives/**
/home/*/.cache/**
/swapfile
```

Docker's image/layer store can be tens of GB and is fully reproducible from Docker Hub — there is no value in snapshotting it.

> **Timeshift is not a backup of your data.** It restores the *operating system*. Keep a separate backup for `/home`, and keep source code in GitHub.

---

## 3. Git

```bash
sudo apt install -y git git-lfs
```

### Configuration

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"

git config --global init.defaultBranch main
git config --global pull.rebase true
git config --global core.editor "code --wait"     # set after §7
git config --global credential.helper "cache --timeout=3600"
git config --global rerere.enabled true

git lfs install
```

Optional but recommended — the GitHub CLI, from GitHub's own APT repo:

```bash
sudo curl -fsSLo /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  https://cli.github.com/packages/githubcli-archive-keyring.gpg
sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg

sudo tee /etc/apt/sources.list.d/github-cli.sources >/dev/null <<'EOF'
Types: deb
URIs: https://cli.github.com/packages
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/githubcli-archive-keyring.gpg
EOF

sudo apt update && sudo apt install -y gh
```

---

## 4. SSH keys for GitHub

### 4.1 Generate the key

```bash
ssh-keygen -t ed25519 -C "your-name@workstation-2604" -f ~/.ssh/id_ed25519_github
```

Use a strong passphrase. `ed25519` is the correct choice; only fall back to `-t rsa -b 4096` if you must talk to something ancient.

### 4.2 Load it into the agent

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_github
```

### 4.3 Persist via `~/.ssh/config`

```bash
cat >> ~/.ssh/config <<'EOF'

Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
    AddKeysToAgent yes
EOF

chmod 600 ~/.ssh/config
chmod 700 ~/.ssh
```

GNOME's Keyring will prompt for the passphrase once per login and cache it.

### 4.4 Add the public key to GitHub

```bash
cat ~/.ssh/id_ed25519_github.pub
```

Copy the output → GitHub → **Settings → SSH and GPG keys → New SSH key** → paste, name it after the machine.

Or, if you installed `gh`:

```bash
gh auth login          # choose SSH, let it upload the key
```

### 4.5 Verify

```bash
ssh -T git@github.com
# Expected: "Hi <username>! You've successfully authenticated,
#            but GitHub does not provide shell access."
```

### 4.6 Optional — signed commits

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519_github.pub
git config --global commit.gpgsign true
```

Then add the *same* public key to GitHub a second time, this time with key type **Signing Key**, so commits show as Verified.

> **Back this up.** `~/.ssh` lives in your home directory, which Timeshift excludes. Copy the private key to an encrypted offline store, or accept that you'll regenerate it after a rebuild.

---

## 5. Python toolchain

Python 3.14 is already present as `python3` — but **not** everything you need. Ubuntu splits CPython's stdlib across several `.deb`s, and `venv` is not in the default desktop set. On a stock install:

```
$ python3 -m venv .venv
The virtual environment was not created successfully because ensurepip is not
available.  On Debian/Ubuntu systems, you need to install the python3-venv
package using the following command.

    apt install python3.14-venv
```

The `venv` module itself is present; Debian strips out the bundled `ensurepip` (which carries the private pip copy used to seed a new environment) into a separate package. Without it, `venv` builds the directory tree, fails to populate pip, and rolls back.

### Option A — minimal (recommended)

```bash
sudo apt install -y python3-venv python3-dev
```

That is the whole real gap. `build-essential` you already have from §1, and it is the other half of what `python3-dev` is for — headers alone are useless without a compiler.

- `python3-venv` — the actual fix. Install the *unversioned* name: it is a metapackage tracking the current default interpreter, so it pulls `python3.14-venv` on 26.04 and will follow the interpreter forward on upgrade.
- `python3-dev` — CPython headers, needed by any dependency lacking a prebuilt wheel for your platform. You will not need it until an install dies with `fatal error: Python.h: No such file or directory`, and at that moment you need it immediately. Cheap insurance on a machine you are about to snapshot.

Everything else below is convenience, not requirement.

### Option B — full

```bash
sudo apt install -y \
  python3-venv python3-dev python3-pip python3-full \
  pipx

pipx ensurepath
```

Log out/in (or `source ~/.profile`) so `~/.local/bin` lands on your `PATH`.

| Package | What it buys you | Skip if |
|---|---|---|
| `python3-pip` | `pip` usable *outside* a venv | You are strict about venvs — every venv has its own pip regardless |
| `pipx` | Isolated installs of standalone CLI tools (`ruff`, `poetry`, `uv`) | You install dev tools per-project instead |
| `python3-full` | Metapackage: venv + pip + dev + tk + full stdlib in one | You prefer to name what you install |

`python3-full` is arguably the simplest single choice if you would rather not think about it — it is a superset of Option A.

### Escape hatch

For the record, this works on a completely stock system:

```bash
python3 -m venv --without-pip .venv
```

A genuine isolated environment with no package manager inside it. Occasionally useful for inspecting the seam between `venv` and `ensurepip`; almost never what you actually want.

### PEP 668 — read this

Ubuntu marks the system Python as *externally managed*. `pip install --user requests` will refuse to run. This is correct behaviour, not a bug. Two supported paths:

**Per-project virtual environments** (default for application code):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**`pipx` for standalone CLI tools** (each gets its own isolated venv):

```bash
pipx install ruff
pipx install black
pipx install poetry
pipx install uv          # fast resolver/installer, worth having
```

Never use `pip install --break-system-packages` on the system interpreter. It is a footgun that will eventually cost you an afternoon.

---

## 6. OpenJDK

`default-jdk` on 26.04 gives you OpenJDK 25:

```bash
sudo apt install -y default-jdk
java -version
javac -version
```

If a project pins an older LTS, install alongside — Ubuntu supports multiple JDKs concurrently:

```bash
sudo apt install -y openjdk-21-jdk        # or openjdk-17-jdk
```

### Switching versions

```bash
sudo update-alternatives --config java
sudo update-alternatives --config javac
```

### JAVA_HOME

```bash
echo 'export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which javac))))' \
  | sudo tee /etc/profile.d/java_home.sh
sudo chmod +x /etc/profile.d/java_home.sh
```

Log out/in, then confirm: `echo $JAVA_HOME` → `/usr/lib/jvm/java-25-openjdk-amd64`.

Build tools:

```bash
sudo apt install -y maven gradle
```

---

## 7. Visual Studio Code

Microsoft's official APT repo — genuine `.deb`, updates through `apt upgrade`.

```bash
wget -qO- https://packages.microsoft.com/keys/microsoft.asc \
  | gpg --dearmor \
  | sudo tee /etc/apt/keyrings/packages.microsoft.gpg >/dev/null
sudo chmod go+r /etc/apt/keyrings/packages.microsoft.gpg

sudo tee /etc/apt/sources.list.d/vscode.sources >/dev/null <<'EOF'
Types: deb
URIs: https://packages.microsoft.com/repos/code
Suites: stable
Components: main
Architectures: amd64 arm64 armhf
Signed-By: /etc/apt/keyrings/packages.microsoft.gpg
EOF

sudo apt update && sudo apt install -y code
```

> If you also install `code` from the vendor `.deb` directly, remove the duplicate `/etc/apt/sources.list.d/vscode.list` it drops, or `apt update` will warn about a duplicate source.

### Extensions (CLI install)

```bash
for ext in \
  ms-python.python \
  ms-python.vscode-pylance \
  ms-python.debugpy \
  charliermarsh.ruff \
  ms-azuretools.vscode-docker \
  ms-vscode-remote.remote-containers \
  ms-vscode-remote.remote-ssh \
  redhat.java \
  vscjava.vscode-java-debug \
  vscjava.vscode-maven \
  github.vscode-pull-request-github \
  github.vscode-github-actions \
  eamodio.gitlens \
  redhat.vscode-yaml \
  hediet.vscode-drawio \
  amazonwebservices.aws-toolkit-vscode \
  anthropic.claude-code
do
  code --install-extension "$ext" --force
done
```

`hediet.vscode-drawio` lets you edit `.drawio` files inside VS Code — useful alongside the desktop app in §11.

### Settings worth setting

**Settings → sync:** sign in with your GitHub account to enable Settings Sync. That way this list becomes irrelevant on the *next* rebuild.

Wayland note: if you hit blurry rendering or IME issues, force native Wayland via `code --ozone-platform-hint=auto`, or set it permanently in `~/.config/code-flags.conf`.

---

## 8. Docker Engine + Compose

Docker officially supports `resolute`. Use Docker's own repo, not Ubuntu's `docker.io`.

### 8.1 Remove conflicting packages

```bash
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt remove -y $pkg 2>/dev/null
done
```

On a fresh install this is a no-op — run it anyway.

### 8.2 Add the repository

```bash
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
```

*(Note the unquoted `EOF` here — the command substitutions must expand.)*

If `apt update` 404s because Docker hasn't published `resolute` yet, edit the `Suites:` line to `noble` and re-run. Docker Engine has no hard dependency on the Ubuntu release.

### 8.3 Install

```bash
sudo apt install -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

### 8.4 Post-install — run Docker without sudo

```bash
sudo groupadd -f docker
sudo usermod -aG docker $USER
newgrp docker            # or log out and back in
```

> **Security note:** membership of the `docker` group is equivalent to root. That's an accepted trade-off on a single-user workstation; on a shared or exposed machine, use rootless mode instead (`dockerd-rootless-setuptool.sh install`).

### 8.5 Enable at boot and verify

```bash
sudo systemctl enable --now docker containerd
docker run --rm hello-world
docker compose version
docker buildx version
```

### 8.6 Docker Hub login

```bash
docker login -u <your-dockerhub-username>
```

Use a **Personal Access Token** from Docker Hub → *Account Settings → Personal access tokens*, not your account password. Credentials land in `~/.docker/config.json` base64-encoded — for encrypted-at-rest storage install a credential helper:

```bash
sudo apt install -y pass gnupg2
# then configure docker-credential-pass
```

### 8.7 Optional daemon hygiene

```bash
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "default-address-pools": [
    { "base": "172.30.0.0/16", "size": 24 }
  ]
}
EOF
sudo systemctl restart docker
```

Log rotation stops a chatty container filling `/var`. The address pool avoids collisions with corporate VPN subnets on `172.17.x.x`.

---

## 9. Claude Desktop

Anthropic ships an official Linux beta (Ubuntu 22.04+/Debian 12+, amd64 and arm64) from its own APT repo. It bundles Chat, Cowork and Claude Code in one window.

```bash
sudo curl -fsSLo /etc/apt/keyrings/claude-desktop-archive-keyring.asc \
  https://downloads.claude.ai/claude-desktop/key.asc

sudo tee /etc/apt/sources.list.d/claude-desktop.sources >/dev/null <<'EOF'
Types: deb
URIs: https://downloads.claude.ai/claude-desktop/apt/stable
Suites: stable
Components: main
Architectures: amd64 arm64
Signed-By: /etc/apt/keyrings/claude-desktop-archive-keyring.asc
EOF

sudo apt update && sudo apt install -y claude-desktop
```

The package installs a legacy `.list` source of its own. Remove the duplicate so `apt update` stays clean:

```bash
sudo rm -f /etc/apt/sources.list.d/claude-desktop.list
sudo rm -f /usr/share/keyrings/claude-desktop-archive-keyring.asc
```

Launch from the app grid, or `claude-desktop`. Sign in with your Claude account (a Console API key alone won't work for Desktop).

### Known Linux-beta gaps

- No Computer Use
- No voice dictation
- Quick Entry global hotkey needs a `GlobalShortcuts` portal — patchy on Wayland, which 26.04 is exclusively

### Claude Code CLI (optional, terminal workflow)

The Desktop app includes Claude Code, but if you want it standalone in the terminal:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Review any piped installer before running it. Verify with `claude --version` and `claude doctor`.

---

## 10. Thunderbird and Firefox — Ubuntu defaults

This section uses Canonical's shipped packages as-is. Both are Snaps on 26.04, which is the one deliberate departure from the no-Snap rule in this run sheet — see the note at the end for what you are trading away and how to reverse it.

### 10.1 Install

```bash
sudo apt update
sudo apt install -y thunderbird firefox
```

Firefox is normally present already on a fresh Ubuntu Desktop install; the command is idempotent, so run it regardless.

Both `apt` names are **transitional packages**. They contain no application — their only job is to invoke `snapd` and install the corresponding Snap. Expect `snapd` activity in the output, and expect it to take noticeably longer than a `.deb` on first run.

### 10.2 Verify

```bash
snap list thunderbird firefox
which thunderbird firefox        # /snap/bin/... is correct here
apt policy thunderbird | head -3
```

`which` returning `/snap/bin/thunderbird` confirms the expected outcome. `apt policy` will show the transitional stub's version, which does *not* match the application version — check the real one with `snap list` or **Help → About**.

### 10.3 First-run behaviour

Snap-packaged Mozilla apps are confined, which changes a few things you may notice:

| Behaviour | Why |
|---|---|
| Slow first launch after install or update | Snap decompresses and sets up the mount namespace once |
| File dialogs limited to `~/`, `/media`, `/run/media` | Confinement. Use the XDG portal dialog, or `snap connect` extra interfaces |
| Cannot attach files from `/tmp` or arbitrary system paths | Same — copy into `~/` first |
| GPG/Enigmail smartcard readers may not be seen | Hardware interfaces need explicit connection |
| Profiles live in `~/snap/thunderbird/common/