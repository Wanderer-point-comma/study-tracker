import hashlib
import hmac
import os
import secrets
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import psycopg2
from psycopg2 import IntegrityError
from psycopg2.pool import ThreadedConnectionPool
import streamlit as st

st.set_page_config(page_title="Личный дневник", page_icon="📚", layout="wide")

PBKDF2_ITERATIONS = 310_000
POOL_MIN = 1
POOL_MAX = 5


def get_database_url():
    try:
        value = st.secrets.get("DATABASE_URL")
    except Exception:
        value = None
    return value or os.getenv("DATABASE_URL")


DATABASE_URL = get_database_url()


@st.cache_resource(show_spinner=False)
def get_pool(database_url):
    if not database_url:
        raise RuntimeError(
            "Не задан DATABASE_URL. Добавь его в Streamlit → Manage app → Settings → Secrets."
        )
    kwargs = {} if "sslmode=" in database_url else {"sslmode": "require"}
    return ThreadedConnectionPool(POOL_MIN, POOL_MAX, database_url, **kwargs)


def get_connection():
    pool = get_pool(DATABASE_URL)
    conn = pool.getconn()
    if conn.closed:
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    return conn


def release_connection(conn, broken=False):
    get_pool(DATABASE_URL).putconn(conn, close=broken)


@st.cache_resource(show_spinner=False)
def init_db():
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_admin BOOLEAN NOT NULL DEFAULT FALSE
                );
                CREATE TABLE IF NOT EXISTS subjects (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT '#3b82f6',
                    UNIQUE(user_id, name)
                );
                CREATE TABLE IF NOT EXISTS records (
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
                CREATE TABLE IF NOT EXISTS events (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    color TEXT NOT NULL DEFAULT '#3b82f6'
                );
                CREATE INDEX IF NOT EXISTS idx_subjects_user_id ON subjects(user_id);
                CREATE INDEX IF NOT EXISTS idx_records_user_id ON records(user_id);
                CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
                CREATE INDEX IF NOT EXISTS idx_records_user_date ON records(user_id, date DESC);
                CREATE INDEX IF NOT EXISTS idx_events_user_date ON events(user_id, date);
                """
            )

            # Миграция старой версии: INTEGER 0/1 -> BOOLEAN.
            cur.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'users'
                  AND column_name = 'is_admin'
                """
            )
            column = cur.fetchone()
            if column and column[0] in ("integer", "bigint", "smallint"):
                cur.execute(
                    """
                    ALTER TABLE users ALTER COLUMN is_admin DROP DEFAULT;
                    ALTER TABLE users ALTER COLUMN is_admin TYPE BOOLEAN
                        USING (is_admin <> 0);
                    ALTER TABLE users ALTER COLUMN is_admin SET DEFAULT FALSE;
                    ALTER TABLE users ALTER COLUMN is_admin SET NOT NULL;
                    """
                )
        conn.commit()
    except Exception:
        conn.rollback()
        broken = True
        raise
    finally:
        release_connection(conn, broken)
    return True


@st.cache_data(ttl=5, show_spinner=False)
def get_df(sql, params=()):
    conn = get_connection()
    broken = False
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken)


def query(sql, params=(), fetch=False, fetchone=False, write=False):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone() if fetchone else cur.fetchall() if fetch else None
        conn.commit()
        if write:
            get_df.clear()
        return result
    except Exception:
        conn.rollback()
        broken = True
        raise
    finally:
        release_connection(conn, broken)


# ============================================================
# PASSWORDS / AUTH
# ============================================================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations)
            ).hex()
            return hmac.compare_digest(digest, expected)
        except (ValueError, TypeError):
            return False
    return hmac.compare_digest(password, stored)


def authenticate(username, password):
    user = query(
        "SELECT id, username, password, is_admin FROM users WHERE username = %s",
        (username.strip(),),
        fetchone=True,
    )
    if not user or not verify_password(password, user[2]):
        return None
    if not user[2].startswith("pbkdf2_sha256$"):
        query(
            "UPDATE users SET password = %s WHERE id = %s",
            (hash_password(password), user[0]), write=True,
        )
    return {"id": user[0], "username": user[1], "is_admin": bool(user[3])}


