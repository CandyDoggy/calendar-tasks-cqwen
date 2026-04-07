"""
Flask API Server for Calendar & Tasks app.
Provides REST API for both desktop and web versions.
"""

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import sqlite3
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import get_db_path, get_connection, init_db
import config

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = config.JWT_SECRET_KEY
CORS(app)
jwt = JWTManager(app)


# ==================== AUTH ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    display_name = data.get('display_name', email.split('@')[0])
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    import bcrypt
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password_hash, display_name, auth_provider) VALUES (?, ?, ?, 'local')",
                (email, password_hash, display_name)
            )
            user_id = cursor.lastrowid
            # Create default settings
            cursor.execute(
                "INSERT INTO settings (user_id) VALUES (?)",
                (user_id,)
            )
            access_token = create_access_token(identity=user_id)
            return jsonify({
                'access_token': access_token,
                'user': {'id': user_id, 'email': email, 'display_name': display_name}
            }), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 400


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    import bcrypt
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not user['password_hash']:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        access_token = create_access_token(identity=user['id'])
        return jsonify({
            'access_token': access_token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'display_name': user['display_name'],
                'auth_provider': user['auth_provider']
            }
        })


@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    data = request.get_json()
    token = data.get('token')
    if not token:
        return jsonify({'error': 'Google token required'}), 400
    
    # TODO: Verify Google token
    email = "user@gmail.com"  # Placeholder
    display_name = "Google User"
    
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, display_name, auth_provider, google_token) VALUES (?, ?, 'google', ?)",
                (email, display_name, token)
            )
            user_id = cursor.lastrowid
            cursor.execute("INSERT INTO settings (user_id) VALUES (?)", (user_id,))
        else:
            user_id = user['id']
            conn.execute("UPDATE users SET google_token = ? WHERE id = ?", (token, user_id))
        
        access_token = create_access_token(identity=user_id)
        return jsonify({'access_token': access_token, 'user': {'id': user_id, 'email': email}})


@app.route('/api/auth/microsoft', methods=['POST'])
def microsoft_auth():
    data = request.get_json()
    token = data.get('token')
    if not token:
        return jsonify({'error': 'Microsoft token required'}), 400
    
    # TODO: Verify Microsoft token
    email = "user@outlook.com"  # Placeholder
    display_name = "Microsoft User"
    
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, display_name, auth_provider, microsoft_token) VALUES (?, ?, 'microsoft', ?)",
                (email, display_name, token)
            )
            user_id = cursor.lastrowid
            cursor.execute("INSERT INTO settings (user_id) VALUES (?)", (user_id,))
        else:
            user_id = user['id']
            conn.execute("UPDATE users SET microsoft_token = ? WHERE id = ?", (token, user_id))
        
        access_token = create_access_token(identity=user_id)
        return jsonify({'access_token': access_token, 'user': {'id': user_id, 'email': email}})


# ==================== EVENTS ====================

@app.route('/api/events', methods=['GET'])
@jwt_required()
def get_events():
    user_id = get_jwt_identity()
    start = request.args.get('start')
    end = request.args.get('end')
    
    query = "SELECT * FROM events WHERE user_id = ?"
    params = [user_id]
    
    if start and end:
        query += " AND start_time >= ? AND start_time <= ?"
        params.extend([start, end])
    
    query += " ORDER BY start_time"
    
    with get_connection() as conn:
        events = conn.execute(query, params).fetchall()
        return jsonify([dict(e) for e in events])


@app.route('/api/events', methods=['POST'])
@jwt_required()
def create_event():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (user_id, title, description, location, start_time, end_time, is_all_day, color, recurrence, reminder_minutes, source, external_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get('title', ''),
            data.get('description', ''),
            data.get('location', ''),
            data.get('start_time'),
            data.get('end_time'),
            data.get('is_all_day', 0),
            data.get('color', '#60cdff'),
            data.get('recurrence', ''),
            data.get('reminder_minutes', 15),
            data.get('source', 'local'),
            data.get('external_id', '')
        ))
        event_id = cursor.lastrowid
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return jsonify(dict(event)), 201


