import hashlib
import hmac
import os
import secrets
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import psycopg2
from psycopg2 import IntegrityError
import streamlit as st

st.set_page_config(page_title="Личный дневник", page_icon="📚", layout="wide")
PBKDF2_ITERATIONS = 310_000

# ---------- DESIGN ----------
st.markdown("""
<style>
.block-container{max-width:1450px;padding-top:2rem;padding-bottom:4rem}
h1,h2,h3{letter-spacing:-.02em}
[data-testid="stMetric"]{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:16px 18px;box-shadow:0 4px 16px rgba(15,23,42,.05)}
div[data-testid="stForm"]{border:1px solid #e5e7eb;border-radius:18px;padding:20px;background:rgba(255,255,255,.8)}
.card{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:14px 16px;margin:8px 0;box-shadow:0 4px 16px rgba(15,23,42,.045)}
.muted{color:#64748b;font-size:.9rem}
</style>
""", unsafe_allow_html=True)

# ---------- DATABASE ----------
def get_database_url():
    try:
        value = st.secrets.get("DATABASE_URL")
    except Exception:
        value = None
    return value or os.getenv("DATABASE_URL")

DATABASE_URL = get_database_url()

def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("Не задан DATABASE_URL. Добавь его в Streamlit → Manage app → Secrets.")
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
            cur.execute("""
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
            CREATE INDEX IF NOT EXISTS idx_subjects_user ON subjects(user_id);
            CREATE INDEX IF NOT EXISTS idx_records_user_date ON records(user_id,date);
            CREATE INDEX IF NOT EXISTS idx_events_user_date ON events(user_id,date);
            """)
            # Migration for the old INTEGER is_admin column.
            cur.execute("""
                SELECT data_type FROM information_schema.columns
                WHERE table_schema='public' AND table_name='users' AND column_name='is_admin'
            """)
            row = cur.fetchone()
            if row and row[0] != 'boolean':
                cur.execute("ALTER TABLE users ALTER COLUMN is_admin DROP DEFAULT")
                cur.execute("ALTER TABLE users ALTER COLUMN is_admin TYPE BOOLEAN USING (is_admin <> 0)")
                cur.execute("ALTER TABLE users ALTER COLUMN is_admin SET DEFAULT FALSE")
        conn.commit()

# ---------- AUTH ----------
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"

def verify_password(password, stored):
    if not stored: return False
    if stored.startswith('pbkdf2_sha256$'):
        try:
            _, iterations, salt, expected = stored.split('$',3)
            digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
            return hmac.compare_digest(digest, expected)
        except (ValueError,TypeError): return False
    return hmac.compare_digest(password, stored)

def authenticate(username,password):
    user=query("SELECT id,username,password,is_admin FROM users WHERE username=%s",(username.strip(),),fetchone=True)
    if not user or not verify_password(password,user[2]): return None
    if not user[2].startswith('pbkdf2_sha256$'):
        query("UPDATE users SET password=%s WHERE id=%s",(hash_password(password),user[0]))
    return {'id':user[0],'username':user[1],'is_admin':bool(user[3])}

def uid(): return st.session_state.get('user_id')
def username(): return st.session_state.get('username','')
def admin(): return bool(st.session_state.get('is_admin',False))
def logout(): st.session_state.clear(); st.rerun()

# ---------- HELPERS ----------
def grade_color(g):
    if g is None or pd.isna(g): return '#64748b'
    g=float(g)
    if g < 3: return '#dc2626'       # 2 red
    if g < 4: return '#eab308'       # 3 yellow
    if g < 5: return '#16a34a'       # 4 green
    return '#2563eb'                 # 5 blue

def grade_icon(g):
    if g is None or pd.isna(g): return '⭐'
    g=float(g)
    return '🔴' if g<3 else '🟡' if g<4 else '🟢' if g<5 else '🔵'

