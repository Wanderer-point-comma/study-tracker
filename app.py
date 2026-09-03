import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3

st.set_page_config(
    page_title="Дневник Успеваемости",
    page_icon="",
    layout="wide"
)

def init_db():
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        username TEXT UNIQUE, 
        password TEXT,
        created_at TEXT, 
        is_admin INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        name TEXT,
        color TEXT, 
        UNIQUE(user_id, name))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        date TEXT,
        subject TEXT, 
        topic TEXT, 
        grade REAL, 
        hours REAL, 
        comment TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        date TEXT,
        title TEXT, 
        description TEXT, 
        color TEXT)''')
    
    try:
        c.execute("ALTER TABLE records ADD COLUMN record_type TEXT DEFAULT 'Оценка'")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE records ADD COLUMN status TEXT")
    except:
        pass
    
    c.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO users (username, password, created_at, is_admin) VALUES (?, ?, ?, 1)',
                 ('admin', 'admin', datetime.now().strftime("%Y-%m-%d")))
    
    conn.commit()
    conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute('SELECT id, is_admin FROM users WHERE username = ? AND password = ?',
             (username, password))
    user = c.fetchone()
    conn.close()
    return user

def create_user(admin_id, username, password, is_admin=0):
    conn = sqlite3.connect('study_tracker.db')
    try:
        conn.execute('INSERT INTO users (username, password, created_at, is_admin) VALUES (?, ?, ?, ?)',
                    (username, password, datetime.now().strftime("%Y-%m-%d"), is_admin))
        conn.commit()
        conn.close()
        return True, "Пользователь создан!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Такой логин уже существует"

def get_users():
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT id, username, is_admin, created_at FROM users", conn)
    conn.close()
    return df

def delete_user(user_id):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.execute('DELETE FROM subjects WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM records WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM events WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def add_subject(user_id, name, color):
    conn = sqlite3.connect('study_tracker.db')
    try:
        conn.execute('INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)',
                    (user_id, name, color))
        conn.commit()
        conn.close()
        return True, "Предмет добавлен!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Такой предмет уже существует"

def get_subjects(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM subjects WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def delete_subject(user_id, subject_name):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('DELETE FROM subjects WHERE user_id = ? AND name = ?', (user_id, subject_name))
    conn.commit()
    conn.close()

def add_record(user_id, date, record_type, subject, topic, grade, hours, comment, status=None):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('''INSERT INTO records (user_id, date, record_type, subject, topic, grade, hours, comment, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (user_id, date, record_type, subject, topic, grade, hours, comment, status))
    conn.commit()
    conn.close()

