from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

from .schema import StructuredGameState


class ReadOnlyMemoryReader(Protocol):
    def read_int32(self, address: int) -> int:
        ...  # pragma: no cover


@dataclass(frozen=True)
class MemoryAttachRequest:
    target_process: str
    pid: int
    platform_name: str

    def __post_init__(self) -> None:
        if not self.target_process:
            raise ValueError("target_process is required")
        if self.pid <= 0:
            raise ValueError("pid must be positive")
        if self.platform_name.casefold() != "windows":
            raise ValueError("memory attach is Windows-only")

    def access_mode(self) -> str:
        return "read-only"


@dataclass(frozen=True)
class MemorySignature:
    game_version: str
    branch: str
    binary_signature: str
    offsets: dict[str, int]

    def __post_init__(self) -> None:
        if not self.game_version or not self.branch:
            raise ValueError("game_version and branch are required")
        if not self.binary_signature:
            raise ValueError("binary_signature is required")
        if not self.offsets:
            raise ValueError("offsets are required")
        for name, offset in self.offsets.items():
            if not name:
                raise ValueError("offset names cannot be empty")
            if offset < 0:
                raise ValueError(f"offset must be non-negative: {name}")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.game_version, self.branch, self.binary_signature)


@dataclass(frozen=True)
class MemorySnapshot:
    game_version: str
    branch: str
    binary_signature: str
    state_payload: dict[str, Any]

    def validate_against(self, registry: "MemorySignatureRegistry") -> MemorySignature:
        return registry.resolve(self.game_version, self.branch, self.binary_signature)

    def to_structured_state(self, template: StructuredGameState, *, source_type: str = "memory") -> StructuredGameState:
        player_payload = self.state_payload.get("player", {})
        if not isinstance(player_payload, dict):
            raise ValueError("memory snapshot player payload must be an object")
        player_data = template.player.to_dict()
        resources = dict(player_data.get("character_resource", {}))
        resources.update(dict(player_payload.get("character_resource", {})))
        for key, value in player_payload.items():
            if key != "character_resource":
                player_data[key] = value
        player_data["character_resource"] = resources
        player = type(template.player).from_dict(player_data)
        return StructuredGameState(
            game_version=template.game_version,
            branch=template.branch,
            catalog_version=template.catalog_version,
            character=template.character,
            ascension=template.ascension,
            floor=template.floor,
            decision_context=source_type,
            player=player,
            cards=template.cards,
            relics=template.relics,
            potions=template.potions,
            monsters=template.monsters,
            path_candidates=template.path_candidates,
            shop_items=template.shop_items,
            event_options=template.event_options,
            rest_options=template.rest_options,
        )


@dataclass(frozen=True)
class MemoryCrossCheckResult:
    usable: bool
    mismatches: dict[str, tuple[object, object]]


class MemorySignatureRegistry:
    def __init__(self, signatures: list[MemorySignature]) -> None:
        self._signatures = {signature.key: signature for signature in signatures}

    def resolve(self, game_version: str, branch: str, binary_signature: str) -> MemorySignature:
        key = (game_version, branch, binary_signature)
        try:
            return self._signatures[key]
        except KeyError as error:
            raise ValueError("unsupported memory signature") from error


class WindowsReadOnlyProcessMemoryReader:  # pragma: no cover
    def __init__(self, pid: int) -> None:
        import ctypes
        import platform

        if platform.system().casefold() != "windows":
            raise ValueError("WindowsReadOnlyProcessMemoryReader is Windows-only")
        self._ctypes = ctypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process_vm_read = 0x0010
        process_query_limited_information = 0x1000
        self._handle = self._kernel32.OpenProcess(process_vm_read | process_query_limited_information, False, int(pid))
        if not self._handle:
            raise OSError(ctypes.get_last_error(), "OpenProcess failed")

    def read_int32(self, address: int) -> int:
        buffer = self._ctypes.c_int32()
        read = self._ctypes.c_size_t()
        ok = self._kernel32.ReadProcessMemory(
            self._handle,
            self._ctypes.c_void_p(address),
            self._ctypes.byref(buffer),
            self._ctypes.sizeof(buffer),
            self._ctypes.byref(read),
        )
        if not ok or read.value != self._ctypes.sizeof(buffer):
            raise OSError(self._ctypes.get_last_error(), f"ReadProcessMemory failed at {address}")
        return int(buffer.value)

    def close(self) -> None:
        self._kernel32.CloseHandle(self._handle)


def memory_snapshot_from_reader(
    *,
    request: MemoryAttachRequest,
    registry: MemorySignatureRegistry,
    game_version: str,
    branch: str,
    binary_signature: str,
    reader: ReadOnlyMemoryReader,
) -> MemorySnapshot:
    if request.access_mode() != "read-only":
        raise ValueError("memory snapshot requires read-only access")
    signature = registry.resolve(game_version, branch, binary_signature)
    state_payload: dict[str, Any] = {}
    for field, address in signature.offsets.items():
        _set_nested_value(state_payload, field, reader.read_int32(address))
    return MemorySnapshot(
        game_version=game_version,
        branch=branch,
        binary_signature=binary_signature,
        state_payload=state_payload,
    )


def load_memory_signature_registry(path: Path) -> MemorySignatureRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("memory registry must be an object")
    signatures = payload.get("signatures")
    if not isinstance(signatures, list):
        raise ValueError("memory registry signatures must be a list")
    return MemorySignatureRegistry(
        [
            MemorySignature(
                game_version=str(item["game_version"]),
                branch=str(item["branch"]),
                binary_signature=str(item["binary_signature"]),
                offsets={str(key): int(value) for key, value in dict(item["offsets"]).items()},
            )
            for item in signatures
        ]
    )


def load_memory_snapshot(path: Path) -> MemorySnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("memory snapshot must be an object")
    state_payload = payload.get("state_payload")
    if not isinstance(state_payload, dict):
        raise ValueError("memory snapshot state_payload must be an object")
    return MemorySnapshot(
        game_version=str(payload["game_version"]),
        branch=str(payload["branch"]),
        binary_signature=str(payload["binary_signature"]),
        state_payload=state_payload,
    )


def cross_check_memory_state(
    *,
    ocr_payload: dict[str, Any],
    memory_payload: dict[str, Any],
    critical_fields: list[str],
) -> MemoryCrossCheckResult:
    mismatches: dict[str, tuple[object, object]] = {}
    for field in critical_fields:
        ocr_value = _nested_value(ocr_payload, field)
        memory_value = _nested_value(memory_payload, field)
        if ocr_value != memory_value:
            mismatches[field] = (ocr_value, memory_value)
    return MemoryCrossCheckResult(usable=not mismatches, mismatches=mismatches)


def _nested_value(payload: dict[str, Any], field: str) -> object:
    current: object = payload
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(payload: dict[str, Any], field: str, value: object) -> None:
    parts = field.split(".")
    current = payload
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise ValueError(f"memory field path collides with scalar: {field}")
        current = child
    current[parts[-1]] = value
