import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3

st.set_page_config(page_title="Дневник", page_icon="", layout="wide")

# === БАЗА ДАННЫХ ===
def init_db():
    conn = sqlite3.connect('study.db')
    c = conn.cursor()
    tables = [
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, created_at TEXT, is_admin INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, color TEXT, UNIQUE(user_id, name))",
        "CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, record_type TEXT DEFAULT 'Оценка', subject TEXT, topic TEXT, grade REAL, hours REAL, comment TEXT, status TEXT)",
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, title TEXT, description TEXT, color TEXT)"
    ]
    for t in tables:
        c.execute(t)
    c.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO users VALUES (1, ?, ?, ?, 1)', ('admin', 'admin', datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def db_query(sql, params=None, fetch=False):
    conn = sqlite3.connect('study.db')
    c = conn.cursor()
    if params:
        c.execute(sql, params)
    else:
        c.execute(sql)
    if fetch:
        result = c.fetchall() if sql.strip().upper().startswith('SELECT') else None
        conn.close()
        return result
    conn.commit()
    conn.close()

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_df(sql, params=None):
    conn = sqlite3.connect('study.db')
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

def card(title, color, metrics):
    st.markdown(f"<div style='padding:15px;margin:10px 0;border-radius:10px;background:{color}15;border-left:5px solid {color}'><h3 style='margin:0'>📚 {title}</h3></div>", unsafe_allow_html=True)
    cols = st.columns(len(metrics))
    for i, (label, val, delta) in enumerate(metrics):
        cols[i].metric(label, val, delta)

# === ИНИЦИАЛИЗАЦИЯ ===
init_db()
for key in ['logged_in', 'user_id', 'username', 'is_admin', 'page']:
    if key not in st.session_state:
        st.session_state[key] = False if key == 'logged_in' else None if key in ['user_id', 'username'] else False if key == 'is_admin' else ' Главная'

# === АВТОРИЗАЦИЯ ===
if not st.session_state.logged_in:
    st.title("📚 Дневник Успеваемости")
    username = st.text_input("👤 Логин")
    password = st.text_input("🔒 Пароль", type="password")
    if st.button("Войти", type="primary", use_container_width=True):
        user = db_query('SELECT id, is_admin FROM users WHERE username = ? AND password = ?', (username, password), fetch=True)
        if user:
            st.session_state.update({'logged_in': True, 'user_id': user[0][0], 'username': username, 'is_admin': bool(user[0][1])})
            st.rerun()
        else:
            st.error("❌ Неверный логин или пароль")
