# Windmill42 (TokenizeArt) Implementation Plan

> **User decision (2026-10-30, after art approval):** the artwork generator was deleted; the committed files `mint/art/windmill42.png`, `mint/art/windmill42.svg` and `code/Windmill42ArtData.sol` are the source of truth. Wherever this plan says `to_svg(build_pixels(), PALETTE)`, use the content of `mint/art/windmill42.svg`; `svg_to_grid` (Task 7) was built in Task 2.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `Windmill42` ERC-721 NFT project (42 TokenizeArt) on Sepolia: pixel-art image on IPFS + on-chain copy, OpenZeppelin contract, Python deploy script, Rich mint TUI, MetaMask website, and documentation that passes the 42 evaluation sheet.

**Architecture:** One Python generator produces the 64×64 artwork (PNG for IPFS, SVG preview, and a generated Solidity data file with the run-length-encoded pixels). The `Windmill42` contract (ERC721 + Ownable) rebuilds the SVG on-chain and returns fully on-chain base64 JSON metadata whose `image` points to IPFS. Python tools (`deployment/deploy.py`, `mint/pin_to_ipfs.py`, `mint/mint_tui.py`) use web3.py and run in a Docker container copied from the reference project `../tokenizer/`; a static page in `mint/website/` uses MetaMask + ethers.js.

**Tech Stack:** Solidity 0.8.35 (py-solc-x, `evm_version="cancun"`), OpenZeppelin Contracts 5.6.1 (npm), Python 3.11, web3.py 8.0.0 (+ `eth-tester` for tests), Rich, readchar, Pillow, requests, pytest, Docker / Docker Compose, ethers.js v6 (CDN), Pinata.

**Spec:** `plans/2026-10-30-tokenizeart-design.md` (read it first; it holds the why). Reference project: `../tokenizer/` — **read-only, never modify it**.

## Global Constraints

- Network: Ethereum Sepolia, chainId `11155111`. Default RPC in `.env.example`: `https://ethereum-sepolia-rpc.publicnode.com`.
- Contract name `Windmill42`; ERC-721 name `"Windmill42"`; symbol `"WM42"`; token name `"Windmill42 #<id>"`; artwork title `"Spring Meadow"`; artist `"flverge"`.
- `MAX_SUPPLY = 42`; token IDs `1..42`; only the owner (deployer) can mint; every token has the same artwork.
- Image: 64×64 pixels, **≤ 16 colours**, PNG pinned on IPFS upscaled ×16 to 1024×1024 (nearest-neighbour). "42" must be large and legible.
- solc `0.8.35`, optimizer on (200 runs), `evm_version="cancun"` for both tests and Sepolia deploys.
- OpenZeppelin `@openzeppelin/contracts` `5.6.1`, installed by npm in `deployment/` (as in tokenizer).
- Secrets only in the gitignored root `.env`: `SEPOLIA_RPC_URL`, `PRIVATE_KEY`, `PINATA_JWT`, `PINATA_GATEWAY` (optional, not secret), `CONTRACT_ADDRESS`. `.env.example` (already written, keep it) ships with empty `PRIVATE_KEY`, `PINATA_JWT`, `PINATA_GATEWAY`, `CONTRACT_ADDRESS`. **No key, JWT or password in any committed file.**
- `SEPOLIA_RPC_URL` may contain a provider API key: **never write it into any committed file** (artifacts, website config, docs examples other than the public publicnode URL).
- **No tracebacks ever reach the user**: every script/TUI/website path catches errors and prints a one-line, human message (Python scripts exit with code 1; Ctrl-C prints "Interrupted." and exits 130).
- Required root layout (evaluation preliminaries): `README.md`, non-empty `code/`, `deployment/`, `mint/`, `documentation/`. No video files. `plans/` stays.
- Python style like tokenizer: type hints, docstrings, black line-length 79, `mypy --strict` clean.
- Git: commit after each task with the user's message style (`ADD: …`, `FIX: …`) ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Never push.**
- All tests run in the container: `docker compose run --rm tokenizeart pytest -q` (from the repo root).
- The user runs every step that uses real secrets or spends Sepolia ETH (marked **USER CHECKPOINT**).

## Review Focus

1. Bad token-ID input in the TUI (`uri`, `uri abc`, `uri -3`, `uri 0`, `uri 43`, `uri 99999999999999999999`) → friendly message, never a crash. Test: Task 8 `test_dispatch_rejects_bad_token_ids`.
2. Unreachable RPC (wrong URL, no internet) → deploy prints one clear error and exits 1; client raises `ClientError`; TUI shows it in the status line. Tests: Task 6 `test_connect_unreachable_rpc`, Task 7 `test_client_unreachable_rpc`.
3. Stale IPFS record: art regenerated after pinning (`ipfs.json` sha256 ≠ PNG sha256) → deploy refuses and tells you to re-run `pin_to_ipfs.py`. Test: Task 6 `test_settings_reject_stale_ipfs_record`.
4. Wallet without enough Sepolia ETH → deploy says how much is needed; mint/transfer say "Not enough Sepolia ETH to pay for gas." Tests: Task 6 `test_deploy_insufficient_funds`, Task 7 `test_mint_insufficient_funds`.
5. Terminal too small for the 64×32 image → `view` says the minimum size instead of drawing garbage. Test: Task 8 `test_view_terminal_too_small`.

---

## File Map

```
tokenizeArt/
├── README.md                          Task 10 (+ address in Task 11)
├── Dockerfile, docker-compose.yml, .dockerignore, .gitignore, .env.example   Task 1
├── pyproject.toml                     Task 1 (pytest, mypy, black config)
├── conftest.py                        Task 1 (shared pytest fixtures; grows in Task 3)
├── code/
│   ├── Windmill42.sol                 Task 3 (core), Task 4 (tokenURI)
│   ├── Windmill42Art.sol              Task 4 (on-chain SVG builder library)
│   ├── Windmill42ArtData.sol          Task 2 (GENERATED palette + runs)
│   └── tests/test_windmill42.py       Tasks 3–4
├── deployment/
│   ├── package.json, requirements.txt Task 1
│   ├── compiler.py                    Task 3
│   ├── deploy.py                      Task 6
│   ├── artifacts/Windmill42.json      written by deploy.py (latest deploy)
│   ├── permanent.json                 Task 11 (hand-written permanent record)
│   └── tests/test_environment.py, test_no_secrets.py (Task 1), test_deploy.py (Task 6), test_docs.py (Task 10)
├── mint/
│   ├── art/generate_art.py            Task 2
│   ├── art/windmill42.png, windmill42.svg   GENERATED (Task 2)
│   ├── pin_to_ipfs.py, ipfs.json      Task 5
│   ├── metadata.py, svg_pixels.py, terminal_image.py, nft_client.py   Task 7
│   ├── mint_tui.py                    Task 8
│   ├── website/index.html, app.js, style.css, config.json   Task 9
│   └── tests/test_art.py (2), test_pin.py (5), test_client.py (7), test_tui.py (8)
├── documentation/                     Task 10
└── plans/                             (this plan, the design, draft art)
```

