#!/usr/bin/env python3
"""Run from ~/Documents/racing-agent to fix the distance parser."""
import re

code = open('data/chart_parser.py').read()

old_func_start = 'def parse_distance_to_yards(text):'
old_func_end = '    return int(round(total)) if total > 0 else None'

start_idx = code.index(old_func_start)
end_idx = code.index(old_func_end) + len(old_func_end)

new_func = """def parse_distance_to_yards(text):
    if not text:
        return None
    t = text.lower().strip()
    DIST_LOOKUP = {
        'two furlongs': 440,
        'three furlongs': 660,
        'three and one half furlongs': 770,
        'four furlongs': 880,
        'four and one half furlongs': 990,
        'five furlongs': 1100,
        'five and one half furlongs': 1210,
        'five and one-half furlongs': 1210,
        'six furlongs': 1320,
        'six and one half furlongs': 1430,
        'six and one-half furlongs': 1430,
        'seven furlongs': 1540,
        'seven and one half furlongs': 1650,
        'one mile': 1760,
        'one mile and forty yards': 1800,
        'one mile and seventy yards': 1830,
        'one mile and one sixteenth': 1870,
        'one mile and one eighth': 1980,
        'one and one sixteenth miles': 1870,
        'one and one eighth miles': 1980,
        'one and three sixteenths miles': 2090,
        'one and one quarter miles': 2200,
        'one and one half miles': 2640,
        'one and three quarters miles': 3080,
        'two miles': 3520,
    }
    for pattern, yards in DIST_LOOKUP.items():
        if pattern in t:
            return yards
    m = re.match(r'(\\d+(?:\\.\\d+)?)\\s*(furlongs?|miles?|yards?)', t)
    if m:
        val = float(m.group(1))
        unit = m.group(2).lower()
        if 'furlong' in unit:
            return int(round(val * 220))
        elif 'mile' in unit:
            return int(round(val * 1760))
        elif 'yard' in unit:
            return int(round(val))
    return None"""

code = code[:start_idx] + new_func + code[end_idx:]
open('data/chart_parser.py', 'w').write(code)
print('Distance parser fixed with lookup table')
