"""Plain-data classes for the objects, materials and boundaries of an AEDT design.

Nothing here talks to AEDT: AnsysSession.DesignReader fills them in. Importing
the package registers every Component subclass, so Component.create() returns
the right subtype.
"""

from .Boundary import Boundary
from .Component import Component
from .LineComponent import LineComponent
from .Material import Material
from .SheetComponent import SheetComponent
from .SolidComponent import SolidComponent

__all__ = ["Boundary", "Component", "LineComponent", "Material", "SheetComponent", "SolidComponent"]
