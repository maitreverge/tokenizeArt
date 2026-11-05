# Environment Setup

## 1. Prerequisites

- **Docker** with **Docker Compose** (v2: `docker compose`)
- **MetaMask** with a Sepolia account holding a little Sepolia ETH (free from a faucet such as Google Cloud's, Alchemy's or Infura's)
- A **Pinata** account (free) only if you want to pin the image again; it is already pinned (`mint/ipfs.json`)

## 2. The `.env` file

All settings and secrets live in **one gitignored file at the repository root**:

```bash
cp .env.example .env
```

| Variable | Needed for | Value |
|---|---|---|
| `SEPOLIA_RPC_URL` | deploy, TUI | a Sepolia node; the default public one needs no account |
| `PRIVATE_KEY` | deploy, mint | the wallet that deploys, owns and mints: MetaMask → account menu → *Account details* → *Show private key* (64 hex characters, `0x` optional) |
| `PINATA_JWT` | `pin_to_ipfs.py` only | Pinata → *API Keys* → *New Key* → copy the **JWT** |
| `PINATA_GATEWAY` | deploy (optional) | your Pinata dedicated gateway, e.g. `name.mypinata.cloud`; empty means `gateway.pinata.cloud`. This is the gateway written into the contract for wallets. |
| `CONTRACT_ADDRESS` | TUI | filled in by `deploy.py` (or typed when the TUI asks) |

> [!WARNING]
> `.env` holds your private key. It is ignored by git (`.gitignore`) and by Docker builds (`.dockerignore`). Never commit it, paste it, or share it. Use a wallet that only holds test ETH.

Checks done for you:
- `deploy.py` validates the key format and the RPC URL before doing anything.
- The test `deployment/tests/test_no_secrets.py` fails if a private key, a JWT or a keyed RPC URL appears in any committed file.

## 3. Build and enter the container

```bash
docker compose build
docker compose run --rm tokenizeart      # opens a shell in /app
```

The image contains:
- Python 3.11 with the pinned requirements (`deployment/requirements.txt`),
- solc `0.8.35`,
- OpenZeppelin Contracts `5.6.1` (`deployment/package.json`).

The project folder is mounted at `/app`: edit on the host, run in the container, no rebuild needed.

> [!NOTE]
> The container runs as `${UID}:${GID}`, which defaults to `1000:1000`. Most shells do not export these variables. If your user id is not 1000 (check with `id -u`), export them first, or the container cannot write `deployment/artifacts/` and `mint/website/config.json`:
> ```bash
> export UID GID=$(id -g)
> ```

## 4. Check the installation

```bash
pytest -q          # 160+ tests on a local chain: no ETH, no network needed
mypy deployment mint conftest.py code/tests
black --check . && flake8 --exclude .venv,node_modules .
```

## 5. Website

The website runs in a second service:

```bash
docker compose up website      # then open http://localhost:8042
```

It needs the MetaMask browser extension and no `.env` value. See [6_website.md](6_website.md).
