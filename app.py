import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# =========================
# Настройки
# =========================

st.set_page_config(
    page_title="Личный дневник",
    page_icon="📚",
    layout="wide",
)

DB_PATH = Path(os.getenv("DIARY_DB_PATH", "study.db"))
PBKDF2_ITERATIONS = 310_000


# =========================
# Безопасность паролей
# =========================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Проверяет новый хеш и старые plaintext-пароли из прежней версии."""
    if not stored:
        return False

    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("ascii"),
                int(iterations),
            ).hex()
            return hmac.compare_digest(digest, expected)
        except (ValueError, TypeError):
            return False

    # Совместимость со старой версией.
    return hmac.compare_digest(password, stored)


# =========================
# База данных
# =========================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#3b82f6',
                UNIQUE(user_id, name),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                record_type TEXT NOT NULL DEFAULT 'Оценка',
                subject TEXT NOT NULL,
                topic TEXT,
                grade REAL,
                hours REAL,
                comment TEXT,
                status TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                color TEXT NOT NULL DEFAULT '#3b82f6',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def query(sql, params=(), fetch=False, fetchone=False):
    with get_connection() as conn:
        cur = conn.execute(sql, params)
        if fetchone:
            return cur.fetchone()
        if fetch:
            return cur.fetchall()
        conn.commit()
        return None


def get_df(sql, params=()):
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# =========================
# Сессия / авторизация
# =========================

def logout():
    st.session_state.clear()
    st.rerun()


def current_user_id():
    return st.session_state.get("user_id")


def current_username():
    return st.session_state.get("username", "")


def is_admin():
    return bool(st.session_state.get("is_admin", False))


def authenticate(username: str, password: str):
    user = query(
        "SELECT id, username, password, is_admin FROM users WHERE username = ?",
        (username.strip(),),
        fetchone=True,
    )

    if not user:
        return None

    user_id, db_username, stored_password, admin = user

    if not verify_password(password, stored_password):
        return None

    # Автоматически переводим старый plaintext-пароль на безопасный хеш.
    if not stored_password.startswith("pbkdf2_sha256$"):
        query(
            "UPDATE users SET password = ? WHERE id = ?",
            (hash_password(password), user_id),
        )

    return {
        "id": user_id,
        "username": db_username,
        "is_admin": bool(admin),
    }


# =========================
# Первый запуск
# =========================

def show_first_setup():
    st.title("📚 Личный дневник")
    st.subheader("Первый запуск")

    st.info(
        "Пользователей пока нет. Создай учётную запись администратора. "
        "Пароль будет сохранён в виде защищённого хеша."
    )

    with st.form("first_setup"):
        username = st.text_input("Логин", placeholder="Например: admin")
        password = st.text_input("Пароль", type="password")
        password2 = st.text_input("Повтори пароль", type="password")
        submitted = st.form_submit_button("Создать администратора", type="primary")

        if submitted:
            username = username.strip()

            if len(username) < 3:
                st.error("Логин должен содержать минимум 3 символа.")
                return

            if len(password) < 8:
                st.error("Пароль должен содержать минимум 8 символов.")
                return

            if password != password2:
                st.error("Пароли не совпадают.")
                return

            try:
                query(
                    """
                    INSERT INTO users (username, password, created_at, is_admin)
                    VALUES (?, ?, ?, 1)
                    """,
                    (
                        username,
                        hash_password(password),
                        datetime.now().strftime("%Y-%m-%d"),
                    ),
                )
                st.success("Администратор создан. Теперь можно войти.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Такой логин уже существует.")


# =========================
# Вход
# =========================

