import hashlib
import hmac
import os
import secrets
import calendar as pycalendar
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import psycopg2
from psycopg2 import IntegrityError
import streamlit as st


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Личный дневник",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

PBKDF2_ITERATIONS = 310_000


# =========================================================
# DARK DESIGN
# =========================================================

st.markdown(
    """
<style>
/* ---------- GLOBAL ---------- */
:root {
    --bg: #090d16;
    --bg-soft: #0e1420;
    --panel: #111827;
    --panel-2: #151e2d;
    --panel-3: #1a2435;
    --border: #263247;
    --border-soft: #1d2839;
    --text: #f5f7fb;
    --muted: #94a3b8;
    --muted-2: #64748b;
    --blue: #60a5fa;
    --blue-strong: #3b82f6;
    --green: #4ade80;
    --yellow: #facc15;
    --red: #ef4444;
    --shadow: 0 16px 45px rgba(0,0,0,.22);
}

html, body, [class*="css"] {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 10% 0%, rgba(59,130,246,.10), transparent 28%),
        radial-gradient(circle at 90% 10%, rgba(139,92,246,.08), transparent 26%),
        var(--bg);
    color: var(--text);
}

.block-container {
    max-width: 1480px;
    padding-top: 2.2rem;
    padding-bottom: 4rem;
}

h1 {
    font-size: clamp(2rem, 4vw, 3.2rem) !important;
    font-weight: 900 !important;
    letter-spacing: -0.045em !important;
    margin-bottom: .4rem !important;
}

h2 {
    font-weight: 850 !important;
    letter-spacing: -0.035em !important;
}

h3 {
    font-weight: 800 !important;
    letter-spacing: -0.025em !important;
}

p, label, span, div {
    color: inherit;
}

/* ---------- SIDEBAR ---------- */
section[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, #0b111d 0%, #0a0f18 100%);
    border-right: 1px solid var(--border);
}

section[data-testid="stSidebar"] > div {
    padding-top: 1.2rem;
}

section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: #e2e8f0;
}

section[data-testid="stSidebar"] .stRadio > div {
    gap: 5px;
}

section[data-testid="stSidebar"] .stRadio label {
    border-radius: 12px;
    padding: 8px 10px;
    transition: .18s ease;
}

section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(96,165,250,.08);
}

/* ---------- METRICS ---------- */
[data-testid="stMetric"] {
    background:
        linear-gradient(145deg, rgba(21,30,45,.96), rgba(15,23,42,.96));
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 19px 20px;
    box-shadow: var(--shadow);
    min-height: 125px;
}

[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    font-size: .92rem !important;
    font-weight: 700 !important;
}

[data-testid="stMetricValue"] {
    color: #f8fafc !important;
    font-size: 2rem !important;
    font-weight: 900 !important;
}

[data-testid="stMetricDelta"] {
    font-weight: 750 !important;
}

/* ---------- FORMS / CONTAINERS ---------- */
div[data-testid="stForm"] {
    background: rgba(17,24,39,.88);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 22px;
    box-shadow: var(--shadow);
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border) !important;
    border-radius: 20px !important;
}

/* ---------- INPUTS ---------- */
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div,
div[data-testid="stDateInput"] > div > div {
    background: #0d1522 !important;
    border-color: #2a3950 !important;
    border-radius: 12px !important;
    color: var(--text) !important;
}

div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
    color: #f8fafc !important;
}

div[data-baseweb="select"] * {
    color: #f8fafc !important;
}

[data-baseweb="popover"] {
    background: #111827 !important;
    border: 1px solid var(--border) !important;
}

[data-baseweb="menu"] {
    background: #111827 !important;
}

[data-baseweb="menu"] li:hover {
    background: #1d293b !important;
}

[data-testid="stDateInput"] input {
    color: #f8fafc !important;
}

[data-testid="stNumberInput"] button {
    background: #172235 !important;
    color: #cbd5e1 !important;
    border-color: #2a3950 !important;
}

/* ---------- BUTTONS ---------- */
.stButton > button,
.stFormSubmitButton > button {
    border-radius: 12px;
    border: 1px solid #2d3d55;
    background: #121c2b;
    color: #f8fafc;
    font-weight: 750;
    min-height: 42px;
    transition: .18s ease;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    border-color: #4b6b96;
    background: #19263a;
    transform: translateY(-1px);
}

.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb, #4f46e5);
    border-color: transparent;
    box-shadow: 0 10px 25px rgba(37,99,235,.24);
}

.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
}

/* ---------- DIVIDER ---------- */
hr {
    border-color: var(--border) !important;
    opacity: .7;
}

/* ---------- CARDS ---------- */
.card {
    background:
        linear-gradient(145deg, rgba(21,30,45,.98), rgba(13,20,32,.98));
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 16px 18px;
    margin: 9px 0;
    box-shadow: 0 9px 28px rgba(0,0,0,.16);
}

.hero-card {
    background:
        radial-gradient(circle at 90% 0%, rgba(96,165,250,.14), transparent 30%),
        linear-gradient(145deg, #121c2b, #0e1623);
    border: 1px solid #2a3a53;
    border-radius: 24px;
    padding: 25px;
    box-shadow: var(--shadow);
}

.section-label {
    color: #93c5fd;
    text-transform: uppercase;
    font-size: .75rem;
    letter-spacing: .13em;
    font-weight: 850;
    margin-bottom: 6px;
}

.muted {
    color: var(--muted) !important;
    font-size: .9rem;
}

.small-muted {
    color: var(--muted-2) !important;
    font-size: .8rem;
}

.subject-banner {
    border-radius: 17px;
    padding: 15px 18px;
    margin: 16px 0 9px;
    font-size: 1.12rem;
    font-weight: 850;
}

.badge {
    display: inline-block;
    padding: 5px 9px;
    border-radius: 999px;
    font-size: .78rem;
    font-weight: 800;
}

.empty-state {
    text-align: center;
    padding: 42px 20px;
    border: 1px dashed #314158;
    border-radius: 20px;
    background: rgba(15,23,42,.5);
}

.empty-state .emoji {
    font-size: 2.6rem;
}

/* ---------- ALERTS ---------- */
div[data-testid="stAlert"] {
    border-radius: 15px;
    border: 1px solid var(--border);
}

/* ---------- DATAFRAME ---------- */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
}

/* ---------- TABS ---------- */
button[data-baseweb="tab"] {
    color: var(--muted) !important;
    font-weight: 750 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #93c5fd !important;
}

/* ---------- CHECKBOX / RADIO ---------- */
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label {
    color: #e2e8f0 !important;
}

/* ---------- CALENDAR ---------- */
.calendar-day {
    background: linear-gradient(145deg, #121b29, #0e1623);
    border: 1px solid #27364b;
    border-radius: 16px;
    padding: 10px;
    min-height: 155px;
    margin-bottom: 12px;
    box-shadow: 0 7px 20px rgba(0,0,0,.12);
}

.calendar-day.today {
    border: 2px solid #3b82f6;
    box-shadow: 0 0 0 3px rgba(59,130,246,.10);
}

.calendar-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 31px;
    height: 31px;
    border-radius: 50%;
    background: #1d293b;
    font-weight: 900;
    margin-bottom: 7px;
}

.calendar-event {
    margin: 5px 0;
    padding: 5px 7px;
    border-radius: 8px;
    font-size: .76rem;
    line-height: 1.25;
}

.weekday {
    text-align: center;
    color: #64748b;
    padding: 8px;
    font-size: .82rem;
    font-weight: 850;
    text-transform: uppercase;
    letter-spacing: .05em;
}

/* ---------- SCROLLBAR ---------- */
::-webkit-scrollbar {
    width: 9px;
    height: 9px;
}
::-webkit-scrollbar-track {
    background: #090d16;
}
::-webkit-scrollbar-thumb {
    background: #263247;
    border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover {
    background: #35455f;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE
# =========================================================

def get_database_url():
    try:
        value = st.secrets.get("DATABASE_URL")
    except Exception:
        value = None
    return value or os.getenv("DATABASE_URL")


DATABASE_URL = get_database_url()


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "Не задан DATABASE_URL. Добавь его в Streamlit → Manage app → Secrets."
        )
    if "sslmode=" not in DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode="require")
    return psycopg2.connect(DATABASE_URL)


def query(sql, params=(), fetch=False, fetchone=False):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetchone:
                return cur.fetchone()
            if fetch:
                return cur.fetchall()
        conn.commit()


def get_df(sql, params=()):
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users(
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_admin BOOLEAN NOT NULL DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS subjects(
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT '#3b82f6',
                    UNIQUE(user_id,name)
                );

                CREATE TABLE IF NOT EXISTS records(
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    record_type TEXT NOT NULL DEFAULT 'Оценка',
                    subject TEXT NOT NULL,
                    topic TEXT,
                    grade DOUBLE PRECISION,
                    hours DOUBLE PRECISION,
                    comment TEXT,
                    status TEXT
                );

                CREATE TABLE IF NOT EXISTS events(
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    color TEXT NOT NULL DEFAULT '#3b82f6'
                );

                CREATE INDEX IF NOT EXISTS idx_subjects_user
                    ON subjects(user_id);

                CREATE INDEX IF NOT EXISTS idx_records_user_date
                    ON records(user_id,date);

                CREATE INDEX IF NOT EXISTS idx_events_user_date
                    ON events(user_id,date);
                """
            )

            cur.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='users'
                  AND column_name='is_admin'
                """
            )
            row = cur.fetchone()

            if row and row[0] != "boolean":
                cur.execute(
                    "ALTER TABLE users ALTER COLUMN is_admin DROP DEFAULT"
                )
                cur.execute(
                    """
                    ALTER TABLE users
                    ALTER COLUMN is_admin TYPE BOOLEAN
                    USING (is_admin <> 0)
                    """
                )
                cur.execute(
                    "ALTER TABLE users ALTER COLUMN is_admin SET DEFAULT FALSE"
                )

        conn.commit()


# =========================================================
# AUTH
# =========================================================

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password, stored):
    if not stored:
        return False

    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt.encode(),
                int(iterations),
            ).hex()
            return hmac.compare_digest(digest, expected)
        except (ValueError, TypeError):
            return False

    return hmac.compare_digest(password, stored)


def authenticate(username, password):
    user = query(
        """
        SELECT id, username, password, is_admin
        FROM users
        WHERE username=%s
        """,
        (username.strip(),),
        fetchone=True,
    )

    if not user or not verify_password(password, user[2]):
        return None

    # Automatically upgrade old plain-text passwords.
    if not user[2].startswith("pbkdf2_sha256$"):
        query(
            "UPDATE users SET password=%s WHERE id=%s",
            (hash_password(password), user[0]),
        )

    return {
        "id": user[0],
        "username": user[1],
        "is_admin": bool(user[3]),
    }


def uid():
    return st.session_state.get("user_id")


def username():
    return st.session_state.get("username", "")


def admin():
    return bool(st.session_state.get("is_admin", False))


def logout():
    st.session_state.clear()
    st.rerun()


# =========================================================
# HELPERS
# =========================================================

def grade_color(g):
    if g is None or pd.isna(g):
        return "#64748b"

    g = float(g)

    # 2 = red
    # 3 = yellow
    # 4 = green
    # 5 = blue
    if g < 3:
        return "#ef4444"
    if g < 4:
        return "#facc15"
    if g < 5:
        return "#22c55e"
    return "#3b82f6"


def grade_icon(g):
    if g is None or pd.isna(g):
        return "⭐"

    g = float(g)

    if g < 3:
        return "🔴"
    if g < 4:
        return "🟡"
    if g < 5:
        return "🟢"
    return "🔵"


def fmt_date(v):
    try:
        return datetime.strptime(str(v), "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return str(v)


def icon(record_type):
    return {
        "Оценка": "⭐",
        "Долг": "🔴",
        "Время": "⏱️",
    }.get(record_type, "📝")


def flash(kind, msg):
    st.session_state.flash = (kind, msg)


def show_flash():
    value = st.session_state.pop("flash", None)
    if not value:
        return

    func = {
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
        "info": st.info,
    }.get(value[0], st.info)

    func(value[1])


def empty_state(text, emoji="📭"):
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="emoji">{emoji}</div>
            <div style="font-size:1.05rem;font-weight:750;margin-top:8px">
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# LOGIN
# =========================================================

def first_setup():
    st.markdown(
        """
        <div class="hero-card">
            <div class="section-label">Первый запуск</div>
            <div style="font-size:2rem;font-weight:900;">📚 Личный дневник</div>
            <div class="muted" style="margin-top:6px;">
                Создай первого пользователя — он автоматически станет администратором.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    with st.form("first_setup"):
        u = st.text_input("Логин", placeholder="Например: student")
        p = st.text_input("Пароль", type="password")
        p2 = st.text_input("Повтори пароль", type="password")

        if st.form_submit_button(
            "Создать администратора",
            type="primary",
            use_container_width=True,
        ):
            u = u.strip()

            if len(u) < 3:
                st.error("Логин должен содержать минимум 3 символа.")
            elif len(p) < 8:
                st.error("Пароль должен содержать минимум 8 символов.")
            elif p != p2:
                st.error("Пароли не совпадают.")
            else:
                try:
                    query(
                        """
                        INSERT INTO users(username,password,created_at,is_admin)
                        VALUES(%s,%s,%s,TRUE)
                        """,
                        (u, hash_password(p), date.today().isoformat()),
                    )
                    flash(
                        "success",
                        "Администратор создан. Теперь можно войти.",
                    )
                    st.rerun()
                except IntegrityError:
                    st.error("Такой логин уже существует.")


