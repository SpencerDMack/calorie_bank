# Calorie Bank

A simple, local-first Streamlit app for tracking calories, estimating weight change, and staying on pace toward your goal.

## Features
- Profile setup with goal type (lose/gain) and target weight
- Daily calorie logging with optional notes
- Progress chart with min/max highlights and hover details
- Weekly check-ins and editable entries
- Simulation tab to explore "what if" scenarios

## Quick Start (Windows)
1. Open PowerShell and go to the project folder:
   ```powershell
   cd C:\Users\Spencer\Downloads\codex_apps\calorie_bank_repo
   ```
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install requirements:
   ```powershell
   pip install -r requirements.txt
   ```
4. Run the app:
   ```powershell
   streamlit run app.py
   ```

## One-Click Launcher (Windows)
If you prefer a double-click launcher, use:
`run_calorie_bank.bat`

## Data Storage
All data is stored locally in `user_data.db`. This file is ignored by Git so your personal data is not committed.

## Screenshots
Add screenshots here to showcase the app:
- `docs/screenshots/dashboard.png`
- `docs/screenshots/entries.png`
- `docs/screenshots/simulation.png`

## License
MIT License. See `LICENSE`.