else:
    # === МЕНЮ ===
    pages = ["📊 Главная", "➕ Запись", "📚 Предметы", "📅 События", "📋 Записи"]
    if st.session_state.is_admin:
        pages.append("👥 Пользователи")
    pages.append(" Выход")
    
    page = st.sidebar.selectbox("Меню", pages, index=pages.index(st.session_state.page) if st.session_state.page in pages else 0)
    st.session_state.page = page
    
    if page == "🚪 Выход":
        st.session_state.clear()
        st.rerun()
    
    # === ГЛАВНАЯ ===
    elif page == "📊 Главная":
        st.title(f"👋 Привет, {st.session_state.username}!")
        df = get_df("SELECT * FROM records WHERE user_id = ?", (st.session_state.user_id,))
        subjects = get_df("SELECT * FROM subjects WHERE user_id = ?", (st.session_state.user_id,))
        
        if df.empty or subjects.empty:
            st.info("📭 Добавь предметы и записи!")
        else:
            debts = df[df['record_type'] == 'Долг']
            st.columns(3)[0].metric("📊 Записей", len(df))
            st.columns(3)[1].metric("📚 Предметов", len(subjects))
            st.columns(3)[2].metric("⚠️ Долги", f"{len(debts[debts['status'] != 'Выполнено'])} из {len(debts)}")
            
            for _, subj in subjects.iterrows():
                s = df[df['subject'] == subj['name']]
                if s.empty:
                    continue
                g = s[s['record_type'] == 'Оценка']['grade'].dropna()
                h = s[s['record_type'] == 'Время']['hours'].dropna()
                d = s[s['record_type'] == 'Долг']
                card(subj['name'], subj['color'], [
                    ("⭐ Балл", f"{g.mean():.1f}" if not g.empty else "—", f"{len(g)} оценок"),
                    ("⏰ Часы", f"{h.sum():.1f}" if not h.empty else "—", f"{len(h)} записей"),
                    ("⚠️ Долги", f"{len(d[d['status'] != 'Выполнено'])}", f"из {len(d)}"),
                    (" Всего", len(s), None)
                ])
                if not d.empty:
                    for _, debt in d.iterrows():
                        st.markdown(f"- {'✅' if debt['status'] == 'Выполнено' else '⏳'} **{debt['topic']}** ({debt['date']}) - {debt['status']}")
            
            col1, col2 = st.columns(2)
            with col1:
                g_df = df[df['record_type'] == 'Оценка']
                if not g_df.empty:
                    st.plotly_chart(px.bar(g_df.groupby('subject')['grade'].mean().reset_index(), x='subject', y='grade', color='grade'), use_container_width=True)
            with col2:
                h_df = df[df['record_type'] == 'Время']
                if not h_df.empty:
                    st.plotly_chart(px.pie(h_df.groupby('subject')['hours'].sum().reset_index(), values='hours', names='subject'), use_container_width=True)
    
    # === ДОБАВИТЬ ЗАПИСЬ ===
    elif page == "➕ Запись":
        st.title("➕ Новая запись")
        subjects = get_df("SELECT name FROM subjects WHERE user_id = ?", (st.session_state.user_id,))
        if subjects.empty:
            st.warning("Сначала добавь предметы!")
        else:
            rtype = st.radio("Тип", ["Оценка", "Долг", "Время"], horizontal=True)
            with st.form("f"):
                c1, c2 = st.columns(2)
                with c1:
                    date = st.date_input("📅", datetime.now())
                    subj = st.selectbox("📚 Предмет", subjects['name'].tolist())
                    topic = st.text_input("📝 Тема", value="" if rtype == "Время" else None)
                with c2:
                    grade = st.number_input("⭐ Оценка", 0.0, 100.0, value=None) if rtype == "Оценка" else None
                    hours = st.number_input("⏱️ Часы", 0.0, 24.0, value=None) if rtype in ["Оценка", "Время"] else None
                    comment = st.text_area("💬")
                    status = st.selectbox("Статус", ["В процессе", "Выполнено"]) if rtype == "Долг" else None
                
                if st.form_submit_button("💾", type="primary", use_container_width=True):
                    if subj and (topic or rtype == "Время"):
                        db_query("INSERT INTO records (user_id, date, record_type, subject, topic, grade, hours, comment, status) VALUES (?,?,?,?,?,?,?,?,?)",
                                (st.session_state.user_id, date.strftime("%Y-%m-%d"), rtype, subj, topic, grade, hours, comment, status))
                        st.success("✅ Добавлено!")
                    else:
                        st.error("️ Заполни поля!")
    
    # === ПРЕДМЕТЫ ===
    elif page == "📚 Предметы":
        st.title("📚 Предметы")
        c1, c2 = st.columns(2)
        with c1:
            with st.form("add_subj"):
                name = st.text_input("Название")
                color = st.color_picker("Цвет", "#3b82f6")
                if st.form_submit_button("Добавить", type="primary", use_container_width=True):
                    if name:
                        try:
                            db_query("INSERT INTO subjects (user_id, name, color) VALUES (?,?,?)", (st.session_state.user_id, name, color))
                            st.success("✅ Добавлено!")
                            st.rerun()
                        except:
                            st.error("❌ Уже есть!")
        with c2:
            subjects = get_df("SELECT * FROM subjects WHERE user_id = ?", (st.session_state.user_id,))
            if not subjects.empty:
                for _, s in subjects.iterrows():
                    cd, cn = st.columns([1, 5])
                    with cd:
                        if st.button("🗑️", key=f"ds{s['id']}"):
                            db_query("DELETE FROM subjects WHERE id = ?", (s['id'],))
                            st.rerun()
                    with cn:
                        st.markdown(f"<div style='padding:8px;margin:5px 0;border-radius:6px;background:{s['color']}20;border-left:4px solid {s['color']}'><strong>{s['name']}</strong></div>", unsafe_allow_html=True)
    
    # === СОБЫТИЯ ===
    elif page == " События":
        st.title(" События")
        c1, c2 = st.columns(2)
        with c1:
            with st.form("add_ev"):
                date = st.date_input("📅", datetime.now())
                title = st.text_input("📝 Название")
                desc = st.text_area("💬 Описание")
                color = st.color_picker("🎨", "#3b82f6")
                if st.form_submit_button("Добавить", type="primary", use_container_width=True):
                    if title:
                        db_query("INSERT INTO events (user_id, date, title, description, color) VALUES (?,?,?,?,?)",
                                (st.session_state.user_id, date.strftime("%Y-%m-%d"), title, desc, color))
                        st.success("✅ Добавлено!")
        with c2:
            events = get_df("SELECT * FROM events WHERE user_id = ?", (st.session_state.user_id,))
            if not events.empty:
                for _, e in events.iterrows():
                    ce, cd = st.columns([5, 1])
                    with ce:
                        st.markdown(f"<div style='padding:8px;margin:5px 0;border-radius:6px;background:{e['color']}20;border-left:4px solid {e['color']}'><strong>{e['date']}</strong> - {e['title']}<br><small>{e['description']}</small></div>", unsafe_allow_html=True)
                    with cd:
                        if st.button("🗑️", key=f"de{e['id']}"):
                            db_query("DELETE FROM events WHERE id = ?", (e['id'],))
                            st.rerun()
    
    # === ВСЕ ЗАПИСИ ===
    elif page == "📋 Записи":
        st.title(" Все записи")
        df = get_df("SELECT * FROM records WHERE user_id = ?", (st.session_state.user_id,))
        if df.empty:
            st.info("📭 Нет записей")
        else:
            c1, c2, c3 = st.columns(3)
            tf = c1.multiselect("Тип", ["Оценка", "Долг", "Время"])
            sf = c2.multiselect("Предмет", df['subject'].unique())
            stf = c3.multiselect("Статус", ["В процессе", "Выполнено"])
            
            fdf = df.copy()
            if tf: fdf = fdf[fdf['record_type'].isin(tf)]
            if sf: fdf = fdf[fdf['subject'].isin(sf)]
            if stf: fdf = fdf[fdf['status'].isin(stf)]
            
            st.dataframe(fdf.sort_values('date', ascending=False), use_container_width=True, hide_index=True)
            
            for _, r in fdf.iterrows():
                cr, ca = st.columns([4, 1])
                with cr:
                    icon = {"Оценка": "⭐", "Долг": "⚠️", "Время": "⏰"}.get(r['record_type'], "📝")
                    topic = f": {r['topic']}" if r.get('topic') else " (общее)"
                    st.markdown(f"{icon} **{r['subject']}**{topic} ({r['date']})")
                with ca:
                    if r['record_type'] == "Долг" and r['status'] != "Выполнено":
                        if st.button("✅", key=f"ok{r['id']}"):
                            db_query("UPDATE records SET status = 'Выполнено' WHERE id = ?", (r['id'],))
                            st.rerun()
                    if st.button("🗑️", key=f"dr{r['id']}"):
                        db_query("DELETE FROM records WHERE id = ?", (r['id'],))
                        st.rerun()
    
    # === ПОЛЬЗОВАТЕЛИ ===
    elif page == "👥 Пользователи" and st.session_state.is_admin:
        st.title("👥 Пользователи")
        c1, c2 = st.columns(2)
        with c1:
            with st.form("add_user"):
                nu = st.text_input("Логин")
                np_ = st.text_input("Пароль", type="password")
                ia = st.checkbox("Админ")
                if st.form_submit_button("Создать", type="primary", use_container_width=True):
                    if nu and np_:
                        try:
                            db_query("INSERT INTO users (username, password, created_at, is_admin) VALUES (?,?,?,?)",
                                    (nu, np_, datetime.now().strftime("%Y-%m-%d"), 1 if ia else 0))
                            st.success("✅ Создан!")
                        except:
                            st.error("❌ Уже есть!")
        with c2:
            users = get_df("SELECT * FROM users")
            if not users.empty:
                for _, u in users.iterrows():
                    cu, cd = st.columns([5, 1])
                    with cu:
                        role = "👑 Админ" if u['is_admin'] else "👤 Юзер"
                        st.markdown(f"<div style='padding:10px;margin:5px 0;border-radius:6px;background:#e0f2fe;border-left:4px solid #0284c7'><strong style='color:#0c4a6e'>{u['username']}</strong> <span style='color:#0369a1'>{role}</span><br><small style='color:#075985'>{u['created_at']}</small></div>", unsafe_allow_html=True)
                    with cd:
                        if u['id'] != st.session_state.user_id:
                            if st.button("🗑️", key=f"du{u['id']}"):
                                db_query("DELETE FROM users WHERE id = ?", (u['id'],))
                                db_query("DELETE FROM subjects WHERE user_id = ?", (u['id'],))
                                db_query("DELETE FROM records WHERE user_id = ?", (u['id'],))
                                db_query("DELETE FROM events WHERE user_id = ?", (u['id'],))
                                st.rerun()
