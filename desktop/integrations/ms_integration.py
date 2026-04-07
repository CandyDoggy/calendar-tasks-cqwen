"""
Microsoft Integration Module
Handles OAuth2 flow (via MSAL), token management, and Microsoft Graph API calls for:
- Microsoft Graph Calendar (Outlook)
- Microsoft Graph Mail (Outlook)
- Microsoft To Do (via Graph API tasks)
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests

import msal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import get_connection
import config


# ==================== CONSTANTS ====================

MICROSOFT_AUTHORITY = "https://login.microsoftonline.com/common"
MICROSOFT_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


# ==================== TOKEN MANAGEMENT ====================

def _get_user_ms_tokens(user_id):
    """Retrieve and parse Microsoft OAuth tokens for a user from the database."""
    with get_connection() as conn:
        user = conn.execute(
            "SELECT microsoft_token FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user or not user['microsoft_token']:
            return None

        try:
            token_data = json.loads(user['microsoft_token'])
            return token_data
        except (json.JSONDecodeError, TypeError):
            return {'access_token': user['microsoft_token']}


def _save_user_ms_tokens(user_id, token_data):
    """Save Microsoft OAuth token data to the user's database record."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET microsoft_token = ? WHERE id = ?",
            (json.dumps(token_data), user_id)
        )


def _build_msal_app():
    """Build and return an MSAL ConfidentialClientApplication."""
    return msal.ConfidentialClientApplication(
        client_id=config.MICROSOFT_CLIENT_ID,
        client_credential=config.MICROSOFT_CLIENT_SECRET,
        authority=MICROSOFT_AUTHORITY,
    )


def _get_access_token(user_id):
    """
    Get a valid Microsoft Graph access token for a user.
    Attempts silent token refresh first, falls back to stored token.
    Returns access token string or None if not authenticated.
    """
    token_data = _get_user_ms_tokens(user_id)
    if not token_data:
        return None

    # Check if we have a refresh token and can do silent auth
    if token_data.get('refresh_token'):
        app = _build_msal_app()
        try:
            result = app.acquire_token_silent(
                scopes=config.MICROSOFT_SCOPES,
                account=_get_ms_account_from_token(token_data),
            )
            if result and 'access_token' in result:
                # Save refreshed tokens
                _save_user_ms_tokens(user_id, result)
                return result['access_token']
        except Exception:
            pass

    # Fall back to stored access token if still valid
    access_token = token_data.get('access_token')
    if access_token:
        # Check expiry if available
        expires_on = token_data.get('expires_on')
        if expires_on:
            try:
                expiry = datetime.fromtimestamp(int(expires_on))
                if expiry < datetime.utcnow():
                    return None
            except (ValueError, TypeError):
                pass
        return access_token

    return None


def _get_ms_account_from_token(token_data):
    """
    Reconstruct an MSAL account dict from stored token data.
    MSAL accounts are dicts with home_account_id, environment, etc.
    """
    if 'home_account_id' in token_data:
        return {
            'home_account_id': token_data['home_account_id'],
            'environment': token_data.get('environment', 'login.microsoftonline.com'),
            'realm': token_data.get('realm', 'consumers'),
            'local_account_id': token_data.get('local_account_id', ''),
            'username': token_data.get('username', ''),
            'authority_type': token_data.get('authority_type', 'MSSTS'),
        }
    return None


# ==================== OAUTH FLOW ====================

def generate_oauth_url():
    """Generate Microsoft OAuth2 authorization URL."""
    # Validate credentials before attempting OAuth
    if 'YOUR_MICROSOFT' in config.MICROSOFT_CLIENT_ID or 'YOUR_MICROSOFT' in config.MICROSOFT_CLIENT_SECRET:
        return {
            'error': 'Microsoft OAuth credentials not configured. '
                     'Please add your credentials to desktop/config.json.'
        }

    try:
        app = _build_msal_app()

        result = app.initiate_auth_code_flow(
            scopes=config.MICROSOFT_SCOPES,
            redirect_uri=config.MICROSOFT_REDIRECT_URI,
        )

        # Store the state in the result so we can validate it on callback
        return {
            'authorization_url': result['auth_uri'],
            'state': result['state'],
        }
    except Exception as e:
        return {'error': str(e)}


