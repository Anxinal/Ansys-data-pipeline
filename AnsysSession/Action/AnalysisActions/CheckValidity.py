"""Validity check of the active design: AEDT's own Validation Check
(Simulation > Validation Check, oDesign.ValidateDesign), run through Session.valid_check."""

from ..Action import AnsysAction


class CheckValidity(AnsysAction):
    """AEDT's Validation Check; ``act()`` returns SUCCESS when the design passes.

    The messages AEDT writes (geometry, boundaries and excitations, mesh,
    analysis setup) end up in ``self.messages``, and in ``self.error`` on failure.
    """

    def __init__(self, session):
        super().__init__(session, "Check_validity")
        self.messages = []

    def act(self):
        passed, self.messages, log_file = self.session.valid_check()
        if not passed:
            details = "\n".join(self.messages) or f"see {log_file}"
            self.error = f'AEDT validation check failed for design "{self.session.design}":\n{details}'
            return self.FAILURE
        return self.SUCCESS
