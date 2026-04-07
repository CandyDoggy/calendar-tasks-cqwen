# Calendar & Tasks

A Google Calendar / Microsoft Calendar style app with task management, notes, and mail integration.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.2+-green.svg)
![Status](https://img.shields.io/badge/Status-Development-orange)

🌐 **[Try Web Version →](https://candydoggy.github.io/calendar-tasks/)**

---

## ✨ Features

### 📅 Calendar
- **Month, Week, Day views** - Google Calendar style interface
- **Mini calendar** in sidebar for quick navigation
- **Event creation** with title, description, location, time, color, reminders
- **Recurring events** support
- **Color-coded** events

### ✅ Tasks
- **Task management** with priority levels (Low, Medium, High, Urgent)
- **Due dates** and categories
- **Check/uncheck** tasks
- **Sort by** due date and priority

### 📝 Notes
- **Google Keep style** notes with colored cards
- **Pin notes** to top
- **Rich text** support

### 📧 Mail
- **Send emails** via Gmail or Outlook
- **Compose** with subject, body, recipients
- **Mail history** logging

### 🔐 Account System
- **Google OAuth** integration
- **Microsoft OAuth** integration
- **Email/Password** authentication
- **JWT** based sessions

### 🎨 Themes
- **Dark mode** - Modern dark interface
- **Light mode** - Clean bright interface
- **Theme persistence** via localStorage/settings

---

## 📦 Installation

### Desktop App

```bash
cd calendar-tasks/desktop
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Web Version

Open `web/index.html` in your browser or deploy to GitHub Pages.

---

## 🚀 Usage

### Desktop
```bash
python main.py
```

### Web
Access at: `https://candydoggy.github.io/calendar-tasks/`

---

## 📁 Project Structure

```
calendar-tasks/
├── desktop/                 # Desktop app (Python + CustomTkinter)
│   ├── main.py             # Entry point
│   ├── requirements.txt    # Python dependencies
│   ├── api/
│   │   └── server.py       # Flask API server
│   ├── db/
│   │   └── database.py     # SQLite database layer
│   └── ui/
│       └── main_ui.py      # CustomTkinter UI
├── web/                    # Web version
│   ├── index.html          # Main HTML
│   ├── css/
│   │   └── styles.css      # All themes + responsive
│   └── js/
│       └── app.js          # Main application logic
└── README.md
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Desktop UI | Python + CustomTkinter |
| Web UI | HTML/CSS/JavaScript (vanilla) |
| Backend API | Flask + SQLite |
| Auth | Google OAuth, Microsoft OAuth, bcrypt |
| Mail | Gmail API, Microsoft Graph API |

---

## 🔗 API Endpoints

### Authentication
- `POST /api/auth/register` - Register with email/password
- `POST /api/auth/login` - Login with email/password
- `POST /api/auth/google` - Google OAuth
- `POST /api/auth/microsoft` - Microsoft OAuth

### Events
- `GET /api/events` - List events
- `POST /api/events` - Create event
- `PUT /api/events/<id>` - Update event
- `DELETE /api/events/<id>` - Delete event

### Tasks
- `GET /api/tasks` - List tasks
- `POST /api/tasks` - Create task
- `PUT /api/tasks/<id>` - Update task

### Notes
- `GET /api/notes` - List notes
- `POST /api/notes` - Create note

### Settings
- `GET /api/settings` - Get settings
- `PUT /api/settings` - Update settings

---

## 🤝 Contributing

Contributions welcome! Feel free to:
1. **Report bugs** - Open an issue
2. **Suggest features** - Share your ideas
3. **Submit PRs** - Help improve the codebase

---

## 📄 License

MIT License
