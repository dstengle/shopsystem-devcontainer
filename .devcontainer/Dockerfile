FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie
# Install
RUN apt-get update && apt-get install -y git vim curl tmux wget golang inotify-tools
RUN pip install uv

# Install gh (GitHub CLI) from the official cli.github.com apt repo.
# No version pin; latest is acceptable.
RUN set -e && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates gnupg && \
    install -dm 0755 /etc/apt/keyrings && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null && \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends gh && \
    gh --version
#
# Specstory for capturing agent chat logs
#
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then SPEC_ARCH="Linux_arm64"; else SPEC_ARCH="Linux_x86_64"; fi && \
    cd /tmp && \
    curl -LO "https://github.com/specstoryai/getspecstory/releases/latest/download/SpecStoryCLI_${SPEC_ARCH}.tar.gz" && \
    tar -xzf "SpecStoryCLI_${SPEC_ARCH}.tar.gz" && \
    mv specstory /usr/local/bin/ && chmod +x /usr/local/bin/specstory && \
    rm "SpecStoryCLI_${SPEC_ARCH}.tar.gz"
#
# Claude code
#
RUN curl -fsSL https://claude.ai/install.sh | sudo -u vscode bash

# Install shopsystem-messaging from the published GitHub release.
# This makes shop_msg importable and puts shop-msg on PATH.
RUN pip install --no-cache-dir \
    "shopsystem-messaging @ git+https://github.com/dstengle/shopsystem-messaging@main"

# Install shop-templates from GitHub.
# This puts shop-templates on PATH.
RUN pip install --no-cache-dir \
    "shop-templates @ git+https://github.com/dstengle/shopsystem-templates@main"

# Install shopsystem-test-harness from GitHub.
# This puts shop-test-harness on PATH.
RUN pip install --no-cache-dir \
    "shopsystem-test-harness @ git+https://github.com/dstengle/shopsystem-test-harness@main"

# Install bd (beads) from github.com/steveyegge/beads releases.
# Detects architecture and downloads the appropriate linux tarball,
# then installs the bd binary to /usr/local/bin/bd.
RUN set -e && \
    ARCH=$(uname -m) && \
    case "$ARCH" in \
        x86_64)  BD_ARCH="amd64" ;; \
        aarch64) BD_ARCH="arm64" ;; \
        *)       echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    BD_VERSION=$(curl -fsSL "https://api.github.com/repos/steveyegge/beads/releases/latest" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))") && \
    BD_URL="https://github.com/steveyegge/beads/releases/download/v${BD_VERSION}/beads_${BD_VERSION}_linux_${BD_ARCH}.tar.gz" && \
    curl -fsSL "$BD_URL" | tar -xz -C /tmp && \
    install -m 0755 /tmp/bd /usr/local/bin/bd && \
    rm -f /tmp/bd && \
    bd --version

# Verify all CLI tools are on PATH
RUN which shop-msg && which shop-templates && which shop-test-harness && which bd && which gh

WORKDIR /workspace
CMD ["/bin/bash"]
