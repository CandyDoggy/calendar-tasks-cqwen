"""
Main UI for Calendar & Tasks app.
Google Calendar / Microsoft Calendar style interface.

Full-featured desktop client with:
- Auth system (email/password, Google OAuth, Microsoft OAuth)
- Calendar view with event CRUD, recurrence, reminders
- Tasks with priorities, filtering, sorting
- Notes (Google Keep style) with pinning, colors
- Mail view with compose, inbox, sent history
- Integration with Google Calendar, Microsoft Outlook, Gmail, Graph Mail
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, colorchooser
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
import calendar
import requests
import json
import os
import webbrowser

API_URL = "http://localhost:5000/api"

THEMES = {
    "dark": {
        "name": "Dark",
        "bg": "#202020",
        "sidebar": "#1a1a1a",
        "card": "#2d2d2d",
        "button": "#3b3b3b",
        "button_hover": "#4a4a4a",
        "accent": "#60cdff",
        "accent_hover": "#7dd5ff",
        "text": "#ffffff",
        "text_secondary": "#a0a0a0",
        "border": "#404040",
    },
    "light": {
        "name": "Light",
        "bg": "#f3f3f3",
        "sidebar": "#e8e8e8",
        "card": "#ffffff",
        "button": "#f6f6f6",
        "button_hover": "#e9e9e9",
        "accent": "#0078d4",
        "accent_hover": "#106ebe",
        "text": "#1a1a1a",
        "text_secondary": "#666666",
        "border": "#e0e0e0",
    },
}

PRIORITY_COLORS = {0: "#60cdff", 1: "#ffd43b", 2: "#ff922b", 3: "#ff4444"}
PRIORITY_NAMES = {0: "Low", 1: "Medium", 2: "High", 3: "Urgent"}
NOTE_COLORS = [
    "#ffffff", "#f87171", "#fb923c", "#fbbf24", "#a3e635",
    "#34d399", "#60cdff", "#818cf8", "#c084fc", "#f472b6",
]
SOURCE_BADGES = {
    "google": {"text": "Google", "bg": "#4285f4", "fg": "#ffffff"},
    "microsoft": {"text": "Outlook", "bg": "#0078d4", "fg": "#ffffff"},
    "local": {"text": "Local", "bg": "#6b7280", "fg": "#ffffff"},
}


# ======================================================================
# API Helper
# ======================================================================

class APIClient:
    """Thin wrapper around the Flask REST API."""

    def __init__(self, base_url=API_URL):
        self.base = base_url.rstrip("/")
        self.token = None

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _url(self, path):
        return f"{self.base}/{path.lstrip('/')}"

    def get(self, path, params=None):
        try:
            r = requests.get(self._url(path), headers=self._headers(), params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            try:
                return {"error": r.json().get("error", str(e))}
            except Exception:
                return {"error": str(e)}
        except requests.RequestException as e:
            return {"error": f"Connection error: {e}"}

    def post(self, path, data=None):
        try:
            r = requests.post(self._url(path), headers=self._headers(), json=data, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            try:
                return {"error": r.json().get("error", str(e))}
            except Exception:
                return {"error": str(e)}
        except requests.RequestException as e:
            return {"error": f"Connection error: {e}"}

    def put(self, path, data=None):
        try:
            r = requests.put(self._url(path), headers=self._headers(), json=data, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            try:
                return {"error": r.json().get("error", str(e))}
            except Exception:
                return {"error": str(e)}
        except requests.RequestException as e:
            return {"error": f"Connection error: {e}"}

    def delete(self, path):
        try:
            r = requests.delete(self._url(path), headers=self._headers(), timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            try:
                return {"error": r.json().get("error", str(e))}
            except Exception:
                return {"error": str(e)}
        except requests.RequestException as e:
            return {"error": f"Connection error: {e}"}


# ======================================================================
# Main Application
# ======================================================================

class CalendarTasksUI(ctk.CTk):
    """Main Calendar & Tasks Application."""

    def __init__(self):
        super().__init__()

        self.api = APIClient()
        self.current_theme = "dark"
        self.current_view = "calendar"
        self.current_user = None
        self.selected_date = datetime.now()

        # Cached data
        self.events = []
        self.tasks = []
        self.notes = []
        self.mail_messages = []
        self.sent_mail = []

        # Filters
        self.task_filter = "all"          # all, pending, completed
        self.task_sort = "due_date"        # due_date, priority
        self.note_search = ""

        # File paths
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.settings_file = os.path.join(self.base_dir, "desktop", "settings.json")

        self._load_settings()
        self._restore_session()

        self.title("Calendar & Tasks")
        self.geometry("1400x800")
        self.minsize(1000, 600)

        self._setup_ui()

    # ------------------------------------------------------------------
    # Settings / Session persistence
    # ------------------------------------------------------------------

    def _load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                    self.current_theme = data.get("theme", "dark")
        except Exception:
            pass

    def _save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump({"theme": self.current_theme}, f)
        except Exception:
            pass

    def _save_session(self):
        try:
            with open(self.settings_file, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["theme"] = self.current_theme
        if self.current_user and self.api.token:
            data["auth_token"] = self.api.token
            data["user"] = self.current_user
        else:
            data.pop("auth_token", None)
            data.pop("user", None)
        try:
            with open(self.settings_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _restore_session(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                token = data.get("auth_token")
                user = data.get("user")
                if token and user:
                    self.api.token = token
                    self.current_user = user
                    # Validate token by fetching events
                    result = self.api.get("api/events")
                    if "error" in result:
                        self.api.token = None
                        self.current_user = None
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI bootstrap
    # ------------------------------------------------------------------

    def _setup_ui(self):
        for w in self.winfo_children():
            w.destroy()
        theme = THEMES[self.current_theme]
        self.configure(fg_color=theme["bg"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self, fg_color=theme["bg"])
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self._create_sidebar(self.main_frame)
        self._create_content_area(self.main_frame)

    def _create_sidebar(self, parent):
        theme = THEMES[self.current_theme]
        sidebar = ctk.CTkFrame(parent, width=220, fg_color=theme["sidebar"])
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        # --- Mini calendar ---
        self._create_mini_calendar(sidebar)

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=theme["border"]).pack(fill="x", padx=15, pady=10)

        # --- Navigation buttons ---
        nav_items = [("calendar", "Calendar"), ("tasks", "Tasks"), ("notes", "Notes"), ("mail", "Mail")]
        icons = {"calendar": "\U0001f4c5", "tasks": "\u2705", "notes": "\U0001f4dd", "mail": "\U0001f4e7"}
        self.nav_buttons = {}
        for view, label in nav_items:
            btn = ctk.CTkButton(
                sidebar,
                text=f"{icons.get(view, '')}  {label}",
                font=ctk.CTkFont(size=14),
                fg_color=theme["accent"] if view == self.current_view else "transparent",
                hover_color=theme["button_hover"],
                text_color=theme["text"],
                anchor="w",
                height=40,
                corner_radius=8,
                command=lambda v=view: self._switch_view(v),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[view] = btn

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=theme["border"]).pack(fill="x", padx=15, pady=(20, 10))

        # --- Integration buttons ---
        self._create_integration_section(sidebar)

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=theme["border"]).pack(fill="x", padx=15, pady=(15, 10))

        # --- Theme selector ---
        ctk.CTkLabel(sidebar, text="Theme:", font=ctk.CTkFont(size=12), text_color=theme["text_secondary"]).pack(
            padx=15, anchor="w"
        )
        self.theme_var = ctk.StringVar(value=THEMES[self.current_theme]["name"])
        combo = ctk.CTkComboBox(
            sidebar,
            values=[t["name"] for t in THEMES.values()],
            variable=self.theme_var,
            command=self._on_theme_change,
            width=180,
            height=32,
        )
        combo.pack(padx=15, pady=5)
        combo.set(THEMES[self.current_theme]["name"])

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=theme["border"]).pack(fill="x", padx=15, pady=(15, 10))

        # --- User section ---
        self._render_user_section(sidebar)

    def _render_user_section(self, parent):
        """Clear and rebuild the bottom user area."""
        # Remove existing user-related widgets (last children)
        for w in parent.winfo_children()[-6:]:
            w.destroy()

        theme = THEMES[self.current_theme]

        if self.current_user:
            name = self.current_user.get("display_name", self.current_user.get("email", "User"))
            provider = self.current_user.get("auth_provider", "local")
            provider_icon = {"google": "\U0001f535", "microsoft": "\U0001fa9f"}.get(provider, "\U0001f511")
            ctk.CTkLabel(
                parent,
                text=f"{provider_icon}  {name}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=theme["text"],
                wraplength=190,
            ).pack(padx=15, anchor="w", pady=(5, 2))
            email = self.current_user.get("email", "")
            ctk.CTkLabel(
                parent,
                text=email,
                font=ctk.CTkFont(size=10),
                text_color=theme["text_secondary"],
                wraplength=190,
            ).pack(padx=15, anchor="w")
            ctk.CTkButton(
                parent,
                text="Logout",
                height=28,
                fg_color=theme["button"],
                hover_color=theme["button_hover"],
                text_color=theme["text"],
                command=self._logout,
            ).pack(fill="x", padx=15, pady=(8, 5))
        else:
            ctk.CTkButton(
                parent,
                text="\U0001f511  Sign In",
                height=32,
                command=self._show_login_dialog,
            ).pack(fill="x", padx=15, pady=5)

    def _create_integration_section(self, parent):
        """Google / Microsoft connect buttons with status."""
        theme = THEMES[self.current_theme]
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=12, pady=2)

        self.google_status_label = ctk.CTkLabel(
            frame, text="Google: Not connected", font=ctk.CTkFont(size=10),
            text_color=theme["text_secondary"], anchor="w",
        )
        self.google_status_label.pack(fill="x", pady=(0, 2))

        self.google_connect_btn = ctk.CTkButton(
            frame, text="Connect Google", height=24, font=ctk.CTkFont(size=10),
            fg_color="#4285f4", hover_color="#5a9cf5", text_color="#fff",
            command=self._connect_google,
        )
        self.google_connect_btn.pack(fill="x", pady=1)

        self.ms_status_label = ctk.CTkLabel(
            frame, text="Microsoft: Not connected", font=ctk.CTkFont(size=10),
            text_color=theme["text_secondary"], anchor="w",
        )
        self.ms_status_label.pack(fill="x", pady=(6, 2))

        self.ms_connect_btn = ctk.CTkButton(
            frame, text="Connect Microsoft", height=24, font=ctk.CTkFont(size=10),
            fg_color="#0078d4", hover_color="#106ebe", text_color="#fff",
            command=self._connect_microsoft,
        )
        self.ms_connect_btn.pack(fill="x", pady=1)

        # Sync buttons (hidden until connected)
        self.sync_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.sync_frame.pack(fill="x", padx=12, pady=(6, 2))

        self.google_sync_btn = ctk.CTkButton(
            self.sync_frame, text="\U0001f504 Sync Google Calendar", height=24, font=ctk.CTkFont(size=10),
            command=self._sync_google_calendar,
        )
        self.google_sync_btn.pack(fill="x", pady=1)

        self.ms_sync_btn = ctk.CTkButton(
            self.sync_frame, text="\U0001f504 Sync Outlook Calendar", height=24, font=ctk.CTkFont(size=10),
            command=self._sync_microsoft_calendar,
        )
        self.ms_sync_btn.pack(fill="x", pady=1)

        self.sync_frame.pack_forget()  # hidden by default
        self._check_integration_status()

    def _check_integration_status(self):
        """Check and display integration connection status."""
        if not self.api.token:
            return
        # Google
        result = self.api.get("api/integrations/google/status")
        if result.get("connected"):
            self.google_status_label.configure(text="Google: Connected", text_color="#4ade80")
            self.google_connect_btn.configure(text="Disconnect Google", command=self._disconnect_google)
            self.sync_frame.pack(fill="x", padx=12, pady=(6, 2))
        else:
            self.google_status_label.configure(text="Google: Not connected", text_color=THEMES[self.current_theme]["text_secondary"])
            self.google_connect_btn.configure(text="Connect Google", command=self._connect_google)

        # Microsoft
        result = self.api.get("api/integrations/microsoft/status")
        if result.get("connected"):
            self.ms_status_label.configure(text="Microsoft: Connected", text_color="#4ade80")
            self.ms_connect_btn.configure(text="Disconnect Microsoft", command=self._disconnect_microsoft)
            self.sync_frame.pack(fill="x", padx=12, pady=(6, 2))
        else:
            self.ms_status_label.configure(text="Microsoft: Not connected", text_color=THEMES[self.current_theme]["text_secondary"])
            self.ms_connect_btn.configure(text="Connect Microsoft", command=self._connect_microsoft)

    # ------------------------------------------------------------------
    # Mini calendar
    # ------------------------------------------------------------------

    def _create_mini_calendar(self, parent):
        self.mini_cal_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.mini_cal_frame.pack(fill="x", padx=10, pady=15)

        self.mini_cal_title = ctk.CTkLabel(
            self.mini_cal_frame,
            text=self.selected_date.strftime("%B %Y"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEMES[self.current_theme]["text"],
        )
        self.mini_cal_title.pack(side="top")

        nav_frame = ctk.CTkFrame(self.mini_cal_frame, fg_color="transparent")
        nav_frame.pack(side="top", fill="x", pady=5)
        ctk.CTkButton(nav_frame, text="<", width=28, height=24, corner_radius=4, command=self._prev_month).pack(
            side="left", padx=5
        )
        ctk.CTkButton(nav_frame, text=">", width=28, height=24, corner_radius=4, command=self._next_month).pack(
            side="right", padx=5
        )

        days_frame = ctk.CTkFrame(parent, fg_color="transparent")
        days_frame.pack(fill="x", padx=10, pady=(5, 2))
        for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            ctk.CTkLabel(days_frame, text=day, font=ctk.CTkFont(size=10), text_color=THEMES[self.current_theme]["text_secondary"], width=26).pack(side="left")

        self.cal_days_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.cal_days_frame.pack(fill="x", padx=10, pady=5)
        self._render_mini_calendar()

    def _render_mini_calendar(self):
        for w in self.cal_days_frame.winfo_children():
            w.destroy()
        year, month = self.selected_date.year, self.selected_date.month
        cal = calendar.Calendar(0)
        weeks = cal.monthdayscalendar(year, month)
        today = datetime.now()
        theme = THEMES[self.current_theme]

        for week in weeks:
            row = ctk.CTkFrame(self.cal_days_frame, fg_color="transparent")
            row.pack(fill="x")
            for day in week:
                if day == 0:
                    ctk.CTkLabel(row, text="", width=26).pack(side="left")
                else:
                    is_today = day == today.day and month == today.month and year == today.year
                    is_sel = day == self.selected_date.day and month == self.selected_date.month
                    color = theme["accent"] if (is_today or is_sel) else theme["text"]
                    bg = theme["button"] if (is_today or is_sel) else "transparent"
                    ctk.CTkButton(
                        row, text=str(day), font=ctk.CTkFont(size=11, weight="bold" if is_today else "normal"),
                        fg_color=bg, hover_color=theme["button_hover"], text_color=color,
                        width=26, height=22, corner_radius=4, command=lambda d=day: self._select_date(d),
                    ).pack(side="left")

        self.mini_cal_title.configure(text=self.selected_date.strftime("%B %Y"))

    # ------------------------------------------------------------------
    # Content area dispatcher
    # ------------------------------------------------------------------

    def _create_content_area(self, parent):
        for w in parent.winfo_children():
            if w == getattr(self, "main_frame", None) and hasattr(self, "_sidebar"):
                continue
        # Destroy content frame if exists
        if hasattr(self, "content_frame"):
            self.content_frame.destroy()

        theme = THEMES[self.current_theme]
        self.content_frame = ctk.CTkFrame(parent, fg_color=theme["bg"])
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        view_map = {
            "calendar": self._render_calendar_view,
            "tasks": self._render_tasks_view,
            "notes": self._render_notes_view,
            "mail": self._render_mail_view,
        }
        fn = view_map.get(self.current_view)
        if fn:
            fn()

    def _switch_view(self, view):
        self.current_view = view
        theme = THEMES[self.current_theme]
        for v, btn in self.nav_buttons.items():
            btn.configure(fg_color=theme["accent"] if v == view else "transparent")
        self._create_content_area(self.main_frame)

    # ==================================================================
    # Auth
    # ==================================================================

    def _show_login_dialog(self):
        """Show login/register dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Sign In")
        dialog.geometry("400x520")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=THEMES[self.current_theme]["card"])

        theme = THEMES[self.current_theme]

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 520) // 2
        dialog.geometry(f"400x520+{x}+{y}")

        ctk.CTkLabel(dialog, text="Welcome", font=ctk.CTkFont(size=22, weight="bold"), text_color=theme["text"]).pack(pady=(30, 5))
        ctk.CTkLabel(dialog, text="Sign in or create an account", font=ctk.CTkFont(size=13), text_color=theme["text_secondary"]).pack(pady=(0, 20))

        # Email
        email_var = ctk.StringVar()
        ctk.CTkEntry(
            dialog, textvariable=email_var, placeholder_text="Email", height=36, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(fill="x", padx=40, pady=4)

        # Password
        pass_var = ctk.StringVar()
        ctk.CTkEntry(
            dialog, textvariable=pass_var, placeholder_text="Password", show="*", height=36, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(fill="x", padx=40, pady=4)

        # Display name (for register)
        name_var = ctk.StringVar()
        name_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        name_frame.pack(fill="x", padx=40, pady=4)
        ctk.CTkEntry(
            name_frame, textvariable=name_var, placeholder_text="Display name (for new accounts)", height=36, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(fill="x")

        status_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=11), text_color="#f87171")
        status_label.pack(pady=5)

        def do_login():
            email, password = email_var.get().strip(), pass_var.get()
            if not email or not password:
                status_label.configure(text="Email and password are required")
                return
            result = self.api.post("api/auth/login", {"email": email, "password": password})
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            self.api.token = result["access_token"]
            self.current_user = result["user"]
            self._save_session()
            dialog.destroy()
            self._setup_ui()
            self._fetch_all_data()

        def do_register():
            email, password, name = email_var.get().strip(), pass_var.get(), name_var.get().strip()
            if not email or not password:
                status_label.configure(text="Email and password are required")
                return
            result = self.api.post("api/auth/register", {
                "email": email, "password": password,
                "display_name": name or email.split("@")[0],
            })
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            self.api.token = result["access_token"]
            self.current_user = result["user"]
            self._save_session()
            dialog.destroy()
            self._setup_ui()
            self._fetch_all_data()

        ctk.CTkButton(dialog, text="Sign In", command=do_login, height=36, corner_radius=8).pack(fill="x", padx=40, pady=6)
        ctk.CTkButton(
            dialog, text="Create Account", command=do_register, height=36, corner_radius=8,
            fg_color=theme["button"], hover_color=theme["button_hover"], text_color=theme["text"],
        ).pack(fill="x", padx=40, pady=4)

        # OAuth buttons
        ctk.CTkFrame(dialog, height=1, fg_color=theme["border"]).pack(fill="x", padx=40, pady=(15, 10))
        ctk.CTkLabel(dialog, text="Or sign in with", font=ctk.CTkFont(size=12), text_color=theme["text_secondary"]).pack()

        def do_google_oauth():
            """Initiate Google OAuth flow."""
            result = self.api.get("api/integrations/google/auth-url")
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            url = result["authorization_url"]
            dialog.destroy()
            webbrowser.open(url)
            # Show polling dialog
            self._show_oauth_polling_dialog("google")

        def do_ms_oauth():
            """Initiate Microsoft OAuth flow."""
            result = self.api.get("api/integrations/microsoft/auth-url")
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            url = result["authorization_url"]
            dialog.destroy()
            webbrowser.open(url)
            self._show_oauth_polling_dialog("microsoft")

        ctk.CTkButton(
            dialog, text="\U0001f535  Sign in with Google", command=do_google_oauth, height=36, corner_radius=8,
            fg_color="#4285f4", hover_color="#5a9cf5", text_color="#fff",
        ).pack(fill="x", padx=40, pady=4)

        ctk.CTkButton(
            dialog, text="\U0001fa9f  Sign in with Microsoft", command=do_ms_oauth, height=36, corner_radius=8,
            fg_color="#0078d4", hover_color="#106ebe", text_color="#fff",
        ).pack(fill="x", padx=40, pady=4)

    def _show_oauth_polling_dialog(self, provider):
        """Show a dialog that polls for OAuth callback completion."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Completing {provider.title()} sign-in")
        dialog.geometry("360x160")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        theme = THEMES[self.current_theme]

        ctk.CTkLabel(dialog, text="Please complete sign-in in your browser,\nthen click the button below.", font=ctk.CTkFont(size=13), text_color=theme["text"]).pack(pady=(20, 10))

        status_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=11), text_color=theme["text_secondary"])
        status_label.pack()

        def check_callback():
            # After user completes browser auth, they may have been redirected to the server.
            # We check integration status to see if tokens were saved.
            result = self.api.get(f"api/integrations/{provider}/status")
            if result.get("connected"):
                dialog.destroy()
                # Now login with the provider-created account
                # We need to get the user info - fetch events to verify token
                events = self.api.get("api/events")
                if "error" not in events or self.api.token:
                    # Token still valid from callback - get user info
                    self._refresh_user_info()
                    self._setup_ui()
                    self._fetch_all_data()
                    return
            status_label.configure(text="Not yet connected. Try again after completing browser sign-in.")
            ctk.CTkButton(dialog, text="Check Again", command=check_callback, height=30).pack(pady=8)

        ctk.CTkButton(dialog, text="I've signed in in the browser", command=check_callback, height=36).pack(pady=10)

    def _refresh_user_info(self):
        """Refresh current user info from the API using the current token."""
        # The API doesn't have a /me endpoint, so we use events as a ping.
        # User info was set during the OAuth callback response.
        pass

    def _logout(self):
        self.api.token = None
        self.current_user = None
        self.events = []
        self.tasks = []
        self.notes = []
        self.mail_messages = []
        self._save_session()
        self._setup_ui()

    # ==================================================================
    # Calendar View
    # ==================================================================

    def _render_calendar_view(self):
        theme = THEMES[self.current_theme]
        cf = self.content_frame
        for w in cf.winfo_children():
            w.destroy()

        # Header
        header = ctk.CTkFrame(cf, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        self.cal_header_label = ctk.CTkLabel(
            header,
            text=self.selected_date.strftime("%B %Y"),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme["text"],
        )
        self.cal_header_label.grid(row=0, column=0, sticky="w")

        nav_btns = ctk.CTkFrame(header, fg_color="transparent")
        nav_btns.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(nav_btns, text="< Prev", height=32, corner_radius=8, command=self._cal_prev).pack(side="left", padx=3)
        ctk.CTkButton(nav_btns, text="Today", height=32, corner_radius=8, fg_color=theme["button"], hover_color=theme["button_hover"], text_color=theme["text"], command=self._cal_today).pack(side="left", padx=3)
        ctk.CTkButton(nav_btns, text="Next >", height=32, corner_radius=8, command=self._cal_next).pack(side="left", padx=3)
        ctk.CTkButton(header, text="+ New Event", height=36, corner_radius=8, command=lambda: self._show_event_dialog()).grid(row=0, column=2, sticky="e", padx=10)

        # Calendar grid
        grid_frame = ctk.CTkFrame(cf, fg_color=theme["card"], corner_radius=12)
        grid_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        for i in range(7):
            grid_frame.grid_columnconfigure(i, weight=1)
        grid_frame.grid_rowconfigure(0, weight=0)
        grid_frame.grid_rowconfigure(1, weight=1)

        for i, day_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            ctk.CTkLabel(grid_frame, text=day_name, font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text_secondary"]).grid(row=0, column=i, sticky="ew", padx=1, pady=5)

        year, month = self.selected_date.year, self.selected_date.month
        cal = calendar.Calendar(0)
        weeks = cal.monthdayscalendar(year, month)
        today = datetime.now()

        self.cal_cells = {}  # (row,col) -> frame

        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                if day == 0:
                    cell = ctk.CTkFrame(grid_frame, fg_color="transparent")
                    cell.grid(row=r + 1, column=c, sticky="nsew", padx=1, pady=1)
                else:
                    is_today = day == today.day and month == today.month and year == today.year
                    is_sel = day == self.selected_date.day and month == self.selected_date.month
                    bg = theme["accent"] if is_today else (theme["button"] if is_sel else theme["card"])
                    tc = "#000" if is_today else theme["text"]

                    cell = ctk.CTkFrame(grid_frame, fg_color=bg, corner_radius=6)
                    cell.grid(row=r + 1, column=c, sticky="nsew", padx=2, pady=2)
                    cell.grid_rowconfigure(0, weight=0)
                    cell.grid_rowconfigure(1, weight=1)
                    cell.grid_columnconfigure(0, weight=1)

                    ctk.CTkLabel(cell, text=str(day), font=ctk.CTkFont(size=12, weight="bold" if is_today else "normal"), text_color=tc).grid(row=0, column=0, sticky="nw", padx=4, pady=2)

                    # Event chips container
                    events_container = ctk.CTkScrollableFrame(cell, fg_color="transparent")
                    events_container.grid(row=1, column=0, sticky="nsew", padx=2, pady=1)

                    # Render events for this day
                    self._render_day_events(events_container, year, month, day)

                    # Click to select day, double-click to create event
                    def select_day(d=day):
                        self.selected_date = self.selected_date.replace(day=d)
                        self._render_mini_calendar()
                        self._render_calendar_view()

                    def new_event_day(d=day):
                        self.selected_date = self.selected_date.replace(day=d)
                        self._show_event_dialog(date_str=f"{year:04d}-{month:02d}-{d:02d}")

                    cell.bind("<Button-1>", lambda e, d=day: select_day(d))
                    cell.bind("<Double-Button-1>", lambda e, d=day: new_event_day(d))

    def _render_day_events(self, container, year, month, day):
        """Render event chips for a specific day."""
        theme = THEMES[self.current_theme]
        day_str = f"{year:04d}-{month:02d}-{day:02d}"
        day_events = [e for e in self.events if self._event_starts_on(e, day_str)]
        # Sort by start time
        day_events.sort(key=lambda e: e.get("start_time", ""))

        for evt in day_events[:4]:  # max 4 chips per cell
            title = evt.get("title", "Untitled")[:20]
            color = evt.get("color", theme["accent"])
            source = evt.get("source", "local")
            badge = SOURCE_BADGES.get(source, SOURCE_BADGES["local"])

            chip_frame = ctk.CTkFrame(container, fg_color="transparent")
            chip_frame.pack(fill="x", pady=1)

            # Source badge
            if source != "local":
                ctk.CTkLabel(
                    chip_frame, text=badge["text"], font=ctk.CTkFont(size=8),
                    fg_color=badge["bg"], text_color=badge["fg"],
                    corner_radius=3, width=42,
                ).pack(side="left", padx=(0, 2))

            chip = ctk.CTkLabel(
                chip_frame, text=title, font=ctk.CTkFont(size=9),
                fg_color=color, text_color="#000" if self._is_light(color) else "#fff",
                corner_radius=4, height=18, anchor="w",
            )
            chip.pack(side="left", fill="x", expand=True)

            # Right-click for edit/delete
            chip.bind("<Button-3>", lambda e, ev=evt: self._show_event_context_menu(e, ev))
            chip_frame.bind("<Button-3>", lambda e, ev=evt: self._show_event_context_menu(e, ev))
            chip.bind("<Button-1>", lambda e, ev=evt: self._show_event_dialog(event=ev))
            chip_frame.bind("<Button-1>", lambda e, ev=evt: self._show_event_dialog(event=ev))

        if len(day_events) > 4:
            ctk.CTkLabel(
                container, text=f"+{len(day_events) - 4} more",
                font=ctk.CTkFont(size=9), text_color=theme["text_secondary"],
            ).pack(fill="x")

    def _event_starts_on(self, event, date_str):
        """Check if an event starts on the given date."""
        st = event.get("start_time", "")
        if not st:
            return False
        try:
            dt = dateutil_parse(st)
            return dt.strftime("%Y-%m-%d") == date_str
        except Exception:
            return st.startswith(date_str)

    def _is_light(self, hex_color):
        """Determine if a hex color is light."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return False
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 > 150

    def _cal_prev(self):
        if self.selected_date.month == 1:
            self.selected_date = self.selected_date.replace(year=self.selected_date.year - 1, month=12)
        else:
            self.selected_date = self.selected_date.replace(month=self.selected_date.month - 1)
        self._render_mini_calendar()
        self._render_calendar_view()

    def _cal_next(self):
        if self.selected_date.month == 12:
            self.selected_date = self.selected_date.replace(year=self.selected_date.year + 1, month=1)
        else:
            self.selected_date = self.selected_date.replace(month=self.selected_date.month + 1)
        self._render_mini_calendar()
        self._render_calendar_view()

    def _cal_today(self):
        self.selected_date = datetime.now()
        self._render_mini_calendar()
        self._render_calendar_view()

    def _show_event_context_menu(self, event, evt):
        """Show right-click context menu for an event."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edit", command=lambda: self._show_event_dialog(event=evt))
        menu.add_command(label="Delete", command=lambda: self._delete_event(evt))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_event_dialog(self, event=None, date_str=None):
        """Show event creation/edit dialog."""
        dialog = ctk.CTkToplevel(self)
        is_edit = event is not None
        dialog.title("Edit Event" if is_edit else "New Event")
        dialog.geometry("480x580")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        theme = THEMES[self.current_theme]

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 480) // 2
        y = self.winfo_y() + (self.winfo_height() - 580) // 2
        dialog.geometry(f"480x580+{x}+{y}")
        dialog.configure(fg_color=theme["card"])

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        # Title
        title_var = ctk.StringVar(value=event.get("title", "") if event else "")
        ctk.CTkLabel(scroll, text="Title", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w", pady=(5, 0))
        ctk.CTkEntry(scroll, textvariable=title_var, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Description
        desc_var = ctk.StringVar(value=event.get("description", "") if event else "")
        ctk.CTkLabel(scroll, text="Description", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        ctk.CTkEntry(scroll, textvariable=desc_var, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Location
        loc_var = ctk.StringVar(value=event.get("location", "") if event else "")
        ctk.CTkLabel(scroll, text="Location", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        ctk.CTkEntry(scroll, textvariable=loc_var, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # All-day toggle
        allday_var = ctk.BooleanVar(value=bool(event.get("is_all_day", 0)) if event else False)
        ctk.CTkCheckBox(scroll, text="All day", variable=allday_var, text_color=theme["text"]).pack(anchor="w", pady=(5, 5))

        # Start date/time
        default_start = date_str or (event.get("start_time", "")[:10] if event else self.selected_date.strftime("%Y-%m-%d"))
        default_start_time = "09:00"
        if event and event.get("start_time"):
            try:
                dt = dateutil_parse(event["start_time"])
                default_start = dt.strftime("%Y-%m-%d")
                default_start_time = dt.strftime("%H:%M")
            except Exception:
                pass

        ctk.CTkLabel(scroll, text="Start", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        start_row = ctk.CTkFrame(scroll, fg_color="transparent")
        start_row.pack(fill="x", pady=(2, 8))
        start_date_var = ctk.StringVar(value=default_start)
        start_time_var = ctk.StringVar(value=default_start_time)
        ctk.CTkEntry(start_row, textvariable=start_date_var, placeholder_text="YYYY-MM-DD", width=140, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(start_row, textvariable=start_time_var, placeholder_text="HH:MM", width=80, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(side="left")

        # End date/time
        default_end = default_start
        default_end_time = "10:00"
        if event and event.get("end_time"):
            try:
                dt = dateutil_parse(event["end_time"])
                default_end = dt.strftime("%Y-%m-%d")
                default_end_time = dt.strftime("%H:%M")
            except Exception:
                pass

        ctk.CTkLabel(scroll, text="End", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        end_row = ctk.CTkFrame(scroll, fg_color="transparent")
        end_row.pack(fill="x", pady=(2, 8))
        end_date_var = ctk.StringVar(value=default_end)
        end_time_var = ctk.StringVar(value=default_end_time)
        ctk.CTkEntry(end_row, textvariable=end_date_var, placeholder_text="YYYY-MM-DD", width=140, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(end_row, textvariable=end_time_var, placeholder_text="HH:MM", width=80, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(side="left")

        # Color
        ctk.CTkLabel(scroll, text="Color", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        color_var = ctk.StringVar(value=event.get("color", "#60cdff") if event else "#60cdff")
        color_row = ctk.CTkFrame(scroll, fg_color="transparent")
        color_row.pack(fill="x", pady=(2, 8))
        color_preview = ctk.CTkLabel(color_row, text="  ", width=30, fg_color=color_var.get(), corner_radius=6)
        color_preview.pack(side="left", padx=(0, 8))

        def pick_color():
            chosen = colorchooser.askcolor(initialcolor=color_var.get(), title="Choose color")
            if chosen[0]:
                hex_val = chosen[1]
                color_var.set(hex_val)
                color_preview.configure(fg_color=hex_val)

        ctk.CTkButton(color_row, text="Pick color", command=pick_color, height=30, fg_color=theme["button"], hover_color=theme["button_hover"], text_color=theme["text"]).pack(side="left")

        # Reminder
        ctk.CTkLabel(scroll, text="Reminder", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        reminder_var = ctk.StringVar(value=str(event.get("reminder_minutes", 15)) if event else "15")
        ctk.CTkComboBox(
            scroll, values=["0", "5", "10", "15", "30", "60", "120", "1440"],
            variable=reminder_var, height=34, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(fill="x", pady=(2, 8))

        # Recurrence
        ctk.CTkLabel(scroll, text="Recurrence", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        recur_var = ctk.StringVar(value=event.get("recurrence", "none") or "none" if event else "none")
        ctk.CTkComboBox(
            scroll, values=["none", "daily", "weekly", "monthly"],
            variable=recur_var, height=34, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(fill="x", pady=(2, 8))

        # Buttons
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 15))

        status_label = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=11), text_color="#f87171")
        status_label.pack(side="top", pady=5)

        def save_event():
            title = title_var.get().strip()
            if not title:
                status_label.configure(text="Title is required")
                return

            allday = allday_var.get()
            start_dt = start_date_var.get().strip()
            start_tm = start_time_var.get().strip()
            end_dt = end_date_var.get().strip()
            end_tm = end_time_var.get().strip()

            if allday:
                start_iso = f"{start_dt}T00:00:00"
                end_iso = f"{end_dt}T23:59:59"
            else:
                start_iso = f"{start_dt}T{start_tm}:00"
                end_iso = f"{end_dt}T{end_tm}:00"

            data = {
                "title": title,
                "description": desc_var.get().strip(),
                "location": loc_var.get().strip(),
                "start_time": start_iso,
                "end_time": end_iso,
                "is_all_day": 1 if allday else 0,
                "color": color_var.get(),
                "reminder_minutes": int(reminder_var.get()),
                "recurrence": recur_var.get() if recur_var.get() != "none" else "",
                "source": "local",
            }

            if is_edit:
                result = self.api.put(f"api/events/{event['id']}", data)
            else:
                result = self.api.post("api/events", data)

            if "error" in result:
                status_label.configure(text=result["error"])
                return

            dialog.destroy()
            self._fetch_events()
            self._render_calendar_view()

        def delete_event():
            if not is_edit:
                return
            result = self.api.delete(f"api/events/{event['id']}")
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            dialog.destroy()
            self._fetch_events()
            self._render_calendar_view()

        btn_inner = ctk.CTkFrame(btn_row, fg_color="transparent")
        btn_inner.pack(fill="x")

        if is_edit:
            ctk.CTkButton(btn_inner, text="Delete", command=delete_event, height=34, corner_radius=8,
                          fg_color="#dc2626", hover_color="#ef4444", text_color="#fff").pack(side="left")

        ctk.CTkButton(btn_inner, text="Save", command=save_event, height=34, corner_radius=8).pack(side="right")

    def _delete_event(self, event):
        """Delete an event directly (no dialog)."""
        if messagebox.askyesno("Delete Event", f"Delete '{event.get('title', '')}'?"):
            result = self.api.delete(f"api/events/{event['id']}")
            if "error" in result:
                messagebox.showerror("Error", result["error"])
                return
            self._fetch_events()
            self._render_calendar_view()

    # ==================================================================
    # Tasks View
    # ==================================================================

    def _render_tasks_view(self):
        theme = THEMES[self.current_theme]
        cf = self.content_frame
        for w in cf.winfo_children():
            w.destroy()

        # Header
        header = ctk.CTkFrame(cf, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Tasks", font=ctk.CTkFont(size=24, weight="bold"), text_color=theme["text"]).grid(row=0, column=0, sticky="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")

        # Filter
        ctk.CTkLabel(controls, text="Filter:", font=ctk.CTkFont(size=12), text_color=theme["text_secondary"]).pack(side="left", padx=(0, 4))
        filter_var = ctk.StringVar(value=self.task_filter.title())
        ctk.CTkComboBox(
            controls, values=["All", "Pending", "Completed"], variable=filter_var, width=100, height=30,
            command=lambda v: setattr(self, "task_filter", v.lower()) or self._render_tasks_view(),
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(side="left", padx=4)

        # Sort
        ctk.CTkLabel(controls, text="Sort:", font=ctk.CTkFont(size=12), text_color=theme["text_secondary"]).pack(side="left", padx=(10, 4))
        sort_var = ctk.StringVar(value="Due Date" if self.task_sort == "due_date" else "Priority")
        ctk.CTkComboBox(
            controls, values=["Due Date", "Priority"], variable=sort_var, width=100, height=30,
            command=lambda v: setattr(self, "task_sort", "due_date" if v == "Due Date" else "priority") or self._render_tasks_view(),
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(side="left", padx=4)

        ctk.CTkButton(header, text="+ New Task", height=36, corner_radius=8, command=self._show_task_dialog).grid(row=0, column=2, sticky="e", padx=10)

        # Task list
        list_frame = ctk.CTkScrollableFrame(cf, fg_color=theme["card"], corner_radius=12)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        list_frame.grid_columnconfigure(0, weight=1)

        # Filter and sort tasks
        filtered = list(self.tasks)
        if self.task_filter == "pending":
            filtered = [t for t in filtered if t.get("status") != "completed"]
        elif self.task_filter == "completed":
            filtered = [t for t in filtered if t.get("status") == "completed"]

        if self.task_sort == "priority":
            filtered.sort(key=lambda t: t.get("priority", 0), reverse=True)
        else:
            def due_key(t):
                d = t.get("due_date") or "9999-99-99"
                try:
                    return dateutil_parse(d).strftime("%Y-%m-%d")
                except Exception:
                    return d
            filtered.sort(key=due_key)

        if not filtered:
            ctk.CTkLabel(list_frame, text="No tasks found\n\nClick '+ New Task' to add one", font=ctk.CTkFont(size=16), text_color=theme["text_secondary"]).grid(row=0, column=0, pady=60)
            return

        for i, task in enumerate(filtered):
            self._render_task_item(list_frame, task, i)

    def _render_task_item(self, parent, task, index):
        """Render a single task row."""
        theme = THEMES[self.current_theme]
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.grid(row=index, column=0, sticky="ew", padx=4, pady=3)
        row_frame.grid_columnconfigure(1, weight=1)

        # Checkbox
        is_done = task.get("status") == "completed"
        check_var = ctk.BooleanVar(value=is_done)

        def toggle(_task=task, _var=check_var):
            new_status = "completed" if _var.get() else "pending"
            result = self.api.put(f"api/tasks/{_task['id']}", {"status": new_status})
            if "error" not in result:
                self._fetch_tasks()
                self._render_tasks_view()

        ctk.CTkCheckBox(row_frame, text="", variable=check_var, width=22, command=toggle).grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Task info
        info_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="w")
        info_frame.grid_columnconfigure(0, weight=1)

        priority = task.get("priority", 0)
        priority_color = PRIORITY_COLORS.get(priority, theme["text"])
        priority_name = PRIORITY_NAMES.get(priority, "")

        title_text = task.get("title", "Untitled")
        title_font = ctk.CTkFont(size=14, slant="italic" if is_done else "normal")
        title_color = theme["text_secondary"] if is_done else theme["text"]

        ctk.CTkLabel(info_frame, text=title_text, font=title_font, text_color=title_color, anchor="w").grid(row=0, column=0, sticky="w")

        # Metadata row
        meta_parts = []
        if priority_name:
            meta_parts.append(f"Priority: {priority_name}")
        due = task.get("due_date")
        if due:
            try:
                due_formatted = dateutil_parse(due).strftime("%b %d, %Y")
            except Exception:
                due_formatted = str(due)[:10]
            meta_parts.append(f"Due: {due_formatted}")
        category = task.get("category", "")
        if category:
            meta_parts.append(category)
        source = task.get("source", "local")
        badge = SOURCE_BADGES.get(source, SOURCE_BADGES["local"])
        if source != "local":
            meta_parts.append(badge["text"])

        meta_text = " | ".join(meta_parts)
        if meta_text:
            ctk.CTkLabel(info_frame, text=meta_text, font=ctk.CTkFont(size=10), text_color=theme["text_secondary"]).grid(row=1, column=0, sticky="w")

        # Priority indicator
        ctk.CTkLabel(row_frame, text="", width=4, height=32, fg_color=priority_color, corner_radius=2).grid(row=0, column=2, sticky="e", padx=(8, 0))

        # Edit/delete on right-click
        def show_task_context(event, _task=task):
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Edit", command=lambda: self._show_task_dialog(task=_task))
            menu.add_command(label="Delete", command=lambda: self._delete_task(_task))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        row_frame.bind("<Button-3>", show_task_context)
        info_frame.bind("<Button-3>", show_task_context)

    def _show_task_dialog(self, task=None):
        """Show task creation/edit dialog."""
        dialog = ctk.CTkToplevel(self)
        is_edit = task is not None
        dialog.title("Edit Task" if is_edit else "New Task")
        dialog.geometry("440x480")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        theme = THEMES[self.current_theme]

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 440) // 2
        y = self.winfo_y() + (self.winfo_height() - 480) // 2
        dialog.geometry(f"440x480+{x}+{y}")
        dialog.configure(fg_color=theme["card"])

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        # Title
        title_var = ctk.StringVar(value=task.get("title", "") if task else "")
        ctk.CTkLabel(scroll, text="Title *", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w", pady=(5, 0))
        ctk.CTkEntry(scroll, textvariable=title_var, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Description
        desc_var = ctk.StringVar(value=task.get("description", "") if task else "")
        ctk.CTkLabel(scroll, text="Description", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        ctk.CTkEntry(scroll, textvariable=desc_var, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Due date
        default_due = ""
        if task and task.get("due_date"):
            try:
                default_due = dateutil_parse(task["due_date"]).strftime("%Y-%m-%d")
            except Exception:
                default_due = str(task["due_date"])[:10]
        ctk.CTkLabel(scroll, text="Due Date", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        due_var = ctk.StringVar(value=default_due)
        ctk.CTkEntry(scroll, textvariable=due_var, placeholder_text="YYYY-MM-DD", height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Priority
        ctk.CTkLabel(scroll, text="Priority", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        priority_var = ctk.StringVar(value=PRIORITY_NAMES.get(task.get("priority", 0), "Low") if task else "Low")
        ctk.CTkComboBox(
            scroll, values=["Low", "Medium", "High", "Urgent"], variable=priority_var, height=34, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"],
        ).pack(fill="x", pady=(2, 8))

        # Category
        cat_var = ctk.StringVar(value=task.get("category", "") if task else "")
        ctk.CTkLabel(scroll, text="Category", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        ctk.CTkEntry(scroll, textvariable=cat_var, height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Buttons
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 15))
        status_label = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=11), text_color="#f87171")
        status_label.pack(side="top", pady=5)

        def save_task():
            title = title_var.get().strip()
            if not title:
                status_label.configure(text="Title is required")
                return

            priority_map = {"Low": 0, "Medium": 1, "High": 2, "Urgent": 3}
            data = {
                "title": title,
                "description": desc_var.get().strip(),
                "due_date": due_var.get().strip() or None,
                "priority": priority_map.get(priority_var.get(), 0),
                "category": cat_var.get().strip(),
                "source": "local",
            }
            if is_edit:
                data["status"] = task.get("status", "pending")
                result = self.api.put(f"api/tasks/{task['id']}", data)
            else:
                data["status"] = "pending"
                result = self.api.post("api/tasks", data)

            if "error" in result:
                status_label.configure(text=result["error"])
                return
            dialog.destroy()
            self._fetch_tasks()
            self._render_tasks_view()

        def delete_task():
            if not is_edit:
                return
            result = self.api.delete(f"api/tasks/{task['id']}")
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            dialog.destroy()
            self._fetch_tasks()
            self._render_tasks_view()

        btn_inner = ctk.CTkFrame(btn_row, fg_color="transparent")
        btn_inner.pack(fill="x")
        if is_edit:
            ctk.CTkButton(btn_inner, text="Delete", command=delete_task, height=34, corner_radius=8,
                          fg_color="#dc2626", hover_color="#ef4444", text_color="#fff").pack(side="left")
        ctk.CTkButton(btn_inner, text="Save", command=save_task, height=34, corner_radius=8).pack(side="right")

    def _delete_task(self, task):
        """Delete a task directly."""
        if messagebox.askyesno("Delete Task", f"Delete '{task.get('title', '')}'?"):
            result = self.api.delete(f"api/tasks/{task['id']}")
            if "error" in result:
                messagebox.showerror("Error", result["error"])
                return
            self._fetch_tasks()
            self._render_tasks_view()

    # ==================================================================
    # Notes View
    # ==================================================================

    def _render_notes_view(self):
        theme = THEMES[self.current_theme]
        cf = self.content_frame
        for w in cf.winfo_children():
            w.destroy()

        # Header
        header = ctk.CTkFrame(cf, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Notes", font=ctk.CTkFont(size=24, weight="bold"), text_color=theme["text"]).grid(row=0, column=0, sticky="w")

        # Search
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            header, textvariable=search_var, placeholder_text="Search notes...", height=34, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"], width=200,
        )
        search_entry.grid(row=0, column=1, sticky="e", padx=10)
        search_entry.bind("<KeyRelease>", lambda e: self._filter_notes(search_var.get()))

        ctk.CTkButton(header, text="+ New Note", height=36, corner_radius=8, command=self._show_note_dialog).grid(row=0, column=2, sticky="e", padx=10)

        # Notes grid (Google Keep style)
        self.notes_scroll = ctk.CTkScrollableFrame(cf, fg_color=theme["bg"], corner_radius=12)
        self.notes_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.notes_scroll.grid_columnconfigure((0, 1, 2), weight=1)

        self._render_notes_grid(self.notes)

    def _render_notes_grid(self, notes):
        """Render notes in a 3-column grid, pinned notes first."""
        theme = THEMES[self.current_theme]

        # Clear existing
        for w in self.notes_scroll.winfo_children():
            w.destroy()

        # Sort: pinned first
        sorted_notes = sorted(notes, key=lambda n: n.get("pinned", 0), reverse=True)

        if not sorted_notes:
            ctk.CTkLabel(self.notes_scroll, text="No notes yet\n\nClick '+ New Note' to add one", font=ctk.CTkFont(size=16), text_color=theme["text_secondary"]).grid(row=0, column=0, columnspan=3, pady=60)
            return

        for i, note in enumerate(sorted_notes):
            row = i // 3
            col = i % 3
            self._render_note_card(self.notes_scroll, note, row, col)

    def _render_note_card(self, parent, note, row, col):
        """Render a single note card (Google Keep style)."""
        theme = THEMES[self.current_theme]
        color = note.get("color", "#ffffff")
        title = note.get("title", "Untitled")
        content = note.get("content", "")
        pinned = note.get("pinned", 0)

        card = ctk.CTkFrame(parent, fg_color=color, corner_radius=8, border_width=2, border_color=theme["border"])
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        # Pin indicator
        if pinned:
            ctk.CTkLabel(card, text="\U0001f4cc", font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="ne", padx=4, pady=4)

        # Title
        title_color = "#000" if self._is_light(color) else "#fff"
        if title:
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color=title_color, anchor="w", wraplength=200).grid(row=0 if not pinned else 1, column=0, sticky="nw", padx=8, pady=(8, 2))

        # Content preview
        preview = content[:150] + "..." if len(content) > 150 else content
        if preview:
            ctk.CTkLabel(card, text=preview, font=ctk.CTkFont(size=11), text_color=title_color, anchor="w", wraplength=200, justify="left").grid(row=(1 if title else 0) if not pinned else 2, column=0, sticky="nw", padx=8, pady=(0, 6))

        # Actions row
        action_row = ctk.CTkFrame(card, fg_color="transparent")
        action_row.grid(row=(2 if title else 1) if not pinned else 3, column=0, sticky="ew", padx=4, pady=4)

        pin_icon = "\U0001f4cc" if not pinned else "\u2b55"
        ctk.CTkButton(action_row, text=pin_icon, width=24, height=24, fg_color="transparent", hover_color=theme["button_hover"], text_color=title_color, command=lambda n=note: self._toggle_pin_note(n)).pack(side="left")
        ctk.CTkButton(action_row, text="\U0001f3a8", width=24, height=24, fg_color="transparent", hover_color=theme["button_hover"], text_color=title_color, command=lambda n=note: self._show_note_color_picker(n)).pack(side="left")
        ctk.CTkButton(action_row, text="\U0001f5d1", width=24, height=24, fg_color="transparent", hover_color=theme["button_hover"], text_color=title_color, command=lambda n=note: self._delete_note(n)).pack(side="right")

        # Click to edit
        card.bind("<Button-1>", lambda e, n=note: self._show_note_dialog(note=n))

    def _filter_notes(self, query):
        self.note_search = query.lower()
        if not query:
            self._render_notes_grid(self.notes)
        else:
            filtered = [n for n in self.notes if query.lower() in n.get("title", "").lower() or query.lower() in n.get("content", "").lower()]
            self._render_notes_grid(filtered)

    def _toggle_pin_note(self, note):
        new_pinned = 0 if note.get("pinned", 0) else 1
        result = self.api.put(f"api/notes/{note['id']}", {"pinned": new_pinned})
        if "error" not in result:
            self._fetch_notes()
            self._render_notes_view()

    def _delete_note(self, note):
        if messagebox.askyesno("Delete Note", f"Delete '{note.get('title', 'Untitled')}'?"):
            result = self.api.delete(f"api/notes/{note['id']}")
            if "error" in result:
                messagebox.showerror("Error", result["error"])
                return
            self._fetch_notes()
            self._render_notes_view()

    def _show_note_color_picker(self, note):
        """Show color picker for a note."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Note Color")
        dialog.geometry("280x120")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        theme = THEMES[self.current_theme]

        ctk.CTkLabel(dialog, text="Choose color:", font=ctk.CTkFont(size=13), text_color=theme["text"]).pack(pady=(10, 8))

        colors_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        colors_frame.pack(padx=15, pady=5)

        for i, color in enumerate(NOTE_COLORS):
            btn = ctk.CTkButton(colors_frame, text="", width=28, height=28, fg_color=color, corner_radius=14,
                                command=lambda c=color, n=note, d=dialog: self._set_note_color(n, c, d))
            btn.grid(row=i // 5, column=i % 5, padx=4, pady=4)

    def _set_note_color(self, note, color, dialog):
        result = self.api.put(f"api/notes/{note['id']}", {"color": color})
        if "error" not in result:
            dialog.destroy()
            self._fetch_notes()
            self._render_notes_view()

    def _show_note_dialog(self, note=None):
        """Show note creation/edit dialog."""
        dialog = ctk.CTkToplevel(self)
        is_edit = note is not None
        dialog.title("Edit Note" if is_edit else "New Note")
        dialog.geometry("420x400")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        theme = THEMES[self.current_theme]

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 420) // 2
        y = self.winfo_y() + (self.winfo_height() - 400) // 2
        dialog.geometry(f"420x400+{x}+{y}")
        dialog.configure(fg_color=theme["card"])

        # Title
        title_var = ctk.StringVar(value=note.get("title", "") if note else "")
        ctk.CTkEntry(
            dialog, textvariable=title_var, placeholder_text="Title", height=40, corner_radius=0,
            fg_color=theme["card"], border_color="transparent",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(fill="x", padx=15, pady=(10, 0))

        # Content
        content_var = ctk.StringVar(value=note.get("content", "") if note else "")
        content_text = ctk.CTkTextbox(dialog, height=240, corner_radius=0, fg_color=theme["card"], border_color="transparent")
        content_text.pack(fill="both", expand=True, padx=15, pady=10)
        content_text.insert("1.0", note.get("content", "") if note else "")

        # Color
        color_var = ctk.StringVar(value=note.get("color", "#ffffff") if note else "#ffffff")
        color_row = ctk.CTkFrame(dialog, fg_color="transparent")
        color_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(color_row, text="  ", width=24, fg_color=color_var.get(), corner_radius=12).pack(side="left", padx=(0, 8))

        def pick_color():
            chosen = colorchooser.askcolor(initialcolor=color_var.get(), title="Note color")
            if chosen[1]:
                color_var.set(chosen[1])
                # Update preview
                for child in color_row.winfo_children():
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(fg_color=chosen[1])

        ctk.CTkButton(color_row, text="\U0001f3a8 Color", command=pick_color, height=28, fg_color=theme["button"], hover_color=theme["button_hover"], text_color=theme["text"]).pack(side="left")

        # Pin
        pin_var = ctk.BooleanVar(value=bool(note.get("pinned", 0)) if note else False)
        ctk.CTkCheckBox(color_row, text="Pin", variable=pin_var, text_color=theme["text"]).pack(side="left", padx=(15, 0))

        # Buttons
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 10))
        status_label = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=11), text_color="#f87171")
        status_label.pack(side="top", pady=4)

        def save_note():
            data = {
                "title": title_var.get().strip(),
                "content": content_text.get("1.0", "end-1c"),
                "color": color_var.get(),
                "pinned": 1 if pin_var.get() else 0,
            }
            if is_edit:
                result = self.api.put(f"api/notes/{note['id']}", data)
            else:
                result = self.api.post("api/notes", data)
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            dialog.destroy()
            self._fetch_notes()
            self._render_notes_view()

        def delete_note():
            if not is_edit:
                return
            result = self.api.delete(f"api/notes/{note['id']}")
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            dialog.destroy()
            self._fetch_notes()
            self._render_notes_view()

        btn_inner = ctk.CTkFrame(btn_row, fg_color="transparent")
        btn_inner.pack(fill="x")
        if is_edit:
            ctk.CTkButton(btn_inner, text="Delete", command=delete_note, height=34, corner_radius=8,
                          fg_color="#dc2626", hover_color="#ef4444", text_color="#fff").pack(side="left")
        ctk.CTkButton(btn_inner, text="Save", command=save_note, height=34, corner_radius=8).pack(side="right")

    # ==================================================================
    # Mail View
    # ==================================================================

    def _render_mail_view(self):
        theme = THEMES[self.current_theme]
        cf = self.content_frame
        for w in cf.winfo_children():
            w.destroy()

        # Header
        header = ctk.CTkFrame(cf, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Mail", font=ctk.CTkFont(size=24, weight="bold"), text_color=theme["text"]).grid(row=0, column=0, sticky="w")

        # Tabs: Inbox / Sent / Compose
        tabs_frame = ctk.CTkFrame(header, fg_color="transparent")
        tabs_frame.grid(row=0, column=1, sticky="e")

        self.mail_tab_var = ctk.StringVar(value="inbox")
        for tab_label, tab_value in [("Inbox", "inbox"), ("Sent", "sent"), ("Compose", "compose")]:
            ctk.CTkButton(
                tabs_frame, text=tab_label, height=30, corner_radius=8,
                fg_color=theme["accent"] if tab_value == "inbox" else "transparent",
                hover_color=theme["button_hover"], text_color=theme["text"],
                command=lambda tv=tab_value: self._switch_mail_tab(tv),
            ).pack(side="left", padx=3)

        ctk.CTkButton(header, text="+ Compose", height=36, corner_radius=8, command=lambda: self._switch_mail_tab("compose")).grid(row=0, column=2, sticky="e", padx=10)

        # Mail content area
        self.mail_content = ctk.CTkFrame(cf, fg_color=theme["card"], corner_radius=12)
        self.mail_content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.mail_content.grid_columnconfigure(0, weight=1)
        self.mail_content.grid_rowconfigure(0, weight=1)

        self._switch_mail_tab("inbox")

    def _switch_mail_tab(self, tab):
        self.mail_tab_var.set(tab)
        theme = THEMES[self.current_theme]

        for w in self.mail_content.winfo_children():
            w.destroy()

        if tab == "inbox":
            self._render_mail_inbox()
        elif tab == "sent":
            self._render_mail_sent()
        elif tab == "compose":
            self._render_mail_compose()

    def _render_mail_inbox(self):
        theme = THEMES[self.current_theme]
        list_frame = ctk.CTkScrollableFrame(self.mail_content, fg_color="transparent")
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)

        if not self.mail_messages:
            ctk.CTkLabel(list_frame, text="No messages\n\nConnect Gmail or Outlook to view emails", font=ctk.CTkFont(size=16), text_color=theme["text_secondary"]).grid(row=0, column=0, pady=60)
            return

        for i, msg in enumerate(self.mail_messages):
            self._render_mail_item(list_frame, msg, i)

    def _render_mail_item(self, parent, msg, index):
        theme = THEMES[self.current_theme]
        row = ctk.CTkFrame(parent, fg_color=theme["button"], corner_radius=8)
        row.grid(row=index, column=0, sticky="ew", padx=4, pady=2)
        row.grid_columnconfigure(1, weight=1)

        # From
        from_text = msg.get("from", msg.get("sender", ""))
        if isinstance(from_text, dict):
            from_text = from_text.get("emailAddress", {}).get("address", "")
        ctk.CTkLabel(row, text=from_text[:30], font=ctk.CTkFont(size=13, weight="bold"), text_color=theme["text"], anchor="w", width=120).grid(row=0, column=0, sticky="w", padx=10, pady=8)

        # Subject + preview
        subject = msg.get("subject", "(No subject)")
        preview = msg.get("body_preview", msg.get("snippet", ""))[:80]
        ctk.CTkLabel(row, text=subject, font=ctk.CTkFont(size=13), text_color=theme["text"], anchor="w").grid(row=0, column=1, sticky="w", padx=5)
        ctk.CTkLabel(row, text=preview, font=ctk.CTkFont(size=10), text_color=theme["text_secondary"], anchor="w").grid(row=1, column=1, sticky="w", padx=5)

        # Date
        date_text = msg.get("received_date_time", msg.get("date", ""))[:10]
        ctk.CTkLabel(row, text=date_text, font=ctk.CTkFont(size=10), text_color=theme["text_secondary"]).grid(row=0, column=2, sticky="e", padx=10, pady=8)

        # Click to read
        row.bind("<Button-1>", lambda e, m=msg: self._show_mail_message(m))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, m=msg: self._show_mail_message(m))

    def _render_mail_sent(self):
        theme = THEMES[self.current_theme]
        list_frame = ctk.CTkScrollableFrame(self.mail_content, fg_color="transparent")
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)

        # Show sent mail from local DB
        ctk.CTkLabel(list_frame, text="Sent mail history (local)", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme["text"]).grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Fetch sent mail from API
        # The API doesn't have a dedicated sent-mail endpoint for local, so show placeholder
        ctk.CTkLabel(list_frame, text="No sent mail recorded locally.\n\nSent mail via Gmail/Outlook is tracked by the provider.", font=ctk.CTkFont(size=13), text_color=theme["text_secondary"]).grid(row=1, column=0, pady=40)

    def _render_mail_compose(self):
        theme = THEMES[self.current_theme]
        compose_frame = ctk.CTkScrollableFrame(self.mail_content, fg_color="transparent")
        compose_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)

        # Provider selector
        ctk.CTkLabel(compose_frame, text="Send via:", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme["text"]).pack(anchor="w", pady=(5, 5))
        provider_var = ctk.StringVar(value="gmail")
        ctk.CTkComboBox(
            compose_frame, values=["Gmail", "Outlook"], variable=provider_var, height=34, corner_radius=8,
            fg_color=theme["button"], border_color=theme["border"], width=150,
        ).pack(anchor="w", pady=(0, 10))

        # To
        ctk.CTkLabel(compose_frame, text="To", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        to_var = ctk.StringVar()
        ctk.CTkEntry(compose_frame, textvariable=to_var, placeholder_text="recipient@example.com", height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Subject
        ctk.CTkLabel(compose_frame, text="Subject", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        subj_var = ctk.StringVar()
        ctk.CTkEntry(compose_frame, textvariable=subj_var, placeholder_text="Subject", height=34, corner_radius=8, fg_color=theme["button"], border_color=theme["border"]).pack(fill="x", pady=(2, 8))

        # Body
        ctk.CTkLabel(compose_frame, text="Message", font=ctk.CTkFont(size=12, weight="bold"), text_color=theme["text"]).pack(anchor="w")
        body_text = ctk.CTkTextbox(compose_frame, height=200, corner_radius=8, fg_color=theme["button"], border_color=theme["border"])
        body_text.pack(fill="both", expand=True, pady=(2, 10))

        status_label = ctk.CTkLabel(compose_frame, text="", font=ctk.CTkFont(size=11), text_color="#f87171")
        status_label.pack(pady=5)

        def send_mail():
            to_addr = to_var.get().strip()
            subject = subj_var.get().strip()
            body = body_text.get("1.0", "end-1c")
            if not to_addr or not subject:
                status_label.configure(text="To and Subject are required")
                return

            provider = provider_var.get().lower()
            endpoint = "api/integrations/gmail/send" if provider == "gmail" else "api/integrations/msgraph/mail/send"
            result = self.api.post(endpoint, {"to": to_addr, "subject": subject, "body": body})
            if "error" in result:
                status_label.configure(text=result["error"])
                return
            status_label.configure(text_color="#4ade80")
            status_label.configure(text="Email sent successfully!")
            to_var.set("")
            subj_var.set("")
            body_text.delete("1.0", "end")

        ctk.CTkButton(compose_frame, text="Send", command=send_mail, height=40, corner_radius=8, width=120).pack(pady=10)

    def _show_mail_message(self, msg):
        """Show a full mail message in a dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(msg.get("subject", "(No subject)"))
        dialog.geometry("600x500")
        dialog.resizable(True, True)
        dialog.transient(self)
        dialog.grab_set()
        theme = THEMES[self.current_theme]

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 600) // 2
        y = self.winfo_y() + (self.winfo_height() - 500) // 2
        dialog.geometry(f"600x500+{x}+{y}")
        dialog.configure(fg_color=theme["card"])

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        # Header info
        ctk.CTkLabel(scroll, text=msg.get("subject", "(No subject)"), font=ctk.CTkFont(size=18, weight="bold"), text_color=theme["text"], wraplength=540).pack(anchor="w", pady=(5, 10))

        from_text = msg.get("from", msg.get("sender", ""))
        if isinstance(from_text, dict):
            from_text = from_text.get("emailAddress", {}).get("address", "")
        ctk.CTkLabel(scroll, text=f"From: {from_text}", font=ctk.CTkFont(size=12), text_color=theme["text_secondary"]).pack(anchor="w")

        to_text = msg.get("to", "")
        ctk.CTkLabel(scroll, text=f"To: {to_text}", font=ctk.CTkFont(size=12), text_color=theme["text_secondary"]).pack(anchor="w")

        date_text = msg.get("received_date_time", msg.get("date", ""))
        ctk.CTkLabel(scroll, text=f"Date: {date_text}", font=ctk.CTkFont(size=12), text_color=theme["text_secondary"]).pack(anchor="w", pady=(0, 15))

        ctk.CTkFrame(scroll, height=1, fg_color=theme["border"]).pack(fill="x", pady=10)

        # Body
        body = msg.get("body", msg.get("body_preview", ""))
        body_label = ctk.CTkLabel(scroll, text=body, font=ctk.CTkFont(size=13), text_color=theme["text"], wraplength=540, justify="left")
        body_label.pack(anchor="w", pady=5)

    # ==================================================================
    # Integration actions
    # ==================================================================

    def _connect_google(self):
        """Connect or disconnect Google account."""
        # Check current status
        result = self.api.get("api/integrations/google/status")
        if result.get("connected"):
            # Disconnect
            if messagebox.askyesno("Disconnect Google", "Disconnect your Google account?"):
                self.api.post("api/integrations/google/disconnect")
                self._check_integration_status()
                self._render_user_section(self.main_frame.winfo_children()[0])
            return

        # Connect via OAuth
        auth_result = self.api.get("api/integrations/google/auth-url")
        if "error" in auth_result:
            messagebox.showerror("Error", auth_result["error"])
            return
        webbrowser.open(auth_result["authorization_url"])
        messagebox.showinfo("Google Sign-In", "Please complete sign-in in your browser.\nThen click 'I've signed in' when done.")
        # Refresh status
        self._check_integration_status()
        self._render_user_section(self.main_frame.winfo_children()[0])

    def _connect_microsoft(self):
        """Connect or disconnect Microsoft account."""
        result = self.api.get("api/integrations/microsoft/status")
        if result.get("connected"):
            if messagebox.askyesno("Disconnect Microsoft", "Disconnect your Microsoft account?"):
                self.api.post("api/integrations/microsoft/disconnect")
                self._check_integration_status()
                self._render_user_section(self.main_frame.winfo_children()[0])
            return

        auth_result = self.api.get("api/integrations/microsoft/auth-url")
        if "error" in auth_result:
            messagebox.showerror("Error", auth_result["error"])
            return
        webbrowser.open(auth_result["authorization_url"])
        messagebox.showinfo("Microsoft Sign-In", "Please complete sign-in in your browser.\nThen click 'I've signed in' when done.")
        self._check_integration_status()
        self._render_user_section(self.main_frame.winfo_children()[0])

    def _disconnect_google(self):
        self.api.post("api/integrations/google/disconnect")
        self._check_integration_status()
        self._render_user_section(self.main_frame.winfo_children()[0])

    def _disconnect_microsoft(self):
        self.api.post("api/integrations/microsoft/disconnect")
        self._check_integration_status()
        self._render_user_section(self.main_frame.winfo_children()[0])

    def _sync_google_calendar(self):
        """Sync Google Calendar events to local DB."""
        if not self.api.token:
            messagebox.showwarning("Not signed in", "Please sign in first.")
            return
        result = self.api.post("api/integrations/google/calendar/sync")
        if "error" in result:
            messagebox.showerror("Sync Error", result["error"])
            return
        created = result.get("created", 0)
        updated = result.get("updated", 0)
        self._fetch_events()
        self._render_calendar_view()
        messagebox.showinfo("Sync Complete", f"Google Calendar sync done.\nCreated: {created}, Updated: {updated}")

    def _sync_microsoft_calendar(self):
        """Sync Microsoft/Outlook Calendar events to local DB."""
        if not self.api.token:
            messagebox.showwarning("Not signed in", "Please sign in first.")
            return
        result = self.api.post("api/integrations/microsoft/calendar/sync")
        if "error" in result:
            messagebox.showerror("Sync Error", result["error"])
            return
        created = result.get("created", 0)
        updated = result.get("updated", 0)
        self._fetch_events()
        self._render_calendar_view()
        messagebox.showinfo("Sync Complete", f"Outlook Calendar sync done.\nCreated: {created}, Updated: {updated}")

    # ==================================================================
    # Data fetching
    # ==================================================================

    def _fetch_all_data(self):
        """Fetch events, tasks, notes, and mail in parallel-ish."""
        if not self.api.token:
            return
        self._fetch_events()
        self._fetch_tasks()
        self._fetch_notes()

    def _fetch_events(self):
        """Fetch events for the current month."""
        if not self.api.token:
            return
        year, month = self.selected_date.year, self.selected_date.month
        start = f"{year:04d}-{month:02d}-01T00:00:00"
        if month == 12:
            end = f"{year + 1:04d}-01-01T00:00:00"
        else:
            end = f"{year:04d}-{month + 1:02d}-01T00:00:00"
        result = self.api.get("api/events", params={"start": start, "end": end})
        if "error" not in result:
            self.events = result

    def _fetch_tasks(self):
        """Fetch all tasks."""
        if not self.api.token:
            return
        result = self.api.get("api/tasks")
        if "error" not in result:
            self.tasks = result

    def _fetch_notes(self):
        """Fetch all notes."""
        if not self.api.token:
            return
        result = self.api.get("api/notes")
        if "error" not in result:
            self.notes = result

    # ==================================================================
    # Navigation helpers
    # ==================================================================

    def _prev_month(self):
        if self.selected_date.month == 1:
            self.selected_date = self.selected_date.replace(year=self.selected_date.year - 1, month=12)
        else:
            self.selected_date = self.selected_date.replace(month=self.selected_date.month - 1)
        self._render_mini_calendar()
        self._fetch_events()
        if self.current_view == "calendar":
            self._render_calendar_view()

    def _next_month(self):
        if self.selected_date.month == 12:
            self.selected_date = self.selected_date.replace(year=self.selected_date.year + 1, month=1)
        else:
            self.selected_date = self.selected_date.replace(month=self.selected_date.month + 1)
        self._render_mini_calendar()
        self._fetch_events()
        if self.current_view == "calendar":
            self._render_calendar_view()

    def _select_date(self, day):
        self.selected_date = self.selected_date.replace(day=day)
        self._render_mini_calendar()
        if self.current_view == "calendar":
            self._render_calendar_view()

    def _on_theme_change(self, name):
        for key, value in THEMES.items():
            if value["name"] == name:
                self.current_theme = key
                break
        self._save_settings()
        self._setup_ui()

    # ==================================================================
    # Mini calendar prev/next/select
    # ==================================================================
    # Already covered by _prev_month, _next_month, _select_date


def run_calendar_tasks():
    """Entry point for the Calendar & Tasks desktop app."""
    from db.database import init_db
    init_db()
    app = CalendarTasksUI()
    app.mainloop()