@app.route('/api/events/<int:event_id>', methods=['PUT'])
@jwt_required()
def update_event(event_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    
    with get_connection() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ? AND user_id = ?", (event_id, user_id)).fetchone()
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        conn.execute("""
            UPDATE events SET title=?, description=?, location=?, start_time=?, end_time=?, 
            is_all_day=?, color=?, recurrence=?, reminder_minutes=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            data.get('title', event['title']),
            data.get('description', event['description']),
            data.get('location', event['location']),
            data.get('start_time', event['start_time']),
            data.get('end_time', event['end_time']),
            data.get('is_all_day', event['is_all_day']),
            data.get('color', event['color']),
            data.get('recurrence', event['recurrence']),
            data.get('reminder_minutes', event['reminder_minutes']),
            event_id
        ))
        
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return jsonify(dict(event))


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    user_id = get_jwt_identity()
    
    with get_connection() as conn:
        result = conn.execute("DELETE FROM events WHERE id = ? AND user_id = ?", (event_id, user_id))
        if result.rowcount == 0:
            return jsonify({'error': 'Event not found'}), 404
        return jsonify({'message': 'Event deleted'})


# ==================== TASKS ====================

@app.route('/api/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    user_id = get_jwt_identity()
    status = request.args.get('status')
    
    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [user_id]
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY due_date ASC, priority DESC"
    
    with get_connection() as conn:
        tasks = conn.execute(query, params).fetchall()
        return jsonify([dict(t) for t in tasks])


@app.route('/api/tasks', methods=['POST'])
@jwt_required()
def create_task():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (user_id, title, description, due_date, priority, status, category, source, external_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get('title', ''),
            data.get('description', ''),
            data.get('due_date'),
            data.get('priority', 0),
            data.get('status', 'pending'),
            data.get('category', ''),
            data.get('source', 'local'),
            data.get('external_id', '')
        ))
        task_id = cursor.lastrowid
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify(dict(task)), 201


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    
    with get_connection() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        conn.execute("""
            UPDATE tasks SET title=?, description=?, due_date=?, priority=?, status=?, 
            category=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (
            data.get('title', task['title']),
            data.get('description', task['description']),
            data.get('due_date', task['due_date']),
            data.get('priority', task['priority']),
            data.get('status', task['status']),
            data.get('category', task['category']),
            task_id
        ))
        
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify(dict(task))


# ==================== NOTES ====================

@app.route('/api/notes', methods=['GET'])
@jwt_required()
def get_notes():
    user_id = get_jwt_identity()
    
    with get_connection() as conn:
        notes = conn.execute(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY pinned DESC, updated_at DESC",
            (user_id,)
        ).fetchall()
        return jsonify([dict(n) for n in notes])


@app.route('/api/notes', methods=['POST'])
@jwt_required()
def create_note():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notes (user_id, title, content, color, pinned, source, external_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get('title', ''),
            data.get('content', ''),
            data.get('color', '#ffffff'),
            data.get('pinned', 0),
            data.get('source', 'local'),
            data.get('external_id', '')
        ))
        note_id = cursor.lastrowid
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return jsonify(dict(note)), 201


