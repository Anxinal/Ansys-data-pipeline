"""Reads a design from AEDT into plain data: the only place the chip layer's inputs come from.

snapshot() reads every object once, in bulk where AEDT allows it (types,
materials and model flags take one call per group or material, not per object),
so the chip layer never calls AEDT. details() and material() read the extras a
report shows, on demand.
"""

from ansys.aedt.core.modules.material import MatProperties

from Chips.Components import Boundary, Component, Material
from Chips.DesignSnapshot import DesignSnapshot
from configs import TYPE_GROUPS
from PIL import Image
from .utils import safe


class DesignReader:
    def __init__(self, app):
        self.app = app

    @property
    def oeditor(self):
        return self.app.modeler.oeditor

    def group_names(self):
        return list(self.oeditor.GetChildNames("Groups"))

    def object_names(self):
        return list(self.app.modeler.object_names)

    def snapshot(self):
        """The active design as a DesignSnapshot."""
        app, oeditor = self.app, self.oeditor
        types = {}
        for group, object_type in TYPE_GROUPS.items():
            for name in oeditor.GetObjectsInGroup(group):
                types[name] = object_type
        non_model = set(oeditor.GetObjectsInGroup("Non Model"))
        materials = {}
        for key in app.materials.material_keys:
            for name in oeditor.GetObjectsByMaterial(key):
                materials[name] = key
        boundaries = self._boundaries()

        components = []
        for name in self.object_names():
            object_type = types.get(name, "Unclassified")
            classified = object_type != "Unclassified"
            box = [float(v) for v in oeditor.GetObjectBoundingBox(name)] if classified else [0.0] * 6
            faces = [int(i) for i in oeditor.GetFaceIDs(name)] if classified else []
            face_set = set(faces)
            assigned = [b for b in boundaries
                        if name.lower() in (o.lower() for o in b.objects) or face_set.intersection(b.faces)]
            components.append(Component.create(name, object_type, bounding_box=box, face_ids=faces,
                                               material_name=materials.get(name, ""),
                                               is_model=name not in non_model, boundaries=assigned))

        groups = {group: tuple(oeditor.GetObjectsInGroup(group)) for group in self.group_names()}
        return DesignSnapshot(app.design_name, app.modeler.model_units, tuple(components), boundaries, groups)
    
    def obtain_image_snapshot() -> Image:
        pass

    def _boundaries(self):
        boundaries = []
        for boundary in self.app.boundaries:
            props = dict(boundary.props)
            faces = tuple(int(face) for face in props.get("Faces", []))
            objects = tuple(props.get("Objects", []))
            center = None
            if faces:
                centers = [[float(v) for v in self.oeditor.GetFaceCenter(face)] for face in faces]
                center = tuple(sum(axis) / len(centers) for axis in zip(*centers))
            boundaries.append(Boundary(boundary.name, boundary.type, faces, objects, center, props))
        return tuple(boundaries)

    def details(self, component):
        """The extras of one object a report shows (id, solve inside, group, volume, area, ...)."""
        app, oeditor, name = self.app, self.oeditor, component.name
        obj = app.modeler.get_object_from_name(name)
        units = app.modeler.model_units
        details = {
            "id": safe(lambda: obj.id),
            "solve inside": safe(lambda: obj.solve_inside),
            "group": safe(lambda: obj.group_name),
            "coordinate system": safe(lambda: obj.part_coordinate_system),
            "edges / vertices": safe(lambda: f"{len(oeditor.GetEdgeIDsFromObject(name))} / "
                                             f"{len(oeditor.GetVertexIDsFromObject(name))}"),
        }
        if component.type == "Solid":
            details["volume"] = f"{safe(lambda: float(oeditor.GetObjectVolume(name)))} {units}^3"
            details["mass (kg)"] = safe(lambda: obj.mass)
        elif component.type == "Sheet":
            faces = component.face_ids
            details["area"] = f"{safe(lambda: sum(float(oeditor.GetFaceArea(f)) for f in faces))} {units}^2"
            if len(faces) == 1:
                details["normal"] = safe(lambda: obj.faces[0].normal)
        elif component.type == "Line":
            edges = safe(lambda: oeditor.GetEdgeIDsFromObject(name))
            details["length"] = f"{safe(lambda: sum(float(oeditor.GetEdgeLength(e)) for e in edges))} {units}"
        return details

    def material(self, name):
        """The project's material called ``name`` as a Material, or None."""
        material = self.app.materials[name] if name else None
        if material is None:
            return None
        properties = {}
        for prop in MatProperties.aedtname:
            value = safe(lambda: getattr(material, prop))
            if value is not None and not isinstance(value, str):
                properties[prop] = f"{value.value} {value.unit or ''}".rstrip()
        return Material(material.name, bool(safe(material.is_conductor) is True), properties)
