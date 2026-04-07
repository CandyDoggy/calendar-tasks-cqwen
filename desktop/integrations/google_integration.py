"""
Google Integration Module
Handles OAuth flow, token management, and API client creation for:
- Google Calendar
- Google Tasks
- Google Keep (via basic API)
"""

import json
import os
import sys
from datetime import datetime, timedelta
from functools import wraps

from flask import request, jsonify, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import get_connection
import config


# ==================== TOKEN MANAGEMENT ====================

def _get_user_google_tokens(user_id):
    """Retrieve and parse Google OAuth tokens for a user from the database."""
    with get_connection() as conn:
        user = conn.execute(
            "SELECT google_token FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user or not user['google_token']:
            return None

        try:
            token_data = json.loads(user['google_token'])
            return token_data
        except (json.JSONDecodeError, TypeError):
            # Legacy format: just an access token string
            return {'access_token': user['google_token']}


def _save_user_google_tokens(user_id, credentials):
    """Save Google OAuth credentials to the user's database record."""
    token_data = {
        'access_token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None,
    }

    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET google_token = ? WHERE id = ?",
            (json.dumps(token_data), user_id)
        )


def _get_credentials_from_token_data(token_data):
    """Convert stored token data back to a Credentials object."""
    expiry = None
    if token_data.get('expiry'):
        try:
            expiry = datetime.fromisoformat(token_data['expiry'])
        except (ValueError, TypeError):
            pass

    return Credentials(
        token=token_data.get('access_token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=token_data.get('client_id', config.GOOGLE_CLIENT_ID),
        client_secret=token_data.get('client_secret', config.GOOGLE_CLIENT_SECRET),
        scopes=token_data.get('scopes', config.GOOGLE_SCOPES),
        expiry=expiry,
    )


def _refresh_credentials_if_needed(credentials):
    """Refresh access token if expired or about to expire."""
    if not credentials.valid and credentials.refresh_token:
        credentials.refresh(Request())
        return True
    return False


def get_google_credentials(user_id):
    """
    Get valid Google credentials for a user, refreshing if necessary.
    Returns Credentials object or None if not authenticated.
    """
    token_data = _get_user_google_tokens(user_id)
    if not token_data:
        return None

    credentials = _get_credentials_from_token_data(token_data)

    # Try to refresh if expired
    if not credentials.valid:
        try:
            credentials.refresh(Request())
            # Save refreshed tokens
            _save_user_google_tokens(user_id, credentials)
        except Exception:
            # Refresh failed, user needs to re-authenticate
            return None

    return credentials if credentials.valid else None


def build_calendar_service(user_id):
    """Build and return a Google Calendar API service for the user."""
    credentials = get_google_credentials(user_id)
    if not credentials:
        return None
    return build('calendar', 'v3', credentials=credentials)


def build_tasks_service(user_id):
    """Build and return a Google Tasks API service for the user."""
    credentials = get_google_credentials(user_id)
    if not credentials:
        return None
    return build('tasks', 'v1', credentials=credentials)


def build_gmail_service(user_id):
    """Build and return a Gmail API service for the user."""
    credentials = get_google_credentials(user_id)
    if not credentials:
        return None
    return build('gmail', 'v1', credentials=credentials)


def build_keep_service(user_id):
    """
    Build a Google Keep service.
    Note: Google Keep does not have an official public API.
    This uses the Google Tasks API as a workaround for note-like items,
    or falls back to a basic approach.
    """
    # Google Keep has no official API - we use a workaround via Google Tasks
    # or the user can sync notes manually
    credentials = get_google_credentials(user_id)
    if not credentials:
        return None
    # Return tasks service as closest alternative for note-like functionality
    return build('tasks', 'v1', credentials=credentials)


# ==================== OAUTH FLOW ====================

def generate_oauth_url():
    """Generate Google OAuth authorization URL."""
    try:
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': config.GOOGLE_CLIENT_ID,
                    'client_secret': config.GOOGLE_CLIENT_SECRET,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': [config.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=config.GOOGLE_SCOPES,
            redirect_uri=config.GOOGLE_REDIRECT_URI,
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',  # Force to always get refresh_token
        )

        return {'authorization_url': authorization_url, 'state': state}
    except Exception as e:
        return {'error': str(e)}


