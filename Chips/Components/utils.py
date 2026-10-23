"""Helpers for the chip-layer classes: lookups, geometry and printing (no AEDT)."""


def boxes_touch(a, b, tolerance=1e-9):
    """True when two bounding boxes [xmin, ymin, zmin, xmax, ymax, zmax] overlap or touch."""
    return all(a[i] <= b[i + 3] + tolerance and b[i] <= a[i + 3] + tolerance for i in range(3))


def find_component(components, name, label):
    """The component called ``name`` (case-insensitive), or a LookupError naming the options."""
    component = next((c for c in components if c.name.lower() == name.lower()), None)
    if component is None:
        raise LookupError(f'No component named "{name}" for {label}. Available: {[c.name for c in components]}')
    return component


def format_info(info, indent=2):
    """Format a nested info dictionary as an indented key/value listing."""
    pad = " " * indent
    if not isinstance(info, dict):
        return f"{pad}{info}"
    lines = []
    for key, value in info.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            if value:
                lines.append(format_info(value, indent + 2))
        elif isinstance(value, list) and len(str(value)) > 100:
            lines.append(f"{pad}{key}: ({len(value)})")
            lines.extend(f"{pad}  {item}" for item in value)
        else:
            lines.append(f"{pad}{key:<28} {value}")
    return "\n".join(lines)


def print_info(info, indent=2):
    """Print a nested info dictionary as an indented key/value listing."""
    print(format_info(info, indent))
