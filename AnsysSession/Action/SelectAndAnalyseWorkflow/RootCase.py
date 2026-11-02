import json
from pathlib import Path

from ..Action import AnsysProcedure
from ..AnalysisActions.BzProcedure import BzProcedure
from ..AnalysisActions.CheckValidity import CheckValidity
from ..SetTerminalPositions import SetTerminalPositions
from .SelectForAnalysis import BoardSelect, BoardUpdate


def board_steps(session, board, previous):
    """Select ``board`` for the first case, swap to it when it changes, or nothing for the same board."""
    if previous is None:
        return [BoardSelect(session, [board])]
    return [] if previous.name == board.name else [BoardUpdate(session, previous, board)]


class RootCase(AnsysProcedure):
    """One SectionCandidate solved in place; writes ``result`` to <case_dir>/result.json.

    ``previous_board`` is the board the last case left active, None for the first case.
    ``bz_options`` are BzProcedure's options; the export goes to ``case_dir``.
    """

    def __init__(self, session, candidate, bz_options, case_dir, previous_board=None):
        section, pair = candidate.section, candidate.pair
        self.case_dir = Path(case_dir)
        self.bz = BzProcedure(session, section.board, **{**bz_options, "output_dir": self.case_dir})
        steps = [*board_steps(session, section.board, previous_board),
                 SetTerminalPositions(session, section, pair), CheckValidity(session), self.bz]
        super().__init__(steps, session, self.case_dir.name)
        self.summary = {"design": session.design, "board": section.board.name, "workflow": "root",
                        "VCC pin count": pair.a.value, "GND pin count": pair.b.value}

    def act(self):
        self.case_dir.mkdir(parents=True, exist_ok=True)
        status = super().act()
        self.result = {**self.summary, **(self.bz.result or {}), "status": "failed" if status else "success"}
        if status:
            self.result["error"] = f"{self.failed.label}: {self.error}"
        (self.case_dir / "result.json").write_text(json.dumps(self.result, indent=2, default=str))
        return status
