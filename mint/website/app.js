/*
 * Windmill42 mint page.
 *
 * Talks to the contract through MetaMask only: no RPC URL, no key and no
 * secret in this page. config.json (written by deployment/deploy.py) gives
 * the contract address and ABI. Every value coming from the chain is shown
 * with textContent, never as HTML.
 */
"use strict";

const SEPOLIA = {
  chainId: "0xaa36a7", // 11155111
  chainName: "Sepolia",
  nativeCurrency: { name: "Sepolia Ether", symbol: "ETH", decimals: 18 },
  rpcUrls: ["https://ethereum-sepolia-rpc.publicnode.com"], // public, no key
  blockExplorerUrls: ["https://sepolia.etherscan.io"],
};
const ETHERSCAN = "https://sepolia.etherscan.io";
const MAX_SUPPLY = 42;

// Same wording as FRIENDLY_ERRORS in mint/nft_client.py.
const FRIENDLY_ERRORS = {
  OwnableUnauthorizedAccount: "Only the contract owner can mint.",
  MaxSupplyReached: "All 42 Windmill42 tokens are already minted.",
  ERC721NonexistentToken: "This token does not exist (yet).",
  ERC721IncorrectOwner: "Your wallet does not own this token.",
  ERC721InsufficientApproval: "Your wallet does not own this token.",
  ERC721InvalidReceiver: "This address cannot receive NFTs.",
  OwnableInvalidOwner: "This address cannot become the owner.",
};
const NO_METAMASK = "Install MetaMask to use this page.";
const CONNECT_FIRST = "Connect MetaMask to load the collection.";
const NO_FUNDS = "Not enough Sepolia ETH to pay for gas.";
const NO_CONTRACT =
  "No Windmill42 contract at this address on Sepolia: re-run deploy.py.";

const state = {
  config: null, // {address, chainId, abi, imageGatewayURL}
  provider: null, // ethers.BrowserProvider over window.ethereum
  contract: null, // read-only contract (calls go through MetaMask)
  account: null, // connected address (checksummed)
  owner: null, // contract owner
  minted: 0,
  busy: false,
};

const $ = (id) => document.getElementById(id);

/* ---------------------------------------------------------------------- */
/* Small helpers                                                          */
/* ---------------------------------------------------------------------- */

