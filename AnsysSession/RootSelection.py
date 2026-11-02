"""Scope the temporary model selection; restoration always runs on exit."""
from contextlib import contextmanager
from .RootState import capture
from .RootRestore import restore


@contextmanager
def root_selection(session, selected, state_file):
    state, modeled, active = capture(session,selected,state_file)
    try:
        print(f"Root isolation: {len(active)} modeled objects; disabling {len(modeled-active)} others",flush=True)
        session.editor.set_model_state(sorted(modeled-active),False)
        session.editor.set_model_state(sorted(active-modeled),True)
        yield state
    finally:
        restore(session,state,state_file)