def handle_oauth_callback(code, state):
    """
    Exchange authorization code for tokens using MSAL.
    Returns token data dict with account info, or error.
    """
    try:
        app = _build_msal_app()

        # Build the token request
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=config.MICROSOFT_SCOPES,
            redirect_uri=config.MICROSOFT_REDIRECT_URI,
        )

        if 'error' in result:
            return {'error': result.get('error_description', result['error'])}

        # Get user info from Graph API
        access_token = result.get('access_token')
        if not access_token:
            return {'error': 'No access token received'}

        user_info = _graph_get(access_token, '/me')
        if 'error' in user_info:
            return {'error': f'Failed to fetch user info: {user_info["error"]}'}

        return {
            'token_data': result,
            'email': user_info.get('mail') or user_info.get('userPrincipalName', ''),
            'display_name': user_info.get('displayName', ''),
            'user_principal_name': user_info.get('userPrincipalName', ''),
        }
    except Exception as e:
        return {'error': str(e)}


# ==================== MICROSOFT GRAPH API HELPERS ====================

def _graph_get(access_token, endpoint, params=None):
    """Make a GET request to Microsoft Graph API."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    url = f'{MICROSOFT_GRAPH_BASE_URL}{endpoint}'

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {'error': f'Graph API HTTP error: {str(e)} - {response.text}'}
    except Exception as e:
        return {'error': f'Graph API request failed: {str(e)}'}


def _graph_post(access_token, endpoint, body):
    """Make a POST request to Microsoft Graph API."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    url = f'{MICROSOFT_GRAPH_BASE_URL}{endpoint}'

    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.exceptions.HTTPError as e:
        return {'error': f'Graph API HTTP error: {str(e)} - {response.text}'}
    except Exception as e:
        return {'error': f'Graph API request failed: {str(e)}'}


# ==================== CALENDAR ====================

def fetch_ms_calendar_events(user_id, start=None, end=None):
    """
    Fetch events from Microsoft Graph Calendar (Outlook).
    Uses /me/calendarView with start/end time range.
    """
    access_token = _get_access_token(user_id)
    if not access_token:
        return {'error': 'Not authenticated with Microsoft. Please connect your account.'}

    if start is None:
        start = datetime.utcnow().isoformat() + 'Z'
    if end is None:
        end = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'

    params = {
        'startDateTime': start,
        'endDateTime': end,
        '$top': 250,
    }

    result = _graph_get(access_token, '/me/calendarView', params=params)

    if 'error' in result:
        return result

    return {'events': result.get('value', [])}