function short(address) {
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

function sameAddress(a, b) {
  return Boolean(a && b) && a.toLowerCase() === b.toLowerCase();
}

/** Show a message in the status line; `link` = {href, text} (optional). */
function setStatus(message, kind = "info", link = null) {
  const status = $("status");
  status.replaceChildren(document.createTextNode(message));
  if (link) {
    const a = document.createElement("a");
    a.href = link.href;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = link.text;
    status.append(" ", a);
  }
  status.dataset.kind = kind;
  // replay the flash so a new message is noticed even if the text repeats
  status.classList.remove("flash");
  void status.offsetWidth;
  status.classList.add("flash");
}

function txLink(hash) {
  return { href: `${ETHERSCAN}/tx/${hash}`, text: "view on Etherscan" };
}

/** Token ID typed by the user -> number 1..42, or an Error. */
function parseTokenId(raw) {
  const text = String(raw).trim();
  const id = Number(text);
  if (!/^\d{1,2}$/.test(text) || id < 1 || id > MAX_SUPPLY) {
    throw new Error("Token ID must be a whole number between 1 and 42.");
  }
  return id;
}

/** "data:application/json;base64,..." -> metadata object. */
function decodeTokenURI(uri) {
  const prefix = "data:application/json;base64,";
  if (!uri.startsWith(prefix)) {
    throw new Error("Unexpected tokenURI format.");
  }
  const binary = atob(uri.slice(prefix.length));
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  const metadata = JSON.parse(new TextDecoder().decode(bytes));
  if (metadata === null || typeof metadata !== "object") {
    throw new Error("The metadata is not a JSON object.");
  }
  return metadata;
}

/** Revert data ("0x...") hidden somewhere in a wallet/ethers error. */
function revertData(err) {
  const candidates = [
    err?.data,
    err?.info?.error?.data,
    err?.info?.error?.data?.data,
    err?.error?.data,
    err?.error?.data?.data,
  ];
  return candidates.find(
    (d) => typeof d === "string" && d.startsWith("0x") && d.length >= 10,
  );
}

/** One sentence explaining `err` to the user. */
function friendlyError(err) {
  if (!err) return "Unknown error.";
  if (
    err.code === "ACTION_REJECTED" ||
    err.code === 4001 ||
    err?.info?.error?.code === 4001
  ) {
    return "Request rejected in MetaMask.";
  }
  if (err.code === -32002) {
    return "MetaMask is already waiting for you: open the extension.";
  }
  let name = err.revert?.name;
  const data = revertData(err);
  if (!name && data && state.config) {
    try {
      name = new ethers.Interface(state.config.abi).parseError(data)?.name;
    } catch {
      name = undefined;
    }
  }
  if (name) return FRIENDLY_ERRORS[name] ?? `The contract refused: ${name}.`;
  const text = `${err.shortMessage ?? ""} ${err.message ?? ""}`;
  if (err.code === "INSUFFICIENT_FUNDS" || /insufficient funds/i.test(text)) {
    return NO_FUNDS;
  }
  if (err.code === "BAD_DATA") return NO_CONTRACT;
  return err.shortMessage || err.message || String(err);
}

/** Wrap an async handler: one action at a time, errors -> status line. */
function guarded(action) {
  return async (event) => {
    event?.preventDefault?.();
    if (state.busy) return;
    state.busy = true;
    updateButtons();
    try {
      await action();
    } catch (err) {
      console.warn(err);
      setStatus(`✗ ${friendlyError(err)}`, "error");
    } finally {
      state.busy = false;
      updateButtons();
    }
  };
}

function updateButtons() {
  const ready = Boolean(state.contract) && !state.busy;
  $("connect-button").disabled = state.busy || !window.ethereum;
  $("switch-button").disabled = state.busy;
  $("disconnect-button").disabled = state.busy;
  $("lookup-button").disabled = !ready;
  $("mint-button").disabled = !ready || state.minted >= MAX_SUPPLY;
}

/* ---------------------------------------------------------------------- */
/* Wallet                                                                 */
/* ---------------------------------------------------------------------- */

async function loadConfig() {
  const response = await fetch("config.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("config.json not found: run deployment/deploy.py first.");
  }
  const config = await response.json();
  if (!ethers.isAddress(config.address) || !Array.isArray(config.abi)) {
    throw new Error("config.json is invalid: re-run deployment/deploy.py.");
  }
  return config;
}

/** Ask MetaMask to use Sepolia (adding it if the wallet does not know it). */
async function ensureSepolia() {
  const current = await window.ethereum.request({ method: "eth_chainId" });
  if (current === SEPOLIA.chainId) return;
  try {
    await window.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: SEPOLIA.chainId }],
    });
  } catch (err) {
    const code = err?.code ?? err?.data?.originalError?.code;
    if (code !== 4902) throw err;
    await window.ethereum.request({
      method: "wallet_addEthereumChain",
      params: [SEPOLIA],
    });
  }
}

async function connectWallet() {
  if (!window.ethereum) throw new Error(NO_METAMASK);
  setStatus("Waiting for MetaMask…");
  const accounts = await window.ethereum.request({
    method: "eth_requestAccounts",
  });
  await ensureSepolia();
  rememberDisconnected(false);
  state.provider = new ethers.BrowserProvider(window.ethereum);
  state.account = ethers.getAddress(accounts[0]);
  state.contract = new ethers.Contract(
    state.config.address,
    state.config.abi,
    state.provider,
  );
  showWallet(true);
  setStatus("Loading the collection…");
  await refreshInfo();
  await showArtwork();
  setStatus("✓ Connected to Sepolia.", "ok");
}

function showWallet(onSepolia) {
  const network = $("network-badge");
  network.hidden = false;
  network.textContent = onSepolia ? "Sepolia" : "Wrong network";
  network.className = `badge ${onSepolia ? "ok" : "warn"}`;
  const account = $("account-badge");
  account.hidden = !state.account;
  account.textContent = state.account ? short(state.account) : "";
  account.title = state.account ?? "";
  const connected = Boolean(state.contract);
  $("connect-button").hidden = connected;
  $("switch-button").hidden = !connected;
  $("disconnect-button").hidden = !connected;
}

/* The "disconnected" choice survives a reload, so the page does not
 * reconnect by itself (older MetaMask cannot revoke the site's access). */
const DISCONNECTED_KEY = "windmill42-disconnected";

function rememberDisconnected(value) {
  try {
    if (value) localStorage.setItem(DISCONNECTED_KEY, "1");
    else localStorage.removeItem(DISCONNECTED_KEY);
  } catch {
    // storage blocked (private mode): only auto-reconnect is affected
  }
}

