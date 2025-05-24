@staticmethod
def from_dict(d):
    def convert_step(step):
        # If it's a list of actions (simultaneous), recurse
        if isinstance(step, list):
            # Simultaneous actions: list of actions (not a stick or button)
            if step and all(isinstance(x, (list, dict, tuple)) for x in step):
                return [convert_step(x) for x in step]
            # Stick: ["LEFT_STICK"/"RIGHT_STICK", direction, magnitude]
            if len(step) == 3 and step[0] in ("LEFT_STICK", "RIGHT_STICK"):
                return tuple(step)
            # Button: single value (should be str/int)
            return step
        return step
    def convert_steps(steps):
        # Each step is (code, delay, [comment])
        out = []
        for s in steps:
            if isinstance(s, (list, tuple)):
                if len(s) == 3:
                    code, delay, comment = s
                    out.append((convert_step(code), delay, comment))
                elif len(s) == 2:
                    code, delay = s
                    out.append((convert_step(code), delay))
                else:
                    out.append(s)
            else:
                out.append(s)
        return out
    return Macro(
        d["name"],
        convert_steps(d["steps"]),
        convert_steps(d.get("end_of_loop_macro", [])),
        d.get("end_of_loop_macro_name"),
        d.get("description"),
    ) 