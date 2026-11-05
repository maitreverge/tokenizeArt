# Minting Website (bonus)

A single page in plain HTML/CSS/JavaScript (`mint/website/`) that talks to the contract through **MetaMask**.

```bash
docker compose up website      # on the host
```

Then open <http://localhost:8042> in a browser that has MetaMask.

## What it shows

- **The artwork, twice, side by side:**
  - *Stored on-chain*: the SVG returned by `svgImage()`.
  - *Pinned on IPFS*: the PNG loaded from the contract's `imageURL()`.
- **The collection:** contract address (linked to Etherscan), name and symbol, owner, minted n/42.
- **Mint:** mints the next token to the connected wallet. If you are not the owner, the contract refuses and the page says so.
- **Look up a token:** a token ID from 1 to 42 shows `ownerOf` plus the decoded `tokenURI` metadata.

## How to use it

1. **Connect MetaMask.** The page asks MetaMask to switch to Sepolia (and to add it if MetaMask does not know it).
2. Both images appear, with the collection info.
3. **Mint** → confirm in MetaMask → the transaction link appears, then the new token's details.
4. **Switch account** opens MetaMask's account picker, for example to try minting from a non-owner account.
5. **Disconnect** removes the site's access to your wallet. After a reload, the page stays disconnected until you click Connect again.

The status line under the header stays on screen and flashes on every message. For example:
- rejecting a transaction shows *"Request rejected in MetaMask."*
- a non-owner gets *"Only the contract owner can mint."*

## How it works

| File | Role |
|---|---|
| `index.html` | the page and its security policy |
| `style.css` | the look (colours from the artwork; dark mode and phone widths supported) |
| `app.js` | the logic: `connectWallet`, `ensureSepolia`, `refreshInfo`, `showArtwork`, `mintToken`, `lookupToken`, `friendlyError` |
| `config.json` | written by `deploy.py`: contract address, chainId, ABI, image link |

- **ethers.js 6.17.0** is loaded from cdnjs with an **SRI hash** (`integrity=…`). The browser refuses the file if a single byte differs.
- All reads and the mint go through MetaMask's provider. The page contains **no RPC URL, no key and no secret**, and MetaMask signs.
- Values read from the chain (metadata, addresses) are written with `textContent`, never as HTML, so a malicious metadata string cannot inject code.
- The on-chain SVG is shown through an `<img>` tag, which never runs scripts inside an SVG.
- A **Content-Security-Policy** limits the page:
  - scripts: only this site and cdnjs;
  - images: only this site, `data:` (the SVG) and `https:` (the gateway);
  - no other network access.
