from enum import Enum

class ActionType(Enum):
    """Usando Enum para mayor seguridad"""
    NEW = 1
    DELETE = 2
    RENAME = 3
    MOVE = 4
    REPLACE = 5
    
    @property
    def label(self):
        return {
            self.NEW: 'new',
            self.DELETE: 'delete',
            self.RENAME: 'rename',
            self.MOVE: 'move',
            self.REPLACE: 'replace',
        }[self]
    
    @classmethod
    def choices(cls):
        return [(item.value, item.label) for item in cls]

