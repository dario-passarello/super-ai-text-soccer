from typing import Any

import attr


@attr.s(frozen=True, auto_attribs=True)
class Stadium:
    prefix: str
    name: str
    capacity: int

    @staticmethod
    def from_dict(data: dict[str, Any]):
        return Stadium(data["prefix"], data["name"], data["capacity"])

    def prefix_name(self):
        return f"{self.prefix} {self.capacity}"
