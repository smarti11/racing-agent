import re

with open('db/database.py', 'r') as f:
    db_text = f.read()

if 'import pytz' not in db_text:
    db_text = db_text.replace(
        'from datetime import datetime',
        'from datetime import datetime\nimport pytz\nEASTERN = pytz.timezone("US/Eastern")'
    )

db_text = db_text.replace(
    'today = datetime.now().date().isoformat()',
    'today = datetime.now(EASTERN).date().isoformat()'
)

with open('db/database.py', 'w') as f:
    f.write(db_text)
print('FIX 1 done')

with open('racing_agent.py', 'r') as f:
    agent_text = f.read()

agent_text = agent_text.replace(
    'today = datetime.now().date().isoformat()',
    'today = datetime.now(pytz.timezone("US/Eastern")).date().isoformat()'
)

with open('racing_agent.py', 'w') as f:
    f.write(agent_text)
print('FIX 2 done')
