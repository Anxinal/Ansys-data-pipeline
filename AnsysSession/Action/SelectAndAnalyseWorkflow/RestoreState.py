import json
from pathlib import Path

from ..Action import AnsysAction


class RestoreState(AnsysAction):
    """Put back the model flags and pin expressions saved in ``state_file``; ``result`` is the updated state."""

    def __init__(self, session, state_file):
        super().__init__(session, "Restore_State")
        self.state_file = Path(state_file)

    def act(self):
        session, state, errors = self.session, json.loads(self.state_file.read_text()), []
        # Restore geometry participation first, before moving terminals back.
        for names, enabled in ((state["non_model_objects"], False), (state["model_objects"], True)):
            try:
                session.set_model_state(names, enabled)
            except Exception as e:
                errors.append(f"model flags: {e}")
        for name, expression in state["pin_expressions"].items():
            try:
                session.set_pin_expression(name, expression)
            except Exception as e:
                errors.append(f"{name}: {e}")
        state.update(restored=not errors, restore_errors=errors)
        self.state_file.write_text(json.dumps(state, indent=2))
        session.refresh()
        self.result = state
        if errors:
            self.error = f"restoration failed; recovery data in {self.state_file}: {errors}"
            return self.FAILURE
        return self.SUCCESS
