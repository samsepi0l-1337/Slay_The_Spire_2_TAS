from __future__ import annotations

import inspect

import pytest

from sts2_tas.memory_play import (
    MemoryAttachRequest,
    MemorySignature,
    MemorySignatureRegistry,
    MemorySnapshot,
    ProcessIdentity,
    cross_check_memory_state,
    load_memory_signature_registry,
    load_memory_snapshot,
    memory_snapshot_from_reader,
)
from sts2_tas.schema import PlayerState, StructuredGameState
import sts2_tas.memory_play as memory_play


def _template_state() -> StructuredGameState:
    return StructuredGameState(
        game_version="0.105.1",
        branch="beta",
        catalog_version="0.105.1:beta",
        character="ironclad",
        ascension=0,
        floor=1,
        decision_context="combat",
        player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
    )


def test_memory_attach_boundary_is_windows_read_only() -> None:
    request = MemoryAttachRequest(target_process="SlayTheSpire2", pid=100, platform_name="Windows")

    assert request.access_mode() == "read-only"
    with pytest.raises(ValueError, match="target_process"):
        MemoryAttachRequest(target_process="", pid=100, platform_name="Windows")
    with pytest.raises(ValueError, match="Windows-only"):
        MemoryAttachRequest(target_process="SlayTheSpire2", pid=100, platform_name="Darwin")
    with pytest.raises(ValueError, match="pid"):
        MemoryAttachRequest(target_process="SlayTheSpire2", pid=0, platform_name="Windows")


def test_memory_signature_registry_validates_supported_version() -> None:
    signature = MemorySignature(
        game_version="0.105.1",
        branch="beta",
        binary_signature="sha256:abc",
        offsets={"player.hp": 10},
    )
    registry = MemorySignatureRegistry([signature])

    assert registry.resolve("0.105.1", "beta", "sha256:abc") == signature
    with pytest.raises(ValueError, match="unsupported"):
        registry.resolve("0.106.0", "beta", "sha256:abc")
    with pytest.raises(ValueError, match="game_version"):
        MemorySignature(game_version="", branch="beta", binary_signature="sha256:abc", offsets={"player.hp": 10})
    with pytest.raises(ValueError, match="binary_signature"):
        MemorySignature(game_version="0.105.1", branch="beta", binary_signature="", offsets={"player.hp": 10})
    with pytest.raises(ValueError, match="offsets"):
        MemorySignature(game_version="0.105.1", branch="beta", binary_signature="sha256:abc", offsets={})
    with pytest.raises(ValueError, match="offset names"):
        MemorySignature(game_version="0.105.1", branch="beta", binary_signature="sha256:abc", offsets={"": 0})
    with pytest.raises(ValueError, match="offset"):
        MemorySignature(game_version="0.105.1", branch="beta", binary_signature="sha256:abc", offsets={"bad": -1})


def test_memory_snapshot_maps_to_structured_state_and_cross_checks_ocr() -> None:
    snapshot = MemorySnapshot(
        game_version="0.105.1",
        branch="beta",
        binary_signature="sha256:abc",
        state_payload={"player": {"hp": 65, "energy": 2, "character_resource": {"gold": 99}}},
        target_pid=1234,
        target_process="SlayTheSpire2",
    )

    state = snapshot.to_structured_state(_template_state(), source_type="memory_cross_checked")
    resolved = snapshot.validate_against(
        MemorySignatureRegistry(
            [
                MemorySignature(
                    game_version="0.105.1",
                    branch="beta",
                    binary_signature="sha256:abc",
                    offsets={"player.hp": 10},
                )
            ]
        )
    )
    ok = cross_check_memory_state(
        ocr_payload={"player": {"hp": 65, "energy": 2}},
        memory_payload=snapshot.state_payload,
        critical_fields=["player.hp", "player.energy"],
    )
    mismatch = cross_check_memory_state(
        ocr_payload={"player": {"hp": 66}},
        memory_payload=snapshot.state_payload,
        critical_fields=["player.hp"],
    )
    missing = cross_check_memory_state(
        ocr_payload={"player": {"hp": 65}},
        memory_payload={"player": {"block": 5}},
        critical_fields=["player.block"],
    )

    assert resolved.binary_signature == "sha256:abc"
    assert state.decision_context == "memory_cross_checked"
    assert state.player.hp == 65
    assert state.player.energy == 2
    assert state.player.character_resource["gold"] == 99
    assert ok.usable is True
    assert mismatch.usable is False
    assert mismatch.mismatches == {"player.hp": (66, 65)}
    assert missing.usable is False
    assert missing.mismatches == {"player.block": (None, 5)}


def test_memory_snapshot_from_reader_builds_nested_read_only_payload() -> None:
    class Reader:
        def process_identity(self) -> ProcessIdentity:
            return ProcessIdentity(pid=1234, process_name="SlayTheSpire2", executable_path=None, binary_signature="sha256:abc")

        def read_int32(self, address: int) -> int:
            values = {16: 70, 24: 3}
            return values[address]

    request = MemoryAttachRequest(target_process="SlayTheSpire2", pid=1234, platform_name="Windows")
    registry = MemorySignatureRegistry(
        [
            MemorySignature(
                game_version="0.105.1",
                branch="beta",
                binary_signature="sha256:abc",
                offsets={"player.hp": 16, "player.energy": 24},
            )
        ]
    )

    snapshot = memory_snapshot_from_reader(
        request=request,
        registry=registry,
        game_version="0.105.1",
        branch="beta",
        binary_signature="sha256:abc",
        reader=Reader(),
    )

    assert snapshot.state_payload == {"player": {"hp": 70, "energy": 3}}
    assert snapshot.target_pid == 1234
    assert snapshot.target_process == "SlayTheSpire2"


