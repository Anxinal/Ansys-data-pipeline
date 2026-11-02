"""Capture the state required to undo a temporary root-design selection."""
import json
from pathlib import Path
from configs import BACKGROUND_MATERIALS, PIN_COUNT_VARIABLES


def capture(session, selected, state_file):
    names, modeled = session.model_objects()
    background = session.objects_with_materials(BACKGROUND_MATERIALS) & modeled
    active = set(selected) | background
    if not active <= names:
        raise LookupError(f"Objects missing from root design: {sorted(active-names)}")
    state = {"project":str(Path(session.path).resolve()),"design":session.design,
             "model_objects":sorted(modeled),"non_model_objects":sorted(names-modeled),
             "pin_expressions":{n:session.variable_value(n) for n in PIN_COUNT_VARIABLES.values()},
             "selected":sorted(selected),"background":sorted(background),"restored":False}
    state_file = Path(state_file)
    state_file.parent.mkdir(parents=True,exist_ok=True)
    state_file.write_text(json.dumps(state,indent=2))
    return state, modeled, active
