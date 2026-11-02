"""Remove the GND base's one-column offset without changing pin row numbering."""
from configs import DEFAULT_GND, DEFAULT_SPEHRE
from .Action import AnsysAction

OLD_X = "(mod(PinCountGND,yballcount))*xballshift"
NEW_X = "(mod(PinCountGND,yballcount)-1)*xballshift"


class CorrectGroundOffset(AnsysAction):
    def __init__(self, app):
        super().__init__(app, "Correct_GND_Offset")

    def act(self):
        native, plans = self.app.modeler.oeditor, []
        names = [DEFAULT_GND, next(s for s in DEFAULT_SPEHRE if "gnd" in s.lower())]
        for name in names:
            history = native.GetChildObject(name)
            matches = []
            for operation in history.GetChildNames():
                node = history.GetChildObject(operation)
                if str(operation).startswith("Move:"):
                    vector = [str(node.GetPropValue(f"Move Vector/{a}")) for a in "XYZ"]
                    if "PinCountGND" in vector[0]:
                        matches.append((name, str(operation), vector))
            if len(matches) != 1 or matches[0][2][0] not in (OLD_X, NEW_X):
                raise ValueError(f"Unexpected GND movement on {name}; no offset edit applied")
            plans.extend(matches)
        changed = []
        try:
            for name, operation, vector in plans:
                changed.append((name, operation, vector))
                self.editor.set_move_vector(name, operation, [NEW_X, *vector[1:]])
        except Exception:
            for name, operation, vector in reversed(changed):
                self.editor.set_move_vector(name, operation, vector)
            raise
        self.result = {"objects": names, "x_expression": NEW_X,
                       "before": plans, "row_expression_changed": False}
        return self.SUCCESS