function wasDisconnected() {
  try {
    return localStorage.getItem(DISCONNECTED_KEY) === "1";
  } catch {
    return false;
  }
}

/** Open MetaMask's account picker, then use the chosen account. */
async function switchAccount() {
  setStatus("Pick an account in MetaMask…");
  await window.ethereum.request({
    method: "wallet_requestPermissions",
    params: [{ eth_accounts: {} }],
  });
  const accounts = await window.ethereum.request({ method: "eth_accounts" });
  if (accounts.length === 0) throw new Error("No account selected.");
  await useAccount(accounts[0]);
  setStatus(`✓ Using ${short(state.account)}.`, "ok");
}

/** Show the page for another account (the collection stays the same). */
async function useAccount(address) {
  state.account = ethers.getAddress(address);
  $("token-table").hidden = true; // its "(you)" marks were for the old one
  showWallet(true);
  await refreshInfo();
}

/** Remove this site's access to the wallet and reset the page. */
async function disconnectWallet() {
  try {
    await window.ethereum.request({
      method: "wallet_revokePermissions",
      params: [{ eth_accounts: {} }],
    });
  } catch (err) {
    console.warn("wallet_revokePermissions unavailable", err);
  }
  rememberDisconnected(true);
  resetPage();
  setStatus("Disconnected. Connect again to choose an account.", "ok");
}

function resetPage() {
  Object.assign(state, {
    provider: null,
    contract: null,
    account: null,
    owner: null,
    minted: 0,
  });
  for (const id of ["collection-name", "contract-owner", "minted-count"]) {
    $(id).textContent = "–";
  }
  $("minted-bar").style.width = "0";
  $("mint-hint").textContent = "";
  $("token-table").hidden = true;
  $("onchain-image").hidden = true;
  $("onchain-placeholder").hidden = false;
  showWallet(false);
  $("network-badge").hidden = true;
  updateButtons();
}

/* ---------------------------------------------------------------------- */
/* Reads                                                                  */
/* ---------------------------------------------------------------------- */

async function refreshInfo() {
  const c = state.contract;
  const [name, symbol, owner, minted, max] = await Promise.all([
    c.name(),
    c.symbol(),
    c.owner(),
    c.totalMinted(),
    c.MAX_SUPPLY(),
  ]);
  state.owner = owner;
  state.minted = Number(minted);
  $("collection-name").textContent = `${name} (${symbol})`;
  $("contract-owner").textContent = sameAddress(owner, state.account)
    ? `${owner} (you)`
    : owner;
  $("minted-count").textContent = `${state.minted} / ${max}`;
  $("minted-bar").style.width = `${(state.minted / Number(max)) * 100}%`;
  const hint = $("mint-hint");
  if (state.minted >= MAX_SUPPLY) {
    hint.textContent = "All 42 tokens are minted.";
  } else if (sameAddress(owner, state.account)) {
    hint.textContent = "You own the contract: the token goes to your wallet.";
  } else {
    hint.textContent =
      `Only the owner (${short(owner)}) can mint: ` +
      "try it to see the contract refuse.";
  }
  updateButtons();
}

/** Both copies of the artwork: the on-chain SVG and the IPFS file. */
async function showArtwork() {
  const [svg, url] = await Promise.all([
    state.contract.svgImage(),
    state.contract.imageURL().catch(() => state.config.imageGatewayURL),
  ]);
  const onchain = $("onchain-image");
  // An <img> never runs scripts inside an SVG: safe to display.
  onchain.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  onchain.hidden = false;
  $("onchain-placeholder").hidden = true;
  showIpfsImage(url);
}

/** Load the IPFS file through its https gateway link (no wallet needed). */
function showIpfsImage(url) {
  if (typeof url !== "string" || !url.startsWith("https://")) return;
  const ipfs = $("ipfs-image");
  if (ipfs.src === url) return;
  ipfs.onload = () => {
    ipfs.hidden = false;
    $("ipfs-placeholder").hidden = true;
  };
  ipfs.onerror = () => {
    $("ipfs-placeholder").textContent = "✗";
    $("ipfs-placeholder").title = "The IPFS gateway did not answer.";
  };
  ipfs.src = url;
  const link = $("ipfs-link");
  link.href = url;
  link.hidden = false;
}