def login():
    st.markdown(
        """
        <div class="hero-card">
            <div class="section-label">Добро пожаловать</div>
            <div style="font-size:2.4rem;font-weight:900;">
                📚 Личный дневник
            </div>
            <div class="muted" style="margin-top:7px;">
                Оценки, долги, время, события и календарь — всё в одном месте.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    with st.form("login"):
        u = st.text_input("Логин")
        p = st.text_input("Пароль", type="password")

        if st.form_submit_button(
            "Войти",
            type="primary",
            use_container_width=True,
        ):
            user = authenticate(u, p)

            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user["id"]
                st.session_state.username = user["username"]
                st.session_state.is_admin = user["is_admin"]
                st.session_state.page = "📊 Главная"
                st.rerun()
            else:
                st.error("Неверный логин или пароль.")


# =========================================================
# DASHBOARD
# =========================================================

def dashboard():
    st.title(f"Привет, {username()}! 👋")
    st.caption("Твоя учебная панель")
    show_flash()

    records = get_df(
        """
        SELECT *
        FROM records
        WHERE user_id=%s
        ORDER BY date DESC,id DESC
        """,
        (uid(),),
    )

    subjects = get_df(
        """
        SELECT *
        FROM subjects
        WHERE user_id=%s
        ORDER BY name
        """,
        (uid(),),
    )

    events = get_df(
        """
        SELECT *
        FROM events
        WHERE user_id=%s
        ORDER BY date,id
        """,
        (uid(),),
    )

    debts = (
        records[records.record_type == "Долг"]
        if not records.empty
        else pd.DataFrame()
    )

    active = (
        len(debts[debts.status != "Выполнено"])
        if not debts.empty
        else 0
    )

    hours = (
        float(records.hours.fillna(0).sum())
        if not records.empty
        else 0
    )

    a, b, c, d = st.columns(4)

    a.metric("📝 Записей", len(records))
    b.metric("📚 Предметов", len(subjects))
    c.metric("🔴 Активных долгов", active)
    d.metric("⏱️ Часов", f"{hours:.1f}")

    if subjects.empty:
        empty_state(
            "Добавь первый предмет в разделе «📚 Предметы».",
            "📚",
        )
        return

    st.divider()
    st.subheader("📚 Учебная статистика")

    for _, s in subjects.iterrows():
        sdf = records[records.subject == s["name"]]

        grades = sdf.loc[
            sdf.record_type == "Оценка",
            "grade",
        ].dropna()

        hrs = sdf.hours.dropna()

        debts2 = sdf[sdf.record_type == "Долг"]
        active2 = debts2[debts2.status != "Выполнено"]

        color = s["color"]

        st.markdown(
            f"""
            <div class="subject-banner"
                 style="
                    background:{color}12;
                    border:1px solid {color}45;
                    border-left:6px solid {color};
                 ">
                <span style="font-size:1.35rem;">📚</span>
                {s["name"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "⭐ Средний балл",
            f"{grades.mean():.2f}" if not grades.empty else "—",
            f"{len(grades)} оценок",
        )

        m2.metric(
            "⏱️ Часы",
            f"{hrs.sum():.1f}" if not hrs.empty else "—",
        )

        m3.metric(
            "🔴 Долги",
            len(active2),
            f"из {len(debts2)}",
        )

        m4.metric("📝 Всего", len(sdf))

        for _, r in debts2.sort_values("date", ascending=False).iterrows():
            debt_color = "#ef4444" if r.status != "Выполнено" else "#22c55e"
            status_text = (
                "Выполнено"
                if r.status == "Выполнено"
                else "Не выполнено"
            )

            st.markdown(
                f"""
                <div class="card"
                     style="border-left:5px solid {debt_color};">
                    <b>{'✅' if r.status == 'Выполнено' else '🔴'}
                    {r.topic or 'Без названия'}</b>
                    <span class="muted"> — {fmt_date(r.date)}</span>
                    <br>
                    <span class="small-muted">{status_text}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not records.empty:
        st.divider()

        c1, c2 = st.columns(2)

        with c1:
            g = records[
                (records.record_type == "Оценка")
                & records.grade.notna()
            ]

            if not g.empty:
                grouped = (
                    g.groupby("subject", as_index=False)
                    .grade.mean()
                    .sort_values("grade", ascending=False)
                )

                fig = px.bar(
                    grouped,
                    x="subject",
                    y="grade",
                    title="Средний балл по предметам",
                    labels={
                        "subject": "Предмет",
                        "grade": "Средний балл",
                    },
                )

                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=20, r=20, t=55, b=20),
                    yaxis=dict(range=[0, 5]),
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

        with c2:
            h = records[records.hours.notna()]

            if not h.empty:
                grouped = (
                    h.groupby("subject", as_index=False)
                    .hours.sum()
                )

                fig = px.pie(
                    grouped,
                    values="hours",
                    names="subject",
                    title="Распределение времени",
                )

                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=55, b=10),
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

    if not events.empty:
        st.divider()
        st.subheader("📅 Ближайшие события")

        upcoming = events.copy()
        upcoming = upcoming[upcoming["date"] >= date.today().isoformat()]
        upcoming = upcoming.head(5)

        if upcoming.empty:
            st.caption("Ближайших событий нет.")
        else:
            for _, e in upcoming.iterrows():
                st.markdown(
                    f"""
                    <div class="card"
                         style="
                            border-left:5px solid {e.color};
                            background:{e.color}10;
                         ">
                        <b>📅 {fmt_date(e.date)} — {e.title}</b>
                        <br>
                        <span class="muted">{e.description or ''}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# =========================================================
# NEW RECORD
# =========================================================

def new_record():
    st.title("✍️ Новая запись")
    st.caption(
        "У каждой записи сохраняется дата. "
        "Для долга тема обязательна, для оценки и времени — нет."
    )
    show_flash()

    subjects = get_df(
        """
        SELECT name
        FROM subjects
        WHERE user_id=%s
        ORDER BY name
        """,
        (uid(),),
    )

    if subjects.empty:
        st.warning("Сначала добавь хотя бы один предмет.")
        return

    rtype = st.radio(
        "Тип записи",
        ["Оценка", "Долг", "Время"],
        horizontal=True,
    )

    with st.form("new_record"):
        c1, c2 = st.columns(2)

        with c1:
            dt = st.date_input("📅 Дата", date.today())
            subj = st.selectbox(
                "📚 Предмет",
                subjects.name.tolist(),
            )
            topic = st.text_input(
                "Тема",
                placeholder=(
                    "Обязательно для долга; "
                    "для оценки и времени можно оставить пустым"
                ),
            )

        with c2:
            grade = None
            hours = None
            status = None

            if rtype == "Оценка":
                grade = st.number_input(
                    "⭐ Оценка",
                    min_value=2.0,
                    max_value=5.0,
                    value=5.0,
                    step=1.0,
                )

                hours = st.number_input(
                    "⏱️ Затрачено часов",
                    min_value=0.0,
                    max_value=24.0,
                    value=0.0,
                    step=0.5,
                )

            elif rtype == "Время":
                hours = st.number_input(
                    "⏱️ Часы",
                    min_value=0.0,
                    max_value=24.0,
                    value=1.0,
                    step=0.5,
                )

            else:
                status = st.selectbox(
                    "Статус",
                    ["В процессе", "Выполнено"],
                )

            comment = st.text_area(
                "Комментарий",
                placeholder="Дополнительная информация...",
            )

        if st.form_submit_button(
            "💾 Сохранить запись",
            type="primary",
            use_container_width=True,
        ):
            topic = topic.strip()
            comment = comment.strip()

            if rtype == "Долг" and not topic:
                st.error("Для долга обязательно укажи тему.")
                return

            query(
                """
                INSERT INTO records(
                    user_id,date,record_type,subject,topic,
                    grade,hours,comment,status
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    uid(),
                    dt.isoformat(),
                    rtype,
                    subj,
                    topic or None,
                    grade,
                    hours if hours and hours > 0 else None,
                    comment or None,
                    status,
                ),
            )

            if rtype == "Долг":
                flash(
                    "warning",
                    f"🔴 Долг добавлен — {subj}, {fmt_date(dt)}.",
                )
            elif rtype == "Оценка":
                flash(
                    "success",
                    f"{grade_icon(grade)} Оценка {grade:g} "
                    f"добавлена — {subj}, {fmt_date(dt)}.",
                )
            else:
                flash(
                    "success",
                    f"⏱️ Время добавлено: {hours:g} ч. "
                    f"— {subj}, {fmt_date(dt)}.",
                )

            st.rerun()


# =========================================================
# SUBJECTS
# =========================================================

def subjects_page():
    st.title("📚 Предметы")
    st.caption("Цвет предмета используется в дневнике и статистике.")
    show_flash()

    c1, c2 = st.columns([1, 1.25])

    with c1:
        with st.form("add_subject"):
            name = st.text_input(
                "Название предмета",
                placeholder="Например: Математика",
            )

            color = st.color_picker(
                "Цвет предмета",
                "#3b82f6",
            )

            st.markdown(
                f"""
                <div style="
                    padding:13px;
                    border-radius:13px;
                    background:{color}12;
                    border:1px solid {color}35;
                    border-left:5px solid {color};
                    margin:8px 0 14px;
                ">
                    <span class="muted">Предпросмотр</span><br>
                    <b style="font-size:1.05rem;">
                        {name or 'Мой предмет'}
                    </b>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.form_submit_button(
                "➕ Добавить предмет",
                type="primary",
                use_container_width=True,
            ):
                name = name.strip()

                if not name:
                    st.error("Название не может быть пустым.")
                else:
                    try:
                        query(
                            """
                            INSERT INTO subjects(user_id,name,color)
                            VALUES(%s,%s,%s)
                            """,
                            (uid(), name, color),
                        )

                        flash(
                            "success",
                            f"📚 Предмет «{name}» добавлен.",
                        )
                        st.rerun()

                    except IntegrityError:
                        st.error("Такой предмет уже существует.")

    with c2:
        st.subheader("Мои предметы")

        df = get_df(
            """
            SELECT *
            FROM subjects
            WHERE user_id=%s
            ORDER BY name
            """,
            (uid(),),
        )

        if df.empty:
            empty_state("Предметов пока нет.", "📚")
            return

        for _, s in df.iterrows():
            l, r = st.columns([7, 1])

            with l:
                st.markdown(
                    f"""
                    <div class="card"
                         style="
                            border-left:6px solid {s.color};
                            background:{s.color}0d;
                         ">
                        <b style="font-size:1.08rem;">
                            📚 {s.name}
                        </b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with r:
                if st.button(
                    "🗑️",
                    key=f"ds{s.id}",
                    use_container_width=True,
                ):
                    count = query(
                        """
                        SELECT COUNT(*)
                        FROM records
                        WHERE user_id=%s AND subject=%s
                        """,
                        (uid(), s.name),
                        fetchone=True,
                    )[0]

                    if count:
                        st.error(
                            "Нельзя удалить предмет, пока у него есть записи."
                        )
                    else:
                        query(
                            """
                            DELETE FROM subjects
                            WHERE id=%s AND user_id=%s
                            """,
                            (int(s.id), uid()),
                        )
                        flash("success", "Предмет удалён.")
                        st.rerun()


# =========================================================
# EVENTS
# =========================================================

def events_page():
    st.title("📅 События")
    st.caption("Обычные события с отдельным цветом и описанием.")
    show_flash()

    c1, c2 = st.columns([1, 1.25])

    with c1:
        with st.form("add_event"):
            dt = st.date_input("📅 Дата", date.today())

            title = st.text_input(
                "Название",
                placeholder="Например: Контрольная работа",
            )

            desc = st.text_area(
                "Описание",
                placeholder="Дополнительная информация...",
            )

            color = st.color_picker(
                "Цвет события",
                "#3b82f6",
            )

            st.markdown(
                f"""
                <div style="
                    padding:13px;
                    border-radius:13px;
                    background:{color}12;
                    border:1px solid {color}35;
                    border-left:5px solid {color};
                    margin:8px 0 14px;
                ">
                    <span class="muted">Предпросмотр</span><br>
                    <b>{title or 'Новое событие'}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.form_submit_button(
                "➕ Добавить событие",
                type="primary",
                use_container_width=True,
            ):
                title = title.strip()
                desc = desc.strip()

                if not title:
                    st.error("Название не может быть пустым.")
                else:
                    query(
                        """
                        INSERT INTO events(
                            user_id,date,title,description,color
                        )
                        VALUES(%s,%s,%s,%s,%s)
                        """,
                        (
                            uid(),
                            dt.isoformat(),
                            title,
                            desc or None,
                            color,
                        ),
                    )

                    flash(
                        "success",
                        f"📅 Событие «{title}» добавлено.",
                    )
                    st.rerun()

    with c2:
        st.subheader("Мои события")

        df = get_df(
            """
            SELECT *
            FROM events
            WHERE user_id=%s
            ORDER BY date,id
            """,
            (uid(),),
        )

        if df.empty:
            empty_state("Событий пока нет.", "📅")
            return

        for _, e in df.iterrows():
            l, r = st.columns([7, 1])

            with l:
                st.markdown(
                    f"""
                    <div class="card"
                         style="
                            border-left:6px solid {e.color};
                            background:{e.color}10;
                         ">
                        <b>
                            📅 {fmt_date(e.date)} — {e.title}
                        </b>
                        <br>
                        <span class="muted">
                            {e.description or ''}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with r:
                if st.button(
                    "🗑️",
                    key=f"de{e.id}",
                    use_container_width=True,
                ):
                    query(
                        """
                        DELETE FROM events
                        WHERE id=%s AND user_id=%s
                        """,
                        (int(e.id), uid()),
                    )
                    flash("success", "Событие удалено.")
                    st.rerun()


# =========================================================
# RECORDS
# =========================================================

def records_page():
    st.title("📋 Записи")
    st.caption("Полная история оценок, долгов и затраченного времени.")
    show_flash()

    df = get_df(
        """
        SELECT *
        FROM records
        WHERE user_id=%s
        ORDER BY date DESC,id DESC
        """,
        (uid(),),
    )

    if df.empty:
        empty_state("Записей пока нет.", "📋")
        return

    c1, c2, c3 = st.columns(3)

    tf = c1.multiselect(
        "Тип",
        ["Оценка", "Долг", "Время"],
    )

    sf = c2.multiselect(
        "Предмет",
        sorted(df.subject.dropna().unique()),
    )

    stf = c3.multiselect(
        "Статус",
        ["В процессе", "Выполнено"],
    )

    f = df.copy()

    if tf:
        f = f[f.record_type.isin(tf)]

    if sf:
        f = f[f.subject.isin(sf)]

    if stf:
        f = f[f.status.isin(stf)]

    if f.empty:
        empty_state(
            "По выбранным фильтрам ничего нет.",
            "🔎",
        )
        return

    view = f[
        [
            "date",
            "record_type",
            "subject",
            "topic",
            "grade",
            "hours",
            "comment",
            "status",
        ]
    ].copy()

    view.date = view.date.map(fmt_date)

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    for _, r in f.iterrows():
        if r.record_type == "Оценка":
            color = grade_color(r.grade)
        elif r.record_type == "Долг":
            color = (
                "#22c55e"
                if r.status == "Выполнено"
                else "#ef4444"
            )
        else:
            color = "#3b82f6"

        extra = ""

        if pd.notna(r.grade):
            extra += f" · ⭐ {r.grade:g}"

        if pd.notna(r.hours):
            extra += f" · ⏱️ {r.hours:g} ч."

        if pd.notna(r.status) and r.status:
            extra += f" · {r.status}"

        st.markdown(
            f"""
            <div class="card"
                 style="border-left:6px solid {color};">
                <div style="
                    display:flex;
                    justify-content:space-between;
                    gap:15px;
                    align-items:flex-start;
                ">
                    <div>
                        <b style="font-size:1.05rem;">
                            {icon(r.record_type)} {r.subject}
                        </b>
                        {' — ' + str(r.topic) if pd.notna(r.topic) and r.topic else ''}
                        <br>
                        <span class="muted">
                            📅 {fmt_date(r.date)}{extra}
                        </span>
                    </div>
                </div>

                {
                    f'<div class="muted" style="margin-top:8px;">{r.comment}</div>'
                    if pd.notna(r.comment) and r.comment
                    else ''
                }
            </div>
            """,
            unsafe_allow_html=True,
        )

        a, b = st.columns(2)

        with a:
            if (
                r.record_type == "Долг"
                and r.status != "Выполнено"
                and st.button(
                    "✅ Выполнено",
                    key=f"cr{r.id}",
                    use_container_width=True,
                )
            ):
                query(
                    """
                    UPDATE records
                    SET status='Выполнено'
                    WHERE id=%s AND user_id=%s
                    """,
                    (int(r.id), uid()),
                )
                flash("success", "Долг выполнен.")
                st.rerun()

        with b:
            if st.button(
                "🗑️ Удалить",
                key=f"dr{r.id}",
                use_container_width=True,
            ):
                query(
                    """
                    DELETE FROM records
                    WHERE id=%s AND user_id=%s
                    """,
                    (int(r.id), uid()),
                )
                flash("success", "Запись удалена.")
                st.rerun()


# =========================================================
# GRADES
# =========================================================

def grades_page():
    st.title("⭐ Оценки")
    st.caption("Средние баллы, состав оценок и история по датам.")
    show_flash()

    df = get_df(
        """
        SELECT id,date,subject,topic,grade,comment
        FROM records
        WHERE user_id=%s
          AND record_type='Оценка'
          AND grade IS NOT NULL
        ORDER BY date DESC,id DESC
        """,
        (uid(),),
    )

    if df.empty:
        empty_state("Оценок пока нет.", "⭐")
        return

    c1, c2 = st.columns(2)

    sf = c1.multiselect(
        "📚 Предметы",
        sorted(df.subject.unique()),
    )

    period = c2.date_input(
        "📅 Период",
        (
            date.today() - timedelta(days=30),
            date.today(),
        ),
    )

    if sf:
        df = df[df.subject.isin(sf)]

    if isinstance(period, (tuple, list)) and len(period) == 2:
        df = df[
            (df.date >= period[0].isoformat())
            & (df.date <= period[1].isoformat())
        ]

    if df.empty:
        empty_state(
            "За выбранный период оценок нет.",
            "🔎",
        )
        return

    avg = df.grade.mean()

    st.markdown(
        f"""
        <div class="hero-card"
             style="
                border-left:6px solid {grade_color(avg)};
                margin:10px 0 22px;
             ">
            <div class="section-label">Общая статистика</div>
            <div class="muted">Средний балл</div>
            <div style="
                font-size:3rem;
                line-height:1;
                font-weight:950;
                color:{grade_color(avg)};
                margin:7px 0;
            ">
                {avg:.2f}
            </div>
            <span class="badge"
                  style="
                    background:{grade_color(avg)}18;
                    color:{grade_color(avg)};
                  ">
                {len(df)} оценок
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("📊 По предметам")

    for subject, g in df.groupby("subject", sort=True):
        avg_subject = g.grade.mean()
        color = grade_color(avg_subject)

        counts = (
            g.grade.round()
            .astype(int)
            .value_counts()
            .reindex([5, 4, 3, 2], fill_value=0)
        )

        composition = " · ".join(
            f"{grade} — {count}"
            for grade, count in counts.items()
            if count
        )

        st.markdown(
            f"""
            <div class="card"
                 style="
                    border-left:6px solid {color};
                    padding:18px 20px;
                 ">
                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    gap:15px;
                ">
                    <div>
                        <div style="
                            font-size:1.2rem;
                            font-weight:900;
                        ">
                            📚 {subject}
                        </div>

                        <div class="muted"
                             style="margin-top:5px;">
                            Состав оценок:
                            <b style="color:#cbd5e1;">
                                {composition or 'нет данных'}
                            </b>
                        </div>
                    </div>

                    <div style="
                        font-size:2.25rem;
                        font-weight:950;
                        color:{color};
                        white-space:nowrap;
                    ">
                        {avg_subject:.2f}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("🗓️ Оценки по датам")

    for day, g in df.groupby("date", sort=False):
        st.markdown(
            f"""
            <div style="
                margin:20px 0 8px;
                font-size:1.05rem;
                font-weight:900;
                color:#cbd5e1;
            ">
                📅 {fmt_date(day)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        for _, r in g.iterrows():
            color = grade_color(r.grade)

            st.markdown(
                f"""
                <div class="card"
                     style="
                        border-left:6px solid {color};
                        background:{color}08;
                     ">
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        gap:12px;
                    ">
                        <div>
                            <b style="font-size:1.08rem;">
                                📚 {r.subject}
                            </b>
                            <br>
                            <span class="muted">
                                📝 {r.topic or 'Без темы'}
                            </span>
                        </div>

                        <div style="
                            font-size:1.75rem;
                            font-weight:950;
                            color:{color};
                        ">
                            {r.grade:g}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# =========================================================
# CALENDAR
# =========================================================

def calendar_page():
    st.title("🗓️ Календарь")
    st.caption(
        "Здесь отображаются абсолютно все записи: "
        "оценки, долги, время и обычные события."
    )
    show_flash()

    if "cal_month" not in st.session_state:
        st.session_state.cal_month = date.today().replace(day=1)

    m = st.session_state.cal_month

    a, b, c = st.columns([1, 2, 1])

    with a:
        if st.button(
            "← Предыдущий месяц",
            use_container_width=True,
        ):
            st.session_state.cal_month = (
                date(m.year - 1, 12, 1)
                if m.month == 1
                else date(m.year, m.month - 1, 1)
            )
            st.rerun()

    with b:
        month_names = [
            "",
            "Январь",
            "Февраль",
            "Март",
            "Апрель",
            "Май",
            "Июнь",
            "Июль",
            "Август",
            "Сентябрь",
            "Октябрь",
            "Ноябрь",
            "Декабрь",
        ]

        st.markdown(
            f"""
            <div style="
                text-align:center;
                font-size:1.5rem;
                font-weight:900;
                padding:7px;
            ">
                {month_names[m.month]} {m.year}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c:
        if st.button(
            "Следующий месяц →",
            use_container_width=True,
        ):
            st.session_state.cal_month = (
                date(m.year + 1, 1, 1)
                if m.month == 12
                else date(m.year, m.month + 1, 1)
            )
            st.rerun()

    nxt = (
        date(m.year + 1, 1, 1)
        if m.month == 12
        else date(m.year, m.month + 1, 1)
    )

    records = get_df(
        """
        SELECT *
        FROM records
        WHERE user_id=%s
          AND date >= %s
          AND date < %s
        ORDER BY date,id
        """,
        (
            uid(),
            m.isoformat(),
            nxt.isoformat(),
        ),
    )

    events = get_df(
        """
        SELECT *
        FROM events
        WHERE user_id=%s
          AND date >= %s
          AND date < %s
        ORDER BY date,id
        """,
        (
            uid(),
            m.isoformat(),
            nxt.isoformat(),
        ),
    )

    q1, q2, q3, q4 = st.columns(4)

    q1.metric(
        "⭐ Оценок",
        int((records.record_type == "Оценка").sum())
        if not records.empty
        else 0,
    )

    q2.metric(
        "🔴 Долгов",
        int((records.record_type == "Долг").sum())
        if not records.empty
        else 0,
    )

    q3.metric(
        "⏱️ Записей времени",
        int((records.record_type == "Время").sum())
        if not records.empty
        else 0,
    )

    q4.metric("📅 Событий", len(events))

    st.write("")

    names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    cols = st.columns(7)

    for i, n in enumerate(names):
        with cols[i]:
            st.markdown(
                f'<div class="weekday">{n}</div>',
                unsafe_allow_html=True,
            )

    cells = (
        [None] * m.weekday()
        + list(range(1, pycalendar.monthrange(m.year, m.month)[1] + 1))
    )

    while len(cells) % 7:
        cells.append(None)

    for start in range(0, len(cells), 7):
        cols = st.columns(7)

        for i, num in enumerate(cells[start:start + 7]):
            with cols[i]:
                if num is None:
                    st.markdown(
                        '<div style="min-height:155px;"></div>',
                        unsafe_allow_html=True,
                    )
                    continue

                ds = date(
                    m.year,
                    m.month,
                    num,
                ).isoformat()

                rr = (
                    records[records.date == ds]
                    if not records.empty
                    else pd.DataFrame()
                )

                ee = (
                    events[events.date == ds]
                    if not events.empty
                    else pd.DataFrame()
                )

                today_class = (
                    "today"
                    if ds == date.today().isoformat()
                    else ""
                )

                html = f"""
                <div class="calendar-day {today_class}">
                    <div class="calendar-number">{num}</div>
                """

                for _, e in ee.iterrows():
                    html += f"""
                    <div class="calendar-event"
                         style="
                            background:{e.color}14;
                            border-left:4px solid {e.color};
                         ">
                        📅 <b>{e.title}</b>
                    </div>
                    """

                for _, r in rr.iterrows():
                    if r.record_type == "Оценка":
                        color = grade_color(r.grade)
                        label = (
                            f"⭐ {r.subject} · {r.grade:g}"
                        )
                    elif r.record_type == "Долг":
                        color = (
                            "#22c55e"
                            if r.status == "Выполнено"
                            else "#ef4444"
                        )
                        label = (
                            f"{'✅' if r.status == 'Выполнено' else '🔴'} "
                            f"{r.subject} · "
                            f"{r.topic or 'Долг'}"
                        )
                    else:
                        color = "#3b82f6"
                        label = (
                            f"⏱️ {r.subject} · "
                            f"{r.hours or 0:g} ч."
                        )

                    html += f"""
                    <div class="calendar-event"
                         style="
                            background:{color}14;
                            border-left:4px solid {color};
                         ">
                        {label}
                    </div>
                    """

                html += "</div>"

                st.markdown(
                    html,
                    unsafe_allow_html=True,
                )

    st.divider()
    st.subheader("📋 Подробности месяца")

    rows = []

    for _, e in events.iterrows():
        rows.append(
            {
                "Дата": fmt_date(e.date),
                "Тип": "📅 Событие",
                "Предмет": "—",
                "Название": e.title,
                "Детали": e.description or "",
            }
        )

    for _, r in records.iterrows():
        if r.record_type == "Оценка":
            details = f"Оценка: {r.grade:g}"
        elif r.record_type == "Время":
            details = f"{r.hours or 0:g} ч."
        else:
            details = r.status or "В процессе"

        rows.append(
            {
                "Дата": fmt_date(r.date),
                "Тип": icon(r.record_type),
                "Предмет": r.subject,
                "Название": r.topic or "Без темы",
                "Детали": details,
            }
        )

    if rows:
        details_df = pd.DataFrame(rows)

        st.dataframe(
            details_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        empty_state(
            "В этом месяце пока ничего нет.",
            "🗓️",
        )


# =========================================================
# SETTINGS
# =========================================================

def settings_page():
    st.title("⚙️ Настройки")
    st.caption("Управление аккаунтом.")
    show_flash()

    with st.form("password_change"):
        old = st.text_input(
            "Текущий пароль",
            type="password",
        )

        new = st.text_input(
            "Новый пароль",
            type="password",
        )

        new2 = st.text_input(
            "Повтори новый пароль",
            type="password",
        )

        if st.form_submit_button(
            "🔐 Изменить пароль",
            type="primary",
        ):
            row = query(
                """
                SELECT password
                FROM users
                WHERE id=%s
                """,
                (uid(),),
                fetchone=True,
            )

            if not row or not verify_password(old, row[0]):
                st.error("Текущий пароль указан неверно.")
            elif len(new) < 8:
                st.error(
                    "Новый пароль должен содержать минимум 8 символов."
                )
            elif new != new2:
                st.error("Новые пароли не совпадают.")
            else:
                query(
                    """
                    UPDATE users
                    SET password=%s
                    WHERE id=%s
                    """,
                    (hash_password(new), uid()),
                )

                flash(
                    "success",
                    "Пароль успешно изменён.",
                )
                st.rerun()


# =========================================================
# USERS
# =========================================================

def users_page():
    if not admin():
        st.error("Доступ запрещён.")
        return

    st.title("👥 Пользователи")
    st.caption("Раздел доступен только администраторам.")
    show_flash()

    c1, c2 = st.columns([1, 1.25])

    with c1:
        with st.form("add_user"):
            u = st.text_input("Логин")
            p = st.text_input("Пароль", type="password")
            a = st.checkbox("👑 Администратор")

            if st.form_submit_button(
                "➕ Создать пользователя",
                type="primary",
                use_container_width=True,
            ):
                u = u.strip()

                if len(u) < 3:
                    st.error(
                        "Логин должен содержать минимум 3 символа."
                    )
                elif len(p) < 8:
                    st.error(
                        "Пароль должен содержать минимум 8 символов."
                    )
                else:
                    try:
                        query(
                            """
                            INSERT INTO users(
                                username,password,created_at,is_admin
                            )
                            VALUES(%s,%s,%s,%s)
                            """,
                            (
                                u,
                                hash_password(p),
                                date.today().isoformat(),
                                bool(a),
                            ),
                        )

                        flash(
                            "success",
                            f"Пользователь «{u}» создан.",
                        )
                        st.rerun()

                    except IntegrityError:
                        st.error(
                            "Такой логин уже существует."
                        )

    with c2:
        df = get_df(
            """
            SELECT id,username,created_at,is_admin
            FROM users
            ORDER BY username
            """
        )

        for _, u in df.iterrows():
            l, r = st.columns([7, 1])

            with l:
                role = (
                    "👑 Администратор"
                    if bool(u.is_admin)
                    else "👤 Пользователь"
                )

                st.markdown(
                    f"""
                    <div class="card">
                        <b>{u.username}</b>
                        <span class="muted"> — {role}</span>
                        <br>
                        <span class="small-muted">
                            Создан: {fmt_date(u.created_at)}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with r:
                if int(u.id) != int(uid()):
                    if st.button(
                        "🗑️",
                        key=f"du{u.id}",
                        use_container_width=True,
                    ):
                        query(
                            """
                            DELETE FROM users
                            WHERE id=%s
                            """,
                            (int(u.id),),
                        )

                        flash(
                            "success",
                            f"Пользователь «{u.username}» удалён.",
                        )
                        st.rerun()


# =========================================================
# MAIN
# =========================================================

try:
    init_db()

    st.session_state.setdefault(
        "logged_in",
        False,
    )

    st.session_state.setdefault(
        "page",
        "📊 Главная",
    )

    show_flash()

    count = query(
        "SELECT COUNT(*) FROM users",
        fetchone=True,
    )[0]

    if count == 0:
        first_setup()

    elif not st.session_state.logged_in:
        login()

    else:
        menu = [
            "📊 Главная",
            "✍️ Новая запись",
            "📚 Предметы",
            "📅 События",
            "📋 Записи",
            "⭐ Оценки",
            "🗓️ Календарь",
            "⚙️ Настройки",
        ]

        if admin():
            menu.append("👥 Пользователи")

        menu.append("🚪 Выйти")

        page = st.sidebar.radio(
            "НАВИГАЦИЯ",
            menu,
            index=(
                menu.index(st.session_state.page)
                if st.session_state.page in menu
                else 0
            ),
        )

        st.session_state.page = page

        st.sidebar.divider()

        st.sidebar.markdown(
            f"""
            <div style="
                padding:12px;
                border-radius:14px;
                background:#111827;
                border:1px solid #263247;
            ">
                <div class="small-muted">Вы вошли как</div>
                <b>👤 {username()}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if page == "🚪 Выйти":
            logout()
        elif page == "📊 Главная":
            dashboard()
        elif page == "✍️ Новая запись":
            new_record()
        elif page == "📚 Предметы":
            subjects_page()
        elif page == "📅 События":
            events_page()
        elif page == "📋 Записи":
            records_page()
        elif page == "⭐ Оценки":
            grades_page()
        elif page == "🗓️ Календарь":
            calendar_page()
        elif page == "⚙️ Настройки":
            settings_page()
        elif page == "👥 Пользователи":
            users_page()

except Exception as exc:
    st.error(
        "Не удалось запустить дневник. "
        "Проверь DATABASE_URL и логи приложения."
    )
    st.exception(exc)
