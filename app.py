import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3

st.set_page_config(
    page_title="Study Tracker",
    page_icon="📚",
    layout="wide"
)

def init_db():
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT,
        created_at TEXT, is_admin INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT,
        color TEXT, UNIQUE(user_id, name))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT,
        subject TEXT, topic TEXT, grade REAL, hours REAL, comment TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT,
        title TEXT, description TEXT, color TEXT)''')
    
    c.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO users VALUES (1, ?, ?, ?, 1)',
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

def add_subject(user_id, name, color):
    conn = sqlite3.connect('study_tracker.db')
    try:
        conn.execute('INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)',
                    (user_id, name, color))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def get_subjects(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM subjects WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def add_record(user_id, date, subject, topic, grade, hours, comment):
    conn = sqlite3.connect('study_tracker.db')
    conn.execute('''INSERT INTO records (user_id, date, subject, topic, grade, hours, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (user_id, date, subject, topic, grade, hours, comment))
    conn.commit()
    conn.close()

def get_records(user_id):
    conn = sqlite3.connect('study_tracker.db')
    df = pd.read_sql_query("SELECT * FROM records WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

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

init_db()

# Простая авторизация через session_state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'

if not st.session_state.logged_in:
    st.title("Study Tracker")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        user = verify_user(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_id = user[0]
            st.session_state.page = 'dashboard'
            st.rerun()
        else:
            st.error("Invalid credentials")
else:
    # Боковое меню
    page = st.sidebar.selectbox("Menu", 
        ["Dashboard", "Add Record", "Subjects", "Events", "Logout"])
    
    if page == "Logout":
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.page = 'login'
        st.rerun()
    
    elif page == "Dashboard":
        st.title("Dashboard")
        df = get_records(st.session_state.user_id)
        
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("Records", len(df))
            col2.metric("Avg Grade", f"{df['grade'].mean():.1f}")
            col3.metric("Hours", f"{df['hours'].sum():.1f}")
            
            st.subheader("Grades by Subject")
            fig = px.bar(df.groupby('subject')['grade'].mean().reset_index(),
                        x='subject', y='grade')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No records yet")
    
    elif page == "Add Record":
        st.title("Add Record")
        subjects_df = get_subjects(st.session_state.user_id)
        
        if subjects_df.empty:
            st.warning("Add subjects first!")
        else:
            with st.form("record_form"):
                col1, col2 = st.columns(2)
                with col1:
                    date = st.date_input("Date", datetime.now())
                    subject = st.selectbox("Subject", subjects_df['name'].tolist())
                    topic = st.text_input("Topic")
                with col2:
                    grade = st.number_input("Grade", 0.0, 100.0)
                    hours = st.number_input("Hours", 0.0, 24.0)
                    comment = st.text_area("Comment")
                
                if st.form_submit_button("Save"):
                    add_record(st.session_state.user_id, 
                              date.strftime("%Y-%m-%d"), subject, topic,
                              grade, hours, comment)
                    st.success("Saved!")
    
    elif page == "Subjects":
        st.title("Subjects")
        
        col1, col2 = st.columns(2)
        with col1:
            with st.form("subject_form"):
                name = st.text_input("Subject name")
                color = st.color_picker("Color", "#3b82f6")
                if st.form_submit_button("Add"):
                    if add_subject(st.session_state.user_id, name, color):
                        st.success("Added!")
                    else:
                        st.error("Already exists")
        
        with col2:
            subjects_df = get_subjects(st.session_state.user_id)
            if not subjects_df.empty:
                st.dataframe(subjects_df, hide_index=True)
    
    elif page == "Events":
        st.title("Events")
        
        col1, col2 = st.columns(2)
        with col1:
            with st.form("event_form"):
                date = st.date_input("Date", datetime.now())
                title = st.text_input("Title")
                desc = st.text_area("Description")
                color = st.color_picker("Color", "#3b82f6")
                if st.form_submit_button("Add"):
                    add_event(st.session_state.user_id, 
                             date.strftime("%Y-%m-%d"), title, desc, color)
                    st.success("Added!")
        
        with col2:
            events_df = get_events(st.session_state.user_id)
            if not events_df.empty:
                st.dataframe(events_df, hide_index=True)
