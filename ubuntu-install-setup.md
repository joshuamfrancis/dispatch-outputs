# Ubuntu 26.04 LTS "Resolute Raccoon" — Workstation Build Run Sheet

**Target OS:** Ubuntu Desktop 26.04 LTS (codename `resolute`, released 23 Apr 2026)
**Goal:** Bring a freshly installed desktop to a known-good developer baseline, then capture a Timeshift snapshot of that baseline.
**Packaging preference:** native `.deb` via APT (Canonical archive first, then vendor APT repos, then vendor `.deb`, then AppImage as last resort). No Snap, no Flatpak.

---

## 0. Read this first — release-specific notes

| Item | Note |
|---|---|
| Codename | `resolute` — verify with `lsb_release -cs`. Vendor repo lines below derive this automatically. |
| Python | 26.04 ships **Python 3.14** as `python3`. Do not remove or replace the system Python. |
| Java | `default-jdk` now points at **OpenJDK 25** (previous LTS default was 21). |
| Display server | 26.04 is **Wayland-only**. Affects OBS (use PipeWire capture) and global-hotkey apps. |
| Snap reality check | Ubuntu Desktop 26.04 still uses Snap for App Center, Firefox and Thunderbird's transitional package. This run sheet routes around those with `.deb` alternatives. Fully purging `snapd` is possible but removes App Center — see §13. |
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
10. Thunderbird (+ Firefox) as `.deb`
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

`gir1.2-ayatanaappindicator3-0.1` plus the **AppIndicator** GNOME extension is what makes tray icons work — Proton VPN, Timeshift and OBS all want it. Enable it in **Extensions → Ubuntu AppIndicators**.

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

Python 3.14 is already present. Add the developer pieces:

```bash
sudo apt install -y \
  python3-pip python3-venv python3-dev python3-full \
  pipx

pipx ensurepath
```

Log out/in (or `source ~/.profile`) so `~/.local/bin` lands on your `PATH`.

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

## 10. Thunderbird as a `.deb` (not Snap)

On 24.04 and 26.04 `apt install thunderbird` installs a **transitional package that pulls in the Snap** and reinstalls `snapd`. To get a real `.deb`, use Mozilla's own APT repository and pin it above the Ubuntu archive.

### 10.1 Add Mozilla's repo

```bash
wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- \
  | sudo tee /etc/apt/keyrings/packages.mozilla.org.asc >/dev/null
```

Verify the key fingerprint — expect `35BAA0B3 3E9EB396 F59CA838 C0BA5CE6 DC6315A3`:

```bash
gpg -n -q --import --import-options import-show \
  /etc/apt/keyrings/packages.mozilla.org.asc | awk '/pub/{getline; gsub(/ /,""); print $0}'
```

```bash
sudo tee /etc/apt/sources.list.d/mozilla.sources >/dev/null <<'EOF'
Types: deb
URIs: https://packages.mozilla.org/apt
Suites: mozilla
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/packages.mozilla.org.asc
EOF
```

### 10.2 Pin Mozilla above Ubuntu — this step is mandatory

Without the pin, Ubuntu's transitional package wins on version number and you get the Snap anyway.

```bash
sudo tee /etc/apt/preferences.d/mozilla >/dev/null <<'EOF'
Package: *
Pin: origin packages.mozilla.org
Pin-Priority: 1000

Package: firefox*
Pin: release o=Ubuntu
Pin-Priority: -1

Package: thunderbird*
Pin: release o=Ubuntu
Pin-Priority: -1
EOF
```

### 10.3 Remove any Snap versions, then install

```bash
sudo snap remove --purge thunderbird 2>/dev/null
sudo snap remove --purge firefox 2>/dev/null

sudo apt update
sudo apt install -y thunderbird firefox
```

Verify you got the real thing:

```bash
apt policy thunderbird     # Installed version should come from packages.mozilla.org
which thunderbird          # /usr/bin/thunderbird, not /snap/bin/
```

> **Alternative:** the `ppa:mozillateam/ppa` Launchpad PPA also ships Thunderbird ESR and Firefox `.deb`s and supports 26.04. Same pinning requirement applies, with `Pin: release o=LP-PPA-mozillateam` / `Pin-Priority: 1001`. Pick one route, not both.

### 10.4 Thunderbird configuration

- Add accounts via **Account Setup**; use OAuth2 where the provider supports it (Gmail, M365).
- **Settings → General → Config Editor** if you need `mail.server.default.check_all_folders_for_new`.
- Your profile lives in `~/.thunderbird/` — that is *not* covered by Timeshift. Back it up separately, or use IMAP so the server is the source of truth.

---

## 11. Utilities: Arduino IDE, draw.io, balenaEtcher, OBS Studio