def show_login():
    st.title("📚 Личный дневник")
    st.caption("Личные записи хранятся в базе приложения.")

    with st.form("login"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти", type="primary")

        if submitted:
            user = authenticate(username, password)

            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user["id"]
                st.session_state.username = user["username"]
                st.session_state.is_admin = user["is_admin"]
                st.session_state.page = "📊 Главная"
                st.rerun()
            else:
                st.error("Неверный логин или пароль.")


# =========================
# Главная
# =========================

def show_dashboard():
    st.title(f"Привет, {current_username()}! 👋")

    uid = current_user_id()

    df = get_df(
        "SELECT * FROM records WHERE user_id = ? ORDER BY date DESC, id DESC",
        (uid,),
    )
    subjects = get_df(
        "SELECT * FROM subjects WHERE user_id = ? ORDER BY name",
        (uid,),
    )
    events = get_df(
        "SELECT * FROM events WHERE user_id = ? ORDER BY date",
        (uid,),
    )

    total_records = len(df)
    total_subjects = len(subjects)
    debts = df[df["record_type"] == "Долг"] if not df.empty else pd.DataFrame()
    active_debts = (
        len(debts[debts["status"] != "Выполнено"])
        if not debts.empty
        else 0
    )
    total_hours = (
        float(df["hours"].fillna(0).sum())
        if not df.empty
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📝 Записей", total_records)
    c2.metric("📚 Предметов", total_subjects)
    c3.metric("⚠️ Активных долгов", active_debts)
    c4.metric("⏱️ Часов", f"{total_hours:.1f}")

    if subjects.empty:
        st.info("Пока нет предметов. Добавь первый предмет в разделе «📚 Предметы».")
        return

    st.divider()
    st.subheader("📚 По предметам")

    for _, subj in subjects.iterrows():
        subject_name = subj["name"]
        subject_df = df[df["subject"] == subject_name]

        grades = (
            subject_df.loc[subject_df["record_type"] == "Оценка", "grade"]
            .dropna()
        )
        hours = subject_df["hours"].dropna()

        subject_debts = subject_df[subject_df["record_type"] == "Долг"]
        active_subject_debts = subject_debts[
            subject_debts["status"] != "Выполнено"
        ]

        st.markdown(
            f"""
            <div style="
                padding:14px;
                margin:12px 0 8px 0;
                border-radius:10px;
                background:{subj['color']}15;
                border-left:5px solid {subj['color']};
            ">
                <h3 style="margin:0;">📚 {subject_name}</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "⭐ Средний балл",
            f"{grades.mean():.1f}" if not grades.empty else "—",
            f"{len(grades)} оценок",
        )
        m2.metric(
            "⏱️ Часы",
            f"{hours.sum():.1f}" if not hours.empty else "—",
            f"{len(hours)} записей",
        )
        m3.metric(
            "⚠️ Долги",
            len(active_subject_debts),
            f"из {len(subject_debts)}",
        )
        m4.metric("📝 Всего", len(subject_df))

        if not active_subject_debts.empty:
            for _, debt in active_subject_debts.iterrows():
                st.markdown(
                    f"- ⏳ **{debt['topic'] or 'Без названия'}** "
                    f"— {debt['date']}"
                )

    if not df.empty:
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            grades_df = df[
                (df["record_type"] == "Оценка") & df["grade"].notna()
            ]
            if not grades_df.empty:
                chart = (
                    grades_df.groupby("subject", as_index=False)["grade"]
                    .mean()
                )
                st.plotly_chart(
                    px.bar(
                        chart,
                        x="subject",
                        y="grade",
                        title="Средний балл по предметам",
                        labels={"subject": "Предмет", "grade": "Средний балл"},
                    ),
                    use_container_width=True,
                )

        with col2:
            hours_df = df[df["hours"].notna()]
            if not hours_df.empty:
                chart = (
                    hours_df.groupby("subject", as_index=False)["hours"]
                    .sum()
                )
                st.plotly_chart(
                    px.pie(
                        chart,
                        values="hours",
                        names="subject",
                        title="Распределение времени",
                    ),
                    use_container_width=True,
                )

    if not events.empty:
        st.divider()
        st.subheader("📅 Ближайшие события")
        today = date.today().isoformat()
        upcoming = events[events["date"] >= today].head(5)

        if upcoming.empty:
            st.caption("Ближайших событий нет.")
        else:
            for _, event in upcoming.iterrows():
                st.markdown(
                    f"**{event['date']}** — {event['title']}  \n"
                    f"{event['description'] or ''}"
                )


# =========================
# Новая запись
# =========================

def show_new_record():
    st.title("✍️ Новая запись")

    uid = current_user_id()
    subjects = get_df(
        "SELECT name FROM subjects WHERE user_id = ? ORDER BY name",
        (uid,),
    )

    if subjects.empty:
        st.warning("Сначала добавь хотя бы один предмет.")
        return

    record_type = st.radio(
        "Тип записи",
        ["Оценка", "Долг", "Время"],
        horizontal=True,
    )

    with st.form("new_record"):
        c1, c2 = st.columns(2)

        with c1:
            record_date = st.date_input("Дата", date.today())
            subject = st.selectbox(
                "Предмет",
                subjects["name"].tolist(),
            )
            topic = st.text_input(
                "Тема",
                placeholder="Например: контрольная, глава 3, лабораторная...",
            )

        with c2:
            grade = None
            hours = None
            status = None

            if record_type == "Оценка":
                grade = st.number_input(
                    "Оценка",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.5,
                )
                hours = st.number_input(
                    "Затрачено часов",
                    min_value=0.0,
                    max_value=24.0,
                    value=0.0,
                    step=0.5,
                )

            elif record_type == "Время":
                hours = st.number_input(
                    "Часы",
                    min_value=0.0,
                    max_value=24.0,
                    value=0.0,
                    step=0.5,
                )

            else:
                status = st.selectbox(
                    "Статус",
                    ["В процессе", "Выполнено"],
                )

            comment = st.text_area("Комментарий")

        submitted = st.form_submit_button("Сохранить", type="primary")

        if submitted:
            if record_type != "Время" and not topic.strip():
                st.error("Укажи тему записи.")
                return

            query(
                """
                INSERT INTO records
                (user_id, date, record_type, subject, topic, grade, hours, comment, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    record_date.isoformat(),
                    record_type,
                    subject,
                    topic.strip(),
                    grade,
                    hours,
                    comment.strip(),
                    status,
                ),
            )
            st.success("Запись сохранена.")


# =========================
# Предметы
# =========================

def show_subjects():
    st.title("📚 Предметы")
    uid = current_user_id()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Добавить предмет")

        with st.form("add_subject"):
            name = st.text_input("Название")
            color = st.color_picker("Цвет", "#3b82f6")
            submitted = st.form_submit_button("Добавить", type="primary")

            if submitted:
                name = name.strip()

                if not name:
                    st.error("Название не может быть пустым.")
                else:
                    try:
                        query(
                            """
                            INSERT INTO subjects (user_id, name, color)
                            VALUES (?, ?, ?)
                            """,
                            (uid, name, color),
                        )
                        st.success("Предмет добавлен.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Такой предмет уже существует.")

    with c2:
        st.subheader("Мои предметы")

        subjects = get_df(
            "SELECT * FROM subjects WHERE user_id = ? ORDER BY name",
            (uid,),
        )

        if subjects.empty:
            st.caption("Предметов пока нет.")
            return

        for _, subject in subjects.iterrows():
            left, right = st.columns([5, 1])

            with left:
                st.markdown(
                    f"""
                    <div style="
                        padding:9px;
                        margin:5px 0;
                        border-radius:7px;
                        background:{subject['color']}20;
                        border-left:4px solid {subject['color']};
                    ">
                        <strong>{subject['name']}</strong>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with right:
                if st.button("🗑️", key=f"delete_subject_{subject['id']}"):
                    record_count = query(
                        """
                        SELECT COUNT(*)
                        FROM records
                        WHERE user_id = ? AND subject = ?
                        """,
                        (uid, subject["name"]),
                        fetchone=True,
                    )[0]

                    if record_count > 0:
                        st.error(
                            "Нельзя удалить предмет, пока у него есть записи."
                        )
                    else:
                        query(
                            """
                            DELETE FROM subjects
                            WHERE id = ? AND user_id = ?
                            """,
                            (int(subject["id"]), uid),
                        )
                        st.success("Предмет удалён.")
                        st.rerun()


# =========================
# События
# =========================

def show_events():
    st.title("📅 События")
    uid = current_user_id()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Добавить событие")

        with st.form("add_event"):
            event_date = st.date_input("Дата", date.today())
            title = st.text_input("Название")
            description = st.text_area("Описание")
            color = st.color_picker("Цвет", "#3b82f6")

            submitted = st.form_submit_button("Добавить", type="primary")

            if submitted:
                title = title.strip()

                if not title:
                    st.error("Название не может быть пустым.")
                else:
                    query(
                        """
                        INSERT INTO events
                        (user_id, date, title, description, color)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            uid,
                            event_date.isoformat(),
                            title,
                            description.strip(),
                            color,
                        ),
                    )
                    st.success("Событие добавлено.")
                    st.rerun()

    with c2:
        st.subheader("Мои события")

        events = get_df(
            """
            SELECT * FROM events
            WHERE user_id = ?
            ORDER BY date DESC, id DESC
            """,
            (uid,),
        )

        if events.empty:
            st.caption("Событий пока нет.")
            return

        for _, event in events.iterrows():
            left, right = st.columns([5, 1])

            with left:
                st.markdown(
                    f"""
                    <div style="
                        padding:9px;
                        margin:5px 0;
                        border-radius:7px;
                        background:{event['color']}20;
                        border-left:4px solid {event['color']};
                    ">
                        <strong>{event['date']} — {event['title']}</strong><br>
                        <small>{event['description'] or ''}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with right:
                if st.button(
                    "🗑️",
                    key=f"delete_event_{event['id']}",
                ):
                    query(
                        """
                        DELETE FROM events
                        WHERE id = ? AND user_id = ?
                        """,
                        (int(event["id"]), uid),
                    )
                    st.success("Событие удалено.")
                    st.rerun()


# =========================
# Все записи
# =========================

def show_records():
    st.title("📋 Все записи")
    uid = current_user_id()

    df = get_df(
        """
        SELECT *
        FROM records
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        """,
        (uid,),
    )

    if df.empty:
        st.info("Записей пока нет.")
        return

    c1, c2, c3 = st.columns(3)

    type_filter = c1.multiselect(
        "Тип",
        ["Оценка", "Долг", "Время"],
    )
    subject_filter = c2.multiselect(
        "Предмет",
        sorted(df["subject"].dropna().unique().tolist()),
    )
    status_filter = c3.multiselect(
        "Статус",
        ["В процессе", "Выполнено"],
    )

    filtered = df.copy()

    if type_filter:
        filtered = filtered[filtered["record_type"].isin(type_filter)]

    if subject_filter:
        filtered = filtered[filtered["subject"].isin(subject_filter)]

    if status_filter:
        filtered = filtered[filtered["status"].isin(status_filter)]

    st.dataframe(
        filtered[
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
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    for _, record in filtered.iterrows():
        icon = {
            "Оценка": "⭐",
            "Долг": "⚠️",
            "Время": "⏰",
        }.get(record["record_type"], "📝")

        topic = record["topic"] or "общее"

        left, right = st.columns([5, 1])

        with left:
            st.markdown(
                f"{icon} **{record['subject']}** — {topic} "
                f"({record['date']})"
            )

            details = []

            if pd.notna(record["grade"]):
                details.append(f"Оценка: {record['grade']}")

            if pd.notna(record["hours"]):
                details.append(f"Часы: {record['hours']}")

            if record["status"]:
                details.append(f"Статус: {record['status']}")

            if record["comment"]:
                details.append(f"💬 {record['comment']}")

            if details:
                st.caption(" · ".join(details))

        with right:
            if (
                record["record_type"] == "Долг"
                and record["status"] != "Выполнено"
            ):
                if st.button(
                    "✅",
                    key=f"complete_record_{record['id']}",
                    help="Отметить выполненным",
                ):
                    query(
                        """
                        UPDATE records
                        SET status = 'Выполнено'
                        WHERE id = ? AND user_id = ?
                        """,
                        (int(record["id"]), uid),
                    )
                    st.rerun()

            if st.button(
                "🗑️",
                key=f"delete_record_{record['id']}",
                help="Удалить запись",
            ):
                query(
                    """
                    DELETE FROM records
                    WHERE id = ? AND user_id = ?
                    """,
                    (int(record["id"]), uid),
                )
                st.rerun()


# =========================
# Настройки аккаунта
# =========================

def show_settings():
    st.title("⚙️ Настройки")

    uid = current_user_id()

    st.subheader("🔐 Смена пароля")

    with st.form("change_password"):
        old_password = st.text_input("Текущий пароль", type="password")
        new_password = st.text_input("Новый пароль", type="password")
        new_password2 = st.text_input("Повтори новый пароль", type="password")

        submitted = st.form_submit_button("Изменить пароль", type="primary")

        if submitted:
            user = query(
                "SELECT password FROM users WHERE id = ?",
                (uid,),
                fetchone=True,
            )

            if not user or not verify_password(old_password, user[0]):
                st.error("Текущий пароль указан неверно.")
            elif len(new_password) < 8:
                st.error("Новый пароль должен содержать минимум 8 символов.")
            elif new_password != new_password2:
                st.error("Новые пароли не совпадают.")
            else:
                query(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (hash_password(new_password), uid),
                )
                st.success("Пароль изменён.")


# =========================
# Администратор
# =========================

def show_users():
    if not is_admin():
        st.error("Доступ запрещён.")
        return

    st.title("👥 Пользователи")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Создать пользователя")

        with st.form("add_user"):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            admin = st.checkbox("Администратор")

            submitted = st.form_submit_button(
                "Создать",
                type="primary",
            )

            if submitted:
                username = username.strip()

                if len(username) < 3:
                    st.error("Логин должен содержать минимум 3 символа.")
                elif len(password) < 8:
                    st.error("Пароль должен содержать минимум 8 символов.")
                else:
                    try:
                        query(
                            """
                            INSERT INTO users
                            (username, password, created_at, is_admin)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                username,
                                hash_password(password),
                                datetime.now().strftime("%Y-%m-%d"),
                                1 if admin else 0,
                            ),
                        )
                        st.success("Пользователь создан.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Такой логин уже существует.")

    with c2:
        st.subheader("Пользователи")

        users = get_df(
            """
            SELECT id, username, created_at, is_admin
            FROM users
            ORDER BY username
            """
        )

        for _, user in users.iterrows():
            left, right = st.columns([5, 1])

            with left:
                role = "👑 Админ" if user["is_admin"] else "👤 Пользователь"
                st.markdown(
                    f"**{user['username']}** — {role}  \n"
                    f"Создан: {user['created_at']}"
                )

            with right:
                if int(user["id"]) != uid:
                    if st.button(
                        "🗑️",
                        key=f"delete_user_{user['id']}",
                    ):
                        query(
                            "DELETE FROM users WHERE id = ?",
                            (int(user["id"]),),
                        )
                        st.success("Пользователь удалён.")
                        st.rerun()


