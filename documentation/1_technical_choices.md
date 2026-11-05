# Technical Choices & Architecture

This document explains the decisions behind Windmill42, the TokenizeArt NFT.

## 1. The blockchain: Ethereum Sepolia

The contract lives on **Sepolia** (chainId `11155111`), Ethereum's recommended test network.

- **Same rules as mainnet:** Proof-of-Stake, the same EVM and the same transaction format. A contract that works here works on mainnet.
- **Free gas:** Sepolia ETH comes from faucets and has no value. A deployment costs a tiny fraction of one test ETH.
- **Tooling:** MetaMask, Etherscan and public RPC nodes (such as `ethereum-sepolia-rpc.publicnode.com`, which needs no account) all support it.
- **Continuity:** my previous project, `tokenizer`, used Sepolia too, with the same wallet and workflow.

## 2. The token standard: ERC-721

An NFT must be **non-fungible**: token #1 is not interchangeable with token #2. **ERC-721** is the Ethereum standard for that.

- Each token has a unique `tokenId` and exactly one owner, given by `ownerOf(tokenId)`.
- `tokenURI(tokenId)` returns the token's metadata (name, image, attributes).
- Transfers (`safeTransferFrom`, `transferFrom`) and approvals are standard, so MetaMask, Etherscan and marketplaces display and move the token without custom code.

ERC-20 (used in `tokenizer`) would not fit: its units are identical and have no individual owner.

## 3. Implementation: Solidity + OpenZeppelin

`code/Windmill42.sol` inherits from three OpenZeppelin building blocks:

| Inherited | Gives |
|---|---|
| `ERC721` | the full NFT standard: `ownerOf`, `balanceOf`, transfers, approvals, `supportsInterface`, and the checks that reject transfers by non-owners |
| `Ownable` | one owner (the deployer), the `onlyOwner` modifier, `transferOwnership`, `renounceOwnership` |
| `IERC4906` | the standard "metadata changed" events wallets listen to |

Only the project-specific parts are hand-written:
- the 42-token cap,
- the owner-only `mint`,
- the image settings,
- the on-chain metadata and SVG.

Solidity `0.8.35` checks arithmetic overflow by itself. Custom errors (`MaxSupplyReached`, …) make failures cheap and easy to decode.

## 4. Supply and minting rules

- **At most 42 tokens** (`MAX_SUPPLY`), with IDs 1 to 42 in mint order (`totalMinted` counts them).
- **Only the owner mints** (`onlyOwner`), and can mint to any address.
- The counter is increased *before* `_safeMint`, so a receiving contract that calls back during the mint cannot reuse an ID.
- Every token shows the same artwork; the metadata carries its edition number (`7/42`).

## 5. Where the image lives: IPFS *and* on-chain

| Copy | Where | Used by |
|---|---|---|
| `windmill42.png` | IPFS, pinned with Pinata (CID `bafkrei…qxjfu`) | the `image` field of the metadata: what wallets show |
| SVG | rebuilt by the contract from `Windmill42ArtData.sol` | `svgImage()`, and the `image_data` field of the metadata |

- **IPFS** is required by the subject. A CID is the hash of the file, so the image cannot be replaced without changing its address.
- **On-chain** is the bonus. The image depends on nothing but the blockchain.

The metadata JSON is itself built on-chain by `tokenURI` (`data:application/json;base64,…`), so there is no metadata server to keep alive.

**Gateway lesson:** wallets cannot fetch `ipfs://` links themselves; they go through an http gateway. The main public gateways (`ipfs.io`, `dweb.link`) closed in September 2026. So the metadata `image` is an https gateway link (`imageGateway` + `imageCID`), and the owner can switch to another gateway with `setImageGateway`. The CID, and so the image, can never change. `imageURI()` still returns the canonical `ipfs://<CID>`. See [3_artwork_and_ipfs.md](3_artwork_and_ipfs.md).

## 6. Tooling: Python instead of Hardhat

Like `tokenizer`, the tooling is plain Python, so each step is visible:

| Tool | Role |
|---|---|
| `py-solc-x` | installs solc `0.8.35` and compiles with the OpenZeppelin imports (from `npm`) |
| `web3.py` | talks to the node; transactions are built, **signed locally**, then sent |
| `eth-tester` + `pytest` | a local in-memory chain: contract, deploy, client and TUI are tested without ETH |
| `Rich` + `readchar` | the terminal interfaces |
| `requests` | Pinata upload and gateway downloads |
| `ethers.js` 6 | the website's link to MetaMask |

Quality gates: `pytest` (160+ tests), `mypy --strict`, `black`, `flake8`.

## 7. Docker

One image contains Python, Node (for the OpenZeppelin package), solc and every dependency. Docker Compose provides:
- `tokenizeart`: an interactive shell for the scripts. The repository is mounted, so edits need no rebuild. Files are created with your user id.
- `website`: serves `mint/website` on port 8042.

The evaluator only needs Docker; nothing is installed on the host.
