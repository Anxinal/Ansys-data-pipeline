"""Remove the GND base's one-column offset without changing pin row numbering."""
from configs import DEFAULT_GND, DEFAULT_SPEHRE
from .Action import AnsysAction

OLD_X = "(mod(PinCountGND,yballcount))*xballshift"
NEW_X = "(mod(PinCountGND,yballcount)-1)*xballshift"


class CorrectGroundOffset(AnsysAction):
    def __init__(self, session):
        super().__init__(session, "Correct_GND_Offset")

    def act(self):
        plans = []
        names = [DEFAULT_GND, next(s for s in DEFAULT_SPEHRE if "gnd" in s.lower())]
        for name in names:
            matches = [(name, operation, vector) for operation, vector in self.session.move_operations(name)
                       if "PinCountGND" in vector[0]]
            if len(matches) != 1 or matches[0][2][0] not in (OLD_X, NEW_X):
                raise ValueError(f"Unexpected GND movement on {name}; no offset edit applied")
            plans.extend(matches)
        changed = []
        try:
            for name, operation, vector in plans:
                changed.append((name, operation, vector))
                self.session.set_move_vector(name, operation, [NEW_X, *vector[1:]])
        except Exception:
            for name, operation, vector in reversed(changed):
                self.session.set_move_vector(name, operation, vector)
            raise
        self.result = {"objects": names, "x_expression": NEW_X,
                       "before": plans, "row_expression_changed": False}
        return self.SUCCESS