Python import roots (set in `pyproject.toml` → `pythonpath`): `deployment` and `mint`. So tests import `compiler`, `deploy`, `nft_client`, `art.generate_art`, etc. Never give two modules the same name across these folders. Each script finds the repo root with `Path(__file__).resolve().parents[N]` and loads `REPO_ROOT / ".env"` explicitly (works from any cwd).

---

### Task 1: Container, configuration and test harness

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `pyproject.toml`, `conftest.py`, `deployment/package.json`, `deployment/requirements.txt`, `deployment/tests/test_environment.py`, `deployment/tests/test_no_secrets.py`
- Modify: `.gitignore` (currently only `subject.pdf`)
- Reference (read-only): `../tokenizer/Dockerfile`, `../tokenizer/docker-compose.yml`, `../tokenizer/.dockerignore`, `../tokenizer/deployment/{package.json,requirements.txt,pyproject.toml}`

**Interfaces:**
- Produces: Compose service `tokenizeart` (interactive, TTY, repo mounted at `/app`, workdir `/app`, anonymous volumes for `/app/deployment/node_modules` and `/app/.venv`); Compose service `website` (same image, runs `python -m http.server 8042 --bind 0.0.0.0 --directory /app/mint/website`, port `8042:8042`). solc 0.8.35 is installed **at image build** (`RUN python -c "import solcx; solcx.install_solc('0.8.35')"`) so `run --rm` containers never re-download it.
- Produces fixture in `conftest.py`: `w3() -> Web3` (fresh `EthereumTesterProvider` per test), `funded_account(w3) -> LocalAccount` (new `Account.create()` sent 100 ETH from `w3.eth.accounts[0]`), `unfunded_account() -> LocalAccount`.

- [ ] **Step 1: Write the container and config files.** Copy tokenizer's Dockerfile/compose/.dockerignore structure; change: final `WORKDIR /app`; drop the obsolete `version:` key; add the solc build step and the `website` service; `.dockerignore` excludes `.env`, `.git`, venvs, caches, `node_modules`. `requirements.txt` = tokenizer's pins + `pillow`, `pytest` (pin to the latest stable versions available now, `pip index versions <pkg>`). `package.json` = tokenizer's with `@openzeppelin/contracts` `5.6.1`. `pyproject.toml`: `[tool.pytest.ini_options] testpaths = ["code/tests", "deployment/tests", "mint/tests"]`, `pythonpath = ["deployment", "mint"]`; mypy strict; black 79. `.gitignore`: `.env`, `.venv/`, `venv/`, `__pycache__/`, `*.py[cod]`, `.mypy_cache/`, `.pytest_cache/`, `node_modules/`, `package-lock.json`, `subject.pdf`, `.superpowers/`. `.env.example` and `.gitignore` already exist (written before Task 1) — keep them, only extend `.gitignore` if needed.

- [ ] **Step 2: Write the environment and secret tests**

```python
# deployment/tests/test_environment.py
def test_solc_is_installed():
    import solcx
    assert "0.8.35" in [str(v) for v in solcx.get_installed_solc_versions()]

def test_openzeppelin_is_installed():
    assert (REPO_ROOT / "deployment/node_modules/@openzeppelin/contracts/token/ERC721/ERC721.sol").is_file()

def test_tester_chain_works(w3, funded_account):
    assert w3.eth.get_balance(funded_account.address) == Web3.to_wei(100, "ether")

# deployment/tests/test_no_secrets.py — scans `git ls-files` (skip binary files)
def test_no_private_key_values_committed():   # no line matching r"PRIVATE_KEY\s*=\s*\S" in any tracked file except a line exactly "PRIVATE_KEY=" in .env.example
def test_no_jwt_committed():                  # no match for r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"
def test_env_is_ignored():                    # `git check-ignore .env` exits 0
def test_no_rpc_api_keys_committed():       # no match for r"(infura\.io/v3/|alchemy\.com/v2/|quiknode\.pro/)[A-Za-z0-9_-]{10,}"
```

- [ ] **Step 3: Build and run**

Run: `docker compose build && docker compose run --rm tokenizeart pytest -q`
Expected: build succeeds; 7 tests PASS.

- [ ] **Step 4: Commit** — `ADD: docker environment, config and test harness`

---

### Task 2: Final artwork and generator

**Files:**
- Create: `mint/art/generate_art.py`, `mint/tests/test_art.py`
- Generated (commit them): `mint/art/windmill42.png`, `mint/art/windmill42.svg`, `code/Windmill42ArtData.sol`
- Reference: `plans/art_draft/draft_generator.py` (`design_a()`), `plans/art_draft/spring_meadow_draft.png`

**Interfaces:**
- Produces in `art/generate_art.py`:
  - `SIZE: int = 64`, `PALETTE: list[str]` (≤16 lowercase `"#rrggbb"`), `GLYPH_42: list[str]` (baked bitmap rows of the "42", `#` = set)
  - `build_pixels() -> list[list[int]]` — 64 rows × 64 palette indices
  - `encode_runs(pixels) -> list[tuple[int, int, int, int]]` — `(color, x, y, length)` horizontal runs, sorted by color, then y, then x
  - `to_svg(pixels, palette) -> str` — **the exact string the contract must return** (format below)
  - `to_png(pixels, palette, path: Path, scale: int = 16) -> None`
  - `to_solidity(pixels, palette) -> str` — source of `code/Windmill42ArtData.sol`
  - `main() -> None` writes the three generated files (paths from `REPO_ROOT`)
