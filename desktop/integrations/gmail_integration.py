"""
Gmail Integration Module
Handles sending and fetching emails via the Gmail API.
"""

import base64
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import get_connection
from integrations.google_integration import build_gmail_service


def send_gmail(user_id, to_address, subject, body, cc=None, bcc=None, html=False):
    """
    Send an email via Gmail API.
    Returns message id or error.
    """
    service = build_gmail_service(user_id)
    if not service:
        return {'error': 'Not authenticated with Google. Please connect your account.'}

    try:
        # Get user's email address from the profile
        profile = service.users().get(userId='me').execute()
        from_address = profile.get('emailAddress', '')

        # Create message
        message = MIMEMultipart()
        message['to'] = to_address
        message['from'] = from_address
        message['subject'] = subject

        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc

        if html:
            message.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            message.attach(MIMEText(body, 'plain', 'utf-8'))

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

        # Send
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()

        # Log to sent_mail table
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO sent_mail (user_id, to_address, subject, body, provider)
                   VALUES (?, ?, ?, ?, 'gmail')""",
                (user_id, to_address, subject, body[:5000])  # Truncate body for storage
            )

        return {
            'message_id': sent_message.get('id'),
            'thread_id': sent_message.get('threadId'),
            'label_ids': sent_message.get('labelIds', []),
        }

    except HttpError as e:
        return {'error': f'Gmail API error: {str(e)}'}
    except Exception as e:
        return {'error': f'Failed to send email: {str(e)}'}


def fetch_gmail_inbox(user_id, max_results=20, query=''):
    """
    Fetch inbox messages from Gmail.
    Returns list of message summaries.
    """
    service = build_gmail_service(user_id)
    if not service:
        return {'error': 'Not authenticated with Google. Please connect your account.'}

    try:
        # List messages
        list_params = {
            'userId': 'me',
            'maxResults': max_results,
            'labelIds': ['INBOX'],
        }

        if query:
            list_params['q'] = query

        messages_result = service.users().messages().list(**list_params).execute()
        messages = messages_result.get('messages', [])

        if not messages:
            return {'messages': [], 'result_size_estimate': messages_result.get('resultSizeEstimate', 0)}

        # Fetch full details for each message
        full_messages = []
        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date'],
                ).execute()

                headers = message.get('payload', {}).get('headers', [])
                msg_data = {
                    'id': message.get('id'),
                    'threadId': message.get('threadId'),
                    'snippet': message.get('snippet', ''),
                    'internalDate': message.get('internalDate'),
                    'labelIds': message.get('labelIds', []),
                }

                for header in headers:
                    name = header.get('name', '')
                    value = header.get('value', '')
                    if name == 'From':
                        msg_data['from'] = value
                    elif name == 'To':
                        msg_data['to'] = value
                    elif name == 'Subject':
                        msg_data['subject'] = value
                    elif name == 'Date':
                        msg_data['date'] = value

                full_messages.append(msg_data)

            except Exception:
                continue

        return {
            'messages': full_messages,
            'result_size_estimate': messages_result.get('resultSizeEstimate', 0),
            'next_page_token': messages_result.get('nextPageToken'),
        }

    except HttpError as e:
        return {'error': f'Gmail API error: {str(e)}'}
    except Exception as e:
        return {'error': f'Failed to fetch inbox: {str(e)}'}


def fetch_gmail_message(user_id, message_id):
    """
    Fetch a full Gmail message by ID.
    """
    service = build_gmail_service(user_id)
    if not service:
        return {'error': 'Not authenticated with Google. Please connect your account.'}

    try:
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full',
        ).execute()

        headers = message.get('payload', {}).get('headers', [])
        msg_data = {
            'id': message.get('id'),
            'threadId': message.get('threadId'),
            'snippet': message.get('snippet', ''),
            'internalDate': message.get('internalDate'),
            'labelIds': message.get('labelIds', []),
            'historyId': message.get('historyId'),
        }

        for header in headers:
            name = header.get('name', '')
            value = header.get('value', '')
            if name in ('From', 'To', 'Subject', 'Date', 'Cc', 'Bcc', 'Reply-To'):
                msg_data[name.lower().replace('-', '_')] = value

        # Extract body text
        body = _extract_body(message.get('payload', {}))
        msg_data['body'] = body

        return msg_data

    except HttpError as e:
        return {'error': f'Gmail API error: {str(e)}'}
    except Exception as e:
        return {'error': f'Failed to fetch message: {str(e)}'}


def _extract_body(payload):
    """Extract the text body from a Gmail message payload."""
    if not payload:
        return ''

    # Simple text/plain
    if payload.get('mimeType') == 'text/plain' and payload.get('body', {}).get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

    # Multipart - recurse into parts
    parts = payload.get('parts', [])
    for part in parts:
        mime = part.get('mimeType', '')
        body_data = part.get('body', {}).get('data')
        if body_data:
            if mime == 'text/plain':
                return base64.urlsafe_b64decode(body_data).decode('utf-8')
            elif mime == 'text/html':
                return base64.urlsafe_b64decode(body_data).decode('utf-8')

    # Try nested parts
    for part in parts:
        if part.get('parts'):
            text = _extract_body(part)
            if text:
                return text

    return ''
