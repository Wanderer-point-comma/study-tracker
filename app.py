import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sqlite3

st.set_page_config(
    page_title="📚 Мой Дневник Успеваемости",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .nav-divider {
        border-top: 2px solid #f0f0f0;
        margin: 15px 0;
    }
    .nav-section {
        font-size: 0.75em;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 10px 0 5px 0;
        font-weight: 600;
    }
    .admin-badge {
        background-color: #ef4444;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7em;
        margin-left: 5px;
    }
    .device-badge {
        background-color: #3b82f6;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7em;
        margin-left: 5px;
    }
</style>
""", unsafe_allow_html=True)

def init_db():
    """Создаёт таблицы и добавляет админа"""
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    
    # Удаляем ВСЕ таблицы для чистой установки
    c.execute("DROP TABLE IF EXISTS login_logs")
    c.execute("DROP TABLE IF EXISTS events")
    c.execute("DROP TABLE IF EXISTS subjects")
    c.execute("DROP TABLE IF EXISTS records")
    c.execute("DROP TABLE IF EXISTS devices")
    c.execute("DROP TABLE IF EXISTS users")
    
    # Создаём все таблицы с нуля
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            created_at TEXT,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_name TEXT,
            username TEXT UNIQUE,
            password TEXT,
            created_at TEXT,
            last_login TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            subject TEXT,
            topic TEXT,
            grade REAL,
            hours REAL,
            comment TEXT,
            created_by_device INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (created_by_device) REFERENCES devices(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            color TEXT,
            UNIQUE(user_id, name)
        )
    ''')
    
    c.execute('''
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            title TEXT,
            description TEXT,
            color TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_id INTEGER,
            device_name TEXT,
            login_time TEXT,
            ip_address TEXT,
            user_agent TEXT
        )
    ''')
    
    # Создаём админа
    c.execute('''
        INSERT INTO users (username, password, created_at, is_admin)
        VALUES (?, ?, ?, ?)
    ''', ('admin', 'admin', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1))
    
    print("✅ База данных создана. Логин: admin, Пароль: admin")
    
    conn.commit()
    conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    
    c.execute('SELECT id, password, is_admin FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    
    if user and user[1] == password:
        conn.close()
        return True, user[0], 'admin' if user[2] else 'user', None
    
    c.execute('SELECT id, user_id, password FROM devices WHERE username = ?', (username,))
    device = c.fetchone()
    
    if device and device[2] == password:
        c.execute('UPDATE devices SET last_login = ? WHERE id = ?', 
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), device[0]))
        conn.commit()
        conn.close()
        return True, device[1], 'device', device[0]
    
    conn.close()
    return False, None, None, None

def log_login(user_id, device_id, device_name, ip_address, user_agent):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO login_logs (user_id, device_id, device_name, login_time, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, device_id, device_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ip_address, user_agent))
    conn.commit()
    conn.close()

def update_user_credentials(user_id, new_username, new_password):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    try:
        c.execute('UPDATE users SET username = ?, password = ? WHERE id = ?', 
                 (new_username, new_password, user_id))
        conn.commit()
        conn.close()
        return True, "Данные обновлены!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Такой логин уже существует"

def add_record(user_id, date, subject, topic, grade, hours, comment, device_id=None):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO records (user_id, date, subject, topic, grade, hours, comment, created_by_device)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, date, subject, topic, grade, hours, comment, device_id))
    conn.commit()
    conn.close()

def get_records(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM records WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def add_device(user_id, device_name, username, password):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO devices (user_id, device_name, username, password, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, device_name, username, password, 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True, "Устройство добавлено!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Такой логин уже существует"

def get_devices(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM devices WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def delete_device(device_id, user_id):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute('DELETE FROM devices WHERE id = ? AND user_id = ?', (device_id, user_id))
    conn.commit()
    conn.close()

def get_login_logs(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query('''
        SELECT * FROM login_logs 
        WHERE user_id = ?
        ORDER BY login_time DESC
    ''', conn, params=(user_id,))
    conn.close()
    return df

def add_subject(user_id, name, color):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO subjects (user_id, name, color)
            VALUES (?, ?, ?)
        ''', (user_id, name, color))
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
    c = conn.cursor()
    c.execute('DELETE FROM subjects WHERE user_id = ? AND name = ?', (user_id, subject_name))
    conn.commit()
    conn.close()

def add_event(user_id, date, title, description, color):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO events (user_id, date, title, description, color)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, date, title, description, color))
    conn.commit()
    conn.close()

def get_events(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM events WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def delete_event(event_id):
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()

def get_all_tables():
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in c.fetchall()]
    conn.close()
    return tables

def get_table_data(table_name):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df

def execute_sql(query):
    conn = sqlite3.connect('study_tracker.db')
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return True, df
    except Exception as e:
        conn.close()
        return False, str(e)

init_db()

def login_page():
    st.markdown("<h1 style='text-align: center;'>📚 Дневник Успеваемости</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Войдите в систему</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    with st.form("login_form"):
        username = st.text_input("👤 Логин")
        password = st.text_input("🔒 Пароль", type="password")
        device_name = st.text_input("📱 Название устройства (необязательно)", 
                                    placeholder="Например: Мой телефон")
        submitted = st.form_submit_button("Войти", type="primary", use_container_width=True)
        
        if submitted:
            if username and password:
                success, user_id, user_type, device_id = verify_user(username, password)
                if success:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = user_id
                    st.session_state['username'] = username
                    st.session_state['user_type'] = user_type
                    st.session_state['device_id'] = device_id
                    st.session_state['current_menu'] = "📊 Дашборд"
                    
                    log_login(user_id, device_id, device_name or "Не указано", 
                             "127.0.0.1", "Browser")
                    
                    st.rerun()
                else:
                    st.error("❌ Неверный логин или пароль")
            else:
                st.warning("⚠️ Заполните все поля")

def logout():
    if st.sidebar.button("🚪 Выйти", use_container_width=True):
        for key in ['logged_in', 'user_id', 'username', 'user_type', 'device_id', 'current_menu']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def main_app():
    user_id = st.session_state['user_id']
    username = st.session_state['username']
    user_type = st.session_state.get('user_type', 'user')
    device_id = st.session_state.get('device_id')
    
    st.sidebar.markdown(f"### 👋 Привет, {username}!")
    
    if user_type == 'admin':
        st.sidebar.markdown('<span class="admin-badge">АДМИН</span>', unsafe_allow_html=True)
    elif user_type == 'device':
        st.sidebar.markdown('<span class="device-badge">УСТРОЙСТВО</span>', unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    
    menu_options = [
        "📊 Дашборд",
        "➕ Добавить запись",
        "📋 Все записи",
        "📚 Мои предметы",
        "📅 Календарь",
        "📈 Аналитика",
        "️ Настройки профиля"
    ]
    
    if user_type == 'admin':
        menu_options.extend([
            "📱 Устройства",
            "🗄️ База данных",
            "📜 Логи входов"
        ])
    
    if 'current_menu' not in st.session_state:
        st.session_state['current_menu'] = "📊 Дашборд"
    
    try:
        default_index = menu_options.index(st.session_state['current_menu'])
    except ValueError:
        default_index = 0
        st.session_state['current_menu'] = menu_options[0]
    
    selected_menu = st.sidebar.radio(
        "Навигация",
        menu_options,
        index=default_index,
        label_visibility="collapsed"
    )
    
    st.session_state['current_menu'] = selected_menu
    
    st.sidebar.markdown("---")
    logout()
    
    if selected_menu == "📊 Дашборд":
        st.header("📊 Общая статистика")
        
        df = get_records(user_id)
        
        if df.empty:
            st.warning("📭 Пока нет записей. Добавьте первую запись в разделе 'Добавить запись'!")
        else:
            col1, col2, col3, col4 = st.columns(4)
            
            total_records = len(df)
            avg_grade = df['grade'].mean()
            total_hours = df['hours'].sum()
            unique_subjects = df['subject'].nunique()
            
            col1.metric("Всего записей", total_records)
            col2.metric("Средний балл", f"{avg_grade:.2f}")
            col3.metric("Всего часов", f"{total_hours:.1f}")
            col4.metric("Предметов", unique_subjects)
            
            st.markdown("---")
            
            st.subheader("📅 Ближайшие события")
            events_df = get_events(user_id)
            
            if events_df.empty:
                st.info("📭 Событий пока нет")
            else:
                events_df['date'] = pd.to_datetime(events_df['date'])
                upcoming = events_df[events_df['date'] >= datetime.now()].sort_values('date').head(5)
                
                if upcoming.empty:
                    st.info(" Нет предстоящих событий")
                else:
                    for _, event in upcoming.iterrows():
                        st.markdown(f"""
                        <div style='padding: 8px; margin: 5px 0; border-radius: 6px; 
                                    background-color: {event['color']}15; 
                                    border-left: 3px solid {event['color']};'>
                            <strong>{event['date'].strftime('%d.%m.%Y')}</strong><br>
                            {event['title']}
                        </div>
                        """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(" Средний балл по предметам")
                subject_avg = df.groupby('subject')['grade'].mean().reset_index()
                fig_subject = px.bar(subject_avg, x='subject', y='grade', 
                                    color='grade', color_continuous_scale='Viridis')
                fig_subject.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_subject, use_container_width=True)
            
            with col2:
                st.subheader("⏰ Часов по предметам")
                subject_hours = df.groupby('subject')['hours'].sum().reset_index()
                fig_hours = px.pie(subject_hours, values='hours', names='subject',
                                  color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_hours.update_layout(height=400)
                st.plotly_chart(fig_hours, use_container_width=True)
            
            st.subheader("📈 Динамика успеваемости")
            df['date'] = pd.to_datetime(df['date'])
            df_sorted = df.sort_values('date')
            
            fig_timeline = px.line(df_sorted, x='date', y='grade', 
                                  color='subject', markers=True,
                                  title='Изменение оценок во времени')
            fig_timeline.update_layout(height=400, xaxis_title="Дата", yaxis_title="Оценка")
            st.plotly_chart(fig_timeline, use_container_width=True)
    
    elif selected_menu == " Добавить запись":
        st.header("➕ Добавить новую запись")
        
        subjects_df = get_subjects(user_id)
        
        if subjects_df.empty:
            st.warning("⚠️ Сначала добавьте предметы в разделе 'Мои предметы'")
        else:
            with st.form("add_record_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    date = st.date_input("📅 Дата", datetime.now())
                    subject_options = subjects_df['name'].tolist()
                    subject = st.selectbox("📚 Предмет", options=subject_options)
                    topic = st.text_input("📝 Тема", placeholder="Например: Интегралы")
                
                with col2:
                    grade = st.number_input("⭐ Оценка", min_value=0.0, max_value=100.0, step=0.5)
                    hours = st.number_input("⏱️ Часов потрачено", min_value=0.0, max_value=24.0, step=0.5)
                    comment = st.text_area("💬 Комментарий", placeholder="Что было сложно?")
                
                submitted = st.form_submit_button("💾 Сохранить запись", type="primary", use_container_width=True)
                
                if submitted:
                    if subject and topic:
                        add_record(user_id, date.strftime("%Y-%m-%d"), subject, 
                                  topic.capitalize(), grade, hours, comment, device_id)
                        st.success("✅ Запись успешно добавлена!")
                        st.balloons()
                    else:
                        st.error("⚠️ Пожалуйста, заполните все обязательные поля")
    
    elif selected_menu == " Все записи":
        st.header(" Все ваши записи")
        
        df = get_records(user_id)
        
        if df.empty:
            st.info("📭 Записей пока нет")
        else:
            col1, col2 = st.columns(2)
            with col1:
                filter_subject = st.multiselect("Фильтр по предмету", 
                                               options=df['subject'].unique())
            with col2:
                min_grade = st.slider("Минимальная оценка", 0.0, 100.0, 0.0)
            
            if filter_subject:
                df = df[df['subject'].isin(filter_subject)]
            df = df[df['grade'] >= min_grade]
            
            st.dataframe(df.sort_values('date', ascending=False), 
                        use_container_width=True,
                        hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Скачать как CSV",
                data=csv,
                file_name='study_tracker.csv',
                mime='text/csv',
            )
    
    elif selected_menu == "📚 Мои предметы":
        st.header("📚 Управление предметами")
        
        subjects_df = get_subjects(user_id)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("➕ Добавить предмет")
            with st.form("add_subject_form"):
                new_subject = st.text_input("Название предмета", placeholder="Например: Математика")
                
                color_options = {
                    "🔴 Красный": "#ef4444",
                    "🟠 Оранжевый": "#f97316",
                    "🟡 Жёлтый": "#eab308",
                    "🟢 Зелёный": "#22c55e",
                    "🔵 Синий": "#3b82f6",
                    "🟣 Фиолетовый": "#a855f7",
                    "⚫ Серый": "#6b7280"
                }
                color_name = st.selectbox("Цвет предмета", options=list(color_options.keys()))
                color = color_options[color_name]
                
                submitted = st.form_submit_button(" Добавить предмет", type="primary", use_container_width=True)
                
                if submitted:
                    if new_subject:
                        success, message = add_subject(user_id, new_subject.capitalize(), color)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.warning("⚠️ Введите название предмета")
        
        with col2:
            st.subheader("📋 Список предметов")
            if subjects_df.empty:
                st.info("📭 Предметов пока нет")
            else:
                for _, subject in subjects_df.iterrows():
                    col_del, col_name = st.columns([1, 5])
                    with col_del:
                        if st.button("🗑️", key=f"del_{subject['id']}"):
                            delete_subject(user_id, subject['name'])
                            st.rerun()
                    with col_name:
                        st.markdown(f"""
                        <div style='padding: 10px; margin: 5px 0; border-radius: 8px; 
                                    background-color: {subject['color']}20; 
                                    border-left: 4px solid {subject['color']};'>
                            <strong>{subject['name']}</strong>
                        </div>
                        """, unsafe_allow_html=True)
    
    elif selected_menu == "📅 Календарь":
        st.header("📅 Календарь событий")
        
        events_df = get_events(user_id)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📆 Ваши события")
            if events_df.empty:
                st.info("📭 Событий пока нет")
            else:
                for idx, event in events_df.iterrows():
                    col_event, col_del = st.columns([5, 1])
                    with col_event:
                        st.markdown(f"""
                        <div style='padding: 8px; margin: 5px 0; border-radius: 6px; 
                                    background-color: {event['color']}15; 
                                    border-left: 3px solid {event['color']};'>
                            <strong>{event['date']}</strong> - {event['title']}<br>
                            <small>{event['description']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_del:
                        if st.button("🗑️", key=f"del_event_{event['id']}"):
                            delete_event(event['id'])
                            st.rerun()
        
        with col2:
            st.subheader("➕ Добавить событие")
            with st.form("add_event_form"):
                event_date = st.date_input("📅 Дата", datetime.now())
                event_title = st.text_input("📝 Название", placeholder="Например: Контрольная")
                event_description = st.text_area("💬 Описание", placeholder="Дополнительная информация")
                
                color_options = {
                    "🔴 Красный": "#ef4444",
                    "🟠 Оранжевый": "#f97316",
                    "🟡 Жёлтый": "#eab308",
                    "🟢 Зелёный": "#22c55e",
                    "🔵 Синий": "#3b82f6",
                    "🟣 Фиолетовый": "#a855f7"
                }
                color_name = st.selectbox("🎨 Цвет", options=list(color_options.keys()))
                color = color_options[color_name]
                
                submitted = st.form_submit_button("💾 Добавить событие", type="primary", use_container_width=True)
                
                if submitted:
                    if event_title:
                        add_event(user_id, event_date.strftime("%Y-%m-%d"), 
                                 event_title, event_description, color)
                        st.success("✅ Событие добавлено!")
                        st.rerun()
                    else:
                        st.warning("️ Введите название события")
    
    elif selected_menu == "📈 Аналитика":
        st.header("📈 Подробная аналитика")
        
        df = get_records(user_id)
        
        if df.empty:
            st.warning("📭 Недостаточно данных для аналитики")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏆 Лучшие предметы")
                best_subjects = df.groupby('subject')['grade'].mean().nlargest(3)
                for i, (subject, grade) in enumerate(best_subjects.items(), 1):
                    st.write(f"{i}. {subject}: {grade:.2f}")
            
            with col2:
                st.subheader("📉 Требуют внимания")
                worst_subjects = df.groupby('subject')['grade'].mean().nsmallest(3)
                for i, (subject, grade) in enumerate(worst_subjects.items(), 1):
                    st.write(f"{i}. {subject}: {grade:.2f}")
            
            st.markdown("---")
            
            st.subheader("📊 Распределение оценок")
            fig_hist = px.histogram(df, x='grade', nbins=20, 
                                   title='Распределение всех оценок',
                                   color_discrete_sequence=['#636EFA'])
            st.plotly_chart(fig_hist, use_container_width=True)
            
            st.subheader("🔥 Активность по предметам")
            heatmap_data = df.groupby(['subject', pd.to_datetime(df['date']).dt.month]).size().unstack(fill_value=0)
            fig_heatmap = px.imshow(heatmap_data, 
                                   labels=dict(x="Месяц", y="Предмет", color="Количество записей"),
                                   color_continuous_scale="YlGnBu")
            st.plotly_chart(fig_heatmap, use_container_width=True)
    
    elif selected_menu == "️ Настройки профиля":
        st.header("⚙️ Настройки профиля")
        
        st.info(f"👤 Текущий логин: **{username}**")
        
        with st.form("update_credentials_form"):
            st.subheader("Изменить логин и пароль")
            
            new_username = st.text_input("👤 Новый логин", value=username)
            new_password = st.text_input("🔒 Новый пароль", type="password")
            confirm_password = st.text_input(" Подтвердите пароль", type="password")
            
            submitted = st.form_submit_button("💾 Сохранить изменения", type="primary", use_container_width=True)
            
            if submitted:
                if new_password != confirm_password:
                    st.error(" Пароли не совпадают")
                elif len(new_password) < 4:
                    st.error("❌ Пароль должен быть не короче 4 символов")
                else:
                    success, message = update_user_credentials(user_id, new_username, new_password)
                    if success:
                        st.success(f"✅ {message}")
                        st.session_state['username'] = new_username
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    elif selected_menu == "📱 Устройства":
        st.header("📱 Управление устройствами")
        
        devices_df = get_devices(user_id)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(" Добавить устройство")
            with st.form("add_device_form"):
                device_name = st.text_input("📱 Название устройства", placeholder="Например: Мой телефон")
                device_username = st.text_input(" Логин для устройства", placeholder="Например: phone_user")
                device_password = st.text_input("🔒 Пароль для устройства", type="password")
                
                submitted = st.form_submit_button("💾 Добавить устройство", type="primary", use_container_width=True)
                
                if submitted:
                    if device_name and device_username and device_password:
                        success, message = add_device(user_id, device_name, device_username, device_password)
                        if success:
                            st.success(f"✅ {message}")
                            st.info(f"📋 Данные для входа:\n- Логин: {device_username}\n- Пароль: {device_password}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.warning("⚠️ Заполните все поля")
        
        with col2:
            st.subheader("📋 Список устройств")
            if devices_df.empty:
                st.info("📭 Устройств пока нет")
            else:
                for _, device in devices_df.iterrows():
                    st.markdown(f"""
                    <div style='padding: 12px; margin: 8px 0; border-radius: 8px; 
                                background-color: #f0f9ff; 
                                border-left: 4px solid #3b82f6;'>
                        <strong>📱 {device['device_name']}</strong><br>
                        <small>Логин: {device['username']}</small><br>
                        <small>Создано: {device['created_at']}</small><br>
                        <small>Последний вход: {device['last_login'] or 'Никогда'}</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"🗑️ Удалить {device['device_name']}", key=f"del_device_{device['id']}"):
                        delete_device(device['id'], user_id)
                        st.success("✅ Устройство удалено")
                        st.rerun()
    
    elif selected_menu == "🗄️ База данных":
        st.header("🗄️ Просмотр базы данных")
        
        tables = get_all_tables()
        
        st.info(f"📊 Всего таблиц в базе данных: {len(tables)}")
        
        selected_table = st.selectbox("Выберите таблицу для просмотра", tables)
        
        if selected_table:
            df = get_table_data(selected_table)
            
            st.subheader(f"📋 Таблица: {selected_table}")
            st.write(f"Записей: {len(df)}")
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Скачать {selected_table} как CSV",
                data=csv,
                file_name=f'{selected_table}.csv',
                mime='text/csv',
            )
        
        st.markdown("---")
        
        st.subheader("🔍 Выполнить SQL запрос")
        sql_query = st.text_area("Введите SQL запрос", placeholder="SELECT * FROM users LIMIT 10")
        
        if st.button("▶️ Выполнить запрос", type="primary"):
            if sql_query:
                success, result = execute_sql(sql_query)
                if success:
                    st.success("✅ Запрос выполнен успешно")
                    st.dataframe(result, use_container_width=True)
                else:
                    st.error(f"❌ Ошибка: {result}")
            else:
                st.warning("️ Введите SQL запрос")
    
    elif selected_menu == "📜 Логи входов":
        st.header("📜 История входов")
        
        logs_df = get_login_logs(user_id)
        
        if logs_df.empty:
            st.info("📭 Логи входов пусты")
        else:
            st.dataframe(logs_df, use_container_width=True, hide_index=True)
            
            st.subheader("📊 Статистика")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Всего входов", len(logs_df))
            
            with col2:
                unique_devices = logs_df['device_name'].nunique()
                st.metric("Уникальных устройств", unique_devices)
            
            with col3:
                today = datetime.now().strftime("%Y-%m-%d")
                today_logins = len(logs_df[logs_df['login_time'].str.startswith(today)])
                st.metric("Входов сегодня", today_logins)
    
    st.markdown("---")
    st.markdown("<div style='text-align: center; color: gray;'>Создано с ❤️ на Streamlit</div>", 
               unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    main_app()
else:
    login_page()