def get_records(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM records WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    
    # Гарантируем наличие всех колонок
    if 'record_type' not in df.columns:
        df['record_type'] = 'Оценка'
    if 'status' not in df.columns:
        df['status'] = None
    if 'topic' not in df.columns:
        df['topic'] = ''
        
    # Заполняем NaN значения
    df['record_type'] = df['record_type'].fillna('Оценка')
    df['status'] = df['status'].fillna('')
    df['topic'] = df['topic'].fillna('')
    
    return df

def update_record_status(record_id, status):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('UPDATE records SET status = ? WHERE id = ?', (status, record_id))
    conn.commit()
    conn.close()

def delete_record(record_id):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('DELETE FROM records WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()

def add_event(user_id, date, title, description, color):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('''INSERT INTO events (user_id, date, title, description, color)
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, date, title, description, color))
    conn.commit()
    conn.close()

def get_events(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM events WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def delete_event(event_id):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()

init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

if not st.session_state.logged_in:
    st.title("📚 Дневник Успеваемости")
    st.markdown("Войдите в систему")
    st.markdown("---")
    
    username = st.text_input(" Логин")
    password = st.text_input("🔒 Пароль", type="password")
    
    if st.button("Войти", type="primary", use_container_width=True):
        user = verify_user(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_id = user[0]
            st.session_state.username = username
            st.session_state.is_admin = bool(user[1])
            st.rerun()
        else:
            st.error("❌ Неверный логин или пароль")
else:
    menu_items = [" Главная", "➕ Добавить запись", " Предметы", "📅 События", "📋 Все записи"]
    
    if st.session_state.is_admin:
        menu_items.append("👥 Управление пользователями")
    
    menu_items.append("🚪 Выйти")
    
    page = st.sidebar.selectbox("Меню", menu_items)
    
    if page == "🚪 Выйти":
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.is_admin = False
        st.rerun()
    
    elif page == " Главная":
        st.title(f" Привет, {st.session_state.username}!")
        st.markdown("---")
        
        df = get_records(st.session_state.user_id)
        subjects_df = get_subjects(st.session_state.user_id)
        
        if not df.empty and not subjects_df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 Всего записей", len(df))
            col2.metric("📚 Предметов", len(subjects_df))
            
            total_debts = len(df[df['record_type'] == 'Долг'])
            pending_debts = len(df[(df['record_type'] == 'Долг') & (df['status'] != 'Выполнено')])
            col3.metric("⚠️ Долги", f"{pending_debts} из {total_debts}")
            
            st.markdown("---")
            st.subheader("📊 Статистика по предметам")
            
            for _, subject in subjects_df.iterrows():
                subj_name = subject['name']
                subj_color = subject['color']
                subj_records = df[df['subject'] == subj_name]
                
                if subj_records.empty:
                    continue
                
                grades = subj_records[subj_records['record_type'] == 'Оценка']['grade'].dropna()
                avg_grade = f"{grades.mean():.1f}" if not grades.empty else "—"
                count_grades = len(grades)
                
                hours = subj_records[subj_records['record_type'] == 'Время']['hours'].dropna()
                total_hours = f"{hours.sum():.1f}" if not hours.empty else "—"
                count_hours = len(hours)
                
                debts = subj_records[subj_records['record_type'] == 'Долг']
                pending_debts_subj = len(debts[debts['status'] != 'Выполнено'])
                total_debts_subj = len(debts)
                
                st.markdown(f"""
                <div style='padding: 15px; margin: 10px 0; border-radius: 10px; 
                            background-color: {subj_color}15; 
                            border-left: 5px solid {subj_color};'>
                    <h3 style='margin: 0 0 10px 0; color: #333;'>📚 {subj_name}</h3>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("⭐ Средний балл", avg_grade, delta=f"{count_grades} оценок")
                col2.metric("⏰ Всего часов", total_hours, delta=f"{count_hours} записей")
                col3.metric("⚠️ Долги", f"{pending_debts_subj}", delta=f"из {total_debts_subj}")
                col4.metric(" Всего записей", len(subj_records))
                
                if not debts.empty:
                    st.markdown("**Долги:**")
                    for _, debt in debts.iterrows():
                        status = debt.get('status') if pd.notna(debt.get('status')) else "В процессе"
                        status_icon = "✅" if status == "Выполнено" else "⏳"
                        st.markdown(f"- {status_icon} **{debt['topic']}** ({debt['date']}) - {status}")
                
                st.markdown("---")
            
            st.subheader("📈 Графики")
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Средний балл по предметам")
                grades_df = df[df['record_type'] == 'Оценка']
                if not grades_df.empty:
                    subject_avg = grades_df.groupby('subject')['grade'].mean().reset_index()
                    fig = px.bar(subject_avg, x='subject', y='grade', color='grade',
                                color_continuous_scale='Viridis')
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Нет оценок")
            
            with col2:
                st.subheader("Время по предметам")
                hours_df = df[df['record_type'] == 'Время']
                if not hours_df.empty:
                    subject_hours = hours_df.groupby('subject')['hours'].sum().reset_index()
                    fig = px.pie(subject_hours, values='hours', names='subject')
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Нет данных о времени")
        
        elif df.empty:
            st.info("📭 Пока нет записей. Добавьте первую запись!")
        else:
            st.warning("⚠️ Сначала добавьте предметы в разделе ' Предметы'")
    
    elif page == "➕ Добавить запись":
        st.title("➕ Добавить запись")
        
        subjects_df = get_subjects(st.session_state.user_id)
        
        if subjects_df.empty:
            st.warning("️ Сначала добавьте предметы в разделе '📚 Предметы'")
        else:
            record_type = st.radio("Тип записи", ["Оценка", "Долг", "Время"], horizontal=True)
            
            with st.form("record_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    date = st.date_input("📅 Дата", datetime.now())
                    subject = st.selectbox(" Предмет", subjects_df['name'].tolist())
                    
                    if record_type == "Время":
                        topic = st.text_input("📝 Тема (необязательно)", value="")
                    else:
                        topic = st.text_input(" Тема")
                
                with col2:
                    if record_type == "Оценка":
                        grade = st.number_input("⭐ Оценка", 0.0, 100.0, value=None)
                        hours = st.number_input("⏱️ Часы (необязательно)", 0.0, 24.0, value=None)
                    elif record_type == "Долг":
                        grade = None
                        hours = None
                        st.info("Для долга оценка и время не требуются")
                    else:
                        grade = None
                        hours = st.number_input("⏱️ Часы", 0.0, 24.0, value=None)
                    
                    comment = st.text_area("💬 Комментарий")
                
                status = None
                if record_type == "Долг":
                    status = st.selectbox("Статус", ["В процессе", "Выполнено"])
                
                submitted = st.form_submit_button("💾 Сохранить", type="primary", use_container_width=True)
                
                if submitted:
                    is_valid = True
                    error_msg = "⚠️ "
                    
                    if not subject:
                        is_valid = False
                        error_msg += "Выберите предмет. "
                    
                    if record_type in ["Оценка", "Долг"] and not topic:
                        is_valid = False
                        error_msg += "Введите тему. "
                        
                    if record_type == "Оценка" and grade is None:
                        is_valid = False
                        error_msg += "Введите оценку. "
                        
                    if record_type == "Время" and hours is None:
                        is_valid = False
                        error_msg += "Введите количество часов. "

                    if is_valid:
                        add_record(st.session_state.user_id, 
                                  date.strftime("%Y-%m-%d"), record_type, subject, topic,
                                  grade, hours, comment, status)
                        st.success("✅ Запись добавлена!")
                    else:
                        st.error(error_msg)
    
    elif page == "📚 Предметы":
        st.title("📚 Управление предметами")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("➕ Добавить предмет")
            with st.form("subject_form"):
                name = st.text_input("Название предмета")
                color = st.color_picker("Цвет", "#3b82f6")
                if st.form_submit_button("Добавить", type="primary", use_container_width=True):
                    if name:
                        success, msg = add_subject(st.session_state.user_id, name, color)
                        if success:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")
                    else:
                        st.warning("⚠️ Введите название")
        
        with col2:
            st.subheader("📋 Список предметов")
            subjects_df = get_subjects(st.session_state.user_id)
            if not subjects_df.empty:
                for _, subj in subjects_df.iterrows():
                    col_del, col_name = st.columns([1, 5])
                    with col_del:
                        if st.button("🗑️", key=f"del_subj_{subj['id']}"):
                            delete_subject(st.session_state.user_id, subj['name'])
                            st.success("Предмет удалён")
                    with col_name:
                        st.markdown(f"""
                        <div style='padding: 8px; margin: 5px 0; border-radius: 6px; 
                                    background-color: {subj['color']}20; 
                                    border-left: 4px solid {subj['color']};'>
                            <strong style='color: #333;'>{subj['name']}</strong>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("Нет предметов")
    
    elif page == "📅 События":
        st.title("📅 События")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("➕ Добавить событие")
            with st.form("event_form"):
                date = st.date_input("📅 Дата", datetime.now())
                title = st.text_input("📝 Название")
                desc = st.text_area("💬 Описание")
                color = st.color_picker("🎨 Цвет", "#3b82f6")
                if st.form_submit_button("Добавить", type="primary", use_container_width=True):
                    if title:
                        add_event(st.session_state.user_id, 
                                 date.strftime("%Y-%m-%d"), title, desc, color)
                        st.success("✅ Событие добавлено!")
                    else:
                        st.warning("️ Введите название")
        
        with col2:
            st.subheader("📋 Список событий")
            events_df = get_events(st.session_state.user_id)
            if not events_df.empty:
                for _, event in events_df.iterrows():
                    col_ev, col_del = st.columns([5, 1])
                    with col_ev:
                        st.markdown(f"""
                        <div style='padding: 8px; margin: 5px 0; border-radius: 6px; 
                                    background-color: {event['color']}20; 
                                    border-left: 4px solid {event['color']};'>
                            <strong style='color: #333;'>{event['date']}</strong> - {event['title']}
                            <br><small style='color: #666;'>{event['description']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_del:
                        if st.button("🗑️", key=f"del_ev_{event['id']}"):
                            delete_event(event['id'])
                            st.success("Событие удалено")
            else:
                st.info("Нет событий")
    
    elif page == " Все записи":
        st.title("📋 Все записи")
        
        df = get_records(st.session_state.user_id)
        
        if df.empty:
            st.info(" Записей пока нет")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                type_filter = st.multiselect("Тип", ["Оценка", "Долг", "Время"])
            with col2:
                subject_filter = st.multiselect("Предмет", df['subject'].unique())
            with col3:
                status_filter = st.multiselect("Статус", ["В процессе", "Выполнено"])
            
            filtered_df = df.copy()
            
            if type_filter:
                filtered_df = filtered_df[filtered_df['record_type'].isin(type_filter)]
            if subject_filter:
                filtered_df = filtered_df[filtered_df['subject'].isin(subject_filter)]
            if status_filter:
                filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]
            
            st.dataframe(filtered_df.sort_values('date', ascending=False), 
                        use_container_width=True, hide_index=True)
            
            st.subheader("Управление записями")
            for idx, record in filtered_df.iterrows():
                col_rec, col_act = st.columns([4, 1])
                with col_rec:
                    rtype = record.get('record_type', 'Оценка')
                    icon = "⭐" if rtype == "Оценка" else "️" if rtype == "Долг" else "⏰"
                    
                    topic_val = record.get('topic', '')
                    if pd.notna(topic_val) and topic_val:
                        topic_display = f": {topic_val}"
                    else:
                        topic_display = " (общее время)"
                    
                    st.markdown(f"{icon} **{record['subject']}**{topic_display} ({record['date']})")
                with col_act:
                    rtype = record.get('record_type', 'Оценка')
                    status = record.get('status', '')
                    if rtype == "Долг" and status != "Выполнено":
                        if st.button("✅", key=f"done_{record['id']}"):
                            update_record_status(record['id'], "Выполнено")
                            st.success("Долг выполнен!")
                    if st.button("🗑️", key=f"del_{record['id']}"):
                        delete_record(record['id'])
                        st.success("Запись удалена")
    
    elif page == "👥 Управление пользователями" and st.session_state.is_admin:
        st.title("👥 Управление пользователями")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(" Создать пользователя")
            with st.form("create_user_form"):
                new_username = st.text_input("Логин")
                new_password = st.text_input("Пароль", type="password")
                is_admin = st.checkbox("Сделать администратором")
                if st.form_submit_button("Создать", type="primary", use_container_width=True):
                    if new_username and new_password:
                        success, msg = create_user(st.session_state.user_id, 
                                                  new_username, new_password, 
                                                  1 if is_admin else 0)
                        if success:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f" {msg}")
                    else:
                        st.warning("⚠️ Заполните все поля")
        
        with col2:
            st.subheader("📋 Список пользователей")
            users_df = get_users()
            if not users_df.empty:
                for idx, user in users_df.iterrows():
                    role = "👑 Админ" if user['is_admin'] else " Пользователь"
                    col_user, col_del = st.columns([5, 1])
                    with col_user:
                        st.markdown(f"""
                        <div style='padding: 10px; margin: 5px 0; border-radius: 6px; 
                                    background-color: #e0f2fe; 
                                    border-left: 4px solid #0284c7;'>
                            <strong style='color: #0c4a6e;'>{user['username']}</strong> 
                            <span style='color: #0369a1;'>{role}</span>
                            <br><small style='color: #075985;'>Создан: {user['created_at']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_del:
                        if user['id'] != st.session_state.user_id:
                            if st.button("🗑️", key=f"del_user_{user['id']}"):
                                delete_user(user['id'])
                                st.success("Пользователь удалён")
            else:
                st.info("Нет пользователей кроме вас")