### 11.1 Arduino IDE 2.x — AppImage

There is no official `.deb` or APT repo for Arduino IDE 2.x. Upstream ships an x86_64 **AppImage**. This is the one exception to the no-AppImage rule; the Snap is stuck on 1.8.19 and the Flatpak is community-maintained.

```bash
sudo apt install -y libfuse2t64          # AppImages need FUSE 2

mkdir -p ~/Applications
cd ~/Applications
# Grab the current Linux AppImage URL from https://www.arduino.cc/en/software
wget -O arduino-ide.AppImage "<paste-appimage-url>"
chmod +x arduino-ide.AppImage
```

Desktop entry so it appears in the app grid:

```bash
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/arduino-ide.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Arduino IDE
Comment=Arduino IDE 2.x
Exec=$HOME/Applications/arduino-ide.AppImage %U
Icon=$HOME/Applications/arduino-ide.png
Terminal=false
Categories=Development;IDE;Electronics;
StartupWMClass=Arduino IDE
EOF

update-desktop-database ~/.local/share/applications
```

**Serial port access — required, or uploads fail with `Permission denied` on `/dev/ttyACM0`:**

```bash
sudo usermod -aG dialout $USER
```

Log out and back in (a full reboot is safest), then `groups` should list `dialout`.

**If a CH340/CH341 clone board is detected but never appears as a port**, the `brltty` braille daemon is claiming it:

```bash
sudo apt remove -y brltty
```

Install boards under **Tools → Board → Boards Manager** (ESP32, RP2040, AVR as needed) and libraries under **Tools → Manage Libraries**. Both land in `~/.arduino15/` and `~/Arduino/` — home directory, so not in the Timeshift snapshot.

> **Auto-updating alternative:** `arduino-cli` is a single static binary and is far more script-friendly if you want reproducible board/library installs. Consider it alongside the IDE.

### 11.2 draw.io Desktop — vendor `.deb`

```bash
cd ~/Downloads
# Get the current amd64 .deb URL from https://github.com/jgraph/drawio-desktop/releases
wget -O drawio-amd64.deb "<paste-deb-url>"
sudo apt install -y ./drawio-amd64.deb
```

Using `apt install ./file.deb` (rather than `dpkg -i`) resolves dependencies automatically.

No APT repo exists, so updates are manual — check the releases page periodically. Pair it with the `hediet.vscode-drawio` extension from §7 so `.drawio` files open natively in VS Code and version cleanly in Git.

### 11.3 balenaEtcher — vendor `.deb`

```bash
cd ~/Downloads
# Get the current amd64 .deb from https://github.com/balena-io/etcher/releases
wget -O balena-etcher-amd64.deb "<paste-deb-url>"
sudo apt install -y ./balena-etcher-amd64.deb
```

If it complains about a missing `libfuse2`, you already installed `libfuse2t64` in §11.1 — otherwise install it now.

> **Lighter alternatives already on your system:** GNOME Disks (`gnome-disk-utility`) has a *Restore Disk Image* function, and `dd`/`cp` write ISOs perfectly well. Etcher's advantage is verification-after-write and refusing to target your system disk.

### 11.4 OBS Studio

In `universe`, so plain APT works:

```bash
sudo apt install -y obs-studio
```

For upstream's latest builds instead, use the official PPA:

```bash
sudo add-apt-repository -y ppa:obsproject/obs-studio
sudo apt update && sudo apt install -y obs-studio
```

Virtual camera support:

```bash
sudo apt install -y v4l2loopback-dkms v4l2loopback-utils
sudo modprobe v4l2loopback
echo v4l2loopback | sudo tee /etc/modules-load.d/v4l2loopback.conf
```

**Wayland configuration.** 26.04 has no X11 session, so:

- Use the **Screen Capture (PipeWire)** source, not *Screen Capture (XSHM)*.
- **Window Capture (PipeWire)** for individual windows.
- Each capture triggers a portal permission dialog on first use. Enable *Restore token* in the source properties so it doesn't re-prompt every launch.
- Global hotkeys do not work while OBS is unfocused under Wayland. Use the WebSocket plugin plus an external controller, or a Stream Deck.

Hardware encoding: install `intel-media-va-driver-non-free` (Intel) or `mesa-va-drivers` (AMD) and choose VAAPI in output settings. NVIDIA users get NVENC once the proprietary driver is installed via **Additional Drivers**.

---

## 12. Proton VPN and RoboForm

### 12.1 Proton VPN (GUI) — vendor APT repo

Proton publishes a small `.deb` whose only job is to install its repository config and keys.

```bash
cd ~/Downloads
wget https://repo.protonvpn.com/debian/dists/stable/main/binary-all/protonvpn-stable-release_1.0.8_all.deb
```

