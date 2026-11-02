"""Prepare plain-data candidates using only explicitly requested geometry."""
from Chips import Chip
from Chips.Generators import FileSectionGenerator


def root_candidates(session, settings):
    rows = FileSectionGenerator.read_rows(settings.SECTIONS_FILE)
    names, boards = set(), []
    for _,row in rows:
        boards.append(row["board"])
        names.update([row["board"],row.get("gnd") or settings.DEFAULT_GND,
                      row.get("vcc") or settings.DEFAULT_VCC,
                      row.get("sphere_vcc") or settings.DEFAULT_SPEHRE[1],
                      row.get("sphere_gnd") or settings.DEFAULT_SPEHRE[0]])
    chip = Chip(session.reader.selected_components(names),gnd=settings.DEFAULT_GND,
                vcc=settings.DEFAULT_VCC,spheres=settings.DEFAULT_SPEHRE,
                boards=list(dict.fromkeys(boards)),units=session.app.modeler.model_units)
    return list(FileSectionGenerator(chip,settings.SECTIONS_FILE))
