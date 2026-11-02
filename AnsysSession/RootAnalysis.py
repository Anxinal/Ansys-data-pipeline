"""Run selected source sections in place without copying or duplicating designs."""
from pathlib import Path
from .RootCandidates import root_candidates
from .RootCase import run_case
from .RootSelection import root_selection


def run_root_sections(session, settings, run_dir):
    results = []
    for index, candidate in enumerate(root_candidates(session,settings),1):
        folder = Path(run_dir)/f"case_{index}_VCC{candidate.pair.a.value}_GND{candidate.pair.b.value}"
        results.append(run_case(session,candidate,settings,folder))
    return results
