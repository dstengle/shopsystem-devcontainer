# shopsystem-devcontainer base image
# Provides a Python 3.12 environment with the shopsystem CLI tools
# (shop-msg, shop-templates, shop-test-harness, bd) pre-installed and on PATH.
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    libpq-dev \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

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
RUN which shop-msg && which shop-templates && which shop-test-harness && which bd

WORKDIR /workspace
CMD ["/bin/bash"]