- **SVG format (fixed, shared with Task 4):** `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' shape-rendering='crispEdges'>` + for each palette index in ascending order that has runs: `<path fill='#rrggbb' d='` + for each of its runs `M{x} {y}h{len}v1h-{len}z` + `'/>` + `</svg>`. Single quotes only (so it embeds in JSON unescaped), no whitespace between elements, decimal numbers without padding.
- **Solidity data format:** `library Windmill42ArtData { uint256 internal constant SIZE = 64; bytes internal constant PALETTE = hex"…"; bytes internal constant RUNS = hex"…"; }` — `PALETTE` = 3 bytes per colour; `RUNS` = 4 bytes per run `[color, x, y, length]` in `encode_runs` order. File starts with `// SPDX-License-Identifier: MIT`, `pragma solidity ^0.8.35;` and a `// GENERATED by mint/art/generate_art.py — do not edit by hand.` comment.

- [ ] **Step 1: Write the failing tests** (`mint/tests/test_art.py`)

```python
def test_canvas_is_64_by_64(): p = build_pixels(); assert len(p) == 64 and all(len(r) == 64 for r in p)
def test_palette_has_at_most_16_colours(): assert 2 <= len(PALETTE) <= 16 and all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in PALETTE)
def test_every_pixel_uses_the_palette(): assert {i for r in build_pixels() for i in r} <= set(range(len(PALETTE)))
def test_42_glyph_is_drawn_large(): # GLYPH_42 is ≥ 30 wide and ≥ 18 tall, and every '#' cell of it is painted in the cloud-white index at its placement offset
def test_runs_cover_every_pixel_exactly_once(): # expand encode_runs back into a grid == build_pixels()
def test_run_count_fits_contract_budget(): assert len(encode_runs(build_pixels())) <= 2000
def test_svg_format(): s = to_svg(build_pixels(), PALETTE); assert s.startswith("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' shape-rendering='crispEdges'>") and s.endswith("</svg>") and '"' not in s
def test_png_is_1024_and_matches_pixels(tmp_path): # to_png → 1024×1024; centre of each 16×16 block equals PALETTE[pixels[y][x]]
def test_generated_files_are_up_to_date(): # running the generators in memory reproduces the committed windmill42.svg and Windmill42ArtData.sol byte-for-byte
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm tokenizeart pytest mint/tests/test_art.py -q`
Expected: FAIL (`ModuleNotFoundError: art.generate_art`).

- [ ] **Step 3: Bake the "42" glyph.** On the host (it has DejaVu Sans Bold), run the draft's `text42` render (size 28, threshold 110) and paste the resulting rows into `GLYPH_42`, so the generator needs no system font.

- [ ] **Step 4: Implement `generate_art.py`.** Start from the draft's `design_a()` composition (sky bands, sun, cloud "42" with a shade row under it, small clouds, far hill + windmill, mid hill, meadow, two round trees, two pines, rabbit, fox, butterfly, two birds, wildflowers). Work with palette indices, not hex strings. Polish: cleaner windmill cap and sails, more readable rabbit/fox, flower variety. Keep the "42" at least as large as the draft. Suggested 16-colour palette (merge the draft's 33): sky top `#5ba8f0`, sky mid `#78bbf4`, sky low `#9acff8`, white `#ffffff`, cloud shade `#c4ddf0`, sun `#ffd93b`, pale yellow `#fff3a0`, far hill `#8fd16f`, mid hill/light leaf `#5db34f`, meadow `#47993f`, leaf `#2f7d32`, dark pine `#1f6b3a`, wood `#7a4a22`, cream `#f4e3c1`, red-orange (roof + fox) `#e0582f`, pink `#ff6fa5`. Use a seeded RNG for flowers so the output is deterministic.

- [ ] **Step 5: Generate, then run the tests**

Run: `docker compose run --rm tokenizeart python mint/art/generate_art.py && docker compose run --rm tokenizeart pytest mint/tests/test_art.py -q`
Expected: 9 PASS; the three generated files exist.

- [ ] **Step 6: USER CHECKPOINT — art approval.** Show the user `mint/art/windmill42.png` (and the draft for comparison). Iterate on Step 4 until they approve. Do not continue to Task 3 before approval.

- [ ] **Step 7: Commit** — `ADD: Windmill42 artwork and generator`

---

### Task 3: Compiler helper and contract core (mint, cap, ownership)

**Files:**
- Create: `deployment/compiler.py`, `code/Windmill42.sol`, `code/tests/test_windmill42.py`
- Modify: `conftest.py` (add contract fixtures)

**Interfaces:**
- Consumes: `code/Windmill42ArtData.sol` exists (Task 2) — not used by the contract yet.
- Produces in `compiler.py`:
  - `SOLC_VERSION = "0.8.35"`, `EVM_VERSION = "cancun"`, `CONTRACT_NAME = "Windmill42"`, `CONTRACT_PATH = REPO_ROOT / "code/Windmill42.sol"`
  - `@dataclass(frozen=True) class CompiledContract: abi: list[dict[str, Any]]; bytecode: str; runtime_bytecode: str`
  - `class CompileError(Exception)`
  - `compile_windmill42(contract_path: Path = CONTRACT_PATH) -> CompiledContract` — `solcx.compile_files` with OpenZeppelin remapping `@openzeppelin/=<deployment/node_modules>/@openzeppelin/`, `allow_paths` = code dir + node_modules, `optimize=True`, `optimize_runs=200`, `evm_version=EVM_VERSION`, outputs `abi`, `bin`, `bin-runtime`. **Select the output key that ends with `:Windmill42`** (never `popitem()`); raise `CompileError` with solc's message on failure or if not exactly one match.
