/* ================================================================
   Calendar & Tasks - Full-featured Web App (vanilla JS)
   Version: 0.5.0
   ================================================================ */

const API_BASE = 'http://localhost:5000/api';

// Google Client ID for web version (client-side Sign-In)
const GOOGLE_CLIENT_ID = '750836360288-e58b73eup05aaofk29c7290oiv715gln.apps.googleusercontent.com';

/* ---- DOM helpers ---- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function pad(n) { return String(n).padStart(2, '0'); }

function fmt(date, opts = {}) {
    return new Intl.DateTimeFormat('en-US', opts).format(new Date(date));
}
function fmtShort(date) { return fmt(date, { month: 'short', day: 'numeric' }); }
function fmtFull(date) { return fmt(date, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }); }
function fmtTime(date) { return fmt(date, { hour: 'numeric', minute: '2-digit' }); }
function toLocalIso(dt) {
    if (!dt) return '';
    const d = new Date(dt);
    if (isNaN(d)) return '';
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function escapeHtml(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

/* ---- constants ---- */
const EVENT_COLORS = ['#60cdff', '#ff6b6b', '#51cf66', '#ffd43b', '#cc5de8', '#ff922b', '#20c997', '#f06595', '#845ef7'];
const NOTE_COLORS = ['#ffffff', '#fff3bf', '#ffe3e3', '#d3f9d8', '#e7f5ff', '#f3d9fa', '#e8e8e8', '#ffe8cc'];
const PRIORITY_NAMES = ['Low', 'Medium', 'High', 'Urgent'];
const DAY_NAMES_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const DAY_NAMES_MINI  = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
const MONTH_NAMES     = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December'];

/* ---- toast notification ---- */
function toast(msg, type = 'info') {
    const container = $('#toast-container');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; setTimeout(() => el.remove(), 300); }, 3500);
}

/* ================================================================
   APIClient - HTTP client with JWT auth
   ================================================================ */
class APIClient {
    constructor(baseURL) {
        this.baseURL = baseURL;
    }

    getToken() {
        return localStorage.getItem('ct-token');
    }

    _headers(extra = {}) {
        const h = { 'Content-Type': 'application/json', ...extra };
        const token = this.getToken();
        if (token) h['Authorization'] = `Bearer ${token}`;
        return h;
    }

    async _request(method, path, body = null) {
        const opts = { method, headers: this._headers() };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(`${this.baseURL}${path}`, opts);

        if (res.status === 401) {
            localStorage.removeItem('ct-token');
            localStorage.removeItem('ct-user');
            throw new Error('Session expired. Please sign in again.');
        }
        if (!res.ok) {
            let msg = `HTTP ${res.status}`;
            try {
                const data = await res.json();
                if (data && data.error) msg = data.error;
            } catch { /* not JSON */ }
            throw new Error(msg);
        }
        // Handle 204 No Content
        if (res.status === 204) return null;
        return res.json();
    }

    get(path)    { return this._request('GET', path); }
    post(path, body) { return this._request('POST', path, body); }
    put(path, body)  { return this._request('PUT', path, body); }
    delete(path)     { return this._request('DELETE', path); }
}

/* ================================================================
   App - Main application class
   ================================================================ */
class App {
    constructor() {
        this.api = new APIClient(API_BASE);

        /* -- persisted state -- */
        this.token = this.api.getToken();
        this.user  = JSON.parse(localStorage.getItem('ct-user') || 'null');

        /* -- view state -- */
        this.view         = 'calendar';
        this.calYear      = new Date().getFullYear();
        this.calMonth     = new Date().getMonth();
        this.selectedDate = this._dateKey(new Date());
        this.miniYear     = new Date().getFullYear();
        this.miniMonth    = new Date().getMonth();

        /* -- data -- */
        this.events  = [];
        this.tasks   = [];
        this.notes   = [];
        this.sentMail = JSON.parse(localStorage.getItem('ct-sent-mail') || '[]');

        /* -- filters -- */
        this.taskFilter  = 'all';       // all | pending | completed
        this.taskSort    = 'due-date';  // due-date | priority | created
        this.mailTab     = 'inbox';     // inbox | sent
        this.noteQuery   = '';

        /* -- editing -- */
        this.editingEventId = null;
        this.editingTaskId  = null;
        this.editingNoteId  = null;

        /* -- integrations -- */
        this.googleConnected = false;
        this.msConnected     = false;

        this.init();
    }

    /* ==========================================================
       INIT
       ========================================================== */
    async init() {
        this._loadTheme();
        this._loadGoogleState();

        /* Wait for DOM to be fully parsed */
        if (document.readyState === 'loading') {
            await new Promise(r => document.addEventListener('DOMContentLoaded', r));
        }

        this._bindGlobal();
        this._renderUserArea();
        this._renderMiniCalendar();
        this._renderColorPicker('event');
        this._renderColorPicker('note');

        if (this.token) {
            await this._loadAll();
            await this._checkIntegrations();
        } else {
            /* render empty views for logged-out users */
            this._renderCalendar();
            this._renderTasks();
            this._renderNotes();
            this._renderMail();
        }
        this._renderIntegrations();
    }

    _loadGoogleState() {
        try {
            const token = localStorage.getItem('ct-google-token');
            const user = localStorage.getItem('ct-google-user');
            if (token && user) {
                this.googleConnected = true;
                this.googleUser = JSON.parse(user);
                this.googleToken = token;
            } else {
                this.googleConnected = false;
                this.googleUser = null;
                this.googleToken = null;
            }
        } catch { this.googleConnected = false; this.googleUser = null; }
    }

    /* ==========================================================
       THEME
       ========================================================== */
    _loadTheme() {
        const t = localStorage.getItem('ct-theme') || 'dark';
        this._applyTheme(t);
    }

    _applyTheme(t) {
        document.body.setAttribute('data-theme', t);
        const sel = $('#theme-select');
        if (sel) sel.value = t;
        localStorage.setItem('ct-theme', t);
    }

