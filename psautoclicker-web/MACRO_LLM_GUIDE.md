# PSAutoClicker LLM Macro Guide

This guide is designed for Large Language Models (LLMs) and prompt engineers to generate valid macros for PSAutoClicker. It describes the macro format, all valid button and stick codes, stick directions, best practices for creating robust macros—including how and when to return sticks to neutral—and now supports **comments for each step and macro-level documentation**.

---

## Macro Step Format

Each macro is a list of steps. **Each step can now include multiple actions performed simultaneously, and an optional comment.**

- **Single action:**
  - For buttons: `["BUTTON_CODE", delay_ms, "optional comment"]`
  - For sticks: `[("STICK_CODE", "DIRECTION", magnitude), delay_ms, "optional comment"]`
  - For autoclickers: `[{...}, delay_ms, "optional comment"]`
- **Simultaneous actions:**
  - `[[action1, action2, ...], delay_ms, "optional comment"]`
  - Each `action` can be a button code (string), a stick tuple, or an autoclicker dict.
- **Backward compatible:** If no comment is provided, the step can be `[action, delay_ms]` as before.

Where `delay_ms` is the time to wait after the step, in milliseconds.

**Both main macro steps and end-of-loop macros support simultaneous actions and comments.**

---

## Macro-Level Description

You can add a `"description"` field to the macro JSON for overall documentation or usage notes.

Example:
```json
{
  "name": "MyMacro",
  "description": "Farming macro for XP and gold. Loops 10 times, then resets.",
  "steps": [ ... ],
  ...
}
```

---

## Button Codes

The following button codes are supported:
- UP, DOWN, LEFT, RIGHT
- CROSS, CIRCLE, SQUARE, TRIANGLE
- L1, L2, L3, R1, R2, R3
- OPTIONS, SHARE, PS, TOUCHPAD

Example:
```json
["CROSS", 100, "Jump over obstacle"]
```

Simultaneous example:
```json
[["CROSS", "CIRCLE"], 150, "Press both to trigger glitch"]
```

---

## Stick Codes and Directions

Sticks:
- LEFT_STICK
- RIGHT_STICK

Directions:
- UP
- DOWN
- LEFT
- RIGHT
- NEUTRAL

Magnitude:
- A float between 0.0 and 1.0 (or -1.0 for opposite direction)
- 1.0 = full push, 0.5 = half push, 0.0 = neutral

Examples:
```json
[["LEFT_STICK", "UP", 1.0], 100, "Move forward"]
[["RIGHT_STICK", "LEFT", 0.5], 200, "Strafe left"]
[["LEFT_STICK", "NEUTRAL", 0.0], 50, "Return to center"]
```

Simultaneous stick and button example:
```json
[[["LEFT_STICK", "UP", 1.0], "CROSS"], 120, "Jump while moving forward"]
```

---

### Returning Sticks to Neutral
- **ALWAYS** return a stick to neutral after a movement, unless you want it held for the next step.
- To return to neutral, add a step: `[("LEFT_STICK", "NEUTRAL", 0.0), delay_ms, "Return to neutral"]` (or RIGHT_STICK)
- The delay after a neutral step can be short (e.g., 50ms) or as needed.

**Example: Move stick up for 200ms, then neutral:**
```json
[["LEFT_STICK", "UP", 1.0], 200, "Move forward"]
[["LEFT_STICK", "NEUTRAL", 0.0], 50, "Return to center"]
```

Simultaneous neutral example:
```json
[[["LEFT_STICK", "NEUTRAL", 0.0], ["RIGHT_STICK", "NEUTRAL", 0.0]], 50, "Reset both sticks"]
```

---

## Full Macro Example

```json
{
  "name": "DemoMacro",
  "description": "Demonstrates comments and simultaneous actions.",
  "steps": [
    ["CROSS", 100, "Jump"],
    [["LEFT_STICK", "UP", 1.0], 300, "Move forward"],
    [["LEFT_STICK", "NEUTRAL", 0.0], 50, "Return to center"],
    ["CIRCLE", 100, "Roll"],
    [["RIGHT_STICK", "RIGHT", 0.7], 150, "Camera right"],
    [["RIGHT_STICK", "NEUTRAL", 0.0], 50, "Camera center"],
    // Simultaneous actions:
    [["L1", "R1", ["LEFT_STICK", "LEFT", 1.0]], 200, "Special move: L1+R1+left"],
    [[["LEFT_STICK", "NEUTRAL", 0.0], ["RIGHT_STICK", "NEUTRAL", 0.0]], 50, "Reset sticks"]
  ]
}
```

---

## Editing and Viewing Simultaneous Steps and Comments in the GUI
- In the Macro Manager, you can add a comment for each step in the Add/Edit Step dialog.
- The actions for the step are shown in a list, and you can remove any before confirming.
- Simultaneous steps are displayed as "Simultaneous: [action1, action2, ...]" in the macro steps list, and comments are shown in a new column or as tooltips.
- You can edit any step to add or remove simultaneous actions and update the comment.
- Macro-level descriptions are shown in the macro details or preview.

---

## Best Practices for LLM Macro Generation
- **Always** return sticks to neutral after a movement unless you want to hold the direction.
- Use realistic delays (100-300ms for button presses, 50-200ms for stick moves, adjust for game needs).
- Use only the codes and directions listed above.
- For autoclickers, use the format:
  ```json
  [{"type": "autoclicker", "button": "SQUARE", "interval": 50, "duration": null}, 0, "Spam SQUARE"]
  ```
- Mix and match button, stick, and autoclicker steps as needed.
- Each step is a tuple: `[action, delay_ms, "optional comment"]` or `[[action1, action2, ...], delay_ms, "optional comment"]` for simultaneous actions.
- For simultaneous actions, all actions in the list are performed at the same time.
- Both main macro steps and end-of-loop macros support simultaneous actions and comments.
- **Use comments to explain the purpose of each step for clarity and better AI prompt engineering.**

---

## Prompt Template for LLMs

> Generate a macro for PSAutoClicker that does the following: [describe your sequence]. Use only the valid button and stick codes. Always return sticks to neutral after movement. Output as a JSON array of steps, each as `[action, delay_ms, "optional comment"]` or `[[action1, action2, ...], delay_ms, "optional comment"]` for simultaneous actions. Add comments to explain each step.

--- 