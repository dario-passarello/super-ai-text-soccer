from dataclasses import dataclass
from typing import Any


@dataclass
class Stadium:
    prefix: str
    name: str
    capacity: int

    @staticmethod
    def from_dict(data: dict[str, Any]):
        return Stadium(data["prefix"], data["name"], data["capacity"])

    def prefix_name(self):
        return f"{self.prefix} {self.capacity}"
