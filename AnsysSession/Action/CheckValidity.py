"""Validity check of the active design: AEDT's own Validation Check
(Simulation > Validation Check, oDesign.ValidateDesign)."""

from pathlib import Path

from .Action import AnsysAction
from .Export import file_stem


class CheckValidity(AnsysAction):
    """AEDT's Validation Check; ``act()`` returns SUCCESS when the design passes.

    The messages AEDT writes (geometry, boundaries and excitations, mesh,
    analysis setup) end up in ``self.messages``, and in ``self.error`` on failure.
    """

    def __init__(self, app):
        super().__init__(app, "Check_validity")
        self.messages = []

    def act(self):
        app = self.app
        log_file = Path(app.working_directory) / f"{file_stem(app.design_name)}_validation.log"
        log_file.unlink(missing_ok=True)
        passed = app.validate_simple(log_file) == 1
        if log_file.is_file():
            self.messages = [line.rstrip() for line in log_file.read_text(errors="replace").splitlines() if line.strip()]

        if not passed:
            details = "\n".join(self.messages) or f"see {log_file}"
            self.error = f'AEDT validation check failed for design "{app.design_name}":\n{details}'
            return self.FAILURE
        return self.SUCCESS

