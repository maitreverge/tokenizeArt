# Security Model

## 1. Who can do what

| Action | Who | Enforced by |
|---|---|---|
| Mint | the contract **owner** only | `onlyOwner` (OpenZeppelin `Ownable`) |
| Mint more than 42 | nobody | `MaxSupplyReached` |
| Move a token | its owner, or an address it approved | OpenZeppelin `ERC721` checks |
| Change the image | nobody: the CID is fixed at deployment | no setter exists |
| Change the image *gateway* | the owner | `onlyOwner` on `setImageGateway` |
| Give the contract away | the owner | `transferOwnership` / `renounceOwnership` |

Things to demonstrate:
- **TUI `hack`:** simulates `mint` from a random wallet with a free `eth_call`. The node answers with `OwnableUnauthorizedAccount`, and the TUI shows *"Only the contract owner can mint."*
- **Website:** *Switch account* to a non-owner, then *Mint*. The page shows the same sentence and MetaMask never asks to sign.
- **TUI `send` of a token you don't own:** *"Your wallet does not own this token."*

## 2. Contract design

- **Audited code first:** ERC-721 and ownership come from OpenZeppelin 5.6.1. The hand-written part is small: the cap, `mint`, the image settings and the metadata.
- **Re-entrancy:** `mint` increases `totalMinted` *before* `_safeMint`, the only external call (`onERC721Received`). A malicious receiver that calls back cannot reuse an ID. It could not mint anyway, because it is not the owner.
- **Overflow:** Solidity 0.8 checks arithmetic.
- **No ETH held:** there is no `payable` function, so the contract has no funds to steal.
- **Immutable art:** `imageCID` and the on-chain pixel data cannot change. Only the gateway, the access door, can, and only by the owner, with a public on-chain event.
- **Size:** 11.6 KB of runtime code, under the 24 KB limit (a test checks it).

## 3. Secrets

| Secret | Lives in | Never in |
|---|---|---|
| Wallet private key | `.env` (gitignored, dockerignored) | git, logs, artifacts, the website |
| Pinata JWT | `.env` | git, `ipfs.json` |
| Keyed RPC URL (Infura, Alchemy) | `.env` | git, artifacts, the website |

- Transactions are **signed locally** (`account.sign_transaction`) and sent raw: the node never sees the key.
- The website never touches a key. MetaMask signs, after asking the user.
- `deploy.py` writes only public data: address, ABI, tx hash, and the image CID and link.
- `deployment/tests/test_no_secrets.py` scans every committed file for:
  - private-key assignments,
  - JWTs (`eyJ…`),
  - Infura, Alchemy and QuickNode keyed URLs.

  It also checks that `.env` is ignored.
- Unit tests never load the real `.env`.

## 4. Input handling

- **Token IDs:** checked to be whole numbers from 1 to 42 before any call, in both the TUI and the website.
- **Addresses:** validated and checksummed (`Web3.to_checksum_address`, `ethers.getAddress`).
- **Errors:** every error becomes one sentence. Neither the scripts nor the TUI ever print a traceback.
- **TUI `ipfs`:** the link comes from the contract, so the TUI only downloads `https://` links and reads at most 2 MB.
- **Gateway changes:** the gateway prefix is pasted into the on-chain JSON, and the contract only rejects an empty one. A `"` would break the metadata of all 42 tokens. So `deploy.py` accepts only a plain domain for `PINATA_GATEWAY`, and checks that it serves the artwork before deploying.
- **Website:** chain data is shown with `textContent`, the SVG goes through `<img>`, and a Content-Security-Policy restricts scripts and connections. ethers.js is pinned with an SRI hash.

## 5. Known limits

- The owner key is a single point of trust: whoever holds it can mint (up to 42) and change the gateway. A multisig would remove that for a real collection.
- Gateways are third-party services. If one closes, images disappear in wallets until the owner sets a new gateway; the on-chain SVG stays available meanwhile.
- `renounceOwnership` is irreversible. After it, no more minting and no gateway change.
