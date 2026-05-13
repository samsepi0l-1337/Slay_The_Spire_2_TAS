from __future__ import annotations

from dataclasses import dataclass

from .ml_schema import GameStep

CATALOG_CATEGORIES = (
    "global",
    "player",
    "card",
    "relic",
    "potion",
    "monster",
    "path",
    "action",
    "observation",
    "decision_context",
)


@dataclass(frozen=True)
class EntityCatalog:
    version: str
    token_to_id: dict[str, int]

    def __init__(self, version: str = "local", token_to_id: dict[str, int] | None = None) -> None:
        base = {"<pad>": 0}
        for category in CATALOG_CATEGORIES:
            base[f"{category}:<unk>"] = len(base)
        if token_to_id is not None:
            base.update(token_to_id)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "token_to_id", base)

    @property
    def size(self) -> int:
        return len(self.token_to_id)

    def id_for(self, category: str, value: str) -> int:
        return self.token_to_id.get(self.key(category, value), self.token_to_id[f"{category}:<unk>"])

    def with_token(self, category: str, value: str) -> EntityCatalog:
        key = self.key(category, value)
        if key in self.token_to_id:
            return self
        token_to_id = dict(self.token_to_id)
        token_to_id[key] = len(token_to_id)
        return EntityCatalog(version=self.version, token_to_id=token_to_id)

    def to_dict(self) -> dict[str, object]:
        return {"version": self.version, "token_to_id": dict(self.token_to_id)}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> EntityCatalog:
        return cls(version=str(data["version"]), token_to_id=dict(data["token_to_id"]))  # type: ignore[arg-type]

    @classmethod
    def from_steps(cls, steps: list[GameStep], version: str = "local") -> EntityCatalog:
        catalog = cls(version=version)
        for step in steps:
            for category, value in _tokens_from_step(step):
                catalog = catalog.with_token(category, value)
        return catalog

    @staticmethod
    def key(category: str, value: str) -> str:
        if category not in CATALOG_CATEGORIES:
            raise ValueError(f"unsupported catalog category: {category}")
        return f"{category}:{value or '<unk>'}"


def _tokens_from_step(step: GameStep) -> list[tuple[str, str]]:
    state = step.state
    tokens = [
        ("global", state.character),
        ("decision_context", state.decision_context),
        ("player", state.character),
        ("observation", step.observation.source_type),
    ]
    tokens.extend(("card", card.card_id) for card in state.cards or [])
    tokens.extend(("relic", relic.relic_id) for relic in state.relics or [])
    tokens.extend(("potion", potion.potion_id) for potion in state.potions or [])
    tokens.extend(("monster", monster.monster_id) for monster in state.monsters or [])
    tokens.extend(("path", path.node_type) for path in state.path_candidates or [])
    tokens.extend(("action", action.identity) for action in step.actions)
    return tokens
