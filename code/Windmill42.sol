// SPDX-License-Identifier: MIT
pragma solidity ^0.8.35;

// OpenZeppelin's audited implementations: the ERC-721 standard
// (ownerOf, balanceOf, transfers, approvals...) and single-owner access
// control (owner, onlyOwner, transferOwnership, renounceOwnership).
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
// ERC-4906: the event that tells wallets and marketplaces to reload metadata.
import "@openzeppelin/contracts/interfaces/IERC4906.sol";
// Helpers to build the on-chain metadata: number -> text, Base64 encoding.
import "@openzeppelin/contracts/utils/Strings.sol";
import "@openzeppelin/contracts/utils/Base64.sol";
// The artwork itself, rebuilt as an SVG image from on-chain pixel data.
import "./Windmill42Art.sol";

/**
 * @title Windmill42
 * @author flverge
 * @notice "Spring Meadow", a 64x64 pixel-art NFT collection for the
 *         42 TokenizeArt project. At most 42 tokens exist, all showing
 *         the same artwork. Only the contract owner can mint.
 * @dev    The artwork is stored twice: pinned on IPFS (`imageCID`) and
 *         on-chain (`svgImage()`). The metadata returned by `tokenURI` is
 *         built on-chain too. Wallets show `imageURL()`: the IPFS file
 *         served by an https gateway, because the public ipfs.io gateway
 *         (used by wallets for "ipfs://" links) closed in September 2026.
 */
contract Windmill42 is ERC721, Ownable, IERC4906 {
    /// @notice Maximum number of tokens that can ever exist.
    uint256 public constant MAX_SUPPLY = 42;

    /// @notice The artist: the author's 42 login.
    string public constant ARTIST = "flverge";

    /// @notice Title of the artwork.
    string public constant TITLE = "Spring Meadow";

    /// @notice IPFS content ID (CID) of the pinned artwork.
    /// @dev Set once in the constructor; there is no function to change it.
    string public imageCID;

    /// @notice https gateway that serves IPFS files, e.g.
    ///         "https://gateway.pinata.cloud/ipfs/". The owner can change
    ///         it if the gateway closes; the image (its CID) never changes.
    string public imageGateway;

    /// @notice Number of tokens minted so far (token IDs are 1..totalMinted).
    uint256 public totalMinted;

    /// @notice Raised when all MAX_SUPPLY tokens are already minted.
    error MaxSupplyReached();

    /// @notice Raised when the contract is deployed without an image CID.
    error EmptyImageCID();

    /// @notice Raised when the image gateway is set to an empty string.
    error EmptyImageGateway();

    /**
     * @notice Deploys the collection. The deployer becomes the owner.
     * @param imageCID_ IPFS CID of the pinned artwork, e.g. "bafkrei...".
     * @param imageGateway_ https gateway prefix, ending with "/ipfs/".
     */
    constructor(string memory imageCID_, string memory imageGateway_)
        ERC721("Windmill42", "WM42")
        Ownable(msg.sender)
    {
        if (bytes(imageCID_).length == 0) revert EmptyImageCID();
        if (bytes(imageGateway_).length == 0) revert EmptyImageGateway();
        imageCID = imageCID_;
        imageGateway = imageGateway_;
    }

    /// @notice IPFS address of the artwork: "ipfs://<CID>".
    function imageURI() public view returns (string memory) {
        return string.concat("ipfs://", imageCID);
    }

    /// @notice https link to the IPFS artwork: gateway + CID.
    function imageURL() public view returns (string memory) {
        return string.concat(imageGateway, imageCID);
    }

    /**
     * @notice Changes the https gateway used in the metadata. Owner only.
     * @dev Emits ERC-4906 BatchMetadataUpdate so wallets reload tokens.
     * @param gateway New gateway prefix, ending with "/ipfs/".
     */
    function setImageGateway(string calldata gateway) external onlyOwner {
        if (bytes(gateway).length == 0) revert EmptyImageGateway();
        imageGateway = gateway;
        emit BatchMetadataUpdate(1, MAX_SUPPLY);
    }

    /// @notice ERC-165: the contract supports ERC-721 and ERC-4906.
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, IERC165)
        returns (bool)
    {
        return interfaceId == bytes4(0x49064906)
            || super.supportsInterface(interfaceId);
    }

    /**
     * @notice Mints the next token to `to`. Only the owner can call it.
     * @param to Address that receives the new token.
     * @return tokenId ID of the new token (1 for the first one, up to 42).
     */
    function mint(address to) external onlyOwner returns (uint256 tokenId) {
        if (totalMinted >= MAX_SUPPLY) revert MaxSupplyReached();
        // The counter is updated before _safeMint, which may call the
        // receiver's contract: a re-entrant call cannot reuse the ID.
        tokenId = ++totalMinted;
        _safeMint(to, tokenId);
    }

    /**
     * @notice The artwork as an SVG image, rebuilt entirely on-chain.
     * @return The SVG text (single-quoted attributes, 64x64 viewBox).
     */
    function svgImage() public pure returns (string memory) {
        return Windmill42Art.svg();
    }

    /**
     * @notice Metadata of a token, stored on-chain (no external server).
     * @dev Returns "data:application/json;base64,<JSON>". The JSON holds:
     *      name, description, image (imageURL(), shown by wallets),
     *      image_data (the on-chain SVG), attributes and artist.
     *      Reverts with ERC721NonexistentToken if the token is not minted.
     * @param tokenId ID of an existing token.
     */
    function tokenURI(uint256 tokenId)
        public
        view
        override
        returns (string memory)
    {
        _requireOwned(tokenId);
        return string.concat(
            "data:application/json;base64,",
            Base64.encode(_metadataJSON(Strings.toString(tokenId)))
        );
    }

    /// @dev Builds the JSON metadata of token `id` (given as text).
    function _metadataJSON(string memory id)
        private
        view
        returns (bytes memory)
    {
        bytes memory header = abi.encodePacked(
            '{"name":"Windmill42 #', id,
            '","description":"', TITLE, " by ", ARTIST,
            ": 64x64 pixel art of a windmill meadow with a cloud-drawn 42."
            " Edition ", id, " of 42. The image is pinned on IPFS and also"
            ' stored on-chain.","image":"', imageURL(),
            '","image_data":"', svgImage(), '",'
        );
        bytes memory attributes = abi.encodePacked(
            '"attributes":[{"trait_type":"Artist","value":"', ARTIST,
            '"},{"trait_type":"Title","value":"', TITLE,
            '"},{"trait_type":"Edition","value":"', id,
            '/42"}],"artist":"', ARTIST, '"}'
        );
        return bytes.concat(header, attributes);
    }
}
