# Skippy YAML Builder v4 – Grid Layout Edition

Includes:
- Two-column form layout
- Responsive font control
- Modular section grouping
- Map Embed, Services, Cities, and Broker fields refactored to right column

To run:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
## Changelog – v4.2

- Replaced flat address & broker with nested YAML structure
- Fixed field mapping for address on load
- Added custom styles to Save YAML button
- Adjusted layout for better alignment and UX
- Added Close to File menu
- Open YAML now defaults to /client_yaml/
