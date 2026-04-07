"""
Configuration file for Calendar & Tasks app.
Stores OAuth client IDs and API settings.

Priority: config.json > environment variables > placeholders
"""

import os
import json

_config_dir = os.path.dirname(os.path.abspath(__file__))
_config_file = os.path.join(_config_dir, 'config.json')

# Load credentials from config.json if it exists
_json_config = {}
try:
    if os.path.exists(_config_file):
        with open(_config_file, 'r') as f:
            _json_config = json.load(f)
except Exception:
    pass

# --- Google OAuth ---
_google_cfg = _json_config.get('google', {})
GOOGLE_CLIENT_ID = os.environ.get(
    'GOOGLE_CLIENT_ID',
    _google_cfg.get('client_id', 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com')
)
GOOGLE_CLIENT_SECRET = os.environ.get(
    'GOOGLE_CLIENT_SECRET',
    _google_cfg.get('client_secret', 'YOUR_GOOGLE_CLIENT_SECRET')
)
GOOGLE_REDIRECT_URI = os.environ.get(
    'GOOGLE_REDIRECT_URI',
    _google_cfg.get('redirect_uri', 'http://localhost:5000/api/integrations/google/callback')
)

GOOGLE_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/contacts.readonly',
]

# --- Microsoft OAuth ---
_ms_cfg = _json_config.get('microsoft', {})
MICROSOFT_CLIENT_ID = os.environ.get(
    'MICROSOFT_CLIENT_ID',
    _ms_cfg.get('client_id', 'YOUR_MICROSOFT_CLIENT_ID')
)
MICROSOFT_CLIENT_SECRET = os.environ.get(
    'MICROSOFT_CLIENT_SECRET',
    _ms_cfg.get('client_secret', 'YOUR_MICROSOFT_CLIENT_SECRET')
)
MICROSOFT_REDIRECT_URI = os.environ.get(
    'MICROSOFT_REDIRECT_URI',
    _ms_cfg.get('redirect_uri', 'http://localhost:5000/api/integrations/microsoft/callback')
)

MICROSOFT_SCOPES = [
    'User.Read',
    'Calendars.Read',
    'Calendars.ReadWrite',
    'Mail.Read',
    'Mail.Send',
]

# --- JWT ---
JWT_SECRET_KEY = os.environ.get(
    'JWT_SECRET_KEY',
    'calendar-tasks-secret-key-change-in-production'
)


def save_oauth_config(google_id=None, google_secret=None, ms_id=None, ms_secret=None):
    """Save OAuth credentials to config.json."""
    cfg = {}
    if os.path.exists(_config_file):
        try:
            with open(_config_file, 'r') as f:
                cfg = json.load(f)
        except Exception:
            pass

    if google_id or google_secret:
        cfg.setdefault('google', {})
        if google_id:
            cfg['google']['client_id'] = google_id
        if google_secret:
            cfg['google']['client_secret'] = google_secret
        cfg['google']['redirect_uri'] = GOOGLE_REDIRECT_URI

    if ms_id or ms_secret:
        cfg.setdefault('microsoft', {})
        if ms_id:
            cfg['microsoft']['client_id'] = ms_id
        if ms_secret:
            cfg['microsoft']['client_secret'] = ms_secret
        cfg['microsoft']['redirect_uri'] = MICROSOFT_REDIRECT_URI

    with open(_config_file, 'w') as f:
        json.dump(cfg, f, indent=4)

    # Update runtime globals
    global GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    global MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET
    if google_id:
        GOOGLE_CLIENT_ID = google_id
    if google_secret:
        GOOGLE_CLIENT_SECRET = google_secret
    if ms_id:
        MICROSOFT_CLIENT_ID = ms_id
    if ms_secret:
        MICROSOFT_CLIENT_SECRET = ms_secret


def get_current_oauth_config():
    """Return current OAuth config for the setup dialog."""
    is_google_real = GOOGLE_CLIENT_ID and not GOOGLE_CLIENT_ID.startswith('YOUR_')
    is_ms_real = MICROSOFT_CLIENT_ID and not MICROSOFT_CLIENT_ID.startswith('YOUR_')
    return {
        'google_client_id': GOOGLE_CLIENT_ID if is_google_real else '',
        'google_client_secret': GOOGLE_CLIENT_SECRET if is_google_real else '',
        'ms_client_id': MICROSOFT_CLIENT_ID if is_ms_real else '',
        'ms_client_secret': MICROSOFT_CLIENT_SECRET if is_ms_real else '',
        'google_connected': is_google_real,
        'microsoft_connected': is_ms_real,
    }