def sync_ms_calendar_to_local(user_id, events=None):
    """
    Sync Microsoft Outlook calendar events to the local database.
    Avoids duplicates using external_id.
    Returns count of created/updated/skipped events.
    """
    if events is None:
        result = fetch_ms_calendar_events(user_id)
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

                title = event.get('subject', 'Untitled Event')
                description = event.get('bodyPreview', '') or (
                    event.get('body', {}).get('content', '')
                )
                location = ''
                locations = event.get('locations', [])
                if locations:
                    location = locations[0].get('displayName', '')

                # Parse start/end times
                start = event.get('start', {})
                end = event.get('end', {})

                if start.get('dateTime'):
                    start_time = start['dateTime']
                    is_all_day = start.get('timeZone') is None or start_time.endswith('T00:00:00')
                elif start.get('date'):
                    start_time = start['date']
                    is_all_day = 1
                else:
                    skipped += 1
                    continue

                if end.get('dateTime'):
                    end_time = end['dateTime']
                elif end.get('date'):
                    end_time = end['date']
                else:
                    end_time = start_time

                # Determine color from event categories
                color = '#60cdff'
                categories = event.get('categories', [])
                if categories:
                    color_map = {
                        'Red': '#dc2127',
                        'Blue': '#60cdff',
                        'Green': '#51b749',
                        'Yellow': '#fbd75b',
                        'Orange': '#ffb878',
                        'Purple': '#dbadff',
                        'Teal': '#46d6db',
                        'Gray': '#8a8a8a',
                    }
                    color = color_map.get(categories[0], color)

                # Check for existing
                existing = conn.execute(
                    "SELECT id FROM events WHERE external_id = ? AND source = 'microsoft' AND user_id = ?",
                    (external_id, user_id)
                ).fetchone()

                if existing:
                    conn.execute(
                        """UPDATE events SET title=?, description=?, location=?,
                           start_time=?, end_time=?, is_all_day=?, color=?,
                           source='microsoft', external_id=?, updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (title, description, location, start_time, end_time,
                         is_all_day, color, external_id, existing['id'])
                    )
                    updated += 1
                else:
                    conn.execute(
                        """INSERT INTO events (user_id, title, description, location,
                           start_time, end_time, is_all_day, color, recurrence,
                           reminder_minutes, source, external_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'microsoft', ?)""",
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
        'errors': errors[:10],
        'total_synced': created + updated,
    }


# ==================== MAIL ====================

def fetch_ms_mail_inbox(user_id, max_results=20):
    """
    Fetch inbox messages from Microsoft Graph Mail (Outlook).
    Uses /me/messages with inbox filter.
    """
    access_token = _get_access_token(user_id)
    if not access_token:
        return {'error': 'Not authenticated with Microsoft. Please connect your account.'}

    params = {
        '$filter': "isRead eq false and parentFolderId ne null",
        '$top': max_results,
        '$orderby': 'receivedDateTime desc',
        '$select': 'id,subject,from,toRecipients,receivedDateTime,isRead,bodyPreview,hasAttachments',
    }

    result = _graph_get(access_token, '/me/mailFolders/inbox/messages', params=params)

    if 'error' in result:
        # Fallback: try /me/messages without inbox filter
        params.pop('$filter', None)
        result = _graph_get(access_token, '/me/messages', params=params)
        if 'error' in result:
            return result

    messages = result.get('value', [])

    # Format messages
    formatted = []
    for msg in messages:
        sender = msg.get('from', {})
        sender_email = sender.get('emailAddress', {}).get('address', '')
        sender_name = sender.get('emailAddress', {}).get('name', sender_email)

        recipients = msg.get('toRecipients', [])
        to_addresses = []
        for r in recipients:
            email = r.get('emailAddress', {})
            to_addresses.append(email.get('address', ''))

        formatted.append({
            'id': msg.get('id'),
            'subject': msg.get('subject', ''),
            'from': f'{sender_name} <{sender_email}>',
            'to': ', '.join(to_addresses),
            'received_date_time': msg.get('receivedDateTime'),
            'is_read': msg.get('isRead', False),
            'body_preview': msg.get('bodyPreview', ''),
            'has_attachments': msg.get('hasAttachments', False),
        })

    return {
        'messages': formatted,
        '@odata.nextLink': result.get('@odata.nextLink'),
    }


def fetch_ms_message(user_id, message_id):
    """
    Fetch a full Microsoft Graph mail message by ID.
    Uses /me/messages/{id}
    """
    access_token = _get_access_token(user_id)
    if not access_token:
        return {'error': 'Not authenticated with Microsoft. Please connect your account.'}

    # Request full message with body
    params = {
        '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,'
                   'isRead,body,hasAttachments,conversationId,inferenceClassification',
    }

    result = _graph_get(access_token, f'/me/messages/{message_id}', params=params)

    if 'error' in result:
        return result

    sender = result.get('from', {})
    sender_email = sender.get('emailAddress', {}).get('address', '')
    sender_name = sender.get('emailAddress', {}).get('name', sender_email)

    recipients = result.get('toRecipients', [])
    to_addresses = []
    for r in recipients:
        email = r.get('emailAddress', {})
        to_addresses.append(email.get('address', ''))

    cc_recipients = result.get('ccRecipients', [])
    cc_addresses = []
    for r in cc_recipients:
        email = r.get('emailAddress', {})
        cc_addresses.append(email.get('address', ''))

    body = result.get('body', {})
    body_content = body.get('content', '')
    body_type = body.get('contentType', 'text')

    return {
        'id': result.get('id'),
        'subject': result.get('subject', ''),
        'from': f'{sender_name} <{sender_email}>',
        'to': ', '.join(to_addresses),
        'cc': ', '.join(cc_addresses),
        'received_date_time': result.get('receivedDateTime'),
        'is_read': result.get('isRead', False),
        'has_attachments': result.get('hasAttachments', False),
        'conversation_id': result.get('conversationId'),
        'body': body_content,
        'body_type': body_type,
    }


def send_ms_mail(user_id, to, subject, body, cc=None, bcc=None, html=False):
    """
    Send an email via Microsoft Graph Mail API.
    Uses POST /me/sendMail
    """
    access_token = _get_access_token(user_id)
    if not access_token:
        return {'error': 'Not authenticated with Microsoft. Please connect your account.'}

    if not to or not subject or not body:
        return {'error': 'to, subject, and body are required'}

    # Build the message payload for Graph API
    message = {
        'message': {
            'subject': subject,
            'body': {
                'contentType': 'HTML' if html else 'Text',
                'content': body,
            },
            'toRecipients': [
                {
                    'emailAddress': {
                        'address': addr.strip(),
                    }
                }
                for addr in to.split(',')
                if addr.strip()
            ],
        },
        'saveToSentItems': True,
    }

    if cc:
        message['message']['ccRecipients'] = [
            {'emailAddress': {'address': addr.strip()}}
            for addr in cc.split(',')
            if addr.strip()
        ]

    if bcc:
        message['message']['bccRecipients'] = [
            {'emailAddress': {'address': addr.strip()}}
            for addr in bcc.split(',')
            if addr.strip()
        ]

    result = _graph_post(access_token, '/me/sendMail', body=message)

    if 'error' in result:
        return result

    # Log to sent_mail table
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO sent_mail (user_id, to_address, subject, body, provider)
               VALUES (?, ?, ?, ?, 'outlook')""",
            (user_id, to, subject, body[:5000])
        )

    return {'message': 'Email sent successfully'}


