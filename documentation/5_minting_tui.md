# Minting TUI

A terminal app to mint and inspect Windmill42 tokens on Sepolia.

```bash
docker compose run --rm tokenizeart
python mint/mint_tui.py
```

It reads `.env`:

| Variable | Use |
|---|---|
| `SEPOLIA_RPC_URL` | the node to talk to |
| `PRIVATE_KEY` | the wallet that mints and sends. Without it, the TUI runs **read-only**. |
| `CONTRACT_ADDRESS` | the contract. Without it, the TUI uses the latest deployment (`deployment/artifacts/Windmill42.json`) or asks for an address and saves it. |

## The screen

- **Left:** the collection (contract, name, owner, minted n/42, image URI), your wallet and balance, the last transaction, and the command list.
- **Right:** the image or the token details.
- **Bottom:** the command line and a status line. Every error is one friendly sentence; the TUI never crashes on bad input.

## Commands

| Command | What it does |
|---|---|
| `mint` | mints the next token to your wallet (owner only) |
| `mint <address>` | mints the next token to another address |
| `owner <id>` | `ownerOf(id)`: who owns token *id* ("that's you" if it is your wallet) |
| `uri <id>` | `tokenURI(id)`, decoded: name, artist, description, image link, on-chain SVG size, attributes |
| `view [id]` | draws the **on-chain** image (`svgImage()`) in the terminal (64×32 cells, two pixels per cell) |
| `ipfs` | downloads the **IPFS** image through the contract's gateway link and checks it is the same as the on-chain one |
| `hack` | security demo: simulates a random wallet calling `mint` (free `eth_call`, nothing is sent). The contract answers *"Only the contract owner can mint."* |
| `send <id> <address>` | transfers your token to another address (`safeTransferFrom`) |
| `refresh` | re-reads the collection and your balance |
| `adr` / `tx` | copy the contract address / last tx hash to the clipboard |
| `q` | quit |

Token IDs are checked before any call: they must be whole numbers from 1 to 42.

## Messages

The TUI and the website use the same sentences for contract errors:

| Contract error | Message |
|---|---|
| `OwnableUnauthorizedAccount` | Only the contract owner can mint. |
| `MaxSupplyReached` | All 42 Windmill42 tokens are already minted. |
| `ERC721NonexistentToken` | This token does not exist (yet). |
| `ERC721IncorrectOwner` / `ERC721InsufficientApproval` | Your wallet does not own this token. |
| no gas money | Not enough Sepolia ETH to pay for gas. |
| no contract at that address | No Windmill42 contract at this address on this network: check CONTRACT_ADDRESS. |

> [!TIP]
> `view` needs a terminal of at least 110×36 characters; the TUI says so if yours is smaller.
