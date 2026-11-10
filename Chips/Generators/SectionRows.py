"""Read section instructions without assigning terminal roles."""
import csv
import re
from pathlib import Path

INSTRUCTION = re.compile(r"\s*board\s*=\s*(?P<board>\S+)\s+sphere_positions\s*=\s*(?P<pins>.*?)\s*", re.I)


def read_rows(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    first = next((line for line in text.splitlines() if line.strip()), "")
    rows = instruction_rows(path, text) if INSTRUCTION.fullmatch(first) else csv_rows(path, text)
    if not rows:
        raise ValueError(f"{path} has no section instructions")
    return rows


def instruction_rows(path, text):
    rows = []
    for line, content in enumerate(text.splitlines(), 1):
        if not content.strip():
            continue
        match = INSTRUCTION.fullmatch(content)
        pins = match.group("pins").split() if match else []
        if len(pins) < 2:
            raise ValueError(f'{path}, line {line}: expected board = <name> Sphere_positions = <at least two pins>')
        rows.append((line, {"board": match.group("board"), "sphere_positions": " ".join(pins)}))
    return rows


def csv_rows(path, text):
    reader = csv.DictReader(text.splitlines())
    fields = set(reader.fieldnames or [])
    if "board" not in fields or not ("sphere_positions" in fields or {"vcc_pin", "gnd_pin"} <= fields):
        if not fields:
            return []
        raise ValueError(f"{path} needs board and sphere_positions, or legacy vcc_pin/gnd_pin columns")
    return list(enumerate(reader, 2))
