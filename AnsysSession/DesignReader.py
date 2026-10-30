"""Reads a design from AEDT into plain data: the only place the chip layer's inputs come from.

snapshot() reads every object once, in bulk where AEDT allows it (types,
materials and model flags take one call per group or material, not per object),
so the chip layer never calls AEDT. details() and material() read the extras a
report shows, on demand.
"""

from pathlib import Path

from ansys.aedt.core.modules.material import MatProperties

from Chips.Components import Boundary, Component, Material
from Chips.DesignSnapshot import DesignSnapshot
from configs import GRID_SIZE, TYPE_GROUPS
from ImageData.BoardImage import BoardImage, crop_to_content
from PIL import Image
from .utils import file_stem, safe


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
        for key in app.odefinition_manager.GetProjectMaterialNames():
            for name in oeditor.GetObjectsByMaterial(key):
                materials[name] = key
        names = self.object_names()
        object_faces = {name: tuple(int(i) for i in oeditor.GetFaceIDs(name))
                        if name in types else () for name in names}
        boundaries = self._boundaries(object_faces)

        components = []
        for name in names:
            object_type = types.get(name, "Unclassified")
            classified = object_type != "Unclassified"
            box = [float(v) for v in oeditor.GetObjectBoundingBox(name)] if classified else [0.0] * 6
            faces = list(object_faces[name])
            face_set = set(faces)
            assigned = [b for b in boundaries
                        if name.lower() in (o.lower() for o in b.objects) or face_set.intersection(b.faces)]
            components.append(Component.create(name, object_type, bounding_box=box, face_ids=faces,
                                               material_name=materials.get(name, ""),
                                               is_model=name not in non_model, boundaries=assigned))

        groups = {group: tuple(oeditor.GetObjectsInGroup(group)) for group in self.group_names()}
        return DesignSnapshot(app.design_name, app.modeler.model_units, tuple(components), boundaries, groups)
    
    def obtain_image_snapshot(self, component: Component) -> BoardImage:
        """A top-view picture of ``component`` from AEDT, cut so the component starts at pixel (0, 0).

        Only the component is drawn (no axis, grid, ruler or region). The cells are
        configs.GRID_SIZE pixels and the grid holds as many whole cells as fit.
        AEDT draws model pictures only in graphical mode.
        """
        if len(GRID_SIZE) != 2:
            raise ValueError(f"configs.GRID_SIZE must be [width, height] in pixels, not {GRID_SIZE}")
        app = self.app
        path = Path(app.working_directory) / f"{file_stem(app.design_name)}_{file_stem(component.name)}_top.jpg"
        path.unlink(missing_ok=True)  # so an earlier picture is never read as this one
        app.post.export_model_picture(path, show_axis=False, show_grid=False, show_ruler=False, show_region="False",
                                      selections=[component.name], orientation="top")
        if not path.is_file():
            raise RuntimeError(f'AEDT exported no picture of "{component.name}"; it needs graphical mode')
        with Image.open(path) as picture:
            image = crop_to_content(picture)
        width, height = GRID_SIZE
        return BoardImage(image, (width, height), image.width // width - 1, image.height // height - 1,
                          name=component.name)

    def _boundaries(self, object_faces):
        """Read live properties/assignments without parsing the saved project.

        BoundaryObject.props loads the complete .aedt file. Its OO properties
        and BoundarySetup.GetAssignment instead read the current desktop state.
        Assignment IDs are resolved against the face IDs already read in bulk.
        """
        boundaries = []
        face_ids = {face for faces in object_faces.values() for face in faces}
        names = {name.lower(): name for name in object_faces}
        for boundary in self.app.boundaries:
            props = dict(boundary.properties)
            faces, objects = [], []
            for assignment in self.app.oboundary.GetAssignment(boundary.name) or ():
                text = str(assignment)
                if text.lower() in names:
                    objects.append(names[text.lower()])
                elif text.isdigit():
                    entity_id = int(text)
                    if entity_id in face_ids:
                        faces.append(entity_id)
                    else:
                        name = self.oeditor.GetObjectNameByID(entity_id)
                        if name:
                            objects.append(str(name))
            faces, objects = tuple(faces), tuple(objects)
            props.update(Faces=list(faces), Objects=list(objects))
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

    def valid_check(self):
        """Run AEDT's Validation Check (oDesign.ValidateDesign) on the active design.

        Returns (passed, messages, log_file): whether the design passed, the
        non-empty lines AEDT wrote to the log, and the log's path.
        """
        app = self.app
        log_file = Path(app.working_directory) / f"{file_stem(app.design_name)}_validation.log"
        log_file.unlink(missing_ok=True)  # so a log from an earlier check is never read as this one's
        passed = app.validate_simple(log_file) == 1
        messages = []
        if log_file.is_file():
            messages = [line.rstrip() for line in log_file.read_text(errors="replace").splitlines() if line.strip()]
        return passed, messages, log_file
