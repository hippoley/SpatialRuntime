from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

@dataclass(frozen=True)
class WorldSnapshot:
    case_id: str
    step: int
    revision: int
    entities: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    relations: tuple[Mapping[str, Any], ...] = ()
    facts: Mapping[str, Any] = field(default_factory=dict)

    def require_monotonic_after(self, previous: "WorldSnapshot") -> None:
        if self.case_id != previous.case_id:
            raise ValueError("case_id changed")
        if self.step < previous.step or self.revision < previous.revision:
            raise ValueError("world snapshot moved backwards")
