# OAuth 2.0 Setup Guide

This guide walks you through creating OAuth credentials for Google and Microsoft so you can connect your accounts in the Calendar & Tasks app.

---

## Table of Contents
1. [Google OAuth Setup](#google-oauth-setup)
2. [Microsoft OAuth Setup](#microsoft-oauth-setup)
3. [Entering Credentials in the App](#entering-credentials-in-the-app)
4. [Connecting Your Account](#connecting-your-account)

---

## Google OAuth Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top and select **New Project**
3. Enter a project name (e.g., "Calendar & Tasks")
4. Click **Create**

### Step 2: Enable Required APIs

1. In the left sidebar, go to **APIs & Services > Library**
2. Search for and enable these APIs:
   - **Google Calendar API**
   - **Google Tasks API**
   - **Gmail API**
   - **People API** (for contacts)
3. Click each one and press **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**
2. Select **External** user type (unless you have a Google Workspace account)
3. Fill in required fields:
   - **App name**: Calendar & Tasks
   - **User support email**: Your email address
   - **Developer contact email**: Your email address
4. Click **Save and Continue**
5. On the **Scopes** page, click **Add or Remove Scopes** and add:
   - `.../auth/calendar`
   - `.../auth/calendar.events`
   - `.../auth/tasks`
   - `.../auth/gmail.send`
   - `.../auth/gmail.readonly`
   - `.../auth/contacts.readonly`
   - `openid`
   - `.../auth/userinfo.email`
   - `.../auth/userinfo.profile`
6. Click **Save and Continue**
7. On the **Test Users** page, add your own email as a test user
8. Click **Save and Continue**

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **+ Create Credentials > OAuth client ID**
3. Select **Web application** as the application type
4. Fill in:
   - **Name**: Calendar & Tasks Desktop
   - **Authorized redirect URIs**: `http://localhost:5000/api/integrations/google/callback`
5. Click **Create**
6. **Copy the Client ID and Client Secret** - you will need these

### Step 5: Enter Credentials in the App

1. Open the Calendar & Tasks desktop app
2. Click the **OAuth Setup** button in the sidebar
3. Paste your **Google Client ID** and **Google Client Secret**
4. Click **Save Credentials**

---

## Microsoft OAuth Setup

### Step 1: Register an Application in Azure

1. Go to [Azure Portal - App registrations](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Click **+ New registration**
3. Fill in:
   - **Name**: Calendar & Tasks
   - **Supported account types**: Select **Accounts in any organizational directory (Any Azure AD directory - Multitenant) and personal Microsoft accounts (e.g. Skype, Xbox)**
   - **Redirect URI**:
     - Type: **Web**
     - URL: `http://localhost:5000/api/integrations/microsoft/callback`
4. Click **Register**
5. **Copy the Application (client) ID** - you will need this

### Step 2: Create a Client Secret

1. In your app registration, go to **Certificates & secrets** in the left sidebar
2. Under **Client secrets**, click **+ New client secret**
3. Add a description (e.g., "Calendar & Tasks")
4. Click **Add**
5. **Immediately copy the Value** (not the Secret ID) - you will not be able to see it again

### Step 3: Configure API Permissions

1. In your app registration, go to **API permissions** in the left sidebar
2. Click **+ Add a permission > Microsoft Graph**
3. Select **Delegated permissions**
4. Add these permissions:
   - **User.Read**
   - **Calendars.Read**
   - **Calendars.ReadWrite**
   - **Mail.Read**
   - **Mail.Send**
5. Click **Add permissions**

### Step 4: Enter Credentials in the App

1. Open the Calendar & Tasks desktop app
2. Click the **OAuth Setup** button in the sidebar
3. Paste your **Microsoft Client ID** (Application ID) and **Microsoft Client Secret** (Value)
4. Click **Save Credentials**

---

## Entering Credentials in the App

You can enter credentials in two ways:

### Via the Desktop UI (Recommended)
1. Open the Calendar & Tasks app
2. Click **OAuth Setup** in the sidebar
3. Paste your credentials in the appropriate fields
4. Click **Save Credentials**

### Via `desktop/config.json` (Manual)
Create or edit the file `desktop/config.json`:
```json
{
  "google_client_id": "your-google-client-id.apps.googleusercontent.com",
  "google_client_secret": "your-google-client-secret",
  "microsoft_client_id": "your-microsoft-client-id",
  "microsoft_client_secret": "your-microsoft-client-secret"
}
```

### Via Environment Variables (Alternative)
You can also set environment variables before running the app:
```bash
export GOOGLE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-google-client-secret"
export MICROSOFT_CLIENT_ID="your-microsoft-client-id"
export MICROSOFT_CLIENT_SECRET="your-microsoft-client-secret"
```

---

## Connecting Your Account

### Connect Google Account
1. Sign in to the app with your local account
2. Click **Connect Google** in the sidebar
3. Your browser will open to the Google sign-in page
4. Select your Google account and grant permissions
5. A success page will appear - the browser tab auto-closes after 2 seconds
6. Back in the app, click **Check Connection**
7. The status will update to "Google: Connected (your@email.com)"

### Connect Microsoft Account
1. Sign in to the app with your local account
2. Click **Connect Microsoft** in the sidebar
3. Your browser will open to the Microsoft sign-in page
4. Sign in and grant permissions
5. A success page will appear - the browser tab auto-closes after 2 seconds
6. Back in the app, click **Check Connection**
7. The status will update to "Microsoft: Connected (your@email.com)"

### Sync Your Calendar
Once connected:
1. Click **Sync Google Calendar** or **Sync Outlook Calendar** in the sidebar
2. Events will be imported to your local calendar

### Disconnect
1. Click **Disconnect Google** or **Disconnect Microsoft** in the sidebar
2. Confirm the disconnect

---

## Troubleshooting

### "OAuth credentials not configured" error
- Click **OAuth Setup** in the sidebar and enter your credentials
- Verify `desktop/config.json` exists and contains valid credentials

### "Redirect URI mismatch" error
- Ensure the redirect URI in your Google/Azure console exactly matches:
  - Google: `http://localhost:5000/api/integrations/google/callback`
  - Microsoft: `http://localhost:5000/api/integrations/microsoft/callback`

### "Unauthorized client" error (Google)
- Make sure your Google account is added as a **Test User** in the OAuth consent screen
- The app must be published (go to OAuth consent screen > Publishing status > Publish)

### "Invalid client secret" error (Microsoft)
- Make sure you copied the **Value** of the client secret, not the Secret ID
- Client secrets expire - create a new one if needed

### Browser doesn't open
- Ensure the Flask API server is running on `http://localhost:5000`
- Check your default browser is configured correctly

---

## Security Notes

- **Never commit `config.json` to version control** - it contains sensitive credentials
- The `.gitignore` file should exclude `desktop/config.json`
- Store your credentials securely (password manager, encrypted file, etc.)
- Rotate client secrets periodically
- For production deployment, use environment variables or a secrets manager instead of `config.json`
