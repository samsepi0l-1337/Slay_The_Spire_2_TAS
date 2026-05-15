from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_ROOT = ROOT / "native" / "sts2_tas_hook"

REQUIRED_HOOK_FILES = [
    HOOK_ROOT / "CMakeLists.txt",
    HOOK_ROOT / "README.md",
    HOOK_ROOT / "ipc_contract.md",
    HOOK_ROOT / "sts2_tas_hook.cpp",
]

REQUIRED_HOOK_TOKENS = [
    "Detours",
    "Present hook",
    "frame counter",
    "foreground window",
    "frame screenshot/hash",
    "passive-only",
    "no input hook",
    "no time hook",
    "session nonce",
    "target pid binding",
    "named pipe",
]


def test_native_sts2_tas_hook_scaffold_files_exist() -> None:
    missing_files = [path for path in REQUIRED_HOOK_FILES if not path.is_file()]
    assert not missing_files


def test_native_sts2_tas_hook_documents_required_contract_tokens() -> None:
    missing_files = [path for path in REQUIRED_HOOK_FILES if not path.is_file()]
    assert not missing_files

    combined = "\n".join(path.read_text(encoding="utf-8") for path in REQUIRED_HOOK_FILES)
    missing_tokens = [token for token in REQUIRED_HOOK_TOKENS if token not in combined]
    assert not missing_tokens
