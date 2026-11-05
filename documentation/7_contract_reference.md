# Contract Reference: `Windmill42`

`code/Windmill42.sol`, Solidity `0.8.35`:

```solidity
contract Windmill42 is ERC721, Ownable, IERC4906
```

Legend:
- 🔓 anyone can call (read calls are free);
- 👑 owner only;
- 🎫 token owner or approved address.

Inherited items come from OpenZeppelin Contracts 5.6.1.

---

## Constructor

```solidity
constructor(string memory imageCID_, string memory imageGateway_)
```

Run once, by the deployer, who becomes the **owner**. It sets the name `Windmill42`, the symbol `WM42`, the IPFS CID of the artwork and the https gateway prefix. It reverts with `EmptyImageCID` or `EmptyImageGateway` if either is empty.

---

## Collection constants and state

### `MAX_SUPPLY`
`uint256 public constant MAX_SUPPLY = 42`. 🔓 The maximum number of tokens that can ever exist.

### `ARTIST`
`string public constant ARTIST = "flverge"`. 🔓 The artist: the author's 42 login. It also appears in the metadata.

### `TITLE`
`string public constant TITLE = "Spring Meadow"`. 🔓 Title of the artwork.

### `totalMinted`
`function totalMinted() view returns (uint256)`. 🔓 How many tokens are minted. Token IDs are `1 … totalMinted`.

### `imageCID`
`function imageCID() view returns (string)`. 🔓 The IPFS CID of the pinned artwork. It is set in the constructor and can **never** change.

### `imageGateway`
`function imageGateway() view returns (string)`. 🔓 The https gateway prefix used in the metadata, e.g. `https://gateway.pinata.cloud/ipfs/`.

### `imageURI`
`function imageURI() view returns (string)`. 🔓 The canonical IPFS address: `ipfs://<imageCID>`.

### `imageURL`
`function imageURL() view returns (string)`. 🔓 `imageGateway + imageCID`: the https link wallets load.

### `name`
`function name() view returns (string)`. 🔓 *(ERC721)* `"Windmill42"`.

### `symbol`
`function symbol() view returns (string)`. 🔓 *(ERC721)* `"WM42"`.

### `owner`
`function owner() view returns (address)`. 🔓 *(Ownable)* The contract owner, the only address allowed to mint.

---

## Minting and art

### `mint`
`function mint(address to) returns (uint256 tokenId)`. 👑 Mints the next token (ID `totalMinted + 1`) to `to` and returns its ID.
- Reverts with `OwnableUnauthorizedAccount` if the caller is not the owner.
- Reverts with `MaxSupplyReached` once 42 tokens exist.
- Reverts with `ERC721InvalidReceiver` if `to` is a contract that cannot hold NFTs (`_safeMint`).
- Emits `Transfer(0x0, to, tokenId)`.

### `svgImage`
`function svgImage() pure returns (string)`. 🔓 The artwork as an SVG (64×64 `viewBox`, one `<path>` per colour), rebuilt on-chain from the pixel data. It is byte for byte equal to `mint/art/windmill42.svg`. A heavy read (~4.4M gas), but free.

### `tokenURI`
`function tokenURI(uint256 tokenId) view returns (string)`. 🔓 *(ERC721, overridden)* The metadata, built on-chain, as `data:application/json;base64,<JSON>`. The JSON holds:
- `name`: `"Windmill42 #<id>"`;
- `description`;
- `image`: `imageURL()`;
- `image_data`: the on-chain SVG;
- `attributes`: Artist, Title, Edition `<id>/42`;
- `artist`: `"flverge"`.

It reverts with `ERC721NonexistentToken` for an unminted ID.

### `setImageGateway`
`function setImageGateway(string gateway)`. 👑 Replaces the https gateway (for example if it closes). The CID, and so the image, does not change. It reverts with `EmptyImageGateway` for `""` and emits `BatchMetadataUpdate(1, 42)`. The contract accepts any other string, so the caller must pass a clean `https://<domain>/ipfs/` prefix.

### `supportsInterface`
`function supportsInterface(bytes4 interfaceId) view returns (bool)`. 🔓 *(ERC165)* `true` for ERC-165 `0x01ffc9a7`, ERC-721 `0x80ac58cd`, ERC-721 Metadata `0x5b5e139f` and ERC-4906 `0x49064906`.

---

## Ownership of tokens (ERC-721, inherited)

