"""Run existing placement, validation and Bz actions inside temporary isolation."""
import json
from pathlib import Path
from configs import PIN_COUNT_VARIABLES
from .RootSelection import root_selection
from .KeepSession import keep_session_on_error
from .Action.SetTerminalPositions import SetTerminalPositions
from .Action.CheckValidity import CheckValidity
from .Action.BzProcedure import BzProcedure


def run_case(session, candidate, settings, case_dir):
    section, case_dir = candidate.section, Path(case_dir)
    selected = [section.board.name,section.gnd.name,section.vcc.name,*[s.name for s in section.spheres]]
    case_dir.mkdir(parents=True,exist_ok=True)
    state_file = case_dir/"original_state.json"
    result = {"design":session.design,"board":section.board.name,"workflow":"root",
              "VCC pin count":candidate.pair.a.value,"GND pin count":candidate.pair.b.value}
    try:
        with keep_session_on_error(), root_selection(session,selected,state_file):
            print(f"Setting PinCount={candidate.pair.a.value}, PinCountGND={candidate.pair.b.value}",flush=True)
            SetTerminalPositions(session.app,section,candidate.pair).run()
            actual = {n:str(session.app.odesign.GetVariableValue(n)) for n in PIN_COUNT_VARIABLES.values()}
            print(f"Live pin counts: {actual}",flush=True)
            print("Validating isolated root section",flush=True)
            CheckValidity(session.app).run()
            result.update(BzProcedure(session.app,section.board,setup=settings.DEFAULT_SETUP,
                output_dir=case_dir,scan_height=settings.DEFAULT_SCAN_HEIGHT,
                step=settings.DEFAULT_GRID_STEP,cores=settings.CORES,solve=settings.SOLVE).run())
            result["status"] = "success"
    except Exception as error:
        result.update(status="failed",error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["restoration"] = json.loads(state_file.read_text()) if state_file.exists() else None
        (case_dir/"result.json").write_text(json.dumps(result,indent=2,default=str))
        if result["restoration"] and result["restoration"]["restored"]:
            session.save()
    return result