# ==================== MICROSOFT TO DO (via Graph API) ====================

def fetch_ms_todo_tasks(user_id):
    """
    Fetch tasks from Microsoft To Do via Graph API.
    Note: Microsoft To Do uses the /me/todo/lists and /me/todo/lists/{id}/tasks endpoints.
    """
    access_token = _get_access_token(user_id)
    if not access_token:
        return {'error': 'Not authenticated with Microsoft. Please connect your account.'}

    try:
        # Get task lists
        lists_result = _graph_get(access_token, '/me/todo/lists')
        if 'error' in lists_result:
            return lists_result

        task_lists = lists_result.get('value', [])
        all_tasks = []

        for task_list in task_lists:
            list_id = task_list.get('id')
            if not list_id:
                continue

            tasks_result = _graph_get(
                access_token,
                f'/me/todo/lists/{list_id}/tasks',
                params={'$filter': "status ne 'completed'"}
            )

            if 'error' not in tasks_result:
                tasks = tasks_result.get('value', [])
                for task in tasks:
                    task['list_title'] = task_list.get('displayName', '')
                    task['list_id'] = list_id
                all_tasks.extend(tasks)

        return {'tasks': all_tasks, 'task_lists': task_lists}

    except Exception as e:
        return {'error': f'Failed to fetch Microsoft To Do tasks: {str(e)}'}


def sync_ms_todo_to_local(user_id, tasks=None):
    """
    Sync Microsoft To Do tasks to the local database.
    Avoids duplicates using external_id.
    Returns count of created/updated/skipped tasks.
    """
    if tasks is None:
        result = fetch_ms_todo_tasks(user_id)
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
                description = task.get('body', {}).get('content', '')
                status = 'completed' if task.get('status') == 'completed' else 'pending'

                # Parse due date
                due = task.get('dueDateTime', {})
                due_date = due.get('dateTime', '') if due else ''

                # Map importance to priority (1-5 -> 0-3 scale)
                importance = task.get('importance', 'normal')
                priority_map = {'low': 0, 'normal': 1, 'high': 2, 'urgent': 3}
                priority = priority_map.get(importance, 1)

                # Check for existing
                existing = conn.execute(
                    "SELECT id FROM tasks WHERE external_id = ? AND source = 'microsoft' AND user_id = ?",
                    (external_id, user_id)
                ).fetchone()

                if existing:
                    conn.execute(
                        """UPDATE tasks SET title=?, description=?, due_date=?,
                           priority=?, status=?, category=?, source='microsoft',
                           external_id=?, updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (title, description, due_date, priority, status,
                         task.get('list_title', ''), external_id, existing['id'])
                    )
                    updated += 1
                else:
                    conn.execute(
                        """INSERT INTO tasks (user_id, title, description, due_date,
                           priority, status, category, source, external_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'microsoft', ?)""",
                        (user_id, title, description, due_date, priority,
                         status, task.get('list_title', ''), external_id)
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
