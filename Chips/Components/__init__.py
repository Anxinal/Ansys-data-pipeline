"""Component classes for the objects in an AEDT design.

Importing the package registers every subclass, so Component.from_object()
and Component.all() return the right subtype.
"""

from .Component import Component
from .LineComponent import LineComponent
from .Material import Material
from .SheetComponent import SheetComponent
from .SolidComponent import SolidComponent

__all__ = ["Component", "LineComponent", "Material", "SheetComponent", "SolidComponent"]