Verify the checksum before installing (this is a bootstrap package — do not skip):

```bash
echo "0b14e71586b22e498eb20926c48c7b434b751149b1f2af9902ef1cfe6b03e180  protonvpn-stable-release_1.0.8_all.deb" | sha256sum --check -
```

If the version number above has moved on, take the current filename and hash from
<https://protonvpn.com/support/official-linux-vpn-ubuntu>.

```bash
sudo dpkg -i ./protonvpn-stable-release_1.0.8_all.deb
sudo apt update
sudo apt install -y proton-vpn-gnome-desktop
```

Tray icon support:

```bash
sudo apt install -y gir1.2-appindicator3-0.1
```

Then enable **Ubuntu AppIndicators** in the Extensions app — GNOME has no tray by default.

Split tunnelling needs kernel headers and `systemd-resolved`:

```bash
sudo apt install -y linux-headers-$(uname -r) systemd-resolved
```

Reboot, then sign in and set your preferences (protocol, NetShield, Kill Switch, auto-connect).

> **Kill Switch warning:** if you uninstall Proton VPN while the kill switch is active, you lose network access. Disable it *in the app* before removing. Recovery, if you forget: `nmcli connection show` and delete every connection prefixed `pvpn-`.

### 12.2 RoboForm browser extension

RoboForm has **no native Linux desktop client**. On Linux the browser extension runs standalone — full functionality without a desktop app.

1. Open Firefox (the `.deb` from §10) or Chrome.
2. Go to <https://www.roboform.com/download?os=linux>
3. Install the extension for your browser (Firefox Add-ons / Chrome Web Store).
4. Click the RoboForm icon → **Log In** → email + master password → complete 2FA.
5. Pin the extension to the toolbar.
6. In Firefox, approve the privacy permission prompt on first click — say yes to both, or filling silently fails.

Consequences of extension-only mode: no offline vault access, no filling of desktop applications, and the *Desktop Editor* view/edit commands are unavailable. Everything web-based works normally.

**If you want Chrome too** (some prefer it for RoboForm):

```bash
wget -qO- https://dl.google.com/linux/linux_signing_key.pub \
  | sudo gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg

sudo tee /etc/apt/sources.list.d/google-chrome.sources >/dev/null <<'EOF'
Types: deb
URIs: https://dl.google.com/linux/chrome/deb/
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/google-chrome.gpg
EOF

sudo apt update && sudo apt install -y google-chrome-stable
```

---

## 13. Verification, then the baseline snapshot

### 13.1 Verification checklist

```bash
# Repos all resolve cleanly — no 404s, no duplicate-source warnings
sudo apt update

# Core toolchain
git --version
gh --version           && ssh -T git@github.com
python3 --version      && pipx --version
java -version          && echo "JAVA_HOME=$JAVA_HOME"
code --version

# Docker
docker run --rm hello-world
docker compose version
docker info | grep -i "Docker Root Dir"

# Everything that should be a .deb, is
which thunderbird firefox code claude-desktop obs-studio drawio timeshift
apt policy thunderbird | head -3

# Nothing unexpected arrived via snap
snap list

# Serial access for Arduino
groups | grep -o dialout
```

Launch each GUI app once — VS Code, Claude Desktop, Thunderbird, Arduino IDE, draw.io, balenaEtcher, OBS, Proton VPN — and complete first-run sign-in / permission prompts. A snapshot taken *after* first-run setup saves you repeating it.

### 13.2 Record what the snapshot won't cover

Timeshift restores the OS, not your home directory. Write this down somewhere durable:

| Not in the snapshot | Where it lives | Mitigation |
|---|---|---|
| SSH private keys | `~/.ssh/` | Encrypted offline copy |
| Git config | `~/.gitconfig` | Dotfiles repo on GitHub |
| VS Code settings/extensions | `~/.config/Code/` | Settings Sync (GitHub) |
| Thunderbird profile | `~/.thunderbird/` | IMAP + separate backup |
| Arduino boards/libraries/sketches | `~/.arduino15/`, `~/Arduino/` | Sketches → GitHub |
| Docker images & volumes | `/var/lib/docker/` (excluded) | Images → Docker Hub; volumes → backup script |
| Claude Desktop config | `~/.config/Claude/` | Re-sign-in |
| RoboForm vault | Proton/RoboForm cloud | Nothing to do |

Consider a dotfiles repository — `~/.gitconfig`, `~/.ssh/config`, `~/.bashrc`, VS Code `settings.json` — which turns most of this table into a single `git clone`.

### 13.3 Take the snapshot

```bash
sudo apt autoremove --purge -y
sudo apt clean
sudo journalctl --vacuum-time=1d
sync
```

Then:

