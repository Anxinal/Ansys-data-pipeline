"""Restore all recorded model flags and pin expressions, including after failure."""
import json
from pathlib import Path


def restore(session, state, state_file):
    errors = []
    # Restore geometry participation first, before moving terminals back.
    for names, enabled in [(state["non_model_objects"],False),(state["model_objects"],True)]:
        try:
            session.editor.set_model_state(names,enabled)
        except Exception as error:
            errors.append(f"model flags: {error}")
    for name, expression in state["pin_expressions"].items():
        try:
            session.editor.set_pin_expression(name,expression)
        except Exception as error:
            errors.append(f"{name}: {error}")
    state.update(restored=not errors,restore_errors=errors)
    Path(state_file).write_text(json.dumps(state,indent=2))
    session.refresh()
    if errors:
        raise RuntimeError(f"Root restoration failed; recovery data in {state_file}: {errors}")
    print("Restored original model flags and pin expressions",flush=True)
