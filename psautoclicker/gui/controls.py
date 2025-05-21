# User-friendly manual controls layout for PlayStation
# Each group: label and list of (display_name, button_code) or (display_name, (stick, direction, magnitude))

MANUAL_CONTROLS = [
    {"label": "D-Pad", "buttons": [
        ("Up", "UP"),
        ("Down", "DOWN"),
        ("Left", "LEFT"),
        ("Right", "RIGHT"),
    ]},
    {"label": "Face Buttons", "buttons": [
        ("Cross (X)", "CROSS"),
        ("Circle (O)", "CIRCLE"),
        ("Square", "SQUARE"),
        ("Triangle", "TRIANGLE"),
    ]},
    {"label": "Shoulders & Triggers", "buttons": [
        ("L1", "L1"), ("L2", "L2"), ("L3", "L3"),
        ("R1", "R1"), ("R2", "R2"), ("R3", "R3"),
    ]},
    {"label": "System", "buttons": [
        ("Options", "OPTIONS"),
        ("Share", "SHARE"),
        ("PS", "PS"),
        ("Touchpad", "TOUCHPAD"),
    ]},
    {"label": "Left Stick", "buttons": [
        ("LS Up", ("LEFT_STICK", "UP", 1.0)),
        ("LS Down", ("LEFT_STICK", "DOWN", 1.0)),
        ("LS Left", ("LEFT_STICK", "LEFT", 1.0)),
        ("LS Right", ("LEFT_STICK", "RIGHT", 1.0)),
        ("LS Neutral", ("LEFT_STICK", "NEUTRAL", 0.0)),
    ]},
    {"label": "Right Stick", "buttons": [
        ("RS Up", ("RIGHT_STICK", "UP", 1.0)),
        ("RS Down", ("RIGHT_STICK", "DOWN", 1.0)),
        ("RS Left", ("RIGHT_STICK", "LEFT", 1.0)),
        ("RS Right", ("RIGHT_STICK", "RIGHT", 1.0)),
        ("RS Neutral", ("RIGHT_STICK", "NEUTRAL", 0.0)),
    ]},
] 