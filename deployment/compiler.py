"""
Compile the Windmill42 smart contract with solc (through py-solc-x).

Used by the deployment script and by the tests, so what is tested is
exactly what gets deployed.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import solcx

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
NODE_MODULES = REPO_ROOT / "deployment/node_modules"

SOLC_VERSION = "0.8.35"
# Fixed EVM version: the local test chain and Sepolia both support it.
EVM_VERSION = "cancun"
CONTRACT_NAME = "Windmill42"
CONTRACT_PATH = CODE_DIR / "Windmill42.sol"


class CompileError(Exception):
    """The contract could not be compiled."""


@dataclass(frozen=True)
class CompiledContract:
    """What the deployment needs from the compiler."""

    # Application Binary Interface: how to call the contract's functions
    abi: list[dict[str, Any]]
    # EVM code sent with the deployment transaction (includes constructor)
    bytecode: str
    # EVM code stored on-chain after deployment (limited to 24 KB)
    runtime_bytecode: str


def ensure_solc() -> None:
    """Install solc SOLC_VERSION if it is missing (already in Docker)."""
    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    if SOLC_VERSION not in installed:
        solcx.install_solc(SOLC_VERSION)


def compile_windmill42(
    contract_path: Path = CONTRACT_PATH,
) -> CompiledContract:
    """
    Compile the contract file and return the Windmill42 contract.

    OpenZeppelin imports ("@openzeppelin/...") are resolved from the npm
    packages in deployment/node_modules.

    Raises:
        CompileError: if the file is missing, solc fails, or the output
        does not contain exactly one Windmill42 contract.
    """
    if not contract_path.is_file():
        raise CompileError(f"Contract file not found: {contract_path}")
    try:
        ensure_solc()
        output = solcx.compile_files(
            [str(contract_path)],
            output_values=["abi", "bin", "bin-runtime"],
            solc_version=SOLC_VERSION,
            evm_version=EVM_VERSION,
            optimize=True,
            optimize_runs=200,
            import_remappings={
                "@openzeppelin/": f"{NODE_MODULES}/@openzeppelin/"
            },
            allow_paths=[str(contract_path.parent), str(NODE_MODULES)],
        )
    except Exception as error:  # solc reports errors as exceptions
        raise CompileError(f"Compilation failed: {error}") from error

    # The output also holds every imported OpenZeppelin contract:
    # pick ours by name instead of relying on the output order.
    matches = [
        value
        for key, value in output.items()
        if key.endswith(f":{CONTRACT_NAME}")
    ]
    if len(matches) != 1:
        raise CompileError(
            f"Expected one {CONTRACT_NAME} contract, found {len(matches)}."
        )
    contract = matches[0]
    return CompiledContract(
        abi=contract["abi"],
        bytecode=contract["bin"],
        runtime_bytecode=contract["bin-runtime"],
    )
