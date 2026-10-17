"""Find the "root" chip in an AEDT design and print its model information.

"root" can be a single 3D object, a 3D component instance or a model-tree
group; all three are looked up by name.

Usage:
    .venv/bin/python generate_data.py path/to/project.aedt [--design NAME] [--root root] [--gui]
"""

import argparse
from pathlib import Path

from ansys.aedt.core.modules.material import MatProperties

from opensession import open_session

ROOT_NAME = "root"


def safe(getter):
    """Return getter(), or a short note if AEDT can't provide the value."""
    try:
        return getter()
    except Exception as e:
        return f"<unavailable: {e}>"


def section(title):
    print(f"\n=== {title} {'=' * max(0, 70 - len(title))}")


def show(label, value, indent=2):
    print(f"{' ' * indent}{label:<28} {value}")


def find_root(modeler, name=ROOT_NAME):
    """Return (kind, item) for the model item called ``name``.

    kind is "object" (Object3d), "component" (UserDefinedComponent) or
    "group" (list of member object names).
    """
    if name in modeler.object_names:
        return "object", modeler.get_object_from_name(name)
    if name in modeler.user_defined_component_names:
        return "component", modeler.user_defined_components[name]
    if name in list(modeler.oeditor.GetChildNames("Groups")):
        return "group", modeler.get_objects_in_group(name) or []

    similar = [n for n in modeler.object_names + modeler.user_defined_component_names if name.lower() in n.lower()]
    raise LookupError(f'No object, 3D component or group named "{name}" in this design. Similar names: {similar or "none"}')


def print_design(app):
    modeler = app.modeler
    section("Design")
    show("Project", app.project_file)
    show("Design", app.design_name)
    show("Design type", app.design_type)
    show("Solution type", app.solution_type)
    show("Model units", modeler.model_units)
    show("Objects", len(modeler.object_names))
    show("3D components", modeler.user_defined_component_names)
    show("Model bounding box", safe(modeler.get_model_bounding_box))

    variables = app.variable_manager.variables
    section(f"Variables ({len(variables)})")
    for name, var in variables.items():
        show(name, f"{var.expression}  (= {var.evaluated_value})")


def print_object(app, obj):
    """Print attributes, geometry, creation history and faces of one 3D object."""
    modeler = app.modeler
    units = modeler.model_units

    section(f'Object "{obj.name}" - attributes')
    # Everything AEDT shows in the object's Properties window.
    for prop in obj.valid_properties:
        show(prop, safe(lambda: modeler.oeditor.GetPropertyValue("Geometry3DAttributeTab", obj.name, prop)))

    section(f'Object "{obj.name}" - geometry')
    show("ID", obj.id)
    show("Object type", obj.object_type)
    show("Bounding box", f"{safe(lambda: obj.bounding_box)} {units}")
    show("Dimensions (x, y, z)", f"{safe(lambda: obj.bounding_dimension)} {units}")
    show("Volume", f"{safe(lambda: obj.volume)} {units}^3")
    show("Mass", f"{safe(lambda: obj.mass)} kg")
    show("Faces / edges / vertices", f"{len(obj.faces)} / {len(obj.edges)} / {len(obj.vertices)}")

    section(f'Object "{obj.name}" - creation history')
    history = obj.history()
    if history:
        for key, value in history.properties.items():
            show(key, value)
        for op_name, op in history.children.items():
            print(f"  -- {op_name}")
            for key, value in op.properties.items():
                show(key, value, indent=4)
    else:
        print("  <history unavailable>")

    section(f'Object "{obj.name}" - faces')
    for face in obj.faces:
        show(f"Face {face.id}", f"area={safe(lambda: face.area)}  center={safe(lambda: face.center)}  normal={safe(lambda: face.normal)}")

    print_material(app, obj.material_name)


def print_material(app, material_name):
    if not material_name:
        return
    section(f'Material "{material_name}"')
    material = app.materials[material_name]
    if material is None:
        print("  <not found in the project's materials>")
        return
    for prop in MatProperties.aedtname:
        mat_prop = getattr(material, prop, None)
        if mat_prop is not None:
            show(prop, f"{mat_prop.value} {mat_prop.unit or ''}".rstrip())


def print_member_table(app, title, names):
    """One line per object: the summary used when root holds several parts."""
    section(f"{title} ({len(names)})")
    units = app.modeler.model_units
    for name in names:
        obj = app.modeler.get_object_from_name(name)
        if obj is None:
            show(name, "<not a 3D object>")
            continue
        show(name, f"{obj.object_type}, material={obj.material_name}, solve_inside={obj.solve_inside}, "
                   f"bbox={safe(lambda: obj.bounding_box)} {units}, volume={safe(lambda: obj.volume)} {units}^3")


def print_root(app, name=ROOT_NAME):
    kind, root = find_root(app.modeler, name)
    print_design(app)

    if kind == "object":
        print_object(app, root)
    elif kind == "component":
        section(f'3D component "{root.name}"')
        show("Definition", root.definition_name)
        show("Group", root.group_name)
        show("Target coordinate system", root.target_coordinate_system)
        show("Bounding box", safe(lambda: root.bounding_box))
        show("Center", safe(lambda: root.center))
        section("Component parameters")
        for key, value in (root.parameters or {}).items():
            show(key, value)
        print_member_table(app, "Component parts", [part.name for part in root.parts.values()])
    else:
        section(f'Group "{name}"')
        show("Bounding box", safe(lambda: app.modeler.get_group_bounding_box(name)))
        print_member_table(app, "Group members", root)


def main():
    parser = argparse.ArgumentParser(description='Print the model information of the "root" chip in an AEDT design.')
    parser.add_argument("path", type=Path, help=".aedt project file, or a folder containing one")
    parser.add_argument("--design", help="design to open (default: the project's active design)")
    parser.add_argument("--root", default=ROOT_NAME, help=f'name of the root item (default: "{ROOT_NAME}")')
    parser.add_argument("--gui", action="store_true", help="show the AEDT GUI")
    args = parser.parse_args()

    app = open_session(args.path, gui=args.gui, design=args.design)
    try:
        print_root(app, args.root)
    finally:
        app.release_desktop(close_projects=True, close_desktop=True)


if __name__ == "__main__":
    main()
