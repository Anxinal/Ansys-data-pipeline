"""Validity check of the active design: AEDT's own Validation Check
(Simulation > Validation Check, oDesign.ValidateDesign), run through DesignReader.valid_check."""

from .Action import AnsysAction


class CheckValidity(AnsysAction):
    """AEDT's Validation Check; ``act()`` returns SUCCESS when the design passes.

    The messages AEDT writes (geometry, boundaries and excitations, mesh,
    analysis setup) end up in ``self.messages``, and in ``self.error`` on failure.
    """

    def __init__(self, app):
        super().__init__(app, "Check_validity")
        self.messages = []

    def act(self):
        passed, self.messages, log_file = self.reader.valid_check()
        if not passed:
            details = "\n".join(self.messages) or f"see {log_file}"
            self.error = f'AEDT validation check failed for design "{self.app.design_name}":\n{details}'
            return self.FAILURE
        return self.SUCCESS
