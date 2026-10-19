"""Helpers shared by the session and the component classes."""


def safe(getter):
    """Return getter(), or a short note if AEDT can't provide the value."""
    try:
        return getter()
    except Exception as e:
        return f"<unavailable: {e}>"


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