### `ownerOf`
`function ownerOf(uint256 tokenId) view returns (address)`. 🔓 The current owner of a token. It reverts with `ERC721NonexistentToken` for an unminted ID.

### `balanceOf`
`function balanceOf(address owner) view returns (uint256)`. 🔓 How many Windmill42 tokens `owner` holds. It reverts with `ERC721InvalidOwner` for the zero address.

### `transferFrom`
`function transferFrom(address from, address to, uint256 tokenId)`. 🎫 Moves a token. It does not check that `to` can receive NFTs.

### `safeTransferFrom`
`function safeTransferFrom(address from, address to, uint256 tokenId[, bytes data])`. 🎫 Moves a token. If `to` is a contract, it must implement `onERC721Received`, otherwise the call reverts. The TUI's `send` uses this.

### `approve`
`function approve(address to, uint256 tokenId)`. 🎫 Allows `to` to transfer this one token.

### `getApproved`
`function getApproved(uint256 tokenId) view returns (address)`. 🔓 The address approved for a token (zero if none).

### `setApprovalForAll`
`function setApprovalForAll(address operator, bool approved)`. 🔓 For the caller's own tokens: allows or forbids `operator` (a marketplace, say) to move all of them.

### `isApprovedForAll`
`function isApprovedForAll(address owner, address operator) view returns (bool)`. 🔓 Whether `operator` may move all of `owner`'s tokens.

---

## Contract ownership (Ownable, inherited)

### `transferOwnership`
`function transferOwnership(address newOwner)`. 👑 Hands the contract, and so the right to mint, to `newOwner`. It reverts with `OwnableInvalidOwner` for the zero address.

### `renounceOwnership`
`function renounceOwnership()`. 👑 Removes the owner for good: nobody can mint or change the gateway any more. Irreversible.

---

## Events

### `Transfer`
`Transfer(address from, address to, uint256 tokenId)`: a mint (`from` = 0x0) or a transfer.

### `Approval`
`Approval(address owner, address approved, uint256 tokenId)`: a single-token approval.

### `ApprovalForAll`
`ApprovalForAll(address owner, address operator, bool approved)`: an operator approval.

### `OwnershipTransferred`
`OwnershipTransferred(address previousOwner, address newOwner)`: emitted at deployment and when ownership changes.

### `BatchMetadataUpdate`
`BatchMetadataUpdate(uint256 fromTokenId, uint256 toTokenId)`: *(ERC-4906)* tells wallets to reload the metadata of tokens 1 to 42 after `setImageGateway`.

### `MetadataUpdate`
`MetadataUpdate(uint256 tokenId)`: *(ERC-4906)* part of the standard interface; this contract only emits the batch version.

---

## Custom errors

### `MaxSupplyReached`
`MaxSupplyReached()`: `mint` was called when 42 tokens already exist.

### `EmptyImageCID`
`EmptyImageCID()`: the constructor got an empty CID.

### `EmptyImageGateway`
`EmptyImageGateway()`: an empty gateway, in the constructor or in `setImageGateway`.

### `OwnableUnauthorizedAccount`
`OwnableUnauthorizedAccount(address account)`: an owner-only function was called by `account`.

### `OwnableInvalidOwner`
`OwnableInvalidOwner(address owner)`: ownership cannot go to this address (zero).

### `ERC721NonexistentToken`
`ERC721NonexistentToken(uint256 tokenId)`: the token is not minted.

### `ERC721IncorrectOwner`
`ERC721IncorrectOwner(address sender, uint256 tokenId, address owner)`: `from` is not the token's owner.

### `ERC721InsufficientApproval`
`ERC721InsufficientApproval(address operator, uint256 tokenId)`: the caller is neither the owner nor approved.

### `ERC721InvalidApprover`
`ERC721InvalidApprover(address approver)`: this address cannot approve.

### `ERC721InvalidOperator`
`ERC721InvalidOperator(address operator)`: this operator is invalid (zero address).

### `ERC721InvalidOwner`
`ERC721InvalidOwner(address owner)`: this owner is invalid (zero address).

### `ERC721InvalidReceiver`
`ERC721InvalidReceiver(address receiver)`: the receiver is the zero address or a contract that cannot hold NFTs.

### `ERC721InvalidSender`
`ERC721InvalidSender(address sender)`: this sender is invalid (a mint of an existing ID).