```bash
sudo timeshift --create --comments "Post-install baseline: 26.04 + dev stack" --tags D
```

Or via the GUI: **Timeshift → Create** and comment it clearly.

Verify it exists and note its size:

```bash
sudo timeshift --list
```

### 13.4 Test the restore path *before* you need it

An untested backup is a hypothesis. At minimum, confirm that Timeshift's live-boot restore works: boot an Ubuntu live USB, install `timeshift` in the live session, point it at your snapshot device, and confirm the snapshot is listed and selectable. Actually performing the restore is optional — being certain you *could* is not.

---

## Appendix A — Consolidated fast path

For a rebuild where you already trust every step above. Run section by section, not blindly as one script.

```bash
#!/usr/bin/env bash
set -euo pipefail

CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
ARCH=$(dpkg --print-architecture)

# --- Base -------------------------------------------------------------
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y ca-certificates curl wget gnupg apt-transport-https \
  build-essential pkg-config software-properties-common git git-lfs \
  unzip zip xz-utils htop tree jq gnome-tweaks \
  gir1.2-ayatanaappindicator3-0.1 libfuse2t64
sudo install -m 0755 -d /etc/apt/keyrings

# --- Archive packages -------------------------------------------------
sudo apt install -y timeshift obs-studio default-jdk maven \
  python3-pip python3-venv python3-dev python3-full pipx \
  v4l2loopback-dkms v4l2loopback-utils

# --- VS Code ----------------------------------------------------------
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor \
  | sudo tee /etc/apt/keyrings/packages.microsoft.gpg >/dev/null
sudo chmod go+r /etc/apt/keyrings/packages.microsoft.gpg
printf 'Types: deb\nURIs: https://packages.microsoft.com/repos/code\nSuites: stable\nComponents: main\nArchitectures: amd64 arm64 armhf\nSigned-By: /etc/apt/keyrings/packages.microsoft.gpg\n' \
  | sudo tee /etc/apt/sources.list.d/vscode.sources >/dev/null

# --- Docker -----------------------------------------------------------
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' \
  "$CODENAME" "$ARCH" | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null

# --- Claude Desktop ---------------------------------------------------
sudo curl -fsSLo /etc/apt/keyrings/claude-desktop-archive-keyring.asc \
  https://downloads.claude.ai/claude-desktop/key.asc
printf 'Types: deb\nURIs: https://downloads.claude.ai/claude-desktop/apt/stable\nSuites: stable\nComponents: main\nArchitectures: amd64 arm64\nSigned-By: /etc/apt/keyrings/claude-desktop-archive-keyring.asc\n' \
  | sudo tee /etc/apt/sources.list.d/claude-desktop.sources >/dev/null

# --- Mozilla ----------------------------------------------------------
wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- \
  | sudo tee /etc/apt/keyrings/packages.mozilla.org.asc >/dev/null
printf 'Types: deb\nURIs: https://packages.mozilla.org/apt\nSuites: mozilla\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/packages.mozilla.org.asc\n' \
  | sudo tee /etc/apt/sources.list.d/mozilla.sources >/dev/null
printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n\nPackage: firefox*\nPin: release o=Ubuntu\nPin-Priority: -1\n\nPackage: thunderbird*\nPin: release o=Ubuntu\nPin-Priority: -1\n' \
  | sudo tee /etc/apt/preferences.d/mozilla >/dev/null

# --- Install everything from the new repos ----------------------------
sudo apt update
sudo apt install -y code \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
  claude-desktop thunderbird firefox
sudo rm -f /etc/apt/sources.list.d/claude-desktop.list \
           /usr/share/keyrings/claude-desktop-archive-keyring.asc

# --- Groups -----------------------------------------------------------
sudo usermod -aG docker,dialout "$USER"
pipx ensurepath

echo "Done. Log out and back in, then continue with the manual .deb/AppImage steps."
```

Still manual after this: Arduino IDE AppImage, draw.io `.deb`, balenaEtcher `.deb`, Proton VPN bootstrap `.deb`, RoboForm extension, SSH key generation, and all first-run sign-ins.

---

## Appendix B — Post-snapshot maintenance

```bash
# Everything from APT, in one command
sudo apt update && sudo apt full-upgrade -y

# What has an update pending
apt list --upgradable
```

Manual-update items, since they have no APT repo — check quarterly:

- Arduino IDE (AppImage) — <https://www.arduino.cc/en/software>
- draw.io Desktop — <https://github.com/jgraph/drawio-desktop/releases>
- balenaEtcher — <https://github.com/balena-io/etcher/releases>

Before any risky change (kernel testing, driver swap, major version bump), take an on-demand snapshot first:

```bash
sudo timeshift --create --comments "Before <change>" --tags O
```