@app.route('/api/notes/<int:note_id>', methods=['PUT'])
@jwt_required()
def update_note(note_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    with get_connection() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)).fetchone()
        if not note:
            return jsonify({'error': 'Note not found'}), 404

        conn.execute("""
            UPDATE notes SET title=?, content=?, color=?, pinned=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            data.get('title', note['title']),
            data.get('content', note['content']),
            data.get('color', note['color']),
            data.get('pinned', note['pinned']),
            note_id
        ))

        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return jsonify(dict(note))


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    user_id = get_jwt_identity()

    with get_connection() as conn:
        result = conn.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        if result.rowcount == 0:
            return jsonify({'error': 'Note not found'}), 404
        return jsonify({'message': 'Note deleted'})


# ==================== SETTINGS ====================

@app.route('/api/settings', methods=['GET'])
@jwt_required()
def get_settings():
    user_id = get_jwt_identity()
    
    with get_connection() as conn:
        settings = conn.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,)).fetchone()
        if not settings:
            return jsonify({})
        return jsonify(dict(settings))


@app.route('/api/settings', methods=['PUT'])
@jwt_required()
def update_settings():
    user_id = get_jwt_identity()
    data = request.get_json()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO settings (user_id, theme, default_view, week_start, notifications_enabled)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                theme=?, default_view=?, week_start=?, notifications_enabled=?
        """, (
            user_id,
            data.get('theme', 'dark'),
            data.get('default_view', 'month'),
            data.get('week_start', 0),
            data.get('notifications_enabled', 1),
            data.get('theme', 'dark'),
            data.get('default_view', 'month'),
            data.get('week_start', 0),
            data.get('notifications_enabled', 1)
        ))
        settings = conn.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,)).fetchone()
        return jsonify(dict(settings))


# ==================== GOOGLE OAUTH ====================

@app.route('/api/integrations/google/auth-url', methods=['GET'])
@jwt_required()
def google_auth_url():
    """Generate Google OAuth authorization URL."""
    from integrations.google_integration import generate_oauth_url
    result = generate_oauth_url()
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
    return jsonify(result)


@app.route('/api/integrations/google/callback', methods=['POST', 'GET'])
def google_callback():
    """
    Handle Google OAuth callback.
    POST: Receive code from frontend
    GET: Direct callback from Google (redirects to frontend)
    """
    if request.method == 'POST':
        data = request.get_json()
        code = data.get('code')
        state = data.get('state', '')

        if not code:
            return jsonify({'error': 'Authorization code required'}), 400

        from integrations.google_integration import handle_oauth_callback
        result = handle_oauth_callback(code, state)

        if 'error' in result:
            return jsonify({'error': result['error']}), 400

        credentials = result['credentials']
        email = result['email']
        display_name = result['display_name']

        with get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO users (email, display_name, auth_provider)
                       VALUES (?, ?, 'google')""",
                    (email, display_name)
                )
                user_id = cursor.lastrowid
                cursor.execute("INSERT INTO settings (user_id) VALUES (?)", (user_id,))
            else:
                user_id = user['id']

            # Save OAuth credentials
            from integrations.google_integration import _save_user_google_tokens
            _save_user_google_tokens(user_id, credentials)

            access_token = create_access_token(identity=user_id)
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user_id,
                    'email': email,
                    'display_name': display_name,
                    'auth_provider': 'google',
                }
            })

    else:
        # GET request - redirect to frontend with code
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

        if error:
            return redirect(f'{frontend_url}/auth/google/callback?error={error}')

        if code:
            return redirect(f'{frontend_url}/auth/google/callback?code={code}&state={state or ""}')

        return redirect(f'{frontend_url}/auth/google/callback?error=no_code')


@app.route('/api/integrations/google/disconnect', methods=['POST'])
@jwt_required()
def google_disconnect():
    """Disconnect Google account and remove stored tokens."""
    user_id = get_jwt_identity()

    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET google_token = NULL WHERE id = ?",
            (user_id,)
        )
    return jsonify({'message': 'Google account disconnected'})


@app.route('/api/integrations/google/status', methods=['GET'])
@jwt_required()
def google_connection_status():
    """Check if user has valid Google credentials."""
    user_id = get_jwt_identity()
    from integrations.google_integration import get_google_credentials

    credentials = get_google_credentials(user_id)
    if credentials:
        return jsonify({'connected': True, 'scopes': credentials.scopes})
    return jsonify({'connected': False})


# ==================== GOOGLE CALENDAR ====================

@app.route('/api/integrations/google/calendar', methods=['GET'])
@jwt_required()
def get_google_calendar_events():
    """Fetch events from Google Calendar."""
    user_id = get_jwt_identity()
    time_min = request.args.get('time_min')
    time_max = request.args.get('time_max')
    max_results = int(request.args.get('max_results', 250))

    from integrations.google_integration import fetch_google_calendar_events
    result = fetch_google_calendar_events(user_id, time_min, time_max, max_results)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/google/calendar/sync', methods=['POST'])
@jwt_required()
def sync_google_calendar():
    """Sync Google Calendar events to local database."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    from integrations.google_integration import sync_google_calendar_to_local
    result = sync_google_calendar_to_local(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/google/calendar/events/<external_id>', methods=['DELETE'])
@jwt_required()
def delete_google_calendar_event(external_id):
    """Delete a Google Calendar event (both from Google and local)."""
    user_id = get_jwt_identity()

    from integrations.google_integration import build_calendar_service
    service = build_calendar_service(user_id)
    if not service:
        return jsonify({'error': 'Not authenticated with Google'}), 400

    try:
        # Delete from Google Calendar
        service.events().delete(
            calendarId='primary',
            eventId=external_id
        ).execute()

        # Delete from local DB
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM events WHERE external_id = ? AND source = 'google' AND user_id = ?",
                (external_id, user_id)
            )

        return jsonify({'message': 'Event deleted from Google Calendar and local database'})

    except Exception as e:
        return jsonify({'error': f'Failed to delete event: {str(e)}'}), 500


