#!/bin/bash
# Serve the racing dashboard on port 8081.
cd "$(dirname "$0")"
exec venv/bin/python3 -m http.server 8081 --bind 0.0.0.0 --directory dashboard
