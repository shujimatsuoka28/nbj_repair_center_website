# NBJ Electronics Repair Center — Monitoring System

## Requirements
- Python 3.8 or newer
- Visual Studio Code (or any text editor)

---

## Setup Instructions

### Step 1 — Install Python
Download from https://python.org and install (check "Add to PATH").

### Step 2 — Open the project in VS Code
Open the `nbj_repair` folder in VS Code.

### Step 3 — Open a terminal
In VS Code: `Terminal > New Terminal`

### Step 4 — Install Flask
```
pip install flask
```

### Step 5 — Run the app
```
python app.py
```

### Step 6 — Open in browser
Go to: http://localhost:5000

---

## Login Credentials

| Role  | Username | Password |
|-------|----------|----------|
| Admin | admin    | 1234     |

Customers use accounts created by the admin.

---

## Features
- Admin dashboard with repair stats
- Add new repair jobs with auto tracking number (NBJ-XXXXXXXX)
- Update repair status: Received → Diagnosing → Repairing → Waiting for Parts → Completed → Released
- Customer accounts management
- Customer login to view their own repairs
- Track any repair by tracking number (no login needed)
- Full repair history with filters

---

## Project Files
```
nbj_repair/
├── app.py                   ← Main Python/Flask app
├── requirements.txt         ← Dependencies
├── nbj_repair.db            ← SQLite database (auto-created)
└── templates/
    ├── base.html            ← Shared layout
    ├── login.html           ← Login page
    ├── dashboard.html       ← Admin dashboard
    ├── add_repair.html      ← Add repair form
    ├── repair_history.html  ← All repairs table
    ├── repair_detail.html   ← Single repair view
    ├── manage_accounts.html ← Customer accounts
    ├── customer_dashboard.html ← Customer repair view
    └── track.html           ← Public tracking page
```
