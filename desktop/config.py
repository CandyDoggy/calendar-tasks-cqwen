"""
Configuration file for Calendar & Tasks app.
Stores OAuth client IDs and API settings.

IMPORTANT: Replace placeholder values with your actual Google Cloud Console credentials.
See: https://console.cloud.google.com/apis/credentials
"""

import os

# Google OAuth Configuration
# Get these from: https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID = os.environ.get(
    'GOOGLE_CLIENT_ID',
    'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com'
)
GOOGLE_CLIENT_SECRET = os.environ.get(
    'GOOGLE_CLIENT_SECRET',
    'YOUR_GOOGLE_CLIENT_SECRET'
)

# Redirect URI for OAuth callback
# Must match exactly what's configured in Google Cloud Console
GOOGLE_REDIRECT_URI = os.environ.get(
    'GOOGLE_REDIRECT_URI',
    'http://localhost:5000/api/integrations/google/callback'
)

# OAuth Scopes
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

# Flask JWT Secret Key
JWT_SECRET_KEY = os.environ.get(
    'JWT_SECRET_KEY',
    'calendar-tasks-secret-key-change-in-production'
)

# Microsoft OAuth Configuration
# Get these from: https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
MICROSOFT_CLIENT_ID = os.environ.get(
    'MICROSOFT_CLIENT_ID',
    'YOUR_MICROSOFT_CLIENT_ID'
)
MICROSOFT_CLIENT_SECRET = os.environ.get(
    'MICROSOFT_CLIENT_SECRET',
    'YOUR_MICROSOFT_CLIENT_SECRET'
)

# Redirect URI for OAuth callback
# Must match exactly what's configured in Azure Portal
MICROSOFT_REDIRECT_URI = os.environ.get(
    'MICROSOFT_REDIRECT_URI',
    'http://localhost:5000/api/integrations/microsoft/callback'
)

# OAuth Scopes for Microsoft Graph API
MICROSOFT_SCOPES = [
    'User.Read',
    'Calendars.Read',
    'Calendars.ReadWrite',
    'Mail.Read',
    'Mail.Send',
]

# Token file path for storing OAuth credentials as fallback
TOKEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tokens')
