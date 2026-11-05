# Defense Walkthrough

This follows the evaluation sheet in order. Commands run inside the container unless noted.

## 0. Preparation (before the evaluator arrives)

```bash
docker compose build
docker compose up -d website                 # http://localhost:8042
docker compose run --rm tokenizeart          # shell for everything else
```

- MetaMask: the owner account is selected on **Sepolia**, and a second (non-owner) account exists.
- The wallet has Sepolia ETH (`python mint/mint_tui.py` shows the balance).
- `pytest -q` is green.

## 1. Preliminaries

- **The repository:** `README.md` plus the folders `code/`, `deployment/`, `mint/`, `documentation/`.
- **No secrets:** `.env` is gitignored. Show `.env.example` (empty values) and run `pytest -q deployment/tests/test_no_secrets.py`.
- **README:** shows the network (Sepolia) and the contract address. The token to show is **#1**, owned by the deployer (`deployment/permanent.json`).

## 2. The NFT in a wallet

MetaMask → Sepolia → **NFTs** → *Import NFT* → the README's contract address and token ID `1` → *Windmill42 #1* with the windmill and the 42.

Also: the Etherscan link from the README.

## 3. Metadata

Three ways to show the same `tokenURI`:
- **TUI:** `uri 1`. Shows name `Windmill42 #1` (contains 42), artist `flverge`, title, image link, edition `1/42`, and the on-chain SVG size.
- **Website:** *Look up a token* → `1`.
- **Etherscan:** the token page (`/nft/<address>/1`) and the mint transaction. Note that the *Read Contract* tab only appears once the source code is verified on Etherscan, which is optional.

The image is on IPFS:
- `imageURI()` returns `ipfs://bafkrei…qxjfu`, and `ipfs` in the TUI downloads it and compares it with the on-chain copy.
- <https://inbrowser.link/ipfs/bafkreictfou6ncwuojw6dp3n7edozfmrr5c7gn7ojbxtz3bbz3opyqxjfu> fetches it from IPFS peers directly.
- If the gateway is down on the day: the owner can call `setImageGateway` with another gateway, without touching the image.

## 4. Ownership: `ownerOf`

- **TUI:** `owner 1` shows the owner address ("that's you").
- **Website:** the lookup shows `ownerOf`.
- **Unminted token:** `owner 42` gives *"This token does not exist (yet)."*

## 5. README and documentation

- **README:** synopsis, deployment box, MetaMask steps, the "why these choices" table (platform and language), quickstart.
- **`documentation/`:** choices, setup, art and IPFS, deployment, TUI, website, contract reference, security, and this walkthrough.

## 6. Code tour

1. `code/Windmill42.sol`:
   - inherits `ERC721, Ownable, IERC4906`;
   - `MAX_SUPPLY = 42`, `mint` with `onlyOwner`;
   - `tokenURI` builds the JSON on-chain;
   - `imageCID` + `imageGateway`.
2. `code/Windmill42Art.sol`: turns the run-length pixel data into SVG paths.
3. `deployment/deploy.py`: the seven steps; local signing.
4. `mint/nft_client.py`: the client; contract errors mapped to friendly messages.
5. Tests: `code/tests/test_windmill42.py` covers the cap, owner-only mint, metadata, and the SVG being byte-identical to the file.

## 7. The evaluator deploys

```bash
python deployment/deploy.py
```

Walk through the seven steps: configuration, Sepolia connection, compiler, compilation, cost estimate (confirm), deployment, saving. Open the new address on Etherscan.

> [!NOTE]
> This creates a **new** contract and updates `CONTRACT_ADDRESS` in `.env`, `deployment/artifacts/Windmill42.json` and `mint/website/config.json`. The README's permanent contract is not touched. Afterwards, `git restore deployment/artifacts mint/website/config.json` and put the permanent address back in `.env`.

## 8. The evaluator mints

- **TUI** (`python mint/mint_tui.py`): `mint` gives *Minted Windmill42 #1*; then `owner 1`, `uri 1`, `view` (the art in the terminal).
- **Website** (reload <http://localhost:8042> so it reads the new `config.json`): *Mint* → confirm in MetaMask → the token appears; then look it up.
- **In MetaMask:** import the new token as in step 2.

## 9. Security demo

| Try | Expected |
|---|---|
| TUI `hack` | a random wallet's mint is simulated → *"Only the contract owner can mint."* (no gas, nothing sent) |
| Website: *Switch account* to the non-owner → *Mint* | *"Only the contract owner can mint."* |
| TUI `send 1 <other address>`, then `owner 1` | the token moved; `send 1 …` again → *"Your wallet does not own this token."* |
| TUI `uri 0`, `uri abc`, `owner 43` | *"Token ID must be … between 1 and 42"*, no crash |
| Website: *Mint* then **Reject** in MetaMask | *"Request rejected in MetaMask."* |
| `pytest -q code/tests` | 43rd mint → `MaxSupplyReached`; non-owner → `OwnableUnauthorizedAccount` |

## 10. Bonuses

- **Art:** the original 64×64 pixel art with the cloud-drawn 42 ([3_artwork_and_ipfs.md](3_artwork_and_ipfs.md)).
- **Website:** connect, mint, look up, switch account ([6_website.md](6_website.md)).
- **On-chain storage:**
  - TUI `view` draws `svgImage()`;
  - the website shows *Stored on-chain* next to *Pinned on IPFS*;
  - TUI `ipfs` proves both are the same image;
  - the metadata itself is built on-chain (`tokenURI` is a `data:` URI).