def handle_oauth_callback(code, state):
    """
    Exchange authorization code for tokens.
    Returns token data dict or error.
    """
    try:
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': config.GOOGLE_CLIENT_ID,
                    'client_secret': config.GOOGLE_CLIENT_SECRET,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': [config.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=config.GOOGLE_SCOPES,
            state=state,
            redirect_uri=config.GOOGLE_REDIRECT_URI,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user info from Google
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        idinfo = id_token.verify_oauth2_token(
            credentials.id_token, google_requests.Request(), config.GOOGLE_CLIENT_ID
        )

        return {
            'credentials': credentials,
            'email': idinfo.get('email'),
            'display_name': idinfo.get('name', idinfo.get('email', '').split('@')[0]),
        }
    except Exception as e:
        return {'error': str(e)}


# ==================== GOOGLE CALENDAR SYNC ====================

def fetch_google_calendar_events(user_id, time_min=None, time_max=None, max_results=250):
    """Fetch events from Google Calendar."""
    service = build_calendar_service(user_id)
    if not service:
        return {'error': 'Not authenticated with Google. Please connect your account.'}

    try:
        now = datetime.utcnow().isoformat() + 'Z'
        calendar_id = 'primary'

        params = {
            'maxResults': max_results,
            'singleEvents': True,
            'orderBy': 'startTime',
        }

        if time_min:
            params['timeMin'] = time_min
        else:
            params['timeMin'] = now

        if time_max:
            params['timeMax'] = time_max

        events_result = service.events().list(calendarId=calendar_id, **params).execute()
        events = events_result.get('items', [])

        return {'events': events, 'next_sync_token': events_result.get('nextSyncToken')}

    except HttpError as e:
        return {'error': f'Google Calendar API error: {str(e)}'}
    except Exception as e:
        return {'error': f'Failed to fetch Google Calendar events: {str(e)}'}


def sync_google_calendar_to_local(user_id, events=None):
    """
    Sync Google Calendar events to the local database.
    Avoids duplicates using external_id.
    Returns count of created/updated/skipped events.
    """
    if events is None:
        result = fetch_google_calendar_events(user_id)
        if 'error' in result:
            return result
        events = result['events']

    created = 0
    updated = 0
    skipped = 0
    errors = []

    with get_connection() as conn:
        for event in events:
            try:
                external_id = event.get('id', '')
                if not external_id:
                    skipped += 1
                    continue

                title = event.get('summary', 'Untitled Event')
                description = event.get('description', '')
                location = event.get('location', '')

                # Parse start time
                start = event.get('start', {})
                end = event.get('end', {})

                if 'dateTime' in start:
                    start_time = start['dateTime']
                    is_all_day = 0
                elif 'date' in start:
                    start_time = start['date']
                    is_all_day = 1
                else:
                    skipped += 1
                    continue

                if 'dateTime' in end:
                    end_time = end['dateTime']
                elif 'date' in end:
                    end_time = end['date']
                else:
                    end_time = start_time

                # Check for existing event
                existing = conn.execute(
                    "SELECT id FROM events WHERE external_id = ? AND source = 'google' AND user_id = ?",
                    (external_id, user_id)
                ).fetchone()

                if existing:
                    # Update existing event
                    conn.execute(
                        """UPDATE events SET title=?, description=?, location=?,
                           start_time=?, end_time=?, is_all_day=?, source='google',
                           external_id=?, updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (title, description, location, start_time, end_time,
                         is_all_day, external_id, existing['id'])
                    )
                    updated += 1
                else:
                    # Insert new event
                    color = '#60cdff'  # Default blue
                    if event.get('colorId'):
                        color_map = {
                            '1': '#a4bdfc', '2': '#7ae7bf', '3': '#dbadff',
                            '4': '#ff887c', '5': '#fbd75b', '6': '#ffb878',
                            '7': '#46d6db', '8': '#5484ed', '9': '#51b749',
                            '10': '#dc2127', '11': '#795548',
                        }
                        color = color_map.get(event.get('colorId'), color)

                    conn.execute(
                        """INSERT INTO events (user_id, title, description, location,
                           start_time, end_time, is_all_day, color, recurrence,
                           reminder_minutes, source, external_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'google', ?)""",
                        (user_id, title, description, location, start_time, end_time,
                         is_all_day, color, '', 15, external_id)
                    )
                    created += 1

            except Exception as e:
                errors.append({'event_id': event.get('id'), 'error': str(e)})
                skipped += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors[:10],  # Limit error details
        'total_synced': created + updated,
    }


# ==================== GOOGLE TASKS SYNC ====================

def fetch_google_tasks(user_id):
    """Fetch tasks from Google Tasks."""
    service = build_tasks_service(user_id)
    if not service:
        return {'error': 'Not authenticated with Google. Please connect your account.'}

    try:
        # Get task lists
        tasklists_result = service.tasklists().list().execute()
        tasklists = tasklists_result.get('items', [])

        all_tasks = []

        for tasklist in tasklists:
            tasklist_id = tasklist['id']
            tasks_result = service.tasks().list(
                tasklist=tasklist_id,
                showHidden=False,
                showCompleted=False,
            ).execute()
            tasks = tasks_result.get('items', [])
            for task in tasks:
                task['tasklist_title'] = tasklist.get('title', '')
                task['tasklist_id'] = tasklist_id
            all_tasks.extend(tasks)

        return {'tasks': all_tasks, 'tasklists': tasklists}

    except HttpError as e:
        return {'error': f'Google Tasks API error: {str(e)}'}
    except Exception as e:
        return {'error': f'Failed to fetch Google Tasks: {str(e)}'}


def sync_google_tasks_to_local(user_id, tasks=None):
    """
    Sync Google Tasks to the local database.
    Avoids duplicates using external_id.
    Returns count of created/updated/skipped tasks.
    """
    if tasks is None:
        result = fetch_google_tasks(user_id)
        if 'error' in result:
            return result
        tasks = result['tasks']

    created = 0
    updated = 0
    skipped = 0

    with get_connection() as conn:
        for task in tasks:
            try:
                external_id = task.get('id', '')
                if not external_id:
                    skipped += 1
                    continue

                title = task.get('title', 'Untitled Task')
                description = task.get('notes', '')
                status = 'completed' if task.get('status') == 'completed' else 'pending'

                # Parse due date
                due_date = task.get('due', task.get('updated'))

                # Map priority from Google Tasks (no native priority, use tasklist)
                priority = 0

                # Check for existing
                existing = conn.execute(
                    "SELECT id FROM tasks WHERE external_id = ? AND source = 'google' AND user_id = ?",
                    (external_id, user_id)
                ).fetchone()

                if existing:
                    conn.execute(
                        """UPDATE tasks SET title=?, description=?, due_date=?,
                           priority=?, status=?, source='google',
                           external_id=?, updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (title, description, due_date, priority, status,
                         external_id, existing['id'])
                    )
                    updated += 1
                else:
                    conn.execute(
                        """INSERT INTO tasks (user_id, title, description, due_date,
                           priority, status, category, source, external_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'google', ?)""",
                        (user_id, title, description, due_date, priority,
                         status, task.get('tasklist_title', ''), external_id)
                    )
                    created += 1

            except Exception:
                skipped += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'total_synced': created + updated,
    }


