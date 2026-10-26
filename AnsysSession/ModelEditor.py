"""Every change to an AEDT design goes through ModelEditor.

Operations raise AedtError when AEDT refuses them. They change AEDT straight
away; snapshots read before a change are out of date afterwards (re-read with
Session.refresh()). Nothing is saved until save() is called.
"""

from configs import IN_PLACE_OFFSET


class AedtError(RuntimeError):
    """AEDT refused or failed an operation."""


class ModelEditor:
    def __init__(self, app):
        self.app = app

    @property
    def modeler(self):
        return self.app.modeler

    # --- geometry ---------------------------------------------------------
    def move(self, name, vector):
        if all(abs(v) < 1e-12 for v in vector):
            return
        if not self.modeler.move([name], list(vector)):
            raise AedtError(f'AEDT could not move "{name}" by {list(vector)}')

    def copy_in_place(self, name):
        """Copy/paste ``name``; same position, excitations not copied. Returns the copy's name."""
        self.modeler.copy([name])
        pasted = self.modeler.paste()
        if len(pasted) != 1:
            raise AedtError(f'Copying "{name}" produced {pasted}, expected exactly one new object')
        return pasted[0]

    def duplicate(self, name, vector):
        """Duplicate ``name`` with its excitations, moved by ``vector``. Returns the copy's name.

        AEDT needs a non-zero vector, so a copy that stays in place is duplicated
        IN_PLACE_OFFSET away and moved straight back.
        """
        in_place = all(abs(v) < 1e-12 for v in vector)
        ok, new = self.modeler.duplicate_along_line(name, IN_PLACE_OFFSET if in_place else list(vector),
                                                    clones=2, duplicate_assignment=True)
        if not ok or len(new) != 1:
            raise AedtError(f'Duplicating "{name}" produced {new}, expected exactly one new object')
        if in_place:
            self.move(new[0], [-v for v in IN_PLACE_OFFSET])
        return new[0]

    def rename(self, name, new_name):
        """Rename an object; returns the name AEDT gave it."""
        obj = self.modeler.get_object_from_name(name)
        if obj is None:
            raise AedtError(f'No object "{name}" to rename')
        obj.name = new_name
        return obj.name

    def create_group(self, names, group):
        return self.modeler.create_group(objects=list(names), group_name=group)

    def delete(self, names):
        if names and not self.modeler.delete(list(names)):
            raise AedtError(f"AEDT could not delete {list(names)}")

    def move_to(self, name, position):
        """Move ``name`` so its bounding-box center lands on ``position`` (a Position).

        The center is read from AEDT, so earlier moves are taken into account. A
        position without a height (z=None) keeps the object's own height; a
        NumericalPositionFixed always has one.
        """
        if self.modeler.get_object_from_name(name) is None:
            raise AedtError(f'No object "{name}" to move')
        box = [float(v) for v in self.modeler.oeditor.GetObjectBoundingBox(name)]
        center = [(box[i] + box[i + 3]) / 2 for i in range(3)]
        target = position.coordinates(z=center[2])
        self.move(name, [t - c for t, c in zip(target, center)])

    # --- properties -------------------------------------------------------
    def edit(self, section, name, /, **changes):
        """Change one item by section: "components", "materials", "variables", "setups",
        "boundaries" or "mesh". Returns the edited values as read back from AEDT."""
        editors = {
            "components": self.set_object_properties,
            "objects": self.set_object_properties,
            "materials": self.set_material_properties,
            "variables": self.set_variable,
        }
        if section in editors:
            return editors[section](name, **changes)
        return self.edit_item(section, name, **changes)

    def set_object_properties(self, name, /, **changes):
        """Set editable object properties (material_name, solve_inside, name, color, ...)."""
        obj = self.modeler.get_object_from_name(name)
        if obj is None:
            raise KeyError(f'No object named "{name}"')
        return self._set_properties(obj, changes, "objects")

    def set_material_properties(self, name, /, **changes):
        """Set material properties, e.g. conductivity=5.8e7; changes every object using it."""
        material = self.app.materials[name]
        if material is None:
            raise KeyError(f'No material named "{name}"')
        for key, value in changes.items():
            setattr(material, key, value)
        return {key: getattr(material, key).value for key in changes}

    def set_variable(self, name, /, **changes):
        """Set variable attributes, e.g. expression="0.2mm"."""
        variable = self.app.variable_manager.variables.get(name)
        if variable is None:
            raise KeyError(f'No variable named "{name}"')
        return self._set_properties(variable, changes, "variables")

    def set_pin_count(self, variable, count):
        """Set the pin-count design variable (e.g. "PinCount") to ``count``; the geometry driven by it moves."""
        expression = str(count)
        try:
            read_back = self.set_variable(variable, expression=expression)["expression"]
        except KeyError as e:
            raise AedtError(e.args[0]) from None
        # PyAEDT only logs when AEDT rejects an expression, so check what was kept.
        if read_back != expression:
            raise AedtError(f'AEDT kept "{variable}" at {read_back} instead of {expression}')

    def edit_item(self, kind, name, /, **changes):
        """Change properties of a setup, boundary or mesh operation and push them to AEDT once."""
        getters = {
            "setups": lambda: self.app.setups,
            "boundaries": lambda: self.app.boundaries,
            "mesh": lambda: self.app.mesh.meshoperations,
        }
        if kind not in getters:
            raise KeyError(f"Unknown section {kind!r}, choose from "
                           f"{['components', 'materials', 'variables', *getters]}")
        items = getters[kind]()
        item = next((i for i in items if i.name == name), None)
        if item is None:
            raise KeyError(f'No {kind} item named "{name}". Available: {[i.name for i in items]}')
        unknown = set(changes) - set(item.props)
        if unknown:
            raise KeyError(f'"{name}" has no properties {sorted(unknown)}. Available: {list(item.props)}')
        # With auto_update on, PyAEDT only logs a warning when a push fails.
        item.auto_update = False
        try:
            for key, value in changes.items():
                item.props[key] = value
        finally:
            item.auto_update = True
        ok = item.update()
        if ok and {"Faces", "Objects", "Edges"} & changes.keys() and hasattr(item, "update_assignment"):
            ok = item.update_assignment()
        if not ok:
            raise AedtError(f'AEDT rejected the changes to {kind} item "{name}": {changes}')
        return {key: item.props[key] for key in changes}

    @staticmethod
    def _set_properties(target, changes, kind):
        for key, value in changes.items():
            prop = getattr(type(target), key, None)
            if not (isinstance(prop, property) and prop.fset):
                raise KeyError(f"{key!r} is not an editable property of {kind}")
            setattr(target, key, value)
        return {key: getattr(target, key) for key in changes}

    # --- designs and project ----------------------------------------------
    def set_active_design(self, name):
        if not self.app.set_active_design(name):
            raise AedtError(f'AEDT could not switch to design "{name}"')

    def duplicate_design(self, name):
        """Duplicate the active design and make the duplicate active; returns its name."""
        if not self.app.duplicate_design(name):
            raise AedtError(f'AEDT could not duplicate design "{self.app.design_name}"')
        return self.app.design_name

    def delete_design(self, name, fallback_design=None):
        self.app.delete_design(name, fallback_design=fallback_design)

    def save(self):
        if self.app.save_project() is False:
            raise AedtError(f'AEDT could not save project "{self.app.project_name}"')
