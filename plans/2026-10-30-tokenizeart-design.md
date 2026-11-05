# TokenizeArt — Design

Date: 2026-10-30 · Author: Flow (`flverge`) with Claude · Status: approved by the user (2026-10-30)

## 1. Intent

TokenizeArt is the 42 project "Build your own NFT". The repo is `blockchain_project/tokenizeArt/` (git, currently empty except an empty `README.md` and the folders `code/`, `deployment/`, `mint/`, `documentation/`).

The goal is to **reuse as much as possible from the finished `blockchain_project/tokenizer/` project** (Python + web3.py + py-solc-x + Rich TUI + Docker, Sepolia), and turn it into an ERC-721 NFT project.

Success means **every line of the evaluation sheet passes in a live defense**, then **all three bonuses** pass. The sources of truth are:

- Subject: `blockchain_project/subject.pdf`
- Evaluation sheet: `blockchain_project/specs/evaluation_sheet.pdf` (kept outside the repo on purpose: it is an intra page with private details)
- Reference project: `blockchain_project/tokenizer/` (read `deployment/contract_uploader.py`, `deployment/wallet_manager.py`, `Dockerfile`, `docker-compose.yml`, `documentation/`)

## 2. Facts settled with the user

| Topic | Decision |
|---|---|
| 42 login (artist name) | `flverge` |
| Network | Ethereum **Sepolia** testnet (user already has Sepolia ETH) |
| Wallet | User's MetaMask wallet; its private key goes in a gitignored `.env`, same pattern as tokenizer |
| IPFS | **Pinata** (user has an account; API JWT goes in `.env`) |
| Contract | Solidity + **OpenZeppelin**, ERC-721 |
| Deployment tool | **Plain Python script** using web3.py — no TUI, but clear, step-by-step, nicely printed output |
| Mint tool | **Rich TUI like tokenizer's**, connecting to Sepolia: mint, show the NFT, `ownerOf`, `tokenURI` |
| Security demo in TUI | Yes: (a) show that a non-owner mint is rejected, (b) transfer a token and show `ownerOf` change |
| Wallet manager clone | **No** — not needed |
| Supply | Every mint = a new token with the **same artwork and metadata**, **capped at 42** |
| Who can mint | **Only the contract owner** (deployer) |
| Artwork | **Design A "Spring Meadow"** (pixel art, 64×64, "42" drawn as clouds) — draft in `plans/art_draft/spring_meadow_draft.png`, generator `plans/art_draft/draft_generator.py` |
| Bonuses | **All three**: beautiful art, mint website, on-chain storage ("inscriptions") |
| On-chain + IPFS | **Both**: image pinned on IPFS (mandatory) *and* image + metadata stored on-chain (bonus). Interpretation (Claude's): one contract does both — see §6. |
| Website | Simple **static HTML/JS** page, connects to MetaMask |
| Showing the on-chain image | **Must** be shown on the website. Showing it in the TUI too is strongly wanted ("fantastic"). Wallets keep showing the IPFS image. |
| Defense setup | Runs on the **user's own laptop**, evaluator driving, through the **Docker container** (kept so anyone can run the project with their own `.env`). The user's own wallet is used, its private key only in the gitignored `.env` — exactly like tokenizer. No separate defense wallet. |
| Live deploy / mint in defense | `deploy.py` deploys a **fresh** contract owned by the `.env` wallet; the evaluator then mints on it (TUI and website). The **permanent** contract (address in README, token #1 owned by the user) is never overwritten. |
| Git | Commit in `tokenizeArt` at every major step. **Never push.** **Never modify anything in `tokenizer/`** (copy from it only). |
| Plans location | `tokenizeArt/plans/` (this doc, the implementation plan, the draft art) |

## 3. What the evaluation sheet demands (drives everything)

The sheet stops the evaluation at the first failure of these gates, in order:

1. **Visual** — the NFT is shown *in a wallet or a marketplace* (TUI/website preview does **not** count for this line). The image must contain a legible 42.
2. **Metadata** — show at least the artist name (= `flverge`) and the work's name (must contain `42`).
3. **Ownership** — show the NFT belongs to the student (`ownerOf`).

Then: README (platform choice + language choice explained), documentation (understand the project, the NFT's actions, and how to mint), code review (comments, names; **functions listed in docs must exist in code**), deployment review (**evaluator deploys live** with the student's help), mint review (**evaluator mints live**).

Hard failure rules:
- **Any API key or password in clear text in any committed file → flag, evaluation stops.**
- **Any crash / uncontrolled termination → grade 0.** Bonus also requires error handling of "unexpected or bad usage".
- Preliminaries: `README.md`, and non-empty `code/`, `documentation/`, deployment folder, `mint/` folder. **No video in the repo** (a link is fine).
- Subject: README must state the **deployed contract address and the network**.

## 4. Goals, non-goals, anti-goals

**Goals**
- Pass every mandatory line, then the three bonuses.
- A permanent deployment on Sepolia with token #1 minted to the user, address recorded in README.
- The same tools let the evaluator re-deploy and mint live during the defense.

**Non-goals**
- No mainnet, no real money, no upgradeable proxy, no royalties, no marketplace listing/sales, no public/paid minting.
- No Hardhat/Foundry — keep tokenizer's Python + py-solc-x pipeline (consistent with the README rationale already written for tokenizer).
- No wallet manager tool.

**Anti-goals (failure even if it "works")**
- A secret in any committed file (including example files, notebooks, logs, website config).
- A Python traceback or unhandled JS error in front of the evaluator.
- A "42" that is not clearly legible (the subject shows a rejected example).
- The on-chain bonus breaking the mandatory wallet display. **Mandatory always wins** (see risk R1).
- Docs that describe functions/commands that don't exist.

## 5. Artwork

- Design **A "Spring Meadow"**, 64×64 pixel art: blue sky, sun, a big cloud-white **"42"**, a windmill with red roof, round trees and pines, a rabbit, a fox, a butterfly, birds, wildflowers.
- The draft is accepted as the direction; the builder **polishes** it (bonus line asks "is it beautiful, sharp, harmonious colours"): nicer windmill cap/blades, better animal sprites, more meadow detail, coherent palette. The "42" must stay as large and legible as in the draft.
- **Palette: max 16 colours** (draft uses 33 near-duplicates — merge them). This keeps the on-chain copy at 4 bits/pixel = 2 048 bytes.
- **Update (user decision, after approving the final art): the generator was deleted.** The committed `mint/art/windmill42.png`, `mint/art/windmill42.svg` and `code/Windmill42ArtData.sol` are now the source of truth; tests prove all three describe the same pixels. Original intent below, kept for history.
- **One generator script was the single source of truth**, committed in the repo (proposed: `mint/art/generate_art.py`). From one indexed pixel grid it produces:
  - `spring_meadow.png` — upscaled with nearest-neighbour to 1024×1024 (sharp in wallets), the file pinned on IPFS;
  - `spring_meadow.svg` — preview;
  - the packed pixel bytes + palette consumed by the contract (e.g. a generated Solidity file in `code/` with a clear "generated — do not edit" header, or constants the builder chooses).
- The PNG on IPFS and the SVG rebuilt on-chain must be **pixel-identical** (tested).
- The generator must be reproducible inside Docker: bake the "42" glyph bitmap into the script rather than depending on a system font (the draft uses DejaVu Sans Bold 28px at render time).

## 6. Smart contract (`code/`)

- Solidity `^0.8.35` (same solc as tokenizer, auto-installed by py-solc-x), OpenZeppelin `@openzeppelin/contracts` 5.6.1 via npm (same as tokenizer).
- Name (user decision): contract **`Windmill42`**, ERC-721 name **"Windmill42"**; symbol **"WM42"** (Claude's call). The artwork title stays **"Spring Meadow"** (the `Title` attribute).
- Inherits `ERC721` + `Ownable` (owner = deployer).
- `MAX_SUPPLY = 42`; token IDs `1..42`; a public counter of minted tokens.
- `mint(address to) external onlyOwner returns (uint256 tokenId)` — reverts with a clear custom error past the cap; uses `_safeMint`.
- **Update (after the Sepolia trial, 2026-10-30):** the public gateways `ipfs.io` and `dweb.link` closed, so wallets showed no image for an `ipfs://` link. The constructor now takes the image CID (still immutable) and an https gateway prefix; `imageURI()` returns `ipfs://<CID>`, the metadata `image` is gateway + CID, and the owner can replace the gateway with `setImageGateway` (emits ERC-4906 `BatchMetadataUpdate`). The image itself can never change. See `documentation/3_artwork_and_ipfs.md`. Original text below, kept for history.
- Constructor argument: the image's IPFS URI (`ipfs://<CID>`), stored once, readable via a getter. No setter (immutable after deploy) — document why.
- `tokenURI(tokenId)` — reverts for non-existent tokens; returns **on-chain metadata** as `data:application/json;base64,…` with:
  - `name`: `"Windmill42 #<id>"` (contains 42; the title "Spring Meadow" is also in `description` and attributes)
  - `description`: short text, mentions 42 and the artist
  - `image`: the `ipfs://` URI → **what wallets/marketplaces display (mandatory: image on IPFS)**
  - `image_data`: the SVG rebuilt on-chain → **bonus: image stored on-chain**
  - `attributes`: at least `Artist = flverge`, `Title = Spring Meadow`, `Edition = <id>/42`
  - an `artist` / `created_by` field = `flverge` is welcome as well
- `svgImage()` (view) — returns the on-chain SVG built from the packed pixels + palette.
- Plus the standard ERC-721 functions inherited from OpenZeppelin (`ownerOf`, `balanceOf`, `transferFrom`, `safeTransferFrom`, `approve`, `setApprovalForAll`, `getApproved`, `isApprovedForAll`, `name`, `symbol`, `supportsInterface`) and `Ownable` (`owner`, `transferOwnership`, `renounceOwnership`).
- **Gas constraint for the SVG builder:** naïve repeated `string.concat` / `abi.encodePacked` in a loop is quadratic and will blow the `eth_call` gas cap of public RPCs. Use run-length encoding per row and a preallocated byte buffer (or another linear approach), and emit compact SVG (e.g. one `<path>` per colour with `M x y h n` segments). A local test must assert `tokenURI` and `svgImage` succeed well under 30M gas.
- **Security model to document:** only the owner can mint; hard cap 42; no payable functions, no withdraw, no pausing, no metadata mutation; ownership transfer/renounce from `Ownable` are the only admin actions. Comments on every non-inherited function (code review line).

## 7. IPFS upload (`mint/`)

- A small script (proposed `mint/pin_to_ipfs.py`) uploads `spring_meadow.png` to Pinata with `PINATA_JWT` from `.env`, prints the CID and a gateway link, and writes the result to a **committed, public** file (proposed `mint/ipfs.json`: CID, `ipfs://` URI, gateway URL). CIDs are public data, not secrets.
- Once pinned, nothing else needs the Pinata key: **live deploy/mint during the defense do not need Pinata at all.**
- Re-running it is safe (same content → same CID).

## 8. Deployment script (`deployment/`)

- One Python script (proposed `deployment/deploy.py`), web3.py, **no TUI**: numbered, coloured steps printed with Rich console (✓ / ✗), reusing tokenizer's `ContractState` logic:
  1. load and validate `.env` (RPC URL, private key format, IPFS URI from `mint/ipfs.json`)
  2. connect to Sepolia, show deployer address and ETH balance (fail clearly if too low)
  3. install solc if missing
  4. compile — **select the contract by name**, not `popitem()` (tokenizer's approach only works by alphabetical luck)
  5. deploy with the IPFS URI as constructor arg, wait for receipt
  6. print address, tx hash, block, gas, Sepolia Etherscan link
  7. write the ABI + address of **this latest deployment** where the TUI and website read them (proposed: `deployment/artifacts/` committed, plus a config JSON for the website), and offer to save `CONTRACT_ADDRESS` to `.env` (tokenizer's `set_key` pattern)
- **Permanent vs latest deployment:** the permanent contract's address/network/token ID is recorded by hand in the README (and may be kept in a separate committed file, e.g. `deployment/permanent.json`). A live deploy during the defense only overwrites the "latest" artifacts, never the permanent record. The TUI and website can be pointed at either one (via `CONTRACT_ADDRESS` / config); the docs explain how.
- Every failure → one clear message, exit code 1, **no traceback**.

## 9. Mint TUI (`mint/`)

- Same look and input loop as tokenizer's `contract_uploader.py` (Rich `Live` + `Layout`, `readchar`, command buffer, status line). Shared TUI helpers may be factored out.
- Left panel: contract address, name/symbol, owner, minted `n/42`, connected account + ETH balance, last tx hash.
- Commands (exact syntax is the builder's call; must be shown in the menu and documented):
  - **mint** to self, or to a given address
  - **ownerOf** for a token ID
  - **tokenURI** for a token ID — decode the base64 JSON and show name, artist, title, edition, image URI (not the raw blob)
  - **view** a token — render the 64×64 image in the terminal with half-block characters (64 columns × 32 rows, true colour). Primary source: the **on-chain** image (parse `svgImage()` or read the packed pixel data from the contract), so the TUI proves the on-chain storage. Optionally also fetch the IPFS PNG to show both match. Strongly wanted by the user; must work in a plain terminal inside Docker and degrade to a clear message (not a crash) on a too-small terminal.
  - **non-owner mint demo** — simulate `mint` from a random fresh address with `eth_call` (no gas needed) and display the `OwnableUnauthorizedAccount` revert
  - **transfer** a token owned by the configured wallet to an address, then show the new `ownerOf`
  - copy address / tx hash (like tokenizer), quit
- If `CONTRACT_ADDRESS` is missing, prompt for it like tokenizer's `ensure_contract_address_env()`.
- **Never crash**: invalid IDs, non-existent tokens, bad addresses, RPC down, gateway down, cap reached, insufficient funds, Ctrl-C → all become status messages.

## 10. Website (bonus, proposed `mint/website/`)

- Static `index.html` + JS + CSS, no build step. ethers.js (v6) from a CDN with a pinned version (or a vendored copy).
- Reads contract address + ABI from a config file produced by `deploy.py`.
- Features: connect MetaMask; detect/switch (or add) Sepolia, chainId 11155111; show the artwork — **the on-chain SVG (from `svgImage()` / `tokenURI.image_data`) is mandatory**, shown next to the IPFS image and labelled as such; minted `n/42`; **Mint** button (to the connected address; non-owner gets a readable "only the owner can mint" message); `ownerOf` / `tokenURI` lookup with decoded metadata; Etherscan links.
- Served on `http://localhost:<port>` from the Docker container (MetaMask doesn't inject into `file://`); port mapped in `docker-compose.yml`.
- Handles: no MetaMask installed, wrong network, user rejects the tx, invalid token ID, cap reached — no uncaught errors.

## 11. Environment, Docker, secrets

- Reuse tokenizer's `Dockerfile` / `docker-compose.yml` (Python 3.11 slim + node/npm for OpenZeppelin, venv, volume mount), adding the website port and new Python deps (e.g. Pillow, requests).
- **One gitignored `.env`** + a committed `.env.example` with **empty** values: `SEPOLIA_RPC_URL`, `PRIVATE_KEY`, `PINATA_JWT`, `CONTRACT_ADDRESS`. Location (root vs per folder) is the builder's call; document it.
- `.gitignore`: `.env`, venv, `node_modules`, caches, `subject.pdf`, `.superpowers/`.
- The container must work for anyone who clones the repo and fills their own `.env` (no host-specific paths).
- Before the final push, scan the repo for anything key-like (e.g. 64-hex strings, `eyJ` JWT prefixes) — none may exist outside `.env`.

## 12. README and documentation

- **README.md** (root): synopsis; **deployed contract address + network + Etherscan link + minted token ID(s)**; how to see it in MetaMask; why Sepolia, why ERC-721, why Solidity + OpenZeppelin, why Python/web3.py, why IPFS/Pinata, why dual storage; repo layout; quickstart; link to docs. Reuse tokenizer README's structure and tone.
- **documentation/** (proposed files): technical choices; environment setup; artwork & IPFS; deployment guide; minting with the TUI; website; **contract reference listing every public function** (must match code); security model; **defense walkthrough** that follows the evaluation sheet line by line (show in MetaMask → metadata → ownerOf → deploy live → mint live → bonuses).

## 13. Testing

- Local contract tests with web3.py's `EthereumTesterProvider` (`web3[tester]` is already a tokenizer dependency) and pytest: owner can mint; non-owner reverts; 43rd mint reverts; IDs 1..42; `tokenURI` decodes to valid JSON with the required fields and values; non-existent token reverts; `svgImage` equals the generator's SVG pixel-for-pixel; transfer changes `ownerOf`; gas of view calls stays under the limit.
- Smoke tests for scripts' error paths (missing env, bad key, bad address) — no tracebacks.
- Manual on Sepolia (user-run): pin, deploy, mint, MetaMask import, website mint.

## 14. Who runs what

Claude builds and tests everything locally. **The user runs every step that uses their secrets or spends Sepolia ETH**: Pinata upload, Sepolia deploy, Sepolia mint, MetaMask import, final README address fill-in (or gives Claude the resulting public address/tx to write in).

Claude commits in `tokenizeArt` after each major step, never pushes, and never modifies `tokenizer/`.

## 15. Risks

- **R1 — MetaMask may not display a `data:` (base64 JSON) `tokenURI`.** This is the first evaluation gate. Verify **early** with a throwaway Sepolia deploy right after the contract works. Fallback if it fails: `tokenURI` returns an `ipfs://` metadata JSON (pinned too), and the on-chain metadata moves to a separate function (e.g. `onChainTokenURI`). Mandatory wins over bonus.
- **R2 — Testnet marketplace support for Sepolia** changes over time. Treat MetaMask as primary; check during build whether a marketplace (and Sepolia Etherscan's NFT view) shows it, and document whatever works.
- **R3 — Public RPC `eth_call` gas caps** on the on-chain SVG — mitigated by the linear builder and the gas test.
- **R4 — Public IPFS gateway slowness** during the defense — the TUI/website fall back to the on-chain image; mention an alternative gateway in docs.

## 16. Suggested order

1. Polish art + generator → **user approves final art**.
2. Contract + local tests.
3. IPFS pin script + deploy script → **user does a throwaway Sepolia deploy + mint and checks MetaMask (R1)**.
4. Mint TUI.
5. Website.
6. README + documentation.
7. Final permanent deploy + mint #1 (user), record address/network in README, secret scan, final push.

## 17. Left to the builder

Exact palette and polish details; file/module names and layout inside each folder (proposals above); TUI command syntax and styling; website styling; JSON field order; how shared Python code is organised between `deployment/` and `mint/`; test file layout.

## 18. Claude's calls (for the user to check)

- One contract for both storage methods (interpretation of "make both").
- Symbol `WM42`; token name "Windmill42 #<id>"; artwork title "Spring Meadow" kept as the `Title` attribute.
- Token IDs start at 1.
- Image IPFS URI is a constructor argument, immutable afterwards. *(Updated: the CID stays immutable, but the https gateway in front of it is owner-updatable; see the §6 update note.)*
- 16-colour palette limit; 1024×1024 PNG on IPFS.
- Non-owner mint demo via `eth_call` simulation (no funded second wallet needed).
- Website lives under `mint/`; Docker files stay at the repo root like tokenizer.
- Wallets display the IPFS image (`image`); the on-chain image is shown through `image_data`, the website and the TUI — not as the wallet image.
- `plans/` folder name for the design doc and implementation plan.