def fmt_date(v):
    try: return datetime.strptime(str(v),'%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception: return str(v)

def icon(t): return {'Оценка':'⭐','Долг':'⚠️','Время':'⏱️'}.get(t,'📝')

def flash(kind,msg): st.session_state.flash=(kind,msg)
def show_flash():
    x=st.session_state.pop('flash',None)
    if x:
        {'success':st.success,'warning':st.warning,'error':st.error,'info':st.info}.get(x[0],st.info)(x[1])

# ---------- LOGIN ----------
def first_setup():
    st.title('📚 Личный дневник'); st.subheader('Первый запуск')
    st.info('Пользователей пока нет. Создай администратора.')
    with st.form('first_setup'):
        u=st.text_input('Логин'); p=st.text_input('Пароль',type='password'); p2=st.text_input('Повтори пароль',type='password')
        if st.form_submit_button('Создать администратора',type='primary',use_container_width=True):
            u=u.strip()
            if len(u)<3: st.error('Логин должен содержать минимум 3 символа.')
            elif len(p)<8: st.error('Пароль должен содержать минимум 8 символов.')
            elif p!=p2: st.error('Пароли не совпадают.')
            else:
                try:
                    query("INSERT INTO users(username,password,created_at,is_admin) VALUES(%s,%s,%s,TRUE)",(u,hash_password(p),date.today().isoformat()))
                    flash('success','Администратор создан. Теперь можно войти.'); st.rerun()
                except IntegrityError: st.error('Такой логин уже существует.')

def login():
    st.title('📚 Личный дневник'); st.caption('Записи хранятся в PostgreSQL Supabase.')
    with st.form('login'):
        u=st.text_input('Логин'); p=st.text_input('Пароль',type='password')
        if st.form_submit_button('Войти',type='primary',use_container_width=True):
            user=authenticate(u,p)
            if user:
                st.session_state.logged_in=True; st.session_state.user_id=user['id']; st.session_state.username=user['username']; st.session_state.is_admin=user['is_admin']; st.session_state.page='📊 Главная'; st.rerun()
            else: st.error('Неверный логин или пароль.')

# ---------- DASHBOARD ----------
def dashboard():
    st.title(f'Привет, {username()}! 👋'); show_flash()
    records=get_df("SELECT * FROM records WHERE user_id=%s ORDER BY date DESC,id DESC",(uid(),))
    subjects=get_df("SELECT * FROM subjects WHERE user_id=%s ORDER BY name",(uid(),))
    events=get_df("SELECT * FROM events WHERE user_id=%s ORDER BY date,id",(uid(),))
    debts=records[records.record_type=='Долг'] if not records.empty else pd.DataFrame()
    active=len(debts[debts.status!='Выполнено']) if not debts.empty else 0
    hours=float(records.hours.fillna(0).sum()) if not records.empty else 0
    a,b,c,d=st.columns(4); a.metric('📝 Записей',len(records)); b.metric('📚 Предметов',len(subjects)); c.metric('⚠️ Активных долгов',active); d.metric('⏱️ Часов',f'{hours:.1f}')
    if subjects.empty: st.info('Добавь первый предмет в разделе «📚 Предметы».'); return
    st.divider(); st.subheader('📚 По предметам')
    for _,s in subjects.iterrows():
        sdf=records[records.subject==s['name']]; grades=sdf.loc[sdf.record_type=='Оценка','grade'].dropna(); hrs=sdf.hours.dropna(); debts2=sdf[sdf.record_type=='Долг']; active2=debts2[debts2.status!='Выполнено']
        st.markdown(f"<div style='padding:16px;margin:12px 0 8px;border-radius:15px;background:{s.color}18;border:1px solid {s.color}35;border-left:6px solid {s.color};font-size:1.2rem;font-weight:800'>📚 {s['name']}</div>",unsafe_allow_html=True)
        m1,m2,m3,m4=st.columns(4); m1.metric('⭐ Средний балл',f'{grades.mean():.2f}' if not grades.empty else '—',f'{len(grades)} оценок'); m2.metric('⏱️ Часы',f'{hrs.sum():.1f}' if not hrs.empty else '—'); m3.metric('⚠️ Долги',len(active2),f'из {len(debts2)}'); m4.metric('📝 Всего',len(sdf))
        for _,r in debts2.sort_values('date',ascending=False).iterrows(): st.markdown(f"- {'✅' if r.status=='Выполнено' else '🔴'} **{r.topic or 'Без названия'}** — {fmt_date(r.date)}")
    if not records.empty:
        st.divider(); c1,c2=st.columns(2)
        with c1:
            g=records[(records.record_type=='Оценка')&records.grade.notna()]
            if not g.empty: st.plotly_chart(px.bar(g.groupby('subject',as_index=False).grade.mean(),x='subject',y='grade',title='Средний балл по предметам'),use_container_width=True)
        with c2:
            h=records[records.hours.notna()]
            if not h.empty: st.plotly_chart(px.pie(h.groupby('subject',as_index=False).hours.sum(),values='hours',names='subject',title='Распределение времени'),use_container_width=True)

# ---------- NEW RECORD ----------
def new_record():
    st.title('✍️ Новая запись'); st.caption('Дата сохраняется у каждой оценки, долга и записи времени.'); show_flash()
    subjects=get_df("SELECT name FROM subjects WHERE user_id=%s ORDER BY name",(uid(),))
    if subjects.empty: st.warning('Сначала добавь хотя бы один предмет.'); return
    rtype=st.radio('Тип записи',['Оценка','Долг','Время'],horizontal=True)
    with st.form('new_record'):
        c1,c2=st.columns(2)
        with c1:
            dt=st.date_input('📅 Дата',date.today()); subj=st.selectbox('📚 Предмет',subjects.name.tolist()); topic=st.text_input('Тема',placeholder='Для долга обязательно, для оценки/времени можно пусто')
        with c2:
            grade=None; hours=None; status=None
            if rtype=='Оценка':
                grade=st.number_input('⭐ Оценка',2.0,5.0,5.0,1.0); hours=st.number_input('⏱️ Затрачено часов',0.0,24.0,0.0,.5)
            elif rtype=='Время': hours=st.number_input('⏱️ Часы',0.0,24.0,1.0,.5)
            else: status=st.selectbox('Статус',['В процессе','Выполнено'])
            comment=st.text_area('Комментарий')
        if st.form_submit_button('💾 Сохранить',type='primary',use_container_width=True):
            topic=topic.strip(); comment=comment.strip()
            if rtype=='Долг' and not topic: st.error('Для долга обязательно укажи тему.'); return
            query("INSERT INTO records(user_id,date,record_type,subject,topic,grade,hours,comment,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(uid(),dt.isoformat(),rtype,subj,topic or None,grade,hours if hours and hours>0 else None,comment or None,status))
            if rtype=='Долг': flash('warning','🔴 Долг добавлен.')
            elif rtype=='Оценка': flash('success',f'{grade_icon(grade)} Оценка {grade:g} добавлена по предмету «{subj}».')
            else: flash('success',f'⏱️ Время добавлено: {hours:g} ч.')
            st.rerun()

# ---------- SUBJECTS ----------
def subjects_page():
    st.title('📚 Предметы'); show_flash(); c1,c2=st.columns([1,1.2])
    with c1:
        with st.form('add_subject'):
            name=st.text_input('Название'); color=st.color_picker('Цвет предмета','#3b82f6')
            st.markdown(f"<div style='padding:10px;border-radius:10px;background:{color}18;border-left:5px solid {color};margin:6px 0 12px'>Предпросмотр: <b>{name or 'Мой предмет'}</b></div>",unsafe_allow_html=True)
            if st.form_submit_button('➕ Добавить',type='primary',use_container_width=True):
                name=name.strip()
                if not name: st.error('Название не может быть пустым.')
                else:
                    try:
                        query('INSERT INTO subjects(user_id,name,color) VALUES(%s,%s,%s)',(uid(),name,color)); flash('success',f'📚 Предмет «{name}» добавлен.'); st.rerun()
                    except IntegrityError: st.error('Такой предмет уже существует.')
    with c2:
        st.subheader('Мои предметы'); df=get_df('SELECT * FROM subjects WHERE user_id=%s ORDER BY name',(uid(),))
        if df.empty: st.caption('Предметов пока нет.')
        for _,s in df.iterrows():
            l,r=st.columns([6,1])
            with l: st.markdown(f"<div class='card' style='border-left:5px solid {s.color};background:{s.color}18'><b>{s.name}</b></div>",unsafe_allow_html=True)
            with r:
                if st.button('🗑️',key=f'ds{s.id}'):
                    count=query('SELECT COUNT(*) FROM records WHERE user_id=%s AND subject=%s',(uid(),s.name),fetchone=True)[0]
                    if count: st.error('Нельзя удалить предмет, пока у него есть записи.')
                    else: query('DELETE FROM subjects WHERE id=%s AND user_id=%s',(int(s.id),uid())); flash('success','Предмет удалён.'); st.rerun()

# ---------- EVENTS ----------
def events_page():
    st.title('📅 События'); show_flash(); c1,c2=st.columns([1,1.2])
    with c1:
        with st.form('add_event'):
            dt=st.date_input('📅 Дата',date.today()); title=st.text_input('Название'); desc=st.text_area('Описание'); color=st.color_picker('Цвет','#3b82f6')
            st.markdown(f"<div style='padding:10px;border-radius:10px;background:{color}18;border-left:5px solid {color};margin:6px 0 12px'>Предпросмотр: <b>{title or 'Новое событие'}</b></div>",unsafe_allow_html=True)
            if st.form_submit_button('➕ Добавить',type='primary',use_container_width=True):
                title=title.strip(); desc=desc.strip()
                if not title: st.error('Название не может быть пустым.')
                else: query('INSERT INTO events(user_id,date,title,description,color) VALUES(%s,%s,%s,%s,%s)',(uid(),dt.isoformat(),title,desc or None,color)); flash('success',f'📅 Событие «{title}» добавлено.'); st.rerun()
    with c2:
        st.subheader('Мои события'); df=get_df('SELECT * FROM events WHERE user_id=%s ORDER BY date,id',(uid(),))
        if df.empty: st.caption('Событий пока нет.')
        for _,e in df.iterrows():
            l,r=st.columns([6,1])
            with l: st.markdown(f"<div class='card' style='border-left:5px solid {e.color};background:{e.color}18'><b>📅 {fmt_date(e.date)} — {e.title}</b><br><span class='muted'>{e.description or ''}</span></div>",unsafe_allow_html=True)
            with r:
                if st.button('🗑️',key=f'de{e.id}'):
                    query('DELETE FROM events WHERE id=%s AND user_id=%s',(int(e.id),uid())); flash('success','Событие удалено.'); st.rerun()

# ---------- RECORDS ----------
def records_page():
    st.title('📋 Записи'); show_flash(); df=get_df('SELECT * FROM records WHERE user_id=%s ORDER BY date DESC,id DESC',(uid(),))
    if df.empty: st.info('Записей пока нет.'); return
    c1,c2,c3=st.columns(3); tf=c1.multiselect('Тип',['Оценка','Долг','Время']); sf=c2.multiselect('Предмет',sorted(df.subject.dropna().unique())); stf=c3.multiselect('Статус',['В процессе','Выполнено'])
    f=df.copy()
    if tf: f=f[f.record_type.isin(tf)]
    if sf: f=f[f.subject.isin(sf)]
    if stf: f=f[f.status.isin(stf)]
    view=f[['date','record_type','subject','topic','grade','hours','comment','status']].copy(); view.date=view.date.map(fmt_date); st.dataframe(view,use_container_width=True,hide_index=True)
    for _,r in f.iterrows():
        color=grade_color(r.grade) if r.record_type=='Оценка' else ('#dc2626' if r.record_type=='Долг' else '#2563eb')
        st.markdown(f"<div class='card' style='border-left:5px solid {color}'><b>{icon(r.record_type)} {r.subject}</b> {'— '+str(r.topic) if pd.notna(r.topic) and r.topic else ''}<br><span class='muted'>📅 {fmt_date(r.date)} {' · ⏱️ '+str(r.hours)+' ч.' if pd.notna(r.hours) else ''} {' · '+str(r.status) if pd.notna(r.status) and r.status else ''}</span><br><span class='muted'>{r.comment or ''}</span></div>",unsafe_allow_html=True)
        a,b=st.columns(2)
        with a:
            if r.record_type=='Долг' and r.status!='Выполнено' and st.button('✅ Выполнено',key=f'cr{r.id}'):
                query("UPDATE records SET status='Выполнено' WHERE id=%s AND user_id=%s",(int(r.id),uid())); flash('success','Долг выполнен.'); st.rerun()
        with b:
            if st.button('🗑️ Удалить',key=f'dr{r.id}'):
                query('DELETE FROM records WHERE id=%s AND user_id=%s',(int(r.id),uid())); flash('success','Запись удалена.'); st.rerun()

# ---------- GRADES ----------
def grades_page():
    st.title('⭐ Оценки'); show_flash()
    df=get_df("SELECT id,date,subject,topic,grade,comment FROM records WHERE user_id=%s AND record_type='Оценка' AND grade IS NOT NULL ORDER BY date DESC,id DESC",(uid(),))
    if df.empty: st.info('Оценок пока нет.'); return
    c1,c2=st.columns(2); sf=c1.multiselect('📚 Предметы',sorted(df.subject.unique())); period=c2.date_input('📅 Период',(date.today()-timedelta(days=30),date.today()))
    if sf: df=df[df.subject.isin(sf)]
    if isinstance(period,(tuple,list)) and len(period)==2: df=df[(df.date>=period[0].isoformat())&(df.date<=period[1].isoformat())]
    if df.empty: st.info('За выбранный период оценок нет.'); return
    st.metric('Средний балл',f"{df.grade.mean():.2f}",f'{len(df)} оценок')
    st.subheader('📊 Средний балл по предметам')
    for subject,g in df.groupby('subject',sort=True):
        avg=g.grade.mean(); color=grade_color(avg); counts=g.grade.round().astype(int).value_counts().reindex([5,4,3,2],fill_value=0); comp=' · '.join(f'{x} — {n}' for x,n in counts.items() if n)
        st.markdown(f"<div class='card' style='border-left:6px solid {color}'><div style='display:flex;justify-content:space-between;align-items:center'><div><b style='font-size:1.2rem'>📚 {subject}</b><br><span class='muted'>Состав оценок: {comp or 'нет данных'}</span></div><b style='font-size:2rem;color:{color}'>{avg:.2f}</b></div></div>",unsafe_allow_html=True)
    st.subheader('🗓️ Оценки по датам')
    for day,g in df.groupby('date',sort=False):
        st.markdown(f'### 📅 {fmt_date(day)}')
        for _,r in g.iterrows():
            color=grade_color(r.grade)
            st.markdown(f"<div class='card' style='border-left:6px solid {color}'><b>📚 {r.subject}</b><span style='float:right;font-size:1.6rem;font-weight:900;color:{color}'>{r.grade:g}</span><br><span class='muted'>📝 {r.topic or 'Без темы'}</span></div>",unsafe_allow_html=True)

# ---------- CALENDAR ----------
def calendar_page():
    st.title('🗓️ Календарь'); st.caption('Все события без исключения: оценки, долги, время и обычные события.'); show_flash()
    if 'cal_month' not in st.session_state: st.session_state.cal_month=date.today().replace(day=1)
    m=st.session_state.cal_month; a,b,c=st.columns([1,2,1])
    with a:
        if st.button('← Предыдущий месяц',use_container_width=True):
            st.session_state.cal_month=date(m.year-1,12,1) if m.month==1 else date(m.year,m.month-1,1); st.rerun()
    with b: st.markdown(f"<div style='text-align:center;font-size:1.4rem;font-weight:800;padding:7px'>{m.strftime('%m.%Y')}</div>",unsafe_allow_html=True)
    with c:
        if st.button('Следующий месяц →',use_container_width=True):
            st.session_state.cal_month=date(m.year+1,1,1) if m.month==12 else date(m.year,m.month+1,1); st.rerun()
    nxt=date(m.year+1,1,1) if m.month==12 else date(m.year,m.month+1,1)
    records=get_df('SELECT * FROM records WHERE user_id=%s AND date>=%s AND date<%s ORDER BY date,id',(uid(),m.isoformat(),nxt.isoformat()))
    events=get_df('SELECT * FROM events WHERE user_id=%s AND date>=%s AND date<%s ORDER BY date,id',(uid(),m.isoformat(),nxt.isoformat()))
    q1,q2,q3,q4=st.columns(4); q1.metric('⭐ Оценок',int((records.record_type=='Оценка').sum()) if not records.empty else 0); q2.metric('🔴 Долгов',int((records.record_type=='Долг').sum()) if not records.empty else 0); q3.metric('⏱️ Времени',int((records.record_type=='Время').sum()) if not records.empty else 0); q4.metric('📅 Событий',len(events))
    names=['Пн','Вт','Ср','Чт','Пт','Сб','Вс']; cols=st.columns(7)
    for i,n in enumerate(names):
        with cols[i]: st.markdown(f"<div style='text-align:center;font-weight:800;color:#64748b;padding:8px'>{n}</div>",unsafe_allow_html=True)
    import calendar as pycalendar
    cells=[None]*m.weekday()+list(range(1,pycalendar.monthrange(m.year,m.month)[1]+1))
    while len(cells)%7: cells.append(None)
    for start in range(0,len(cells),7):
        cols=st.columns(7)
        for i,num in enumerate(cells[start:start+7]):
            with cols[i]:
                if num is None: st.markdown('<div style="min-height:120px"></div>',unsafe_allow_html=True); continue
                ds=date(m.year,m.month,num).isoformat(); rr=records[records.date==ds] if not records.empty else pd.DataFrame(); ee=events[events.date==ds] if not events.empty else pd.DataFrame(); border='#2563eb' if ds==date.today().isoformat() else '#e5e7eb'; html=f"<div style='background:white;border:2px solid {border};border-radius:14px;padding:10px;min-height:120px;margin-bottom:10px'><b>{num}</b>"
                for _,e in ee.iterrows(): html+=f"<div style='margin:4px 0;padding:4px 6px;border-radius:7px;background:{e.color}18;border-left:4px solid {e.color};font-size:.78rem'>📅 <b>{e.title}</b></div>"
                for _,r in rr.iterrows():
                    color=grade_color(r.grade) if r.record_type=='Оценка' else ('#dc2626' if r.record_type=='Долг' else '#2563eb')
                    label=f"⭐ {r.subject} · {r.grade:g}" if r.record_type=='Оценка' else f"🔴 {r.subject} · {r.topic or 'Долг'}" if r.record_type=='Долг' else f"⏱️ {r.subject} · {r.hours or 0:g} ч."
                    html+=f"<div style='margin:4px 0;padding:4px 6px;border-radius:7px;background:{color}18;border-left:4px solid {color};font-size:.78rem'>{label}</div>"
                html+='</div>'; st.markdown(html,unsafe_allow_html=True)
    st.divider(); st.subheader('📋 Подробности месяца'); rows=[]
    for _,e in events.iterrows(): rows.append({'Дата':fmt_date(e.date),'Тип':'📅 Событие','Предмет':'—','Название':e.title,'Детали':e.description or ''})
    for _,r in records.iterrows(): rows.append({'Дата':fmt_date(r.date),'Тип':icon(r.record_type),'Предмет':r.subject,'Название':r.topic or 'Без темы','Детали':f"Оценка: {r.grade:g}" if r.record_type=='Оценка' else f"{r.hours or 0:g} ч." if r.record_type=='Время' else (r.status or 'В процессе')})
    if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else: st.info('В этом месяце пока ничего нет.')

# ---------- SETTINGS / USERS ----------
def settings_page():
    st.title('⚙️ Настройки'); show_flash()
    with st.form('password_change'):
        old=st.text_input('Текущий пароль',type='password'); new=st.text_input('Новый пароль',type='password'); new2=st.text_input('Повтори новый пароль',type='password')
        if st.form_submit_button('Изменить пароль',type='primary'):
            row=query('SELECT password FROM users WHERE id=%s',(uid(),),fetchone=True)
            if not row or not verify_password(old,row[0]): st.error('Текущий пароль указан неверно.')
            elif len(new)<8: st.error('Новый пароль должен содержать минимум 8 символов.')
            elif new!=new2: st.error('Новые пароли не совпадают.')
            else: query('UPDATE users SET password=%s WHERE id=%s',(hash_password(new),uid())); flash('success','Пароль успешно изменён.'); st.rerun()

def users_page():
    if not admin(): st.error('Доступ запрещён.'); return
    st.title('👥 Пользователи'); show_flash(); c1,c2=st.columns([1,1.2])
    with c1:
        with st.form('add_user'):
            u=st.text_input('Логин'); p=st.text_input('Пароль',type='password'); a=st.checkbox('Администратор')
            if st.form_submit_button('Создать',type='primary',use_container_width=True):
                u=u.strip()
                if len(u)<3: st.error('Логин должен содержать минимум 3 символа.')
                elif len(p)<8: st.error('Пароль должен содержать минимум 8 символов.')
                else:
                    try: query('INSERT INTO users(username,password,created_at,is_admin) VALUES(%s,%s,%s,%s)',(u,hash_password(p),date.today().isoformat(),bool(a))); flash('success',f'Пользователь «{u}» создан.'); st.rerun()
                    except IntegrityError: st.error('Такой логин уже существует.')
    with c2:
        df=get_df('SELECT id,username,created_at,is_admin FROM users ORDER BY username')
        for _,u in df.iterrows():
            l,r=st.columns([6,1])
            with l: st.markdown(f"<div class='card'><b>{u.username}</b> — {'👑 Администратор' if bool(u.is_admin) else '👤 Пользователь'}<br><span class='muted'>Создан: {fmt_date(u.created_at)}</span></div>",unsafe_allow_html=True)
            with r:
                if int(u.id)!=int(uid()) and st.button('🗑️',key=f'du{u.id}'):
                    query('DELETE FROM users WHERE id=%s',(int(u.id),)); flash('success',f'Пользователь «{u.username}» удалён.'); st.rerun()

# ---------- MAIN ----------
try:
    init_db()
    st.session_state.setdefault('logged_in',False)
    st.session_state.setdefault('page','📊 Главная')
    show_flash()
    count=query('SELECT COUNT(*) FROM users',fetchone=True)[0]
    if count==0: first_setup()
    elif not st.session_state.logged_in: login()
    else:
        menu=['📊 Главная','✍️ Новая запись','📚 Предметы','📅 События','📋 Записи','⭐ Оценки','🗓️ Календарь','⚙️ Настройки']
        if admin(): menu.append('👥 Пользователи')
        menu.append('🚪 Выйти')
        page=st.sidebar.radio('Меню',menu,index=menu.index(st.session_state.page) if st.session_state.page in menu else 0)
        st.session_state.page=page; st.sidebar.divider(); st.sidebar.markdown(f'👤 **{username()}**')
        if page=='🚪 Выйти': logout()
        elif page=='📊 Главная': dashboard()
        elif page=='✍️ Новая запись': new_record()
        elif page=='📚 Предметы': subjects_page()
        elif page=='📅 События': events_page()
        elif page=='📋 Записи': records_page()
        elif page=='⭐ Оценки': grades_page()
        elif page=='🗓️ Календарь': calendar_page()
        elif page=='⚙️ Настройки': settings_page()
        elif page=='👥 Пользователи': users_page()
except Exception as exc:
    st.error('Не удалось запустить дневник. Проверь DATABASE_URL и логи приложения.')
    st.exception(exc)