# ==================== GOOGLE NOTES (via Tasks as workaround) ====================

def fetch_google_notes(user_id):
    """
    Fetch notes from Google.
    Note: Google Keep has no official public API.
    This returns Google Tasks as a note-like fallback.
    """
    # Since Google Keep has no public API, return tasks as notes alternative
    result = fetch_google_tasks(user_id)
    if 'error' in result:
        return result

    # Transform tasks into note-like format
    notes = []
    for task in result.get('tasks', []):
        notes.append({
            'title': task.get('title', ''),
            'content': task.get('notes', ''),
            'source': 'google_tasks',
            'external_id': task.get('id', ''),
            'updated': task.get('updated', ''),
            'tasklist': task.get('tasklist_title', ''),
        })

    return {'notes': notes, 'message': 'Google Keep has no public API. Showing Google Tasks as notes.'}


def sync_google_notes_to_local(user_id):
    """
    Sync Google notes/tasks to local notes database.
    """
    result = fetch_google_tasks(user_id)
    if 'error' in result:
        return result

    tasks = result['tasks']
    created = 0
    updated = 0
    skipped = 0

    with get_connection() as conn:
        for task in tasks:
            try:
                external_id = task.get('id', '')
                if not external_id:
                    skipped += 1
                    continue

                title = task.get('title', '')
                content = task.get('notes', '')

                if not title and not content:
                    skipped += 1
                    continue

                existing = conn.execute(
                    "SELECT id FROM notes WHERE external_id = ? AND source = 'google_tasks' AND user_id = ?",
                    (external_id, user_id)
                ).fetchone()

                if existing:
                    conn.execute(
                        """UPDATE notes SET title=?, content=?, source='google_tasks',
                           external_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (title, content, external_id, existing['id'])
                    )
                    updated += 1
                else:
                    conn.execute(
                        """INSERT INTO notes (user_id, title, content, color, pinned,
                           source, external_id)
                           VALUES (?, ?, ?, ?, 0, 'google_tasks', ?)""",
                        (user_id, title, content, '#ffffff', external_id)
                    )
                    created += 1

            except Exception:
                skipped += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'total_synced': created + updated,
        'message': 'Google Keep has no public API. Syncing Google Tasks as notes.',
    }
