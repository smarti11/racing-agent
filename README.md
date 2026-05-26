# Horse Racing Research Agent — Phase 1

## What it does
- Fetches daily entries for all US Thoroughbred tracks from Equibase
- Monitors scratches every 30 minutes
- Updates odds from TVG and TwinSpires every 15 minutes
- Generates a mobile-friendly dashboard accessible on your iPhone

## Setup

### 1. Create project folder on your Mac mini
```bash
mkdir ~/Documents/racing-agent
cd ~/Documents/racing-agent
```

### 2. Copy all files into the folder maintaining this structure:
```
racing-agent/
├── racing_agent.py          ← main entry point
├── requirements.txt
├── config/settings.py
├── data/equibase.py
├── data/odds.py
├── db/database.py
├── dashboard/builder.py
└── logs/                    ← auto-created
```

### 3. Set up Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Create __init__.py files
```bash
touch config/__init__.py data/__init__.py db/__init__.py dashboard/__init__.py
```

### 5. Test it
```bash
# See today's active tracks
python racing_agent.py --tracks

# Fetch entries and generate dashboard
python racing_agent.py --once

# Print today's card to terminal
python racing_agent.py --card

# Run continuously (updates every 15 min)
python racing_agent.py
```

### 6. View on iPhone
The dashboard saves to dashboard/racing.html
Serve it on port 8081 (different from trading agent on 8080):
```bash
python3 -m http.server 8081 --bind 0.0.0.0 --directory ~/Documents/racing-agent/dashboard &
```

Then on iPhone: http://100.68.82.83:8081/racing.html

## Phase 2 (coming next)
- Speed figure calculation from past performances
- Handicapping score for each horse
- Automated pick suggestions
- Pick tracker with ROI calculation
- Pace scenario modeling
