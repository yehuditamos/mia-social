STEPS = [
    {"key": "welcome_message",       "save_to": ("user",     "name")},
    {"key": "ask_brand",             "save_to": ("business", "brand_name")},
    {"key": "ask_what_you_do",       "save_to": ("business", "what_you_do")},
    {"key": "ask_style",             "save_to": ("business", "writing_style")},
    {"key": "ask_planning_schedule", "save_to": ("business", "planning_schedule")},
    {"key": "ask_accessibility",     "save_to": ("user",     "accessibility")},
]

NUM_STEPS = len(STEPS)
