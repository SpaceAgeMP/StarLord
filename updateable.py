from abc import ABC, abstractmethod

class UpdateableResource(ABC):
    folder: str
    name: str

    def __init__(self, folder: str, name: str) -> None:
        super().__init__()
        self.folder = folder
        self.name = name

    @abstractmethod
    def checkUpdate(self, offline=False):
        pass
        
    @abstractmethod
    def update(self):
        pass

    def __repr__(self) -> str:
        return f"class={self.__class__.__name__} name={self.name} folder={self.folder}"