# =========================
# Запуск
# =========================

init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "page" not in st.session_state:
    st.session_state.page = "📊 Главная"

user_count = query(
    "SELECT COUNT(*) FROM users",
    fetchone=True,
)[0]

if user_count == 0:
    show_first_setup()
elif not st.session_state.logged_in:
    show_login()
else:
    menu = [
        "📊 Главная",
        "✍️ Новая запись",
        "📚 Предметы",
        "📅 События",
        "📋 Записи",
        "⚙️ Настройки",
    ]

    if is_admin():
        menu.append("👥 Пользователи")

    menu.append("🚪 Выйти")

    current_page = st.session_state.page
    if current_page not in menu:
        current_page = "📊 Главная"

    page = st.sidebar.radio(
        "Меню",
        menu,
        index=menu.index(current_page),
    )
    st.session_state.page = page

    st.sidebar.divider()
    st.sidebar.caption(f"👤 {current_username()}")

    if page == "🚪 Выйти":
        logout()
    elif page == "📊 Главная":
        show_dashboard()
    elif page == "✍️ Новая запись":
        show_new_record()
    elif page == "📚 Предметы":
        show_subjects()
    elif page == "📅 События":
        show_events()
    elif page == "📋 Записи":
        show_records()
    elif page == "⚙️ Настройки":
        show_settings()
    elif page == "👥 Пользователи":
        show_users()
