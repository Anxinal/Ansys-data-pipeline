"""Keeps the CopyRecord of every extracted copy in a JSON file next to the project.

The file is <project>.pyaedt/copies.json (PyAEDT's folder for the project),
holding {source design: {group: record}}.
"""

import json
from pathlib import Path

from Chips.CopyRecord import CopyRecord


class CopyStore:
    def __init__(self, app):
        self.path = Path(app.toolkit_directory) / "copies.json"

    def _read(self):
        return json.loads(self.path.read_text()) if self.path.is_file() else {}

    def save(self, record):
        data = self._read()
        data.setdefault(record.source_design, {})[record.group] = record.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def load(self, source_design, group):
        """The record of ``group`` in ``source_design`` (group name case-insensitive), or None."""
        records = self._read().get(source_design, {})
        spelled = next((name for name in records if name.lower() == group.lower()), None)
        return CopyRecord.from_dict(records[spelled]) if spelled else None
