from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar


T_Serializable = TypeVar("T_Serializable", bound="Serializable")


class Serializable(ABC):
    @abstractmethod
    def serialize(self) -> Any:
        """Convert the object to a dictionary."""
        pass

    @classmethod
    @abstractmethod
    def deserialize(cls: Type[T_Serializable], data: Any) -> T_Serializable:
        """Create an instance of the class from a dictionary."""
        pass