def logout():
    st.session_state.clear()
    st.rerun()


def uid():
    return st.session_state.get("user_id")


def username():
    return st.session_state.get("username", "")


def admin():
    return bool(st.session_state.get("is_admin", False))


# ============================================================
# LOGIN
# ============================================================

def show_first_setup():
    st.title("📚 Личный дневник")
    st.subheader("Первый запуск")
    st.info("Пользователей пока нет. Создай учётную запись администратора.")
    with st.form("first_setup"):
        login = st.text_input("Логин", placeholder="Например: admin")
        password = st.text_input("Пароль", type="password")
        password2 = st.text_input("Повтори пароль", type="password")
        if st.form_submit_button("Создать администратора", type="primary"):
            login = login.strip()
            if len(login) < 3:
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
                    """INSERT INTO users (username,password,created_at,is_admin)
                       VALUES (%s,%s,%s,TRUE)""",
                    (login, hash_password(password), datetime.now().strftime("%Y-%m-%d")),
                    write=True,
                )
                st.success("Администратор создан. Теперь можно войти.")
                st.rerun()
            except IntegrityError:
                st.error("Такой логин уже существует.")


def show_login():
    st.title("📚 Личный дневник")
    st.caption("Личные записи хранятся в PostgreSQL Supabase.")
    with st.form("login"):
        login = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        if st.form_submit_button("Войти", type="primary"):
            user = authenticate(login, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user["id"]
                st.session_state.username = user["username"]
                st.session_state.is_admin = user["is_admin"]
                st.session_state.page = "📊 Главная"
                st.rerun()
            else:
                st.error("Неверный логин или пароль.")


# ============================================================
# DASHBOARD
# ============================================================

def show_dashboard():
    st.title(f"Привет, {username()}! 👋")
    user_id = uid()
    df = get_df("SELECT * FROM records WHERE user_id=%s ORDER BY date DESC,id DESC", (user_id,))
    subjects = get_df("SELECT * FROM subjects WHERE user_id=%s ORDER BY name", (user_id,))
    events = get_df("SELECT * FROM events WHERE user_id=%s ORDER BY date", (user_id,))

    debts = df[df.record_type == "Долг"] if not df.empty else pd.DataFrame()
    active_debts = len(debts[debts.status != "Выполнено"]) if not debts.empty else 0
    total_hours = float(df.hours.fillna(0).sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📝 Записей", len(df))
    c2.metric("📚 Предметов", len(subjects))
    c3.metric("⚠️ Активных долгов", active_debts)
    c4.metric("⏱️ Часов", f"{total_hours:.1f}")

    if subjects.empty:
        st.info("Пока нет предметов. Добавь первый предмет в разделе «📚 Предметы».")
        return

    st.divider()
    st.subheader("📚 По предметам")
    for _, subj in subjects.iterrows():
        subject_name = subj["name"]
        subject_df = df[df.subject == subject_name]
        grades = subject_df.loc[subject_df.record_type == "Оценка", "grade"].dropna()
        hours = subject_df.hours.dropna()
        subject_debts = subject_df[subject_df.record_type == "Долг"]
        active = subject_debts[subject_debts.status != "Выполнено"]

        st.markdown(f"### 📚 {subject_name}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("⭐ Средний балл", f"{grades.mean():.1f}" if not grades.empty else "—", f"{len(grades)} оценок")
        m2.metric("⏱️ Часы", f"{hours.sum():.1f}" if not hours.empty else "—", f"{len(hours)} записей")
        m3.metric("⚠️ Долги", len(active), f"из {len(subject_debts)}")
        m4.metric("📝 Всего", len(subject_df))
        for _, debt in active.iterrows():
            st.markdown(f"- ⏳ **{debt['topic'] or 'Без названия'}** — {debt['date']}")

    if not df.empty:
        st.divider()
        left, right = st.columns(2)
        with left:
            grades_df = df[(df.record_type == "Оценка") & df.grade.notna()]
            if not grades_df.empty:
                chart = grades_df.groupby("subject", as_index=False).grade.mean()
                st.plotly_chart(
                    px.bar(chart, x="subject", y="grade", title="Средний балл по предметам",
                           labels={"subject": "Предмет", "grade": "Средний балл"}),
                    use_container_width=True,
                )
        with right:
            hours_df = df[df.hours.notna()]
            if not hours_df.empty:
                chart = hours_df.groupby("subject", as_index=False).hours.sum()
                st.plotly_chart(
                    px.pie(chart, values="hours", names="subject", title="Распределение времени"),
                    use_container_width=True,
                )

    if not events.empty:
        st.divider()
        st.subheader("📅 Ближайшие события")
        upcoming = events[events.date >= date.today().isoformat()].head(5)
        if upcoming.empty:
            st.caption("Ближайших событий нет.")
        else:
            for _, event in upcoming.iterrows():
                st.markdown(f"**{event['date']}** — {event['title']}")
                if event["description"]:
                    st.caption(event["description"])


# ============================================================
# RECORDS
# ============================================================

def show_new_record():
    st.title("✍️ Новая запись")
    subjects = get_df("SELECT name FROM subjects WHERE user_id=%s ORDER BY name", (uid(),))
    if subjects.empty:
        st.warning("Сначала добавь хотя бы один предмет.")
        return

    record_type = st.radio("Тип записи", ["Оценка", "Долг", "Время"], horizontal=True)
    with st.form("new_record"):
        c1, c2 = st.columns(2)
        with c1:
            record_date = st.date_input("Дата", date.today())
            subject = st.selectbox("Предмет", subjects["name"].tolist())
            topic = st.text_input("Тема", placeholder="Контрольная, глава 3, лабораторная...")
        with c2:
            grade = hours = status = None
            if record_type == "Оценка":
                grade = st.number_input("Оценка", 0.0, 100.0, 0.0, 0.5)
                hours = st.number_input("Затрачено часов", 0.0, 24.0, 0.0, 0.5)
            elif record_type == "Время":
                hours = st.number_input("Часы", 0.0, 24.0, 0.0, 0.5)
            else:
                status = st.selectbox("Статус", ["В процессе", "Выполнено"])
            comment = st.text_area("Комментарий")
        if st.form_submit_button("Сохранить", type="primary"):
            if record_type == "Долг" and not topic.strip():
                st.error("Для долга обязательно укажи тему.")
                return
            query(
                """INSERT INTO records
                (user_id,date,record_type,subject,topic,grade,hours,comment,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uid(), record_date.isoformat(), record_type, subject, topic.strip(), grade, hours, comment.strip(), status),
                write=True,
            )
            set_notice(record_success_message(record_type))
            st.rerun()


def show_records():
    st.title("📋 Все записи")
    df = get_df("SELECT * FROM records WHERE user_id=%s ORDER BY date DESC,id DESC", (uid(),))
    if df.empty:
        st.info("Записей пока нет.")
        return

    c1, c2, c3 = st.columns(3)
    type_filter = c1.multiselect("Тип", ["Оценка", "Долг", "Время"])
    subject_filter = c2.multiselect("Предмет", sorted(df.subject.dropna().unique().tolist()))
    status_filter = c3.multiselect("Статус", ["В процессе", "Выполнено"])

    filtered = df.copy()
    if type_filter:
        filtered = filtered[filtered.record_type.isin(type_filter)]
    if subject_filter:
        filtered = filtered[filtered.subject.isin(subject_filter)]
    if status_filter:
        filtered = filtered[filtered.status.isin(status_filter)]

    st.dataframe(
        filtered[["date", "record_type", "subject", "topic", "grade", "hours", "comment", "status"]],
        use_container_width=True,
        hide_index=True,
    )
    st.divider()

    for _, record in filtered.iterrows():
        icon = {"Оценка": "⭐", "Долг": "⚠️", "Время": "⏰"}.get(record.record_type, "📝")
        left, right = st.columns([5, 1])
        with left:
            st.markdown(f"{icon} **{record.subject}** — {record.topic or 'общее'} ({record.date})")
            details = []
            if pd.notna(record.grade): details.append(f"Оценка: {record.grade}")
            if pd.notna(record.hours): details.append(f"Часы: {record.hours}")
            if record.status: details.append(f"Статус: {record.status}")
            if record.comment: details.append(f"💬 {record.comment}")
            if details: st.caption(" · ".join(details))
        with right:
            if record.record_type == "Долг" and record.status != "Выполнено":
                if st.button("✅", key=f"complete_record_{record.id}"):
                    query("UPDATE records SET status='Выполнено' WHERE id=%s AND user_id=%s", (int(record.id), uid()), write=True)
                    st.rerun()
            if st.button("🗑️", key=f"delete_record_{record.id}"):
                query("DELETE FROM records WHERE id=%s AND user_id=%s", (int(record.id), uid()), write=True)
                st.rerun()


# ============================================================
# SUBJECTS / EVENTS
# ============================================================

def show_subjects():
    st.title("📚 Предметы")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Добавить предмет")
        with st.form("add_subject"):
            name = st.text_input("Название")
            color = st.color_picker("Цвет", "#3b82f6")
            if st.form_submit_button("Добавить", type="primary"):
                name = name.strip()
                if not name:
                    st.error("Название не может быть пустым.")
                else:
                    try:
                        query("INSERT INTO subjects (user_id,name,color) VALUES (%s,%s,%s)", (uid(), name, color), write=True)
                        set_notice("📚 Предмет добавлен!")
                        st.rerun()
                    except IntegrityError:
                        st.error("Такой предмет уже существует.")
    with c2:
        st.subheader("Мои предметы")
        subjects = get_df("SELECT * FROM subjects WHERE user_id=%s ORDER BY name", (uid(),))
        if subjects.empty:
            st.caption("Предметов пока нет.")
            return
        for _, subject in subjects.iterrows():
            left, right = st.columns([5, 1])
            with left:
                st.markdown(f"**{subject['name']}**")
            with right:
                if st.button("🗑️", key=f"delete_subject_{subject.id}"):
                    count = query(
                        "SELECT COUNT(*) FROM records WHERE user_id=%s AND subject=%s",
                        (uid(), subject.name), fetchone=True,
                    )[0]
                    if count:
                        st.error("Нельзя удалить предмет, пока у него есть записи.")
                    else:
                        query("DELETE FROM subjects WHERE id=%s AND user_id=%s", (int(subject.id), uid()), write=True)
                        st.rerun()


def show_events():
    st.title("📅 События")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Добавить событие")
        with st.form("add_event"):
            event_date = st.date_input("Дата", date.today())
            title = st.text_input("Название")
            description = st.text_area("Описание")
            color = st.color_picker("Цвет", "#3b82f6")
            if st.form_submit_button("Добавить", type="primary"):
                title = title.strip()
                if not title:
                    st.error("Название не может быть пустым.")
                else:
                    query(
                        "INSERT INTO events (user_id,date,title,description,color) VALUES (%s,%s,%s,%s,%s)",
                        (uid(), event_date.isoformat(), title, description.strip(), color), write=True,
                    )
                    set_notice("📅 Событие добавлено!")
                    st.rerun()
    with c2:
        st.subheader("Мои события")
        events = get_df("SELECT * FROM events WHERE user_id=%s ORDER BY date DESC,id DESC", (uid(),))
        if events.empty:
            st.caption("Событий пока нет.")
            return
        for _, event in events.iterrows():
            left, right = st.columns([5, 1])
            with left:
                st.markdown(f"**{event.date} — {event.title}**")
                if event.description:
                    st.caption(event.description)
            with right:
                if st.button("🗑️", key=f"delete_event_{event.id}"):
                    query("DELETE FROM events WHERE id=%s AND user_id=%s", (int(event.id), uid()), write=True)
                    st.rerun()


# ============================================================
# SETTINGS / USERS
# ============================================================

def show_settings():
    st.title("⚙️ Настройки")
    st.subheader("🔐 Смена пароля")
    with st.form("change_password"):
        old = st.text_input("Текущий пароль", type="password")
        new = st.text_input("Новый пароль", type="password")
        new2 = st.text_input("Повтори новый пароль", type="password")
        if st.form_submit_button("Изменить пароль", type="primary"):
            user = query("SELECT password FROM users WHERE id=%s", (uid(),), fetchone=True)
            if not user or not verify_password(old, user[0]):
                st.error("Текущий пароль указан неверно.")
            elif len(new) < 8:
                st.error("Новый пароль должен содержать минимум 8 символов.")
            elif new != new2:
                st.error("Новые пароли не совпадают.")
            else:
                query("UPDATE users SET password=%s WHERE id=%s", (hash_password(new), uid()), write=True)
                st.success("Пароль изменён.")


def show_users():
    if not admin():
        st.error("Доступ запрещён.")
        return
    st.title("👥 Пользователи")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Создать пользователя")
        with st.form("add_user"):
            login = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            make_admin = st.checkbox("Администратор")
            if st.form_submit_button("Создать", type="primary"):
                login = login.strip()
                if len(login) < 3:
                    st.error("Логин должен содержать минимум 3 символа.")
                elif len(password) < 8:
                    st.error("Пароль должен содержать минимум 8 символов.")
                else:
                    try:
                        query(
                            "INSERT INTO users (username,password,created_at,is_admin) VALUES (%s,%s,%s,%s)",
                            (login, hash_password(password), datetime.now().strftime("%Y-%m-%d"), bool(make_admin)),
                            write=True,
                        )
                        set_notice("👤 Пользователь создан!")
                        st.rerun()
                    except IntegrityError:
                        st.error("Такой логин уже существует.")
    with c2:
        st.subheader("Пользователи")
        users = get_df("SELECT id,username,created_at,is_admin FROM users ORDER BY username")
        for _, user in users.iterrows():
            left, right = st.columns([5, 1])
            with left:
                role = "👑 Админ" if bool(user.is_admin) else "👤 Пользователь"
                st.markdown(f"**{user.username}** — {role}")
                st.caption(f"Создан: {user.created_at}")
            with right:
                if int(user.id) != int(uid()):
                    if st.button("🗑️", key=f"delete_user_{user.id}"):
                        query("DELETE FROM users WHERE id=%s", (int(user.id),), write=True)
                        st.rerun()


# ============================================================
# APP
# ============================================================

try:
    init_db()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        user_count = query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        if user_count == 0:
            show_first_setup()
        else:
            show_login()
    else:
        menu = ["📊 Главная", "✍️ Новая запись", "📚 Предметы", "📅 События", "📋 Записи", "⚙️ Настройки"]
        if admin():
            menu.append("👥 Пользователи")
        menu.append("🚪 Выйти")

        if st.session_state.get("page") not in menu:
            st.session_state.page = "📊 Главная"

        page = st.sidebar.radio("Меню", menu, key="page")
        st.sidebar.divider()
        st.sidebar.caption(f"👤 {username()}")

        if page == "🚪 Выйти": logout()
        elif page == "📊 Главная": show_dashboard()
        elif page == "✍️ Новая запись": show_new_record()
        elif page == "📚 Предметы": show_subjects()
        elif page == "📅 События": show_events()
        elif page == "📋 Записи": show_records()
        elif page == "⚙️ Настройки": show_settings()
        elif page == "👥 Пользователи": show_users()

except Exception:
    st.error("Не удалось запустить дневник. Попробуйте обновить страницу.")