# ==================== GOOGLE TASKS ====================

@app.route('/api/integrations/google/tasks', methods=['GET'])
@jwt_required()
def get_google_tasks():
    """Fetch tasks from Google Tasks."""
    user_id = get_jwt_identity()

    from integrations.google_integration import fetch_google_tasks
    result = fetch_google_tasks(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/google/tasks/sync', methods=['POST'])
@jwt_required()
def sync_google_tasks():
    """Sync Google Tasks to local database."""
    user_id = get_jwt_identity()

    from integrations.google_integration import sync_google_tasks_to_local
    result = sync_google_tasks_to_local(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


# ==================== GOOGLE NOTES ====================

@app.route('/api/integrations/google/notes', methods=['GET'])
@jwt_required()
def get_google_notes():
    """
    Fetch notes from Google.
    Note: Google Keep has no public API. Returns Google Tasks as notes alternative.
    """
    user_id = get_jwt_identity()

    from integrations.google_integration import fetch_google_notes
    result = fetch_google_notes(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/google/notes/sync', methods=['POST'])
@jwt_required()
def sync_google_notes():
    """
    Sync Google notes/tasks to local database.
    Note: Google Keep has no public API. Syncs Google Tasks as notes.
    """
    user_id = get_jwt_identity()

    from integrations.google_integration import sync_google_notes_to_local
    result = sync_google_notes_to_local(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


# ==================== GMAIL ====================

@app.route('/api/integrations/gmail/send', methods=['POST'])
@jwt_required()
def gmail_send():
    """Send email via Gmail API."""
    user_id = get_jwt_identity()
    data = request.get_json()

    to_address = data.get('to')
    subject = data.get('subject')
    body = data.get('body')

    if not to_address or not subject or not body:
        return jsonify({'error': 'to, subject, and body are required'}), 400

    from integrations.gmail_integration import send_gmail
    result = send_gmail(
        user_id=user_id,
        to_address=to_address,
        subject=subject,
        body=body,
        cc=data.get('cc'),
        bcc=data.get('bcc'),
        html=data.get('html', False),
    )

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result), 201


@app.route('/api/integrations/gmail/inbox', methods=['GET'])
@jwt_required()
def gmail_inbox():
    """Fetch inbox messages from Gmail."""
    user_id = get_jwt_identity()
    max_results = int(request.args.get('max_results', 20))
    query = request.args.get('q', '')

    from integrations.gmail_integration import fetch_gmail_inbox
    result = fetch_gmail_inbox(user_id, max_results, query)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/gmail/messages/<message_id>', methods=['GET'])
@jwt_required()
def gmail_get_message(message_id):
    """Fetch a full Gmail message by ID."""
    user_id = get_jwt_identity()

    from integrations.gmail_integration import fetch_gmail_message
    result = fetch_gmail_message(user_id, message_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


# ==================== MICROSOFT OAUTH ====================

@app.route('/api/integrations/microsoft/auth-url', methods=['GET'])
@jwt_required()
def microsoft_auth_url():
    """Generate Microsoft OAuth2 authorization URL."""
    from integrations.ms_integration import generate_oauth_url
    result = generate_oauth_url()
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
    return jsonify(result)


@app.route('/api/integrations/microsoft/callback', methods=['POST', 'GET'])
def microsoft_callback():
    """
    Handle Microsoft OAuth2 callback.
    POST: Receive code from frontend
    GET: Direct callback from Microsoft (redirects to frontend)
    """
    if request.method == 'POST':
        data = request.get_json()
        code = data.get('code')
        state = data.get('state', '')

        if not code:
            return jsonify({'error': 'Authorization code required'}), 400

        from integrations.ms_integration import handle_oauth_callback
        result = handle_oauth_callback(code, state)

        if 'error' in result:
            return jsonify({'error': result['error']}), 400

        token_data = result['token_data']
        email = result['email']
        display_name = result['display_name']

        with get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO users (email, display_name, auth_provider)
                       VALUES (?, ?, 'microsoft')""",
                    (email, display_name)
                )
                user_id = cursor.lastrowid
                cursor.execute("INSERT INTO settings (user_id) VALUES (?)", (user_id,))
            else:
                user_id = user['id']

            # Save OAuth credentials
            from integrations.ms_integration import _save_user_ms_tokens
            _save_user_ms_tokens(user_id, token_data)

            access_token = create_access_token(identity=user_id)
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user_id,
                    'email': email,
                    'display_name': display_name,
                    'auth_provider': 'microsoft',
                }
            })

    else:
        # GET request - redirect to frontend with code
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

        if error:
            return redirect(f'{frontend_url}/auth/microsoft/callback?error={error}')

        if code:
            return redirect(f'{frontend_url}/auth/microsoft/callback?code={code}&state={state or ""}')

        return redirect(f'{frontend_url}/auth/microsoft/callback?error=no_code')


@app.route('/api/integrations/microsoft/disconnect', methods=['POST'])
@jwt_required()
def microsoft_disconnect():
    """Disconnect Microsoft account and remove stored tokens."""
    user_id = get_jwt_identity()

    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET microsoft_token = NULL WHERE id = ?",
            (user_id,)
        )
    return jsonify({'message': 'Microsoft account disconnected'})


@app.route('/api/integrations/microsoft/status', methods=['GET'])
@jwt_required()
def microsoft_connection_status():
    """Check if user has valid Microsoft credentials."""
    user_id = get_jwt_identity()
    from integrations.ms_integration import _get_access_token

    access_token = _get_access_token(user_id)
    if access_token:
        return jsonify({'connected': True, 'scopes': config.MICROSOFT_SCOPES})
    return jsonify({'connected': False})


# ==================== MICROSOFT CALENDAR ====================

@app.route('/api/integrations/microsoft/calendar', methods=['GET'])
@jwt_required()
def get_microsoft_calendar_events():
    """Fetch events from Microsoft Graph Calendar (Outlook)."""
    user_id = get_jwt_identity()
    time_min = request.args.get('time_min')
    time_max = request.args.get('time_max')

    from integrations.ms_integration import fetch_ms_calendar_events
    result = fetch_ms_calendar_events(user_id, time_min, time_max)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/microsoft/calendar/sync', methods=['POST'])
@jwt_required()
def sync_microsoft_calendar():
    """Sync Microsoft Outlook calendar events to local database."""
    user_id = get_jwt_identity()

    from integrations.ms_integration import sync_ms_calendar_to_local
    result = sync_ms_calendar_to_local(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/microsoft/calendar/events/<external_id>', methods=['DELETE'])
@jwt_required()
def delete_microsoft_calendar_event(external_id):
    """Delete a Microsoft Outlook calendar event (both from Graph API and local DB)."""
    user_id = get_jwt_identity()
    from integrations.ms_integration import _get_access_token, _graph_post

    access_token = _get_access_token(user_id)
    if not access_token:
        return jsonify({'error': 'Not authenticated with Microsoft'}), 400

    try:
        # Delete from Microsoft Graph (soft delete via PATCH cancel)
        # Note: Graph API doesn't have a simple delete endpoint for calendar events
        # We cancel the event instead
        _graph_post(access_token, f'/me/events/{external_id}/cancel', {})

        # Delete from local DB
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM events WHERE external_id = ? AND source = 'microsoft' AND user_id = ?",
                (external_id, user_id)
            )

        return jsonify({'message': 'Event deleted from Outlook Calendar and local database'})

    except Exception as e:
        return jsonify({'error': f'Failed to delete event: {str(e)}'}), 500


# ==================== MICROSOFT TODO ====================

@app.route('/api/integrations/microsoft/todo', methods=['GET'])
@jwt_required()
def get_microsoft_todo_tasks():
    """Fetch tasks from Microsoft To Do via Graph API."""
    user_id = get_jwt_identity()

    from integrations.ms_integration import fetch_ms_todo_tasks
    result = fetch_ms_todo_tasks(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/microsoft/todo/sync', methods=['POST'])
@jwt_required()
def sync_microsoft_todo():
    """Sync Microsoft To Do tasks to local database."""
    user_id = get_jwt_identity()

    from integrations.ms_integration import sync_ms_todo_to_local
    result = sync_ms_todo_to_local(user_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


# ==================== MICROSOFT GRAPH MAIL ====================

@app.route('/api/integrations/msgraph/mail/inbox', methods=['GET'])
@jwt_required()
def msgraph_mail_inbox():
    """Fetch inbox messages from Microsoft Graph Mail (Outlook)."""
    user_id = get_jwt_identity()
    max_results = int(request.args.get('max_results', 20))

    from integrations.ms_integration import fetch_ms_mail_inbox
    result = fetch_ms_mail_inbox(user_id, max_results)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/msgraph/mail/messages/<message_id>', methods=['GET'])
@jwt_required()
def msgraph_get_message(message_id):
    """Fetch a full Microsoft Graph mail message by ID."""
    user_id = get_jwt_identity()

    from integrations.ms_integration import fetch_ms_message
    result = fetch_ms_message(user_id, message_id)

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result)


@app.route('/api/integrations/msgraph/mail/send', methods=['POST'])
@jwt_required()
def msgraph_send_mail():
    """Send email via Microsoft Graph Mail API."""
    user_id = get_jwt_identity()
    data = request.get_json()

    to_address = data.get('to')
    subject = data.get('subject')
    body = data.get('body')

    if not to_address or not subject or not body:
        return jsonify({'error': 'to, subject, and body are required'}), 400

    from integrations.ms_integration import send_ms_mail
    result = send_ms_mail(
        user_id=user_id,
        to=to_address,
        subject=subject,
        body=body,
        cc=data.get('cc'),
        bcc=data.get('bcc'),
        html=data.get('html', False),
    )

    if 'error' in result:
        return jsonify({'error': result['error']}), 400 if 'Not authenticated' in result['error'] else 500

    return jsonify(result), 201


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
