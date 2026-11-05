FROM python:3.11-slim

# System tools: node/npm (OpenZeppelin), git (secret-scan tests), vim (editing)
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm git vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    SOLCX_BINARY_PATH=/opt/solcx \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# OpenZeppelin contracts, pinned in package.json
COPY deployment/package.json ./deployment/
RUN cd deployment && npm install

# Python virtual env + pinned dependencies
COPY deployment/requirements.txt ./deployment/
RUN python3 -m venv $VIRTUAL_ENV \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r deployment/requirements.txt

# Solidity compiler installed once at build time (readable by any user)
RUN mkdir -p /opt/solcx \
    && python -c "import solcx; solcx.install_solc('0.8.35')" \
    && chmod -R a+rX /opt/solcx

# The tests run git inside the container (secret scan, docs checks); the
# mounted repo may belong to another uid than the container user, which
# git refuses ("dubious ownership") unless the folder is marked safe.
RUN git config --system --add safe.directory '*'

COPY . .

CMD ["/bin/bash"]