def test_memory_snapshot_from_reader_rejects_non_read_only_and_colliding_paths() -> None:
    class Reader:
        def process_identity(self) -> ProcessIdentity:
            return ProcessIdentity(pid=1234, process_name="SlayTheSpire2", executable_path=None, binary_signature="sha256:abc")

        def read_int32(self, address: int) -> int:
            return address

    class WriteRequest:
        def access_mode(self) -> str:
            return "write"

    registry = MemorySignatureRegistry(
        [
            MemorySignature(
                game_version="0.105.1",
                branch="beta",
                binary_signature="sha256:abc",
                offsets={"player": 16, "player.hp": 24},
            )
        ]
    )

    with pytest.raises(ValueError, match="read-only"):
        memory_snapshot_from_reader(
            request=WriteRequest(),  # type: ignore[arg-type]
            registry=registry,
            game_version="0.105.1",
            branch="beta",
            binary_signature="sha256:abc",
            reader=Reader(),
        )


def test_memory_snapshot_from_reader_rejects_process_identity_mismatch() -> None:
    class WrongProcessReader:
        def process_identity(self) -> ProcessIdentity:
            return ProcessIdentity(pid=999, process_name="OtherProcess", executable_path=None, binary_signature="sha256:abc")

        def read_int32(self, address: int) -> int:  # pragma: no cover
            raise AssertionError("memory must not be read after identity mismatch")

    class WrongSignatureReader:
        def process_identity(self) -> ProcessIdentity:
            return ProcessIdentity(pid=1234, process_name="SlayTheSpire2", executable_path=None, binary_signature="sha256:other")

        def read_int32(self, address: int) -> int:  # pragma: no cover
            raise AssertionError("memory must not be read after signature mismatch")

    request = MemoryAttachRequest(target_process="SlayTheSpire2", pid=1234, platform_name="Windows")
    registry = MemorySignatureRegistry(
        [MemorySignature(game_version="0.105.1", branch="beta", binary_signature="sha256:abc", offsets={"player.hp": 16})]
    )

    with pytest.raises(ValueError, match="process identity"):
        memory_snapshot_from_reader(
            request=request,
            registry=registry,
            game_version="0.105.1",
            branch="beta",
            binary_signature="sha256:abc",
            reader=WrongProcessReader(),
        )
    with pytest.raises(ValueError, match="binary signature"):
        memory_snapshot_from_reader(
            request=request,
            registry=registry,
            game_version="0.105.1",
            branch="beta",
            binary_signature="sha256:abc",
            reader=WrongSignatureReader(),
        )
    with pytest.raises(ValueError, match="collides"):
        memory_snapshot_from_reader(
            request=MemoryAttachRequest(target_process="SlayTheSpire2", pid=1234, platform_name="Windows"),
            registry=registry,
            game_version="0.105.1",
            branch="beta",
            binary_signature="sha256:abc",
            reader=Reader(),
        )


def test_memory_snapshot_rejects_non_object_player_payload() -> None:
    snapshot = MemorySnapshot(
        game_version="0.105.1",
        branch="beta",
        binary_signature="sha256:abc",
        state_payload={"player": "bad"},
        target_pid=1234,
        target_process="SlayTheSpire2",
    )

    with pytest.raises(ValueError, match="player payload"):
        snapshot.to_structured_state(_template_state())


def test_memory_reader_module_has_no_mutation_api_tokens() -> None:
    source = inspect.getsource(memory_play)

    assert "WriteProcessMemory" not in source
    assert "DLL mutation" not in source
    assert "RNG hook" not in source


def test_memory_registry_and_snapshot_loaders_reject_invalid_shapes(tmp_path) -> None:
    registry_list = tmp_path / "registry-list.json"
    registry_list.write_text("[]", encoding="utf-8")
    registry_missing = tmp_path / "registry-missing.json"
    registry_missing.write_text("{}", encoding="utf-8")
    snapshot_list = tmp_path / "snapshot-list.json"
    snapshot_list.write_text("[]", encoding="utf-8")
    snapshot_missing = tmp_path / "snapshot-missing.json"
    snapshot_missing.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="registry must be an object"):
        load_memory_signature_registry(registry_list)
    with pytest.raises(ValueError, match="signatures"):
        load_memory_signature_registry(registry_missing)
    with pytest.raises(ValueError, match="snapshot must be an object"):
        load_memory_snapshot(snapshot_list)
    with pytest.raises(ValueError, match="state_payload"):
        load_memory_snapshot(snapshot_missing)

    snapshot_missing_binding = tmp_path / "snapshot-missing-binding.json"
    snapshot_missing_binding.write_text(
        '{"game_version":"0.105.1","branch":"beta","binary_signature":"sha256:abc","state_payload":{}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="target_pid"):
        load_memory_snapshot(snapshot_missing_binding)