async function lookupToken(id) {
  const [owner, uri] = await Promise.all([
    state.contract.ownerOf(id),
    state.contract.tokenURI(id),
  ]);
  const metadata = decodeTokenURI(uri);
  const rows = [
    ["ownerOf", sameAddress(owner, state.account) ? `${owner} (you)` : owner],
    ["name", metadata.name],
    ["artist", metadata.artist],
    ["description", metadata.description],
    ["image", metadata.image],
    [
      "image_data",
      `on-chain SVG, ${String(metadata.image_data ?? "").length} characters`,
    ],
  ];
  for (const attribute of metadata.attributes ?? []) {
    rows.push([attribute.trait_type, attribute.value]);
  }
  rows.push(["tokenURI", `data:application/json;base64 (${uri.length} chars)`]);

  const body = $("token-rows");
  body.replaceChildren(
    ...rows.map(([key, value]) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      const td = document.createElement("td");
      th.scope = "row";
      th.textContent = key;
      td.textContent = String(value ?? "–");
      tr.append(th, td);
      return tr;
    }),
  );
  $("token-table").hidden = false;
  setStatus(`✓ Windmill42 #${id}`, "ok", {
    href: `${ETHERSCAN}/nft/${state.config.address}/${id}`,
    text: "view on Etherscan",
  });
}

/* ---------------------------------------------------------------------- */
/* Write                                                                  */
/* ---------------------------------------------------------------------- */

async function mintToken() {
  const signer = await state.provider.getSigner();
  const contract = state.contract.connect(signer);
  setStatus("Confirm the transaction in MetaMask…");
  const tx = await contract.mint(state.account);
  setStatus("Minting: waiting for the block…", "info", txLink(tx.hash));
  const receipt = await tx.wait();
  let tokenId = null;
  for (const log of receipt.logs) {
    const parsed = contract.interface.parseLog(log);
    if (parsed?.name === "Transfer") tokenId = parsed.args.tokenId;
  }
  await refreshInfo();
  if (tokenId !== null) {
    $("token-id").value = String(tokenId);
    await lookupToken(Number(tokenId));
  }
  setStatus(
    `✓ Minted Windmill42 #${tokenId ?? "?"} to your wallet.`,
    "ok",
    txLink(tx.hash),
  );
}

/* ---------------------------------------------------------------------- */
/* Start                                                                  */
/* ---------------------------------------------------------------------- */

async function init() {
  $("connect-button").addEventListener("click", guarded(connectWallet));
  $("switch-button").addEventListener("click", guarded(switchAccount));
  $("disconnect-button").addEventListener("click", guarded(disconnectWallet));
  $("mint-button").addEventListener("click", guarded(mintToken));
  $("lookup-form").addEventListener(
    "submit",
    guarded(() => lookupToken(parseTokenId($("token-id").value))),
  );
  updateButtons();

  if (typeof ethers === "undefined") {
    setStatus("✗ Could not load ethers.js (offline?).", "error");
    return;
  }
  try {
    state.config = await loadConfig();
  } catch (err) {
    setStatus(`✗ ${err.message}`, "error");
    return;
  }
  const link = $("contract-link");
  link.href = `${ETHERSCAN}/address/${state.config.address}`;
  link.textContent = state.config.address;
  showIpfsImage(state.config.imageGatewayURL);

  if (!window.ethereum) {
    setStatus(NO_METAMASK, "error");
    updateButtons();
    return;
  }
  setStatus(CONNECT_FIRST);
  // A network change invalidates every read: start again from a clean page.
  window.ethereum.on?.("chainChanged", () => window.location.reload());
  // Account changed in MetaMask itself (or the site was disconnected there).
  window.ethereum.on?.("accountsChanged", (accounts) => {
    if (!state.contract) return;
    if (accounts.length === 0) {
      resetPage();
      setStatus("MetaMask disconnected this site.");
      return;
    }
    if (sameAddress(accounts[0], state.account)) return;
    guarded(async () => {
      await useAccount(accounts[0]);
      setStatus(`✓ Using ${short(state.account)}.`, "ok");
    })();
  });
  if (wasDisconnected()) return; // the user chose to disconnect
  // Already authorised and on Sepolia: reconnect without any prompt.
  let accounts;
  let chainId;
  try {
    [accounts, chainId] = await Promise.all([
      window.ethereum.request({ method: "eth_accounts" }),
      window.ethereum.request({ method: "eth_chainId" }),
    ]);
  } catch (err) {
    console.warn(err);
    setStatus(`✗ ${friendlyError(err)}`, "error");
    return;
  }
  if (accounts.length > 0 && chainId === SEPOLIA.chainId) {
    await guarded(connectWallet)();
  } else if (accounts.length > 0) {
    state.account = ethers.getAddress(accounts[0]);
    showWallet(false);
  }
}

init();