    /* ==========================================================
       EVENT BINDINGS
       ========================================================== */
    _bindGlobal() {
        /* Theme selector */
        const themeSel = $('#theme-select');
        if (themeSel) themeSel.addEventListener('change', e => this._applyTheme(e.target.value));

        /* Sidebar navigation (desktop + mobile) */
        $$('.nav-item[data-view]').forEach(btn => {
            btn.addEventListener('click', () => this.switchView(btn.dataset.view));
        });

        /* Modal close buttons */
        $$('[data-close]').forEach(btn => {
            btn.addEventListener('click', () => this._hideModal(btn.dataset.close));
        });
        /* Close modal on overlay background click */
        $$('.modal-overlay').forEach(ov => {
            ov.addEventListener('click', e => { if (e.target === ov) this._hideModal(ov.id); });
        });

        /* Escape key closes active modal / context menu */
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                const active = $('.modal-overlay.active');
                if (active) this._hideModal(active.id);
                this._hideContextMenu();
            }
        });

        /* ---- Calendar month navigation ---- */
        const calPrev = $('#cal-prev');
        const calNext = $('#cal-next');
        const calToday = $('#cal-today');
        const btnNewEvent = $('#btn-new-event');
        if (calPrev) calPrev.addEventListener('click', () => { this._shiftMonth(-1); this._renderCalendar(); });
        if (calNext) calNext.addEventListener('click', () => { this._shiftMonth(1); this._renderCalendar(); });
        if (calToday) calToday.addEventListener('click', () => {
            const now = new Date();
            this.calYear = now.getFullYear();
            this.calMonth = now.getMonth();
            this.selectedDate = this._dateKey(now);
            this._renderCalendar();
        });
        if (btnNewEvent) btnNewEvent.addEventListener('click', () => this._openEventModal());

        /* Event form */
        const eventForm = $('#event-form');
        if (eventForm) eventForm.addEventListener('submit', e => { e.preventDefault(); this._saveEvent(); });
        const btnSaveEvent = $('#btn-event-save');
        if (btnSaveEvent) btnSaveEvent.addEventListener('click', () => { if (eventForm) eventForm.requestSubmit(); });
        const btnDelEvent = $('#btn-event-delete');
        if (btnDelEvent) btnDelEvent.addEventListener('click', () => this._deleteEvent());
        const allDayCheck = $('#event-all-day');
        if (allDayCheck) allDayCheck.addEventListener('change', e => this._toggleAllDay(e.target.checked));

        /* Task filters & sort */
        $$('.filter-btn[data-filter]').forEach(b => {
            b.addEventListener('click', () => {
                $$('.filter-btn[data-filter]').forEach(x => x.classList.remove('active'));
                b.classList.add('active');
                this.taskFilter = b.dataset.filter;
                this._renderTasks();
            });
        });
        const taskSortSel = $('#task-sort');
        if (taskSortSel) taskSortSel.addEventListener('change', e => { this.taskSort = e.target.value; this._renderTasks(); });

        /* Task form */
        const taskForm = $('#task-form');
        if (taskForm) taskForm.addEventListener('submit', e => { e.preventDefault(); this._saveTask(); });
        const btnSaveTask = $('#btn-task-save');
        if (btnSaveTask) btnSaveTask.addEventListener('click', () => { if (taskForm) taskForm.requestSubmit(); });
        const btnDelTask = $('#btn-task-delete');
        if (btnDelTask) btnDelTask.addEventListener('click', () => this._deleteTask());
        const btnNewTask = $('#btn-new-task');
        if (btnNewTask) btnNewTask.addEventListener('click', () => this._openTaskModal());

        /* Note form */
        const noteForm = $('#note-form');
        if (noteForm) noteForm.addEventListener('submit', e => { e.preventDefault(); this._saveNote(); });
        const btnSaveNote = $('#btn-note-save');
        if (btnSaveNote) btnSaveNote.addEventListener('click', () => { if (noteForm) noteForm.requestSubmit(); });
        const btnDelNote = $('#btn-note-delete');
        if (btnDelNote) btnDelNote.addEventListener('click', () => this._deleteNote());
        const btnNewNote = $('#btn-new-note');
        if (btnNewNote) btnNewNote.addEventListener('click', () => this._openNoteModal());

        /* Notes search */
        const noteSearchInput = $('#notes-search');
        if (noteSearchInput) noteSearchInput.addEventListener('input', e => { this.noteQuery = e.target.value.toLowerCase(); this._renderNotes(); });

        /* Mail tabs */
        $$('.mail-tab[data-mail-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                $$('.mail-tab[data-mail-tab]').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.mailTab = tab.dataset.mailTab;
                this._renderMail();
            });
        });

        /* Mail compose */
        const btnCompose = $('#btn-compose');
        if (btnCompose) btnCompose.addEventListener('click', () => this._showModal('modal-compose'));
        const composeForm = $('#compose-form');
        if (composeForm) composeForm.addEventListener('submit', e => e.preventDefault());
        const btnSendMail = $('#btn-send-mail');
        if (btnSendMail) btnSendMail.addEventListener('click', () => this._sendMail());

        /* Integration buttons */
        const intGoogle = $('#int-google');
        if (intGoogle) intGoogle.addEventListener('click', () => this.connectGoogle());
        const intMs = $('#int-microsoft');
        if (intMs) intMs.addEventListener('click', () => this.connectMicrosoft());
        const syncGcal = $('#sync-gcal');
        if (syncGcal) syncGcal.addEventListener('click', () => this.syncGoogleCalendar());
        const syncOutlook = $('#sync-outlook');
        if (syncOutlook) syncOutlook.addEventListener('click', () => this.syncOutlookCalendar());

        /* Auth */
        const emailForm = $('#email-auth-form');
        if (emailForm) emailForm.addEventListener('submit', e => this._handleEmailAuth(e));
        const btnGoogleAuth = $('#btn-google-auth');
        if (btnGoogleAuth) btnGoogleAuth.addEventListener('click', () => this._handleGoogleOAuth());
        const btnMsAuth = $('#btn-ms-auth');
        if (btnMsAuth) btnMsAuth.addEventListener('click', () => this._handleMsOAuth());

        /* Context menu dismiss */
        document.addEventListener('click', () => this._hideContextMenu());
        document.addEventListener('contextmenu', () => this._hideContextMenu());
    }

    /* ==========================================================
       VIEW SWITCHING
       ========================================================== */
    switchView(name) {
        this.view = name;
        $$('.nav-item[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === name));
        $$('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));

        if (name === 'calendar') this._renderCalendar();
        else if (name === 'tasks') this._renderTasks();
        else if (name === 'notes') this._renderNotes();
        else if (name === 'mail') this._renderMail();
    }

    /* ==========================================================
       MODALS
       ========================================================== */
    _showModal(id) { const el = $(`#${id}`); if (el) el.classList.add('active'); }
    _hideModal(id) {
        const el = $(`#${id}`);
        if (!el) return;
        el.classList.remove('active');
        if (id === 'modal-event') this._resetEventForm();
        if (id === 'modal-task')  this._resetTaskForm();
        if (id === 'modal-note')  this._resetNoteForm();
    }

    /* ==========================================================
       AUTH
       ========================================================== */
    async _handleEmailAuth(e) {
        e.preventDefault();
        const email    = $('#auth-email')?.value.trim();
        const password = $('#auth-password')?.value;
        if (!email || !password) { toast('Enter email and password', 'error'); return; }

        try {
            /* Try login first */
            let data;
            try {
                data = await this.api.post('/auth/login', { email, password });
            } catch (loginErr) {
                /* If login fails, try register */
                data = await this.api.post('/auth/register', { email, password });
            }
            this._setSession(data);
            this._hideModal('modal-auth');
            await this._loadAll();
            await this._checkIntegrations();
            toast('Signed in successfully', 'success');
        } catch (err) {
            toast(err.message || 'Authentication failed', 'error');
        }
    }

    async _handleGoogleOAuth() {
        /* Use the same flow as connectGoogle() - no email auth required */
        if (this.googleConnected) {
            if (!confirm('Disconnect Google account?')) return;
            localStorage.removeItem('ct-google-token');
            localStorage.removeItem('ct-google-user');
            this.googleConnected = false;
            this.googleUser = null;
            this.googleToken = null;
            this._renderIntegrations();
            toast('Google disconnected', 'info');
            return;
        }
        try {
            const oauth2 = new google.accounts.oauth2.TokenClient({
                client_id: GOOGLE_CLIENT_ID,
                scope: 'https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/tasks https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly',
                callback: (response) => {
                    if (response.access_token) {
                        this._saveGoogleToken(response.access_token);
                    }
                },
                error_callback: (err) => {
                    toast('Google OAuth failed: ' + (err.message || 'User cancelled'), 'error');
                }
            });
            oauth2.requestAccessToken();
        } catch (err) { toast('Google Sign-In not available: ' + err.message, 'error'); }
    }

    async _saveGoogleToken(accessToken) {
        try {
            // Get user info from Google
            const resp = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            });
            const user = await resp.json();
            // Save to local storage for the web app
            localStorage.setItem('ct-google-token', accessToken);
            localStorage.setItem('ct-google-user', JSON.stringify({ email: user.email, name: user.name }));
            this.googleConnected = true;
            this.googleUser = user;
            this._renderIntegrations();
            toast(`Connected to Google as ${user.email}`, 'success');
        } catch (err) { toast('Failed to save Google token: ' + err.message, 'error'); }
    }

    async _handleMsOAuth() {
        if (!this.token) { toast('Sign in with email first, then connect Microsoft', 'info'); return; }
        try {
            const data = await this.api.get('/integrations/microsoft/auth-url');
            if (data?.url) {
                window.open(data.url, '_blank');
                toast('Complete Microsoft OAuth in the new tab, then click Microsoft again to connect', 'info');
            }
        } catch (err) { toast('Could not get Microsoft auth URL: ' + err.message, 'error'); }
    }

    _setSession(data) {
        this.token = data.access_token || data.token;
        this.user  = data.user || data;
        localStorage.setItem('ct-token', this.token);
        localStorage.setItem('ct-user', JSON.stringify(this.user));
        this._renderUserArea();
    }

    logout() {
        this.token = null;
        this.user  = null;
        this.events  = [];
        this.tasks   = [];
        this.notes   = [];
        this.sentMail = [];
        localStorage.removeItem('ct-token');
        localStorage.removeItem('ct-user');
        localStorage.removeItem('ct-sent-mail');
        this._renderUserArea();
        this._renderCalendar();
        this._renderTasks();
        this._renderNotes();
        this._renderMail();
        toast('Signed out', 'info');
    }

    _renderUserArea() {
        const area = $('#user-area');
        if (!area) return;
        if (this.user) {
            const name = escapeHtml(this.user.display_name || this.user.name || 'User');
            const email = escapeHtml(this.user.email || '');
            area.innerHTML = `
                <div class="user-info">
                    <div class="user-display" title="${name}">${name}</div>
                    <div class="user-email" title="${email}">${email}</div>
                    <button class="btn-logout" id="btn-logout">Sign Out</button>
                </div>`;
            const btn = $('#btn-logout');
            if (btn) btn.addEventListener('click', () => this.logout());
        } else {
            area.innerHTML = `<button class="btn-signin" id="btn-open-auth">Sign In</button>`;
            const btn = $('#btn-open-auth');
            if (btn) btn.addEventListener('click', () => this._showModal('modal-auth'));
        }
    }

    /* ==========================================================
       DATA LOADING
       ========================================================== */
    async _loadAll() {
        const start = `${this.calYear}-${pad(this.calMonth + 1)}-01`;
        const lastDay = new Date(this.calYear, this.calMonth + 1, 0).getDate();
        const end = `${this.calYear}-${pad(this.calMonth + 1)}-${pad(lastDay)}`;

        /* Load events for current month */
        try {
            this.events = await this.api.get(`/events?start=${start}&end=${end}`);
            if (!Array.isArray(this.events)) this.events = [];
        } catch { this.events = []; }

        /* Load tasks */
        try {
            this.tasks = await this.api.get('/tasks');
            if (!Array.isArray(this.tasks)) this.tasks = [];
        } catch { this.tasks = []; }

        /* Load notes */
        try {
            this.notes = await this.api.get('/notes');
            if (!Array.isArray(this.notes)) this.notes = [];
        } catch { this.notes = []; }

        this._renderCalendar();
        this._renderTasks();
        this._renderNotes();
        this._renderMiniCalendar();
    }

    /* ==========================================================
       CALENDAR VIEW
       ========================================================== */
    _shiftMonth(dir) {
        this.calMonth += dir;
        if (this.calMonth < 0)  { this.calMonth = 11; this.calYear--; }
        if (this.calMonth > 11) { this.calMonth = 0;  this.calYear++; }
    }

    _renderCalendar() {
        const grid  = $('#cal-grid');
        const label = $('#cal-month-label');
        if (!grid) return;
        if (label) label.textContent = `${MONTH_NAMES[this.calMonth]} ${this.calYear}`;

        const firstDay   = new Date(this.calYear, this.calMonth, 1);
        const lastDay    = new Date(this.calYear, this.calMonth + 1, 0);
        const startPad   = (firstDay.getDay() + 6) % 7;  // Monday = 0
        const today      = new Date();
        const todayKey   = this._dateKey(today);

        /* Build event lookup map */
        const eventMap = {};
        this.events.forEach(ev => {
            const key = (ev.start_time || '').substring(0, 10);
            if (key) {
                if (!eventMap[key]) eventMap[key] = [];
                eventMap[key].push(ev);
            }
        });

        let html = DAY_NAMES_SHORT.map(d => `<div class="cal-day-header">${d}</div>`).join('');

        /* Leading empty cells */
        for (let i = 0; i < startPad; i++) {
            html += '<div class="cal-day other-month"></div>';
        }

        /* Day cells */
        for (let day = 1; day <= lastDay.getDate(); day++) {
            const dateStr = `${this.calYear}-${pad(this.calMonth + 1)}-${pad(day)}`;
            const isToday = dateStr === todayKey;
            const isSelected = dateStr === this.selectedDate;
            const dayEvents = eventMap[dateStr] || [];

            const classes = ['cal-day'];
            if (isToday)     classes.push('today');
            if (isSelected)  classes.push('selected');

            const chips = dayEvents.slice(0, 3).map(ev => {
                const color = ev.color || '#60cdff';
                const title = escapeHtml(ev.title || '(no title)');
                const srcBadge = ev.source === 'google'    ? '<span class="source-badge">G</span>' :
                                 ev.source === 'microsoft' ? '<span class="source-badge">O</span>' : '';
                return `<div class="event-chip${ev.source ? ' source-' + ev.source : ''}"
                    style="background:${color}"
                    data-event-id="${ev.id}"
                    onclick="event.stopPropagation();app._openEventModal(${ev.id})"
                    oncontextmenu="event.stopPropagation();app._eventContext(event,${ev.id})"
                    title="${title}">${title}${srcBadge}</div>`;
            }).join('');
            const more = dayEvents.length > 3
                ? `<div style="font-size:10px;color:var(--text-secondary);padding:0 4px">+${dayEvents.length - 3} more</div>`
                : '';

            html += `<div class="${classes.join(' ')}" data-date="${dateStr}"
                onclick="app._selectDate('${dateStr}')"
                ondblclick="app._openEventModal(null,'${dateStr}')">
                <div class="cal-day-number">${day}</div>
                ${chips}${more}
            </div>`;
        }

        /* Trailing empty cells to fill grid */
        const totalCells = startPad + lastDay.getDate();
        const remaining = (7 - (totalCells % 7)) % 7;
        for (let i = 0; i < remaining; i++) {
            html += '<div class="cal-day other-month"></div>';
        }

        grid.innerHTML = html;
    }

    _selectDate(dateStr) {
        this.selectedDate = dateStr;
        this._renderCalendar();
    }

    _toggleAllDay(checked) {
        const s = $('#event-start');
        const e = $('#event-end');
        if (!s || !e) return;
        if (checked) {
            s.type = 'date';
            e.type = 'date';
            if (s.value) s.value = s.value.substring(0, 10);
            if (e.value) e.value = e.value.substring(0, 10);
        } else {
            s.type = 'datetime-local';
            e.type = 'datetime-local';
            if (s.value && s.value.length === 10) s.value += 'T09:00';
            if (e.value && e.value.length === 10) e.value += 'T10:00';
        }
    }

    /* -- Event CRUD -- */
    _openEventModal(eventId = null, dateStr = null) {
        this.editingEventId = eventId;
        const form = $('#event-form');
        if (form) form.reset();
        this._renderColorPicker('event');

        if (eventId) {
            const ev = this.events.find(e => e.id === eventId);
            if (!ev) return;
            const titleEl = $('#event-modal-title');
            if (titleEl) titleEl.textContent = 'Edit Event';
            const idField = $('#event-id');
            if (idField) idField.value = ev.id;
            const titleField = $('#event-title');
            if (titleField) titleField.value = ev.title || '';
            const descField = $('#event-description');
            if (descField) descField.value = ev.description || '';
            const locField = $('#event-location');
            if (locField) locField.value = ev.location || '';
            const startField = $('#event-start');
            const endField   = $('#event-end');
            if (startField) {
                startField.value = toLocalIso(ev.start_time);
                startField.type = ev.is_all_day ? 'date' : 'datetime-local';
            }
            if (endField) {
                endField.value = toLocalIso(ev.end_time);
                endField.type = ev.is_all_day ? 'date' : 'datetime-local';
            }
            const allDay = $('#event-all-day');
            if (allDay) allDay.checked = !!ev.is_all_day;
            const colorField = $('#event-color');
            if (colorField) colorField.value = ev.color || '#60cdff';
            const reminderField = $('#event-reminder');
            if (reminderField) reminderField.value = ev.reminder_minutes ?? 15;
            const recurField = $('#event-recurrence');
            if (recurField) recurField.value = ev.recurrence || '';
            const delBtn = $('#btn-event-delete');
            if (delBtn) delBtn.style.display = '';

            /* Highlight selected color swatch */
            this._selectColor('event', ev.color || '#60cdff');
        } else {
            const titleEl = $('#event-modal-title');
            if (titleEl) titleEl.textContent = 'New Event';
            const delBtn = $('#btn-event-delete');
            if (delBtn) delBtn.style.display = 'none';
            if (dateStr) {
                const startField = $('#event-start');
                const endField   = $('#event-end');
                if (startField) startField.value = `${dateStr}T09:00`;
                if (endField)   endField.value   = `${dateStr}T10:00`;
            }
            this._selectColor('event', '#60cdff');
        }

        this._showModal('modal-event');
    }

    async _saveEvent() {
        if (!this.token) { toast('Sign in to create events', 'error'); return; }

        const title = $('#event-title')?.value.trim();
        if (!title) { toast('Event title is required', 'error'); return; }

        const isAllDay = $('#event-all-day')?.checked || false;
        let startVal = $('#event-start')?.value || '';
        let endVal   = $('#event-end')?.value   || '';
        if (isAllDay) {
            if (startVal && startVal.length === 10) startVal += 'T00:00';
            if (endVal   && endVal.length === 10)   endVal   += 'T23:59';
        }

        const data = {
            title,
            description:    $('#event-description')?.value.trim() || '',
            location:       $('#event-location')?.value.trim()    || '',
            start_time:     startVal,
            end_time:       endVal,
            is_all_day:     isAllDay ? 1 : 0,
            color:          $('#event-color')?.value || '#60cdff',
            reminder_minutes: parseInt($('#event-reminder')?.value || '0', 10),
            recurrence:     $('#event-recurrence')?.value || '',
            source:         'local'
        };

        try {
            if (this.editingEventId) {
                await this.api.put(`/events/${this.editingEventId}`, data);
                toast('Event updated', 'success');
            } else {
                await this.api.post('/events', data);
                toast('Event created', 'success');
            }
            this._hideModal('modal-event');
            await this._loadAll();
        } catch (err) {
            toast('Failed to save event: ' + err.message, 'error');
        }
    }

    async _deleteEvent() {
        if (!this.editingEventId) return;
        if (!confirm('Delete this event?')) return;
        try {
            await this.api.delete(`/events/${this.editingEventId}`);
            toast('Event deleted', 'success');
            this._hideModal('modal-event');
            await this._loadAll();
        } catch (err) {
            toast('Failed to delete event: ' + err.message, 'error');
        }
    }

    _eventContext(e, eventId) {
        e.preventDefault();
        e.stopPropagation();
        this._showContextMenu(e.clientX, e.clientY, [
            { label: 'Edit', action: () => this._openEventModal(eventId) },
            { divider: true },
            { label: 'Delete', danger: true, action: async () => {
                if (!confirm('Delete this event?')) return;
                try {
                    await this.api.delete(`/events/${eventId}`);
                    toast('Event deleted', 'success');
                    await this._loadAll();
                } catch (err) { toast('Failed: ' + err.message, 'error'); }
            }}
        ]);
    }

    _resetEventForm() {
        const form = $('#event-form');
        if (form) form.reset();
        const idField = $('#event-id');
        if (idField) idField.value = '';
        this.editingEventId = null;
        const titleEl = $('#event-modal-title');
        if (titleEl) titleEl.textContent = 'New Event';
        const delBtn = $('#btn-event-delete');
        if (delBtn) delBtn.style.display = 'none';
        const s = $('#event-start');
        const e = $('#event-end');
        if (s) s.type = 'datetime-local';
        if (e) e.type = 'datetime-local';
    }

    /* ==========================================================
       TASKS VIEW
       ========================================================== */
    _renderTasks() {
        const container = $('#task-list');
        if (!container) return;

        let tasks = [...this.tasks];

        /* Filter */
        if (this.taskFilter === 'pending')   tasks = tasks.filter(t => t.status !== 'completed');
        if (this.taskFilter === 'completed') tasks = tasks.filter(t => t.status === 'completed');

        /* Sort */
        if (this.taskSort === 'due-date') {
            tasks.sort((a, b) => (a.due_date || '9999-12-31').localeCompare(b.due_date || '9999-12-31'));
        } else if (this.taskSort === 'priority') {
            tasks.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
        } else {
            tasks.sort((a, b) => (b.id || 0) - (a.id || 0));
        }

        if (!tasks.length) {
            const icon = this.taskFilter === 'completed' ? '\u2705' : this.taskFilter === 'pending' ? '\u{1F4CB}' : '\u2705';
            const text = this.taskFilter === 'completed' ? 'No completed tasks' : 'No tasks here';
            container.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon">${icon}</div>
                <div class="empty-state-text">${text}</div>
                <div class="empty-state-sub">Click "+ New Task" to create one</div>
            </div>`;
            return;
        }

        container.innerHTML = tasks.map(t => {
            const completed = t.status === 'completed';
            const pri = t.priority ?? 1;
            const due = t.due_date ? fmtShort(t.due_date) : '';
            return `<div class="task-item" oncontextmenu="app._taskContext(event,${t.id})">
                <div class="task-priority-bar priority-${pri}"></div>
                <div class="task-checkbox ${completed ? 'checked' : ''}"
                    onclick="app._toggleTask(${t.id})" title="${completed ? 'Mark pending' : 'Mark complete'}"></div>
                <div class="task-content" onclick="app._openTaskModal(${t.id})" style="cursor:pointer">
                    <div class="task-title ${completed ? 'completed' : ''}">${escapeHtml(t.title)}</div>
                    ${t.description ? `<div class="task-desc">${escapeHtml(t.description)}</div>` : ''}
                    <div class="task-meta">
                        ${due ? `<span>${due}</span>` : ''}
                        <span class="priority-label priority-${pri}">${PRIORITY_NAMES[pri]}</span>
                        ${t.category ? `<span>${escapeHtml(t.category)}</span>` : ''}
                    </div>
                </div>
                <div class="task-actions">
                    <button class="task-action-btn" onclick="app._openTaskModal(${t.id})" title="Edit">\u270F\uFE0F</button>
                    <button class="task-action-btn delete" onclick="app._deleteTaskById(${t.id})" title="Delete">\u{1F5D1}\uFE0F</button>
                </div>
            </div>`;
        }).join('');
    }

    _openTaskModal(taskId = null) {
        this.editingTaskId = taskId;
        const form = $('#task-form');
        if (form) form.reset();

        if (taskId) {
            const t = this.tasks.find(x => x.id === taskId);
            if (!t) return;
            const titleEl = $('#task-modal-title');
            if (titleEl) titleEl.textContent = 'Edit Task';
            const idField = $('#task-id');
            if (idField) idField.value = t.id;
            const titleField = $('#task-title');
            if (titleField) titleField.value = t.title || '';
            const descField = $('#task-description');
            if (descField) descField.value = t.description || '';
            const dueField = $('#task-due');
            if (dueField) dueField.value = t.due_date || '';
            const priField = $('#task-priority');
            if (priField) priField.value = t.priority ?? 1;
            const catField = $('#task-category');
            if (catField) catField.value = t.category || '';
            const delBtn = $('#btn-task-delete');
            if (delBtn) delBtn.style.display = '';
        } else {
            const titleEl = $('#task-modal-title');
            if (titleEl) titleEl.textContent = 'New Task';
            const delBtn = $('#btn-task-delete');
            if (delBtn) delBtn.style.display = 'none';
        }
        this._showModal('modal-task');
    }

    async _saveTask() {
        if (!this.token) { toast('Sign in to create tasks', 'error'); return; }

        const title = $('#task-title')?.value.trim();
        if (!title) { toast('Task title is required', 'error'); return; }

        const data = {
            title,
            description: $('#task-description')?.value.trim() || '',
            due_date:    $('#task-due')?.value || null,
            priority:    parseInt($('#task-priority')?.value || '1', 10),
            category:    $('#task-category')?.value.trim() || ''
        };

        try {
            if (this.editingTaskId) {
                await this.api.put(`/tasks/${this.editingTaskId}`, data);
                toast('Task updated', 'success');
            } else {
                data.status = 'pending';
                await this.api.post('/tasks', data);
                toast('Task created', 'success');
            }
            this._hideModal('modal-task');
            try {
                const res = await this.api.get('/tasks');
                this.tasks = Array.isArray(res) ? res : [];
            } catch {}
            this._renderTasks();
        } catch (err) {
            toast('Failed to save task: ' + err.message, 'error');
        }
    }

    async _toggleTask(taskId) {
        const t = this.tasks.find(x => x.id === taskId);
        if (!t) return;
        const newStatus = t.status === 'completed' ? 'pending' : 'completed';
        try {
            await this.api.put(`/tasks/${taskId}`, { status: newStatus });
            t.status = newStatus;
            this._renderTasks();
        } catch (err) {
            toast('Failed: ' + err.message, 'error');
        }
    }

    async _deleteTask() {
        if (!this.editingTaskId) return;
        await this._doDeleteTask(this.editingTaskId);
        this._hideModal('modal-task');
    }

    async _deleteTaskById(taskId) {
        await this._doDeleteTask(taskId);
    }

    async _doDeleteTask(taskId) {
        if (!confirm('Delete this task?')) return;
        try {
            await this.api.delete(`/tasks/${taskId}`);
            toast('Task deleted', 'success');
            try {
                const res = await this.api.get('/tasks');
                this.tasks = Array.isArray(res) ? res : [];
            } catch {}
            this._renderTasks();
        } catch (err) {
            toast('Failed to delete task: ' + err.message, 'error');
        }
    }

    _taskContext(e, taskId) {
        e.preventDefault();
        e.stopPropagation();
        this._showContextMenu(e.clientX, e.clientY, [
            { label: 'Edit', action: () => this._openTaskModal(taskId) },
            { label: 'Toggle complete', action: async () => { await this._toggleTask(taskId); } },
            { divider: true },
            { label: 'Delete', danger: true, action: async () => { await this._doDeleteTask(taskId); }}
        ]);
    }

    _resetTaskForm() {
        const form = $('#task-form');
        if (form) form.reset();
        const idField = $('#task-id');
        if (idField) idField.value = '';
        this.editingTaskId = null;
        const titleEl = $('#task-modal-title');
        if (titleEl) titleEl.textContent = 'New Task';
        const delBtn = $('#btn-task-delete');
        if (delBtn) delBtn.style.display = 'none';
    }

    /* ==========================================================
       NOTES VIEW
       ========================================================== */
    _renderNotes() {
        const grid = $('#notes-grid');
        if (!grid) return;

        let notes = [...this.notes];

        /* Pinned first */
        const pinned   = notes.filter(n => n.pinned);
        const unpinned = notes.filter(n => !n.pinned);

        /* Search filter */
        const filter = (arr) => {
            if (!this.noteQuery) return arr;
            const q = this.noteQuery;
            return arr.filter(n =>
                (n.title || '').toLowerCase().includes(q) ||
                (n.content || '').toLowerCase().includes(q)
            );
        };

        notes = [...filter(pinned), ...filter(unpinned)];

        if (!notes.length) {
            grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
                <div class="empty-state-icon">\u{1F4DD}</div>
                <div class="empty-state-text">${this.noteQuery ? 'No matching notes' : 'No notes'}</div>
                <div class="empty-state-sub">Click "+ New Note" to create one</div>
            </div>`;
            return;
        }

        grid.innerHTML = notes.map(n => {
            const bg = n.color || '#ffffff';
            const textColor = this._brightness(bg) > 160 ? '#333' : '#fff';
            const titleText = n.title ? escapeHtml(n.title) : '';
            const contentPreview = n.content ? escapeHtml(n.content).substring(0, 200) : '';
            const updated = n.updated_at || n.created_at;
            const dateStr = updated ? fmtShort(updated) : '';

            return `<div class="note-card ${n.pinned ? 'pinned' : ''}"
                style="background:${bg};color:${textColor}"
                onclick="app._openNoteModal(${n.id})"
                oncontextmenu="app._noteContext(event,${n.id})">
                ${titleText ? `<div class="note-title-text">${titleText}</div>` : ''}
                ${contentPreview ? `<div class="note-content-text">${contentPreview}</div>` : ''}
                ${dateStr ? `<div class="note-date">${dateStr}</div>` : ''}
            </div>`;
        }).join('');
    }

    _openNoteModal(noteId = null) {
        this.editingNoteId = noteId;
        const form = $('#note-form');
        if (form) form.reset();
        this._renderColorPicker('note');

        if (noteId) {
            const n = this.notes.find(x => x.id === noteId);
            if (!n) return;
            const titleEl = $('#note-modal-title');
            if (titleEl) titleEl.textContent = 'Edit Note';
            const idField = $('#note-id');
            if (idField) idField.value = n.id;
            const titleField = $('#note-title');
            if (titleField) titleField.value = n.title || '';
            const contentField = $('#note-content');
            if (contentField) contentField.value = n.content || '';
            const colorField = $('#note-color');
            if (colorField) colorField.value = n.color || '#ffffff';
            const pinnedField = $('#note-pinned');
            if (pinnedField) pinnedField.checked = !!n.pinned;
            const delBtn = $('#btn-note-delete');
            if (delBtn) delBtn.style.display = '';

            this._selectColor('note', n.color || '#ffffff');
        } else {
            const titleEl = $('#note-modal-title');
            if (titleEl) titleEl.textContent = 'New Note';
            const delBtn = $('#btn-note-delete');
            if (delBtn) delBtn.style.display = 'none';
            this._selectColor('note', '#ffffff');
        }
        this._showModal('modal-note');
    }

    async _saveNote() {
        if (!this.token) { toast('Sign in to create notes', 'error'); return; }

        const data = {
            title:   $('#note-title')?.value.trim() || '',
            content: $('#note-content')?.value.trim() || '',
            color:   $('#note-color')?.value || '#ffffff',
            pinned:  $('#note-pinned')?.checked ? 1 : 0
        };

        try {
            if (this.editingNoteId) {
                await this.api.put(`/notes/${this.editingNoteId}`, data);
                toast('Note updated', 'success');
            } else {
                await this.api.post('/notes', data);
                toast('Note created', 'success');
            }
            this._hideModal('modal-note');
            try {
                const res = await this.api.get('/notes');
                this.notes = Array.isArray(res) ? res : [];
            } catch {}
            this._renderNotes();
        } catch (err) {
            toast('Failed to save note: ' + err.message, 'error');
        }
    }

    async _deleteNote() {
        if (!this.editingNoteId) return;
        await this._doDeleteNote(this.editingNoteId);
        this._hideModal('modal-note');
    }

    async _doDeleteNote(noteId) {
        if (!confirm('Delete this note?')) return;
        try {
            await this.api.delete(`/notes/${noteId}`);
            toast('Note deleted', 'success');
            try {
                const res = await this.api.get('/notes');
                this.notes = Array.isArray(res) ? res : [];
            } catch {}
            this._renderNotes();
        } catch (err) {
            toast('Failed to delete note: ' + err.message, 'error');
        }
    }

    _noteContext(e, noteId) {
        e.preventDefault();
        e.stopPropagation();
        this._showContextMenu(e.clientX, e.clientY, [
            { label: 'Edit', action: () => this._openNoteModal(noteId) },
            { divider: true },
            { label: 'Delete', danger: true, action: async () => { await this._doDeleteNote(noteId); }}
        ]);
    }

    _resetNoteForm() {
        const form = $('#note-form');
        if (form) form.reset();
        const idField = $('#note-id');
        if (idField) idField.value = '';
        this.editingNoteId = null;
        const titleEl = $('#note-modal-title');
        if (titleEl) titleEl.textContent = 'New Note';
        const delBtn = $('#btn-note-delete');
        if (delBtn) delBtn.style.display = 'none';
    }

    /* ==========================================================
       MAIL VIEW
       ========================================================== */
    _renderMail() {
        const container = $('#mail-list');
        if (!container) return;

        if (!this.token) {
            container.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon">\u{1F4E7}</div>
                <div class="empty-state-text">Sign in to access your mail</div>
            </div>`;
            return;
        }

        if (this.mailTab === 'inbox') {
            if (this.googleConnected || this.msConnected) {
                container.innerHTML = `<div class="empty-state">
                    <div class="empty-state-icon">\u{1F4E5}</div>
                    <div class="empty-state-text">No messages in your inbox</div>
                </div>`;
            } else {
                container.innerHTML = `<div class="empty-state">
                    <div class="empty-state-icon">\u{1F4E5}</div>
                    <div class="empty-state-text">Connect Gmail or Outlook to view your inbox</div>
                    <div class="empty-state-sub">Use the Integrations section in the sidebar</div>
                </div>`;
            }
        } else {
            /* Sent tab - show locally stored sent mail */
            const sent = this.sentMail || [];
            if (!sent.length) {
                container.innerHTML = `<div class="empty-state">
                    <div class="empty-state-icon">\u{1F4E4}</div>
                    <div class="empty-state-text">No sent messages</div>
                </div>`;
            } else {
                container.innerHTML = sent.map(m => {
                    const initial = (m.to_address || '?')[0].toUpperCase();
                    return `<div class="mail-item" onclick="app._openReadMailSent(${m.id})">
                        <div class="mail-avatar" style="background:var(--accent)">${initial}</div>
                        <div class="mail-info">
                            <div class="mail-from">To: ${escapeHtml(m.to_address)}</div>
                            <div class="mail-subject-line">${escapeHtml(m.subject)}</div>
                        </div>
                        <div class="mail-date-col">${m.sent_at ? fmtShort(m.sent_at) : ''}</div>
                    </div>`;
                }).join('');
            }
        }
    }

    async _sendMail() {
        if (!this.token) { toast('Sign in to send mail', 'error'); return; }

        const to      = $('#compose-to')?.value.trim();
        const subject = $('#compose-subject')?.value.trim();
        const body    = $('#compose-body')?.value.trim();
        const provider = $('#compose-provider')?.value || 'gmail';

        if (!to || !subject || !body) {
            toast('Fill in To, Subject, and Message fields', 'error');
            return;
        }

        const btnSend = $('#btn-send-mail');
        if (btnSend) { btnSend.disabled = true; btnSend.textContent = 'Sending...'; }

        try {
            const endpoint = provider === 'gmail'
                ? '/integrations/gmail/send'
                : '/integrations/msgraph/mail/send';
            await this.api.post(endpoint, {
                to_address: to,
                subject,
                body
            });
            toast('Email sent!', 'success');
            this._hideModal('modal-compose');
            const cForm = $('#compose-form');
            if (cForm) cForm.reset();

            /* Store locally in sent mail */
            if (!this.sentMail) this.sentMail = [];
            this.sentMail.push({
                id: Date.now(),
                to_address: to,
                subject,
                body,
                provider,
                sent_at: new Date().toISOString()
            });
            localStorage.setItem('ct-sent-mail', JSON.stringify(this.sentMail));
            this._renderMail();
        } catch (err) {
            toast('Failed to send: ' + err.message, 'error');
        } finally {
            if (btnSend) { btnSend.disabled = false; btnSend.textContent = 'Send'; }
        }
    }

    _openReadMailSent(id) {
        const m = (this.sentMail || []).find(x => x.id === id);
        if (!m) return;
        const bodyEl = $('#read-mail-body');
        if (!bodyEl) return;
        bodyEl.innerHTML = `<div class="read-mail-header">
            <div class="read-mail-meta">
                <span><strong>To:</strong> ${escapeHtml(m.to_address)}</span>
                <span><strong>Date:</strong> ${m.sent_at ? fmtFull(m.sent_at) : ''}</span>
                <span><strong>Provider:</strong> ${m.provider || 'gmail'}</span>
            </div>
            <div class="read-mail-subject">${escapeHtml(m.subject)}</div>
        </div>
        <div class="read-mail-body">${escapeHtml(m.body)}</div>`;
        const titleEl = $('#modal-read-mail .modal-header h2');
        if (titleEl) titleEl.textContent = 'Sent Message';
        this._showModal('modal-read-mail');
    }

    /* ==========================================================
       MINI CALENDAR (sidebar)
       ========================================================== */
    _renderMiniCalendar() {
        const container = $('#mini-cal');
        if (!container) return;

        const year  = this.miniYear;
        const month = this.miniMonth;
        const firstDay = new Date(year, month, 1);
        const lastDay  = new Date(year, month + 1, 0);
        const startPad = (firstDay.getDay() + 6) % 7;
        const today    = new Date();
        const todayKey = this._dateKey(today);

        const monthName = `${MONTH_NAMES[month].substring(0, 3)} ${year}`;

        /* Dates that have events */
        const eventDates = new Set(
            this.events
                .map(e => (e.start_time || '').substring(0, 10))
                .filter(Boolean)
        );

        let html = `<div class="mini-cal-header">
            <h3>${monthName}</h3>
            <div class="mini-cal-nav">
                <button onclick="app._miniCalNav(-1)" title="Previous month">&#9664;</button>
                <button onclick="app._miniCalNav(1)" title="Next month">&#9654;</button>
            </div>
        </div><div class="mini-cal-grid">`;

        DAY_NAMES_MINI.forEach(d => { html += `<div class="mini-cal-day-name">${d}</div>`; });

        /* Leading empty */
        for (let i = 0; i < startPad; i++) {
            html += '<div class="mini-cal-day empty"></div>';
        }

        /* Days */
        for (let day = 1; day <= lastDay.getDate(); day++) {
            const dateStr = `${year}-${pad(month + 1)}-${pad(day)}`;
            const isToday     = dateStr === todayKey;
            const isSelected  = dateStr === this.selectedDate;
            const hasEvents   = eventDates.has(dateStr);

            const cls = ['mini-cal-day'];
            if (isToday)    cls.push('today');
            if (isSelected) cls.push('selected');
            if (hasEvents)  cls.push('has-events');

            html += `<div class="${cls.join(' ')}" onclick="app._miniCalSelect(${day})">${day}</div>`;
        }

        html += '</div>';
        container.innerHTML = html;
    }

    _miniCalNav(dir) {
        this.miniMonth += dir;
        if (this.miniMonth < 0)  { this.miniMonth = 11; this.miniYear--; }
        if (this.miniMonth > 11) { this.miniMonth = 0;  this.miniYear++; }
        this._renderMiniCalendar();
    }

    _miniCalSelect(day) {
        this.selectedDate = `${this.miniYear}-${pad(this.miniMonth + 1)}-${pad(day)}`;
        this.calYear = this.miniYear;
        this.calMonth = this.miniMonth;
        this._renderMiniCalendar();
        this._renderCalendar();
        this.switchView('calendar');
    }

    /* ==========================================================
       INTEGRATIONS
       ========================================================== */
    async _checkIntegrations() {
        if (!this.token) return;

        try {
            const g = await this.api.get('/integrations/google/status');
            this.googleConnected = !!(g && g.connected);
        } catch { this.googleConnected = false; }

        try {
            const m = await this.api.get('/integrations/microsoft/status');
            this.msConnected = !!(m && m.connected);
        } catch { this.msConnected = false; }

        this._renderIntegrations();
    }

    _renderIntegrations() {
        const gBtn = $('#int-google');
        const mBtn = $('#int-microsoft');
        const syncG = $('#sync-gcal');
        const syncO = $('#sync-outlook');

        if (gBtn) {
            gBtn.classList.toggle('connected', this.googleConnected);
            const span = gBtn.querySelector('span:last-child');
            if (span) span.textContent = this.googleConnected ? 'Google \u2713' : 'Google';
        }
        if (mBtn) {
            mBtn.classList.toggle('connected', this.msConnected);
            const span = mBtn.querySelector('span:last-child');
            if (span) span.textContent = this.msConnected ? 'Microsoft \u2713' : 'Microsoft';
        }
        if (syncG) syncG.style.display = this.googleConnected ? '' : 'none';
        if (syncO) syncO.style.display = this.msConnected     ? '' : 'none';
    }

    async connectGoogle() {
        if (this.googleConnected) {
            if (!confirm('Disconnect Google account?')) return;
            localStorage.removeItem('ct-google-token');
            localStorage.removeItem('ct-google-user');
            this.googleConnected = false;
            this.googleUser = null;
            this.googleToken = null;
            this._renderIntegrations();
            toast('Google disconnected', 'info');
        } else {
            try {
                const oauth2 = new google.accounts.oauth2.TokenClient({
                    client_id: GOOGLE_CLIENT_ID,
                    scope: 'https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/tasks https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly',
                    callback: (response) => {
                        if (response.access_token) {
                            this._saveGoogleToken(response.access_token);
                        }
                    },
                    error_callback: (err) => {
                        toast('Google OAuth failed: ' + (err.message || 'User cancelled'), 'error');
                    }
                });
                oauth2.requestAccessToken();
            } catch (err) { toast('Google Sign-In not available: ' + err.message, 'error'); }
        }
    }

    async connectMicrosoft() {
        if (!this.token) { toast('Sign in first', 'error'); return; }
        if (this.msConnected) {
            if (!confirm('Disconnect Microsoft account?')) return;
            try {
                await this.api.post('/integrations/microsoft/disconnect');
                this.msConnected = false;
                this._renderIntegrations();
                toast('Microsoft disconnected', 'info');
            } catch (err) { toast('Failed: ' + err.message, 'error'); }
        } else {
            try {
                const data = await this.api.get('/integrations/microsoft/auth-url');
                if (data?.url) {
                    window.open(data.url, '_blank');
                    toast('Complete Microsoft OAuth in the new tab, then click Microsoft again', 'info');
                }
            } catch (err) { toast('Failed: ' + err.message, 'error'); }
        }
    }

    async syncGoogleCalendar() {
        if (!this.googleConnected || !this.googleToken) { toast('Connect Google first', 'error'); return; }
        try {
            const now = new Date();
            const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
            const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59).toISOString();
            const resp = await fetch(`https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin=${start}&timeMax=${end}&singleEvents=true&orderBy=startTime`, {
                headers: { 'Authorization': `Bearer ${this.googleToken}` }
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error.message);
            const events = data.items || [];
            toast(`Fetched ${events.length} events from Google Calendar`, 'success');
            // Merge with local events
            for (const gEvent of events) {
                const exists = this.events.find(e => e.external_id === gEvent.id);
                if (!exists) {
                    const ev = {
                        id: `g_${gEvent.id}`,
                        title: gEvent.summary || 'Untitled',
                        description: gEvent.description || '',
                        location: gEvent.location || '',
                        start_time: gEvent.start?.dateTime || gEvent.start?.date,
                        end_time: gEvent.end?.dateTime || gEvent.end?.date,
                        color: '#4dabf7',
                        source: 'google',
                        external_id: gEvent.id
                    };
                    this.events.push(ev);
                }
            }
            this._renderCalendar();
        } catch (err) { toast('Sync failed: ' + err.message, 'error'); }
    }

    async syncOutlookCalendar() {
        if (!this.msConnected) { toast('Connect Microsoft first', 'error'); return; }
        try {
            const result = await this.api.post('/integrations/microsoft/calendar/sync');
            const count = (result && result.synced) || 0;
            toast(`Synced ${count} events from Outlook Calendar`, 'success');
            await this._loadAll();
        } catch (err) { toast('Sync failed: ' + err.message, 'error'); }
    }

    /* ==========================================================
       COLOR PICKERS
       ========================================================== */
    _renderColorPicker(prefix) {
        const colors  = prefix === 'note' ? NOTE_COLORS : EVENT_COLORS;
        const container = $(`#${prefix}-color-picker`);
        const input     = $(`#${prefix}-color`);
        if (!container || !input) return;
        const selected = input.value || colors[0];

        container.innerHTML = colors.map(c =>
            `<div class="color-swatch ${c === selected ? 'selected' : ''}"
                style="background:${c}" data-color="${c}"
                onclick="app._selectColor('${prefix}','${c}')"></div>`
        ).join('');
    }

    _selectColor(prefix, color) {
        const input = $(`#${prefix}-color`);
        if (input) input.value = color;
        $$(`#${prefix}-color-picker .color-swatch`).forEach(s => {
            s.classList.toggle('selected', s.dataset.color === color);
        });
    }

    /* ==========================================================
       CONTEXT MENU
       ========================================================== */
    _showContextMenu(x, y, items) {
        const menu = $('#context-menu');
        if (!menu) return;

        const actionItems = items.filter(i => !i.divider);

        menu.innerHTML = items.map((item, i) => {
            if (item.divider) return '<div class="context-menu-divider"></div>';
            const actionIdx = actionItems.indexOf(item);
            return `<button class="context-menu-item ${item.danger ? 'danger' : ''}" data-action-idx="${actionIdx}">${item.label}</button>`;
        }).join('');

        /* Position */
        const menuHeight = items.length * 40;
        menu.style.left  = `${Math.min(x, window.innerWidth - 180)}px`;
        menu.style.top   = `${Math.min(y, window.innerHeight - menuHeight)}px`;
        menu.classList.add('active');

        /* Store actions and bind */
        menu._actions = actionItems;
        $$('.context-menu-item', menu).forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.actionIdx, 10);
                const action = menu._actions[idx];
                if (action?.action) action.action();
                this._hideContextMenu();
            });
        });
    }

    _hideContextMenu() {
        const menu = $('#context-menu');
        if (menu) { menu.classList.remove('active'); menu._actions = []; }
    }

    /* ==========================================================
       UTILITIES
       ========================================================== */
    _dateKey(d) {
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    _brightness(hex) {
        const h = hex.replace('#', '');
        if (h.length !== 6) return 0;
        const r = parseInt(h.substring(0, 2), 16);
        const g = parseInt(h.substring(2, 4), 16);
        const b = parseInt(h.substring(4, 6), 16);
        return (r * 299 + g * 587 + b * 114) / 1000;
    }
}

/* ================================================================
   Initialize application
   ================================================================ */
const app = new App();
