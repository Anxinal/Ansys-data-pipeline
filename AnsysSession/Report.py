"""The 11-section report of everything an open project can tell about itself."""

from datetime import datetime
from pathlib import Path

from Chips.Components.utils import print_info
from configs import NAMED_EXPRESSIONS

from .utils import safe


def _folder_size_mb(path):
    path = Path(path)
    if not path.is_dir():
        return 0.0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


class ProjectReport:
    """Report of an open Session: session, project, design, variables, geometry,
    components, materials, boundaries, mesh, setups, optimetrics and post."""

    def __init__(self, session):
        self.session = session

    def show(self, attr=None):
        """Print and return every section, or only ``attr``."""
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
                for component in self.session.components:
                    component.print(info[name][component.name])
            elif name == "materials" and isinstance(info[name], dict):
                for material in self.session.materials:
                    material.print(info[name][material.name])
            else:
                print_info(info[name])
        return info[attr] if attr else info

    def _session_section(self):
        return {**dict(self.session.app.info), "install folder": self.session.app.desktop_install_dir}

    def _project_section(self):
        app = self.session.app
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
        app = self.session.app
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

        manager = self.session.app.variable_manager
        return {"project": describe(manager.project_variables), "design": describe(manager.design_variables)}

    def _geometry_section(self):
        modeler = self.session.app.modeler
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
        reader = self.session.reader
        return {c.name: {**c.info(), **reader.details(c)} for c in self.session.components}

    def _materials_section(self):
        return {material.name: material.info() for material in self.session.materials}

    def _boundaries_section(self):
        return {b.name: {"type": b.type, **b.props} for b in self.session.app.boundaries}

    def _mesh_section(self):
        mesh = self.session.app.mesh
        initial = mesh.initial_mesh_settings
        return {
            "initial settings": dict(initial.props) if initial else {},
            "operations": {op.name: {"type": op.type, **op.props} for op in mesh.meshoperations},
        }

    def _setups_section(self):
        app = self.session.app
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
        app = self.session.app
        return {
            "parametric": {s.name: dict(s.props) for s in app.parametrics.setups},
            "optimization": {s.name: dict(s.props) for s in app.optimizations.setups},
        }

    def _post_section(self):
        app = self.session.app
        return {
            "reports": {r.plot_name: {"type": r.report_type, "solution": r.setup} for r in app.post.plots},
            "field plots": safe(lambda: list(app.post.field_plot_names)),
            "named expressions": {
                name: bool(app.ofieldsreporter.DoesNamedExpressionExists(name)) for name in NAMED_EXPRESSIONS
            },
        }