- Produces in `code/Windmill42.sol` (this task's part):
  - `contract Windmill42 is ERC721, Ownable`
  - `uint256 public constant MAX_SUPPLY = 42;` `string public constant ARTIST = "flverge";` `string public constant TITLE = "Spring Meadow";`
  - `string public imageURI;` (set once in the constructor, no setter) and `uint256 public totalMinted;`
  - `error MaxSupplyReached(); error EmptyImageURI();`
  - `constructor(string memory imageURI_) ERC721("Windmill42", "WM42") Ownable(msg.sender)` — reverts `EmptyImageURI` on `""`
  - `function mint(address to) external onlyOwner returns (uint256 tokenId)` — next ID = `totalMinted + 1`, reverts `MaxSupplyReached` past 42, uses `_safeMint`
  - NatSpec comment on every non-inherited item (code-review line of the sheet)
- Produces fixtures in `conftest.py`: `compiled() -> CompiledContract` (session-scoped), `TEST_IMAGE_URI = "ipfs://bafytestwindmill42"`, `windmill(w3, compiled) -> Contract` (deployed from `w3.eth.accounts[0]` with `TEST_IMAGE_URI`).

- [ ] **Step 1: Write the failing tests** (`code/tests/test_windmill42.py`)

```python
def test_compiles_and_selects_windmill42(compiled): assert any(e.get("name") == "mint" for e in compiled.abi)
def test_name_symbol_and_constants(windmill): assert (windmill.functions.name().call(), windmill.functions.symbol().call(), windmill.functions.MAX_SUPPLY().call(), windmill.functions.ARTIST().call(), windmill.functions.imageURI().call()) == ("Windmill42", "WM42", 42, "flverge", TEST_IMAGE_URI)
def test_deployer_is_owner(w3, windmill): assert windmill.functions.owner().call() == w3.eth.accounts[0]
def test_owner_mints_ids_from_one(w3, windmill): # two mints to accounts[1] → ownerOf(1) == ownerOf(2) == accounts[1], totalMinted() == 2
def test_non_owner_cannot_mint(w3, windmill): # transact from accounts[1] raises; decoded error name == "OwnableUnauthorizedAccount"
def test_supply_is_capped_at_42(w3, windmill): # 42 mints succeed; 43rd raises MaxSupplyReached; totalMinted() == 42
def test_empty_image_uri_rejected(w3, compiled): # constructor("") raises EmptyImageURI
def test_transfer_changes_owner(w3, windmill): # mint to accounts[0]; transferFrom(accounts[0], accounts[2], 1); ownerOf(1) == accounts[2]
def test_unknown_contract_path_raises_compile_error(tmp_path): # compile_windmill42(tmp_path / "missing.sol") raises CompileError
```

Decode custom errors in tests by matching the 4-byte selector of each ABI `error` entry against the revert data (a helper in `conftest.py`, `revert_name(exc, abi) -> str`, reused by Task 7's `decode_revert`).

- [ ] **Step 2: Run to verify failure**

Run: `docker compose run --rm tokenizeart pytest code/tests -q`
Expected: FAIL (`ModuleNotFoundError: compiler`).

- [ ] **Step 3: Implement `compiler.py` and the contract core** per the Interfaces above.

- [ ] **Step 4: Run tests**

Run: `docker compose run --rm tokenizeart pytest code/tests -q`
Expected: 9 PASS.

- [ ] **Step 5: Commit** — `ADD: Windmill42 contract core and compiler helper`

---

### Task 4: On-chain SVG and on-chain metadata (`tokenURI`)

**Files:**
- Create: `code/Windmill42Art.sol`
- Modify: `code/Windmill42.sol`, `code/tests/test_windmill42.py`

**Interfaces:**
- Consumes: `Windmill42ArtData.PALETTE`, `.RUNS`, `.SIZE` (Task 2); the SVG format in Task 2.
- Produces:
  - `library Windmill42Art { function svg() internal pure returns (string memory); }` — **linear**: allocate one `bytes` buffer of a safe upper bound (header + footer + 16 path wrappers + `RUNS.length / 4` × 22 bytes), write into it with a cursor, then shrink its length with assembly. No `string.concat`/`abi.encodePacked` inside loops (quadratic gas). Helpers: write a decimal 0–64, write a colour as 6 lowercase hex digits.
  - `Windmill42.svgImage() public pure returns (string memory)` → `Windmill42Art.svg()`
  - `Windmill42.tokenURI(uint256 tokenId) public view override returns (string memory)` — `_requireOwned(tokenId)` first (reverts `ERC721NonexistentToken`); returns `"data:application/json;base64," + Base64.encode(json)` (OpenZeppelin `Base64`, `Strings`). JSON, exact keys and order:
    ```json
    {"name":"Windmill42 #<id>","description":"Spring Meadow by flverge: 64x64 pixel art of a windmill meadow with a cloud-drawn 42. Edition <id> of 42. The image is pinned on IPFS and also stored on-chain.","image":"<imageURI>","image_data":"<svgImage()>","attributes":[{"trait_type":"Artist","value":"flverge"},{"trait_type":"Title","value":"Spring Meadow"},{"trait_type":"Edition","value":"<id>/42"}],"artist":"flverge"}
    ```

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_svg_matches_committed_svg_byte_for_byte(windmill): assert windmill.functions.svgImage().call() == (REPO_ROOT / "mint/art/windmill42.svg").read_text()
def test_token_uri_is_onchain_json(w3, windmill): # mint 1; decode base64 → dict with name "Windmill42 #1", image TEST_IMAGE_URI, image_data == svgImage(), attributes include Artist=flverge, Title=Spring Meadow, Edition=1/42, artist "flverge"
def test_token_uri_name_contains_42(w3, windmill): # minted token 7 → name "Windmill42 #7" and "42" in name
def test_token_uri_unknown_token_reverts(windmill): # tokenURI(1) before minting → ERC721NonexistentToken
def test_runtime_bytecode_under_eip170(compiled): assert len(bytes.fromhex(compiled.runtime_bytecode)) < 24_576
def test_view_calls_are_cheap(w3, windmill): # estimate_gas of svgImage() < 15_000_000 and of tokenURI(1) (after a mint) < 20_000_000
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose run --rm tokenizeart pytest code/tests -q`
Expected: the 6 new tests FAIL (`svgImage` missing from the ABI).

- [ ] **Step 3: Implement `Windmill42Art.sol`, `svgImage()` and `tokenURI()`.**

- [ ] **Step 4: Run the whole suite**

Run: `docker compose run --rm tokenizeart pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit** — `ADD: on-chain SVG and on-chain metadata`

---

### Task 5: IPFS pinning script

**Files:**
- Create: `mint/pin_to_ipfs.py`, `mint/tests/test_pin.py`
- Generated by the user later (committed): `mint/ipfs.json`

**Interfaces:**
- Produces in `pin_to_ipfs.py`:
  - `PINATA_UPLOAD_URL = "https://uploads.pinata.cloud/v3/files"` — **check the current Pinata docs** (docs.pinata.cloud) for the public-file upload endpoint and response shape before coding; if it differs, use the current one and update the tests to match. Auth header `Authorization: Bearer <PINATA_JWT>`; multipart fields `file`, `network=public`, `name=windmill42.png`.
  - `class PinError(Exception)`
  - `pin_file(path: Path, jwt: str, timeout: float = 60) -> str` — returns the CID; `PinError` on empty JWT, missing file, HTTP ≠ 2xx (include status code, and "check PINATA_JWT" for 401/403), network errors, or a response without a CID.
  - `write_record(cid: str, png_path: Path, out: Path) -> dict[str, str]` — writes `mint/ipfs.json`: `{"file": "mint/art/windmill42.png", "sha256": <hex of the PNG>, "cid": cid, "imageURI": "ipfs://<cid>", "gatewayURL": "https://<PINATA_GATEWAY or gateway.pinata.cloud>/ipfs/<cid>"}` (signature gains `gateway: str = "gateway.pinata.cloud"`; `main()` passes `PINATA_GATEWAY` when set)
  - `main() -> None` — loads `.env`, pins `mint/art/windmill42.png`, writes the record, prints CID + gateway link. Rich console output, no traceback.

- [ ] **Step 1: Write the failing tests** (monkeypatch `requests.post`; never call the network)

```python
def test_pin_returns_cid(monkeypatch, tmp_path): # fake 200 response with the documented CID field → returns "bafyfake"
def test_pin_sends_bearer_jwt(monkeypatch, tmp_path): # captured headers["Authorization"] == "Bearer jwt123"
def test_pin_unauthorized(monkeypatch, tmp_path): # 401 → PinError mentioning "PINATA_JWT"
def test_pin_network_error(monkeypatch, tmp_path): # requests.ConnectionError → PinError
def test_pin_empty_jwt(tmp_path): # pin_file(path, "") → PinError without any HTTP call
def test_record_contents(tmp_path): # write_record → JSON with imageURI "ipfs://bafyfake" and sha256 of the file
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm tokenizeart pytest mint/tests/test_pin.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** per the Interfaces.
- [ ] **Step 4: Run** — same command → 6 PASS.
- [ ] **Step 5: Commit** — `ADD: IPFS pinning script`

---

### Task 6: Deployment script

**Files:**
- Create: `deployment/deploy.py`, `deployment/tests/test_deploy.py`

**Interfaces:**
- Consumes: `compile_windmill42()`, `CompiledContract`, `CompileError` (Task 3); `mint/ipfs.json` format (Task 5).
- Produces in `deploy.py`:
  - `class DeployError(Exception)`
  - `@dataclass(frozen=True) class Settings: rpc_url: str; private_key: str; image_uri: str`
  - `load_settings(env: Mapping[str, str], ipfs_record_path: Path, png_path: Path) -> Settings` — `DeployError` when: `SEPOLIA_RPC_URL` missing/not `http(s)://`; `PRIVATE_KEY` missing or not 64 hex chars (with or without `0x`, surrounding whitespace stripped); `ipfs.json` missing ("run mint/pin_to_ipfs.py first"); its `sha256` ≠ the PNG's ("artwork changed since it was pinned: re-run mint/pin_to_ipfs.py"); `imageURI` not starting with `ipfs://`.
  - `connect(rpc_url: str, expected_chain_id: int = 11155111) -> Web3` — `DeployError` if unreachable or wrong chain.
  - `@dataclass(frozen=True) class DeploymentResult: address: str; tx_hash: str; block_number: int; gas_used: int; deployer: str; chain_id: int`
  - `estimate_cost_wei(w3, account, compiled, image_uri) -> int` and `deploy_contract(w3, account, compiled, image_uri) -> DeploymentResult` — signing via `SignAndSendRawMiddlewareBuilder` like tokenizer; `DeployError` "Not enough Sepolia ETH: need ~X ETH, have Y ETH" when the balance is below the estimate.
  - `write_artifacts(result, compiled, image_uri, artifact_path: Path, website_config_path: Path) -> None` — `deployment/artifacts/Windmill42.json`: `{"contract": "Windmill42", "network": "sepolia", "chainId", "address", "txHash", "blockNumber", "deployer", "imageURI", "abi"}`; `mint/website/config.json`: `{"address", "chainId", "abi", "imageGatewayURL"}` (`imageGatewayURL` copied from `ipfs.json` `gatewayURL`). Never touches `deployment/permanent.json`.
  - `main(argv: list[str] | None = None) -> int` — numbered steps `[1/7] Loading configuration … ✓` (config → connect, show deployer + balance → solc check → compile → estimate cost, ask `Deploy Windmill42 to Sepolia? [y/N]` unless `--yes` → deploy, wait → write artifacts, print address, tx, block, gas, `https://sepolia.etherscan.io/address/<addr>`, then ask `Save CONTRACT_ADDRESS to .env? [Y/n]` using `dotenv.set_key(..., quote_mode="never")`). Catches `DeployError`, `CompileError`, any other `Exception` → `✗ <message>` and return 1; `KeyboardInterrupt` → `Interrupted.` and return 130. `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Step 1: Write the failing tests**

```python
def test_settings_ok(tmp_path): # valid env + matching ipfs.json → Settings with image_uri "ipfs://bafyfake"
@pytest.mark.parametrize("key", ["", "abc", "0x" + "g" * 64, "1" * 63])
def test_settings_reject_bad_private_key(tmp_path, key): # DeployError
def test_settings_accept_key_without_0x_and_with_spaces(tmp_path): # "  " + "a"*64 + " " → ok
def test_settings_reject_missing_ipfs_record(tmp_path): # DeployError mentioning "pin_to_ipfs.py"
def test_settings_reject_stale_ipfs_record(tmp_path): # sha mismatch → DeployError mentioning "re-run"
def test_connect_unreachable_rpc(): # connect("http://127.0.0.1:9") → DeployError
def test_deploy_on_tester_chain(w3, funded_account, compiled): # deploy_contract → address has code; owner() == funded_account.address
def test_deploy_insufficient_funds(w3, unfunded_account, compiled): # DeployError containing "Not enough Sepolia ETH"
def test_write_artifacts(tmp_path, ...): # both JSON files written with the documented keys; permanent.json untouched
def test_main_returns_1_without_traceback(monkeypatch, capsys, tmp_path): # empty env → return 1, stdout has "✗", no "Traceback"
```

`connect` is tested only for the error path; `test_deploy_on_tester_chain` passes the tester `w3` straight into `deploy_contract`.

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm tokenizeart pytest deployment/tests/test_deploy.py -q` → FAIL.
- [ ] **Step 3: Implement** per the Interfaces; reuse tokenizer's `ContractState.deploy_contract` logic (read-only reference `../tokenizer/deployment/contract_uploader.py`).
- [ ] **Step 4: Run** — full suite `pytest -q` → all PASS.
- [ ] **Step 5: Commit** — `ADD: deployment script`

---

### Task 7: Mint client library (web3 wrapper, metadata, image decoding)

**Files:**
- Create: `mint/nft_client.py`, `mint/metadata.py`, `mint/svg_pixels.py`, `mint/terminal_image.py`, `mint/tests/test_client.py`

**Interfaces:**
- Consumes: deployed contract ABI (from `compiled` fixture in tests, from `deployment/artifacts/Windmill42.json` at runtime); `TEST_IMAGE_URI`, `windmill` fixtures.
- Produces:
  - `metadata.decode_token_uri(uri: str) -> dict[str, Any]` — requires prefix `data:application/json;base64,`; `ValueError` otherwise or on bad base64/JSON.
  - `svg_pixels.svg_to_grid(svg: str, size: int = 64) -> list[list[str]]` — parses the Task 2 SVG format (one regex for `<path fill='#…' d='…'/>`, one for `M{x} {y}h{n}v1h-{n}z`); `ValueError` if malformed or any pixel is left uncovered.
  - `terminal_image.grid_to_text(grid: list[list[str]]) -> rich.text.Text` — 32 lines × 64 chars of `"▀"`, style `"<top> on <bottom>"`.
  - `terminal_image.png_to_grid(png: bytes, size: int = 64) -> list[list[str]]` — samples the centre of each block of the 1024×1024 PNG.
  - `nft_client`:
    - `class ClientError(Exception)`
    - `@dataclass(frozen=True) class ContractInfo: address: str; name: str; symbol: str; owner: str; total_minted: int; max_supply: int; image_uri: str`
    - `@dataclass(frozen=True) class TxResult: tx_hash: str; token_id: int | None`
    - `decode_revert(error: Exception, abi: list[dict[str, Any]]) -> str` — custom-error name from the selector, else a short text.
    - `FRIENDLY_ERRORS: dict[str, str]` — `OwnableUnauthorizedAccount` → "Only the contract owner can mint."; `MaxSupplyReached` → "All 42 Windmill42 tokens are already minted."; `ERC721NonexistentToken` → "This token does not exist (yet)."; `ERC721IncorrectOwner` / `ERC721InsufficientApproval` → "Your wallet does not own this token."; `ERC721InvalidReceiver` → "This address cannot receive NFTs."; insufficient funds → "Not enough Sepolia ETH to pay for gas."
    - `class Windmill42Client:` `__init__(self, w3: Web3, address: str, abi: list[dict[str, Any]], account: LocalAccount | None = None)`; `info() -> ContractInfo`; `eth_balance() -> Decimal`; `mint(to: str | None = None) -> TxResult` (defaults to own wallet; token ID read from the `Transfer` event); `owner_of(token_id: int) -> str`; `token_uri(token_id: int) -> str`; `metadata(token_id: int) -> dict[str, Any]`; `svg_image() -> str`; `image_grid() -> list[list[str]]` (on-chain SVG → grid); `transfer(token_id: int, to: str) -> TxResult`; `simulate_non_owner_mint() -> str` (fresh random address, `eth_call` of `mint` from it, returns the friendly message of the revert — no gas, no signing). **Every public method raises only `ClientError`** (bad address → "Not a valid Ethereum address: …", write without account → "No PRIVATE_KEY configured: read-only mode.").

- [ ] **Step 1: Write the failing tests**

```python
def test_decode_token_uri_roundtrip(): # base64 of '{"a":1}' with the prefix → {"a": 1}
@pytest.mark.parametrize("bad", ["", "ipfs://x", "data:application/json;base64,!!!", "data:application/json;base64,bm90IGpzb24="])
def test_decode_token_uri_rejects(bad): # ValueError
def test_grid_to_text_shape(): # 32 lines, each 64 cells
def test_png_to_grid_matches_svg(): # png_to_grid(committed PNG bytes) == svg_to_grid(committed SVG)
def test_client_info(w3, windmill, compiled): # ContractInfo(name="Windmill42", symbol="WM42", max_supply=42, total_minted=0, image_uri=TEST_IMAGE_URI, owner=accounts[0])
def test_client_mint_and_owner(w3, windmill_local, funded_account): # client signs with funded_account (the owner); mint() → TxResult(token_id=1); owner_of(1) == funded_account.address
def test_client_metadata(...): # metadata(1)["name"] == "Windmill42 #1"
def test_client_image_grid_is_onchain_art(...): # image_grid() == svg_to_grid(committed SVG)
def test_simulate_non_owner_mint(...): assert client.simulate_non_owner_mint() == "Only the contract owner can mint."
def test_client_transfer(...): # transfer(1, accounts[3]) then owner_of(1) == accounts[3]
def test_client_unknown_token(...): # owner_of(5) → ClientError("This token does not exist (yet).")
def test_client_bad_address(...): # mint("0x123") → ClientError
def test_mint_insufficient_funds(...): # windmill_local.transferOwnership(unfunded_account) from funded_account; client signing with unfunded_account → mint() raises ClientError("Not enough Sepolia ETH to pay for gas.")
def test_client_unreachable_rpc(compiled): # Web3(HTTPProvider("http://127.0.0.1:9")) → info() raises ClientError
def test_read_only_client_cannot_mint(...): # account=None → ClientError mentioning "read-only"
```

Add a `conftest.py` fixture `windmill_local(w3, funded_account, compiled) -> Contract` that deploys via `deploy.deploy_contract(w3, funded_account, compiled, TEST_IMAGE_URI)` (owner = `funded_account`, a `LocalAccount` the client can sign with). In this task, make Task 3's `revert_name` test helper delegate to `nft_client.decode_revert` so there is one decoder.

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm tokenizeart pytest mint/tests/test_client.py -q` → FAIL.
- [ ] **Step 3: Implement the four modules** per the Interfaces.
- [ ] **Step 4: Run** — full suite → all PASS; `docker compose run --rm tokenizeart mypy deployment mint` → no errors.
- [ ] **Step 5: Commit** — `ADD: mint client library`

---

### Task 8: Mint TUI

**Files:**
- Create: `mint/mint_tui.py`, `mint/tests/test_tui.py`
- Reference (read-only): `../tokenizer/deployment/contract_uploader.py` (`build_layout`, input loop, copy helpers), `../tokenizer/deployment/wallet_manager.py` (`ensure_contract_address_env`, `load_contract_address`)

**Interfaces:**
- Consumes: everything in Task 7; `deployment/artifacts/Windmill42.json`.
- Produces in `mint_tui.py`:
  - `@dataclass class Session: client: Windmill42Client | None; info: ContractInfo | None = None; last_tx: str = ""; image: Text | None = None; image_title: str = ""; details: Text | None = None`
  - `parse_token_id(raw: str) -> int` — `ValueError("Token ID must be a whole number between 1 and 42.")` for anything else.
  - `resolve_contract(env: Mapping[str, str], artifact_path: Path) -> tuple[str, list[dict[str, Any]]]` — address from `CONTRACT_ADDRESS`, else from the artifact; ABI always from the artifact. Raises `ClientError` with a hint ("run deployment/deploy.py first") if neither exists.
  - `dispatch(command: str, session: Session, terminal_size: tuple[int, int]) -> str` — returns the Rich-markup status line; **never raises**. Commands (shown in the menu, same style as tokenizer):

    | Command | Action |
    |---|---|
    | `mint` / `mint <address>` | mint to own wallet / to address; refresh info; store tx |
    | `owner <id>` | `ownerOf`, and say "(that's you)" when it is the wallet |
    | `uri <id>` | show decoded metadata (name, artist, title, edition, image URI, `image_data` length) in the details panel |
    | `view` / `view <id>` | draw the **on-chain** image (`image_grid()`); with an id, check it exists first |
    | `ipfs` | download the IPFS PNG (`gatewayURL` from `mint/ipfs.json` when its CID matches `imageURI`, else `https://gateway.pinata.cloud/ipfs/<cid>`; 15 s timeout), draw it, and report "✓ IPFS image matches the on-chain image" or a mismatch |
    | `hack` | `simulate_non_owner_mint()` result |
    | `send <id> <address>` | transfer, then show new `ownerOf` |
    | `refresh` | reload info + balance |
    | `adr` / `tx` | copy contract address / last tx hash (tokenizer's clipboard + manual fallback) |
    | `q` / `quit` / `exit` | quit |

  - Image commands need the terminal to be at least 70 columns × 36 rows; otherwise return `"Terminal too small for the image: need 70x36, have WxH."`.
  - `build_layout(session, input_buffer, status, terminal_size) -> Layout` — info panel (address, name/symbol, owner, minted n/42, wallet + ETH balance, last tx), image/details panel, menu panel with input line.
  - `main() -> None` — loads `.env`; if no contract can be resolved, ask for the address like tokenizer's `ensure_contract_address_env` (save with `set_key`, quote_mode `"never"`); account from `PRIVATE_KEY` if valid, else read-only mode with a warning; start the Live loop. All startup errors → one message, exit 1. Ctrl-C/Ctrl-D quit cleanly.

- [ ] **Step 1: Write the failing tests** (use a real client on the tester chain via `windmill_local`, or a small fake client)

```python
@pytest.mark.parametrize("raw", ["", "abc", "-3", "0", "43", "99999999999999999999", "1.5"])
def test_parse_token_id_rejects(raw): # ValueError
@pytest.mark.parametrize("cmd", ["uri", "uri abc", "uri -3", "uri 0", "uri 43", "uri 99999999999999999999", "owner", "send 1", "send x y", "view 0", "mint 0x12"])
def test_dispatch_rejects_bad_token_ids(session, cmd): # returns a string, no exception, contains no "Traceback"
def test_dispatch_mint_then_owner(session): # "mint" → status mentions "#1"; "owner 1" → contains the wallet address and "that's you"
def test_dispatch_uri_shows_artist_and_name(session): # after mint, "uri 1" → session.details plain text contains "flverge" and "Windmill42 #1"
def test_dispatch_view_draws_onchain_image(session): # "view" with size (120, 50) → session.image has 32 lines
def test_view_terminal_too_small(session): # "view" with size (60, 20) → "Terminal too small" and session.image is None
def test_dispatch_hack(session): # contains "Only the contract owner can mint."
def test_dispatch_send(session): # mint, "send 1 <accounts[4]>" → status contains accounts[4]
def test_dispatch_unknown_command(session): # "dance" → "Unknown command"
def test_dispatch_survives_rpc_failure(): # Session with a client pointed at http://127.0.0.1:9 → "owner 1" returns an error status, no exception
def test_resolve_contract_prefers_env(tmp_path): # env CONTRACT_ADDRESS wins over the artifact address
def test_resolve_contract_missing_everything(tmp_path): # ClientError mentioning "deploy.py"
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm tokenizeart pytest mint/tests/test_tui.py -q` → FAIL.
- [ ] **Step 3: Implement `mint_tui.py`** per the Interfaces, keeping tokenizer's look (cyan panels, yellow command keys, `→` status line, blinking cursor).
- [ ] **Step 4: Run** — full suite → all PASS.
- [ ] **Step 5: Manual smoke** — with no `.env` and no `deployment/artifacts/Windmill42.json`, run `docker compose run --rm tokenizeart python mint/mint_tui.py` → it asks for a contract address; Ctrl-C → "Interrupted.", no traceback.
- [ ] **Step 6: Commit** — `ADD: mint TUI`

---

### Checkpoint A (USER): first real run on Sepolia — verifies risk R1

Not a code task. The orchestrator walks the user through it and records the outcome in the plan:

1. User fills `.env` (`PRIVATE_KEY`, `PINATA_JWT`).
2. `docker compose run --rm tokenizeart python mint/pin_to_ipfs.py` → `mint/ipfs.json`; open the gateway URL, check the image.
3. `docker compose run --rm tokenizeart python deployment/deploy.py` → trial contract.
4. `docker compose run --rm tokenizeart python mint/mint_tui.py` → `mint`, `uri 1`, `view`, `ipfs`, `hack`.
5. In MetaMask (Sepolia) → NFTs → Import NFT (contract address, token ID 1). **Does the image and name show?** Also check `https://sepolia.etherscan.io/nft/<address>/1` and whether any testnet marketplace lists it.

**If MetaMask does NOT show it (R1 fallback):** add a task before Task 9: pin a metadata JSON (same fields, without `image_data`) on IPFS, make `tokenURI` return its `ipfs://` URI (constructor arg `metadataURI_`), and add `onChainTokenURI(uint256)` returning the current on-chain JSON. Update tests, TUI (`uri` shows both), website and docs accordingly.

Commit `mint/ipfs.json` (public data) — `ADD: pinned artwork record`.

---

### Task 9: Website (bonus)

**Files:**
- Create: `mint/website/index.html`, `mint/website/app.js`, `mint/website/style.css`
- Generated by `deploy.py`: `mint/website/config.json` (commit the latest one)

**Interfaces:**
- Consumes: `config.json` `{address, chainId, abi, imageGatewayURL}`; contract functions `name`, `symbol`, `owner`, `totalMinted`, `MAX_SUPPLY`, `imageURI`, `svgImage`, `mint`, `ownerOf`, `tokenURI`.
- Produces (`app.js`, plain ES2020, no bundler): `loadConfig()`, `connectWallet()`, `ensureSepolia()` (`wallet_switchEthereumChain` to `0xaa36a7`; on error 4902 `wallet_addEthereumChain` with the Sepolia params), `refreshInfo()`, `showArtwork()`, `mintToken()`, `lookupToken(id)`, `friendlyError(err) -> string` (same wording as `FRIENDLY_ERRORS` in Task 7; handles `err.revert?.name`, user rejection code `4001`/`ACTION_REJECTED`, missing MetaMask).
- ethers v6 UMD from cdnjs with an exact version and `integrity` + `crossorigin` attributes (pick a 6.x version cdnjs serves; verify the URL loads).

Page sections: header (title, connect button, account + network badge); **artwork** — on-chain SVG from `svgImage()` (labelled "Stored on-chain") next to the IPFS image from `imageGatewayURL` (labelled "Pinned on IPFS"), both with `image-rendering: pixelated`; collection info (address with Etherscan link, owner, minted n/42); **Mint** button (mints to the connected wallet, shows tx link, then refreshes); **Lookup** (token ID → owner + decoded metadata table). All reads go through MetaMask's provider after `connectWallet()` + `ensureSepolia()` (no RPC URL in the page or config); before connecting, show "Connect MetaMask to load the collection."; without MetaMask, show "Install MetaMask to use this page." Wrap every handler in `try/catch` → status area; validate token ID 1–42 before calling.

- [ ] **Step 1: Implement the three files.**
- [ ] **Step 2: Syntax check** — `docker compose run --rm tokenizeart node --check mint/website/app.js` → no output, exit 0.
- [ ] **Step 3: Serve** — `docker compose up website`, open `http://localhost:8042` in the browser pane; confirm the page loads, ethers loads, and with no wallet it shows the MetaMask message without console errors (`read_console_messages`).
- [ ] **Step 4: USER CHECKPOINT — MetaMask test** against the Checkpoint A contract: connect, switch network, both images visible, mint from the owner wallet, lookup token 1, reject a tx (message shown), try mint from a second MetaMask account (friendly "Only the contract owner can mint.").
- [ ] **Step 5: Commit** — `ADD: mint website`

---

### Task 10: README and documentation

**Files:**
- Create/replace: `README.md`; `documentation/1_technical_choices.md`, `2_environment_setup.md`, `3_artwork_and_ipfs.md`, `4_deployment_guide.md`, `5_minting_tui.md`, `6_website.md`, `7_contract_reference.md`, `8_security_model.md`, `9_defense_walkthrough.md`; test `deployment/tests/test_docs.py`
- Optional: screenshots in `documentation/img/` (no video)
- Reference (read-only): `../tokenizer/README.md`, `../tokenizer/documentation/*.md` (structure and tone)

Content requirements:
- `README.md`: logo/art image (`mint/art/windmill42.png`), synopsis, a **Deployment** box with network `Ethereum Sepolia (chainId 11155111)`, contract address, Etherscan link, minted token ID and owner (placeholders `TO_FILL` until Task 11); "See it in MetaMask" steps; **why Sepolia, why ERC-721, why Solidity + OpenZeppelin, why Python/web3.py (no Hardhat), why IPFS/Pinata, why IPFS + on-chain** (sheet: platform and language choices); folder map; quickstart (copy `.env.example`, build, pin, deploy, TUI, website); links to docs; author `flverge`; licence MIT (copy tokenizer's LICENSE).
- `3_artwork_and_ipfs.md`: generator, palette, how pinning works, CID, and an alternative public gateway (`https://ipfs.io/ipfs/<cid>`) if Pinata's is slow.
- `7_contract_reference.md`: one `### \`name\`` heading per public/external function, constant and custom error of `Windmill42` (own + inherited ERC721/Ownable), each with signature, who may call it, and what it does.
- `9_defense_walkthrough.md`: follows the evaluation sheet in order — preliminaries → show in MetaMask → metadata (`uri 1` / website lookup / Etherscan) → `owner 1` → README & docs → code tour → evaluator deploys (`deploy.py`) → evaluator mints (TUI and website) → `hack` + `send` security demo → bonuses (art, website, on-chain `view` / "Stored on-chain").

- [ ] **Step 1: Write the failing test** (`deployment/tests/test_docs.py`)

```python
def test_every_documented_function_exists(compiled): # every name in "### `name`" headings of 7_contract_reference.md is in the ABI (functions, errors) — and every ABI function is documented
def test_readme_mentions_network_and_choices(): # README contains "Sepolia", "ERC-721", "Solidity", "Python", "IPFS"
def test_required_folders_not_empty(): # code, deployment, mint, documentation each contain at least one tracked file
def test_no_video_files(): # no tracked *.mp4, *.mov, *.webm, *.avi, *.mkv
```

- [ ] **Step 2: Run to verify failure** — `pytest deployment/tests/test_docs.py -q` → FAIL.
- [ ] **Step 3: Write README and the nine docs.**
- [ ] **Step 4: Run the full suite** → all PASS.
- [ ] **Step 5: Commit** — `ADD: README and documentation`

---

### Task 11: Permanent deployment and final checks (USER + orchestrator)

**Files:**
- Create: `deployment/permanent.json`
- Modify: `README.md` (replace `TO_FILL`), `mint/website/config.json` (point at the permanent contract)

- [ ] **Step 1: USER** — `python deployment/deploy.py` (permanent contract), then TUI `mint` (token #1 to the user's wallet), MetaMask import of token #1.
- [ ] **Step 2: Record** — write `deployment/permanent.json` `{"network": "sepolia", "chainId": 11155111, "address", "txHash", "tokenId": 1, "owner"}` from the user's output; fill the README deployment box (address, Etherscan link, token #1, owner).
- [ ] **Step 3: Fresh-clone rehearsal** — `git clone` the repo into an empty temp folder, copy `.env` in, `docker compose build`, run `pytest -q`, `deploy.py --yes` is **not** run (costs ETH); run the TUI read-only against the permanent address: `owner 1`, `uri 1`, `view`.
- [ ] **Step 4: Secret scan** — `pytest deployment/tests/test_no_secrets.py -q` PASS, and review `git grep -nE "[0-9a-fA-F]{64}"` hits by hand (tx hashes and CIDs are fine; private keys are not).
- [ ] **Step 5: Commit** — `ADD: permanent deployment record` (do not push).
