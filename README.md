# Skippy YAML Builder v4 – Grid Layout Edition

Includes:
- Two-column form layout
- Responsive font control
- Modular section grouping
- Map Embed, Services, Cities, and Broker fields refactored to right column

To run, double-click `run.cmd` (or run it from a terminal) -- it creates
`venv\` if it doesn't already exist, installs/updates dependencies, and
launches the app:
```cmd
run.cmd
```

Or manually, one command at a time in an interactive shell:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

To run tests:
```bash
venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```
