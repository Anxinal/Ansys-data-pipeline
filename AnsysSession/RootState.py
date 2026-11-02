"""Capture the state required to undo a temporary root-design selection."""
import json
from pathlib import Path
from configs import BACKGROUND_MATERIALS, PIN_COUNT_VARIABLES, TYPE_GROUPS


def capture(session, selected, state_file):
    native = session.app.modeler.oeditor
    names = {str(n) for group in TYPE_GROUPS for n in native.GetObjectsInGroup(group)}
    modeled = names-set(native.GetObjectsInGroup("Non Model"))
    background = {str(n) for m in BACKGROUND_MATERIALS for n in native.GetObjectsByMaterial(m)} & modeled
    active = set(selected) | background
    if not active <= names:
        raise LookupError(f"Objects missing from root design: {sorted(active-names)}")
    state = {"project":str(Path(session.path).resolve()),"design":session.design,
             "model_objects":sorted(modeled),"non_model_objects":sorted(names-modeled),
             "pin_expressions":{n:str(session.app.odesign.GetVariableValue(n)) for n in PIN_COUNT_VARIABLES.values()},
             "selected":sorted(selected),"background":sorted(background),"restored":False}
    state_file = Path(state_file)
    state_file.parent.mkdir(parents=True,exist_ok=True)
    state_file.write_text(json.dumps(state,indent=2))
    return state, modeled, active
