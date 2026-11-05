# Deployment Guide

## 1. Before deploying

- `.env` contains `PRIVATE_KEY` and `SEPOLIA_RPC_URL` ([2_environment_setup.md](2_environment_setup.md)).
- The wallet has some Sepolia ETH. A deployment uses about 19M gas, which costs a tiny amount at Sepolia's usual gas prices; the script shows the exact estimate first.
- The image is pinned: `mint/ipfs.json` exists (it is committed).

## 2. Deploy

Inside the container (`docker compose run --rm tokenizeart`):

```bash
python deployment/deploy.py          # asks before deploying and before editing .env
python deployment/deploy.py --yes    # no questions
```

The script prints seven steps:

| Step | What happens |
|---|---|
| 1. Loading configuration | reads `.env` and `mint/ipfs.json`; checks the key format, the RPC URL, that the PNG still matches the pinned one, and the gateway; downloads the image once through the gateway link, as wallets will |
| 2. Connecting to Sepolia | connects and checks the chain is really Sepolia (`11155111`); shows the deployer address and balance |
| 3. Checking the Solidity compiler | installs solc `0.8.35` if needed (already in the image) |
| 4. Compiling | compiles `code/Windmill42.sol` with the OpenZeppelin imports; shows the size on-chain |
| 5. Estimating the cost | gas × gas price; stops early if the wallet cannot pay |
| 6. Deploying | builds the transaction, **signs it locally** with the key, sends it, waits for the block; prints the address and tx hash |
| 7. Saving | writes `deployment/artifacts/Windmill42.json` and `mint/website/config.json`; offers to put `CONTRACT_ADDRESS` into `.env` |

The constructor receives the image CID and the gateway. The deployer becomes the contract **owner**, the only one who can mint.

Example output:

```
[6/7] Deploying (waiting for the transaction to be mined)
      ✓ contract: 0x45DEDC83B233B846F6FED1a118d71bEEffAE0f97
      ✓ tx hash : 0x65fdc2d9…1108
      ✓ block 12027336, gas used 19221812
```

## 3. What is saved, and what is not

| File | Content | Committed |
|---|---|---|
| `deployment/artifacts/Windmill42.json` | network, chainId, address, tx hash, block, deployer, image URI, ABI | yes (public data) |
| `mint/website/config.json` | address, chainId, ABI, image link: everything the website needs | yes |
| `.env` → `CONTRACT_ADDRESS` | the address, for the TUI | no (gitignored) |

No key and no RPC URL are ever written to the committed files: an RPC URL can contain an API key. A test checks this.

## 4. Errors you may meet

Every failure ends with one clear line and no Python traceback:

| Message | Fix |
|---|---|
| `PRIVATE_KEY in .env must be 64 hexadecimal characters` | copy the key again from MetaMask |
| `SEPOLIA_RPC_URL must be an http(s) URL` | use the default from `.env.example` |
| `The artwork changed since it was pinned` | run `python mint/pin_to_ipfs.py` again |
| `The image link did not answer` / `does not serve the artwork` | set `PINATA_GATEWAY` to your dedicated gateway (the shared one is unreliable), or retry |
| `Not enough Sepolia ETH` | use a faucet, then retry |
| `Could not reach …` / wrong chain | check the RPC URL is a **Sepolia** node |

## 5. Check the deployment

- Etherscan: `https://sepolia.etherscan.io/address/<address>`
- TUI: `python mint/mint_tui.py`, then `refresh` ([5_minting_tui.md](5_minting_tui.md))
- Website: `docker compose up website` ([6_website.md](6_website.md))
