# shopsystem-devcontainer base image
# Provides a Python 3.12 environment with shopsystem-messaging (shop_msg)
# and all its dependencies pre-installed, including the shop-msg CLI.
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install shopsystem-messaging from the published GitHub release.
# This makes shop_msg importable and puts shop-msg on PATH.
RUN pip install --no-cache-dir \
    "shopsystem-messaging @ git+https://github.com/dstengle/shopsystem-messaging@main"

# Verify installation
RUN python -c "import shop_msg" && which shop-msg

WORKDIR /workspace
CMD ["/bin/bash"]
