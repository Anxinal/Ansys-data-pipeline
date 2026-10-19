from datetime import datetime
from pathlib import Path

from ansys.aedt.core import Desktop

from Chips.Components import Component
from Chips.Components.utils import find_component, print_info, safe

# Fields-calculator expressions created by the simulation workflow. AEDT can
# check a named expression by name but has no call that lists them all.
NAMED_EXPRESSIONS = ("smoothscalBx", "smoothscalBy", "smoothscalBz")


def _folder_size_mb(path):
    path = Path(path)
    if not path.is_dir():
        return 0.0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


class Session:

    def __init__(self, path: str, design=None):
        self.path = path  
        # No GUI: everything below goes through the AEDT API.
        desktop = Desktop(non_graphical=True, new_desktop=True)
        try:
            # The design's app object, e.g. ansys.aedt.core.Maxwell3d (not a Desktop).
            self.app = desktop.load_project(path, design_name=design)
        except Exception:
            desktop.release_desktop(close_projects=True, close_on_exit=True)
            raise
        if not self.app:
            desktop.release_desktop(close_projects=True, close_on_exit=True)
            raise RuntimeError(f"AEDT could not open {path}" + (f' (design "{design}")' if design else ""))
        self._components = None

    @property
    def components(self):
        """Every object in the design as a Component subclass (read once, then cached)."""
        if self._components is None:
            self._components = Component.all(self.app)
        return self._components

    def get_component(self, name):
        """The component called ``name`` (case-insensitive, like Chip and Terminal)."""
        try:
            return find_component(self.components, name, "this design")
        except LookupError as e:
            raise KeyError(str(e)) from None

    @property
    def materials(self):
        """The Materials used by the components, one per material."""
        materials = {}
        for component in self.components:
            material = component.material
            if material is not None:
                materials.setdefault(material.name, material)
        return [materials[name] for name in sorted(materials)]

    def get_material(self, name):
        material = next((m for m in self.materials if m.name.lower() == name.lower()), None)
        if material is None:
            raise KeyError(f'No material named "{name}" in use. Available: {[m.name for m in self.materials]}')
        return material


    def generate_data(self):
        pass 

    def release(self):
        """Release the session"""
        self.app.release_desktop(close_projects=True, close_desktop=True)


    def get_session_info(self, attr: str | None = None):
        """Print and return everything the open project can tell about itself.

        Returns a dict of sections: session, project, design, variables,
        geometry, components, materials, boundaries, mesh, setups, optimetrics
        and post. Pass ``attr`` (one of those names) to print and return one
        section.
        """
        sections = {
            "session": self._session_section,
            "project": self._project_section,
            "design": self._design_section,
            "variables": self._variables_section,
            "geometry": self._geometry_section,
            "components": self._components_section,
            "materials": self._materials_section,
            "boundaries": self._boundaries_section,
            "mesh": self._mesh_section,
            "setups": self._setups_section,
            "optimetrics": self._optimetrics_section,
            "post": self._post_section,
        }
        if attr is not None and attr not in sections:
            raise KeyError(f"Unknown section {attr!r}, choose from {list(sections)}")

        info = {}
        for name in [attr] if attr else sections:
            # One section failing (an API this design type lacks) shouldn't hide the rest.
            info[name] = safe(sections[name])
            print(f"\n=== {name} {'=' * max(0, 70 - len(name))}")
            if name == "components" and isinstance(info[name], dict):
                # Each component prints itself, with the fields of its subtype.
                for component in self.components:
                    component.print(info[name][component.name])
            elif name == "materials" and isinstance(info[name], dict):
                for material in self.materials:
                    material.print(info[name][material.name])
            else:
                print_info(info[name])
        return info[attr] if attr else info

    def edit(self, section: str, name: str, **changes):
        """Change one item listed by get_session_info through the API.

        ``section`` is "variables", "components", "materials", "setups",
        "boundaries" or "mesh", and ``changes`` use the property names
        get_session_info shows, e.g.::

            s.edit("variables", "defect_depth", expression="0.2mm")
            s.edit("components", "PCB", material_name="FR4_epoxy", solve_inside=False)
            s.edit("materials", "copper", conductivity=5.8e7)
            s.edit("setups", "Setup1", MaximumPasses=12, PercentError=0.5)

        Returns the edited values as read back from the session. Changes stay
        in the open session until save() is called.
        """
        app = self.app
        if section in ("components", "objects"):
            return self.get_component(name).edit(**changes)
        if section == "materials":
            return self.get_material(name).edit(**changes)
        if section == "variables":
            item = app.variable_manager.variables.get(name)
            if item is None:
                raise KeyError(f'No variables item named "{name}"')
            for key, value in changes.items():
                prop = getattr(type(item), key, None)
                if not (isinstance(prop, property) and prop.fset):
                    raise KeyError(f"{key!r} is not an editable property of {section} items")
                setattr(item, key, value)
            return {key: getattr(item, key) for key in changes}

        getters = {
            "setups": lambda: app.setups,
            "boundaries": lambda: app.boundaries,
            "mesh": lambda: app.mesh.meshoperations,
        }
        if section not in getters:
            raise KeyError(f"Unknown section {section!r}, choose from {['variables', 'components', 'materials', *getters]}")
        items = getters[section]()
        item = next((i for i in items if i.name == name), None)
        if item is None:
            raise KeyError(f'No {section} item named "{name}". Available: {[i.name for i in items]}')
        unknown = set(changes) - set(item.props)
        if unknown:
            raise KeyError(f'"{name}" has no properties {sorted(unknown)}. Available: {list(item.props)}')

        # Apply all changes, then push them to AEDT once and check the result
        # (with auto_update on, PyAEDT only logs a warning when a push fails).
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
            raise RuntimeError(f'AEDT rejected the changes to {section} item "{name}": {changes}')
        return {key: item.props[key] for key in changes}

    def save(self):
        """Write the edits made in this session to the .aedt project."""
        return self.app.save_project()

    def _session_section(self):
        return {**dict(self.app.info), "install folder": self.app.desktop_install_dir}

    def _project_section(self):
        app = self.app
        project_file = Path(app.project_file)
        designs = {}
        for name in app.design_list:
            design = app.oproject.GetDesign(name)
            designs[name] = f"{safe(design.GetDesignType)}, {safe(design.GetSolutionType)}"
        return {
            "name": app.project_name,
            "file": str(project_file),
            "last saved": datetime.fromtimestamp(project_file.stat().st_mtime).isoformat(sep=" ", timespec="seconds"),
            ".aedt size (MB)": round(project_file.stat().st_size / 1e6, 1),
            "results folder": app.results_directory,
            "results size (MB)": round(_folder_size_mb(app.results_directory), 1),
            "active design": app.design_name,
            "designs": designs,
            "datasets": list(app.project_datasets),
            "materials in project": sorted(m.name for m in app.materials.material_keys.values()),
        }

    def _design_section(self):
        app = self.app
        return {
            "name": app.design_name,
            "design type": app.design_type,
            "solution type": app.solution_type,
            "model units": app.modeler.model_units,
            "symmetry multiplier": safe(lambda: app.symmetry_multiplier),
            "excitations": app.excitation_names,
            "output variables": safe(lambda: list(app.output_variables)),
            "datasets": list(app.design_datasets),
        }

    def _variables_section(self):
        def describe(variables):
            return {
                name: {
                    "expression": var.expression,
                    "value": var.evaluated_value,
                    "sweep": safe(lambda: var.sweep),
                    "description": safe(lambda: var.description),
                }
                for name, var in variables.items()
            }

        manager = self.app.variable_manager
        return {"project": describe(manager.project_variables), "design": describe(manager.design_variables)}

    def _geometry_section(self):
        modeler = self.app.modeler
        return {
            "units": modeler.model_units,
            "solids / sheets / lines": f"{len(modeler.solid_objects)} / {len(modeler.sheet_objects)} / {len(modeler.line_objects)}",
            "points": len(modeler.point_names),
            "non-model objects": modeler.non_model_objects,
            "3D components": modeler.user_defined_component_names,
            "groups": safe(lambda: list(modeler.oeditor.GetChildNames("Groups"))),
            "coordinate systems": [cs.name for cs in modeler.coordinate_systems],
            "model bounding box": safe(modeler.get_model_bounding_box),
        }

    def _components_section(self):
        return {component.name: component.info() for component in self.components}

    def _materials_section(self):
        return {material.name: material.info() for material in self.materials}

    def _boundaries_section(self):
        return {b.name: {"type": b.type, **b.props} for b in self.app.boundaries}

    def _mesh_section(self):
        mesh = self.app.mesh
        initial = mesh.initial_mesh_settings
        return {
            "initial settings": dict(initial.props) if initial else {},
            "operations": {op.name: {"type": op.type, **op.props} for op in mesh.meshoperations},
        }

    def _setups_section(self):
        app = self.app
        solved_variations = {}
        for solution in app.existing_analysis_sweeps:
            setup_name, sweep_name = (part.strip() for part in solution.split(":", 1))
            solved_variations[solution] = app.list_of_variations(setup_name, sweep_name) or []
        return {
            "setups": {s.name: {"solved": s.is_solved, **s.props} for s in app.setups},
            "nominal variation": safe(lambda: app.get_nominal_variation(with_values=True)),
            "solved variations": solved_variations,
        }

    def _optimetrics_section(self):
        app = self.app
        return {
            "parametric": {s.name: dict(s.props) for s in app.parametrics.setups},
            "optimization": {s.name: dict(s.props) for s in app.optimizations.setups},
        }

    def _post_section(self):
        app = self.app
        return {
            "reports": {r.plot_name: {"type": r.report_type, "solution": r.setup} for r in app.post.plots},
            "field plots": safe(lambda: list(app.post.field_plot_names)),
            "named expressions": {
                name: bool(app.ofieldsreporter.DoesNamedExpressionExists(name)) for name in NAMED_EXPRESSIONS
            },
        }





