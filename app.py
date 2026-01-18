import streamlit as st
import sqlite3
import datetime
import pandas as pd
import speech_recognition as sr
import io
import os
import time
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
from gtts import gTTS
from streamlit_gsheets import GSheetsConnection

# --- PAGE SETUP (International Look) ---
st.set_page_config(page_title="Nia Rice Mill SaaS", page_icon="🌾", layout="wide")

# --- CONNECT TO GOOGLE SHEET ---
try:
    conn_gsheets = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("⚠️ Internet Error: Google Sheet connect nahi hui.")
    st.stop()

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pending_weight' not in st.session_state:
    st.session_state.pending_weight = None

# --- HELPER: SPEAK ---
def speak(text):
    try:
        tts = gTTS(text=text, lang='hi')
        tts.save("temp.mp3")
        st.audio("temp.mp3", format="audio/mp3", autoplay=True)
    except:
        pass

# --- LOGIN LOGIC ---
def check_login(username, password):
    try:
        users_df = conn_gsheets.read(worksheet="Users")
        users_df['Username'] = users_df['Username'].astype(str)
        user = users_df[users_df['Username'] == str(username)]
        
        if not user.empty:
            stored_password = str(user.iloc[0]['Password'])
            raw_active = user.iloc[0]['Is_Active']
            status_str = str(raw_active).strip().upper()
            
            if str(password) == stored_password:
                if status_str in ['TRUE', '1', '1.0', 'YES', 'ON']:
                    return user.iloc[0].to_dict()
                else:
                    return "BLOCKED"
        return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

# --- SAVE DATA ---
def save_data_secure(wazan, price):
    now = datetime.datetime.now()
    d_date = now.strftime("%Y-%m-%d")
    d_time = now.strftime("%H:%M:%S")
    my_mill_id = st.session_state.user_info['Mill_ID']
    munim_name = st.session_state.user_info['Name']

    # Local Backup
    try:
        conn = sqlite3.connect('rice_mill.db')
        conn.execute('INSERT INTO records (date, time, weight, price, mill_id) VALUES (?, ?, ?, ?, ?)', 
                  (d_date, d_time, wazan, price, my_mill_id))
        conn.commit()
        conn.close()
    except:
        pass

    # Cloud Save
    try:
        new_data = pd.DataFrame(
            [[my_mill_id, d_date, d_time, wazan, price, munim_name]], 
            columns=['Mill_ID', 'Date', 'Time', 'Weight', 'Price', 'EntryBy']
        )
        existing_data = conn_gsheets.read() 
        updated_df = pd.concat([existing_data, new_data], ignore_index=True)
        conn_gsheets.update(data=updated_df)
        st.toast(f"✅ Saved: {wazan}kg", icon="💾")
        return True
    except Exception as e:
        st.error(f"Cloud Save Error: {e}")
        return False

# ==========================================
# 🔐 LOGIN SCREEN (Simple & Clean)
# ==========================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br><h1 style='text-align: center;'>🌾 Nia Rice Mill</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: grey;'>Secure Login System</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("🔒 Secure Login", type="primary", use_container_width=True)
            
            if submit:
                user_data = check_login(username, password)
                if user_data == "BLOCKED":
                    st.error("🚫 Account Deactivated.")
                elif user_data:
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_data
                    st.rerun()
                else:
                    st.error("❌ Invalid Credentials")
    st.stop()

# ==========================================
# 🏭 MAIN DASHBOARD (The International Look)
# ==========================================

# 1. HEADER SECTION
st.markdown(f"### 🌾 {st.session_state.user_info['Mill_ID']}")
st.markdown(f"**Welcome, {st.session_state.user_info['Name']}** | Role: {st.session_state.user_info['Role']}")

# Logout Button (Top Right)
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.divider()

# 2. DATA LOADING & PROCESSING
all_data = conn_gsheets.read()
# Filter only My Mill Data
my_data = all_data[all_data['Mill_ID'] == st.session_state.user_info['Mill_ID']].copy()

# Ensure Numbers are Numbers (Data Cleaning)
my_data['Weight'] = pd.to_numeric(my_data['Weight'], errors='coerce').fillna(0)
my_data['Price'] = pd.to_numeric(my_data['Price'], errors='coerce').fillna(0)

# Calculate "Today's" Stats
today_date = datetime.datetime.now().strftime("%Y-%m-%d")
todays_data = my_data[my_data['Date'] == today_date]

total_weight_today = todays_data['Weight'].sum()
total_price_today = todays_data['Price'].sum()
total_trucks_today = len(todays_data)

# 3. KPI CARDS (Bade Numbers)
st.markdown("### 📊 Aaj ka Hisab (Today's Overview)")
kpi1, kpi2, kpi3 = st.columns(3)

kpi1.metric(
    label="📦 Aaj Ki Aavak (Weight)",
    value=f"{total_weight_today:,.1f} kg",
    delta=f"{total_trucks_today} Entries"
)

kpi2.metric(
    label="💰 Aaj Ki Value",
    value=f"₹ {total_price_today:,.0f}",
    delta="Estimated"
)

kpi3.metric(
    label="🚛 Total Entries (All Time)",
    value=len(my_data),
    delta_color="off"
)

st.divider()

# 4. ENTRY SECTION (Left) & CHART (Right)
col_entry, col_chart = st.columns([1, 2])

with col_entry:
    st.subheader("🎙️ Nayi Entry")
    st.info("Mic dabayein aur wazan bolein...")
    
    # Audio Input
    if st.session_state.step == 1:
        audio = mic_recorder(start_prompt="🔴 Record", stop_prompt="⏹️ Stop", key='rec1')
        if audio:
            try:
                webm = audio['bytes']
                sound = AudioSegment.from_file(io.BytesIO(webm))
                wav = io.BytesIO()
                sound.export(wav, format="wav")
                wav.seek(0)
                r = sr.Recognizer()
                with sr.AudioFile(wav) as source:
                    txt = r.recognize_google(r.record(source), language="hi-IN")
                    nums = [float(s) for s in txt.split() if s.replace('.', '', 1).isdigit()]
                    if nums:
                        st.session_state.pending_weight = nums[0]
                        st.session_state.step = 2
                        st.rerun()
            except:
                st.warning("Retry...")

    # Confirmation
    elif st.session_state.step == 2:
        w = st.session_state.pending_weight
        st.success(f"⚖️ Weight: **{w} kg**")
        speak(f"{w} kilo")
        
        c1, c2 = st.columns(2)
        if c1.button("✅ SAVE", type="primary", use_container_width=True):
            save_data_secure(w, w * 25.0)
            time.sleep(1)
            st.session_state.step = 1
            st.rerun()
        if c2.button("❌ CANCEL", use_container_width=True):
            st.session_state.step = 1
            st.rerun()

with col_chart:
    st.subheader("📈 Aavak Trend (Last 7 Days)")
    if not my_data.empty:
        # Group by Date to show daily totals
        daily_data = my_data.groupby('Date')['Weight'].sum().reset_index()
        st.bar_chart(daily_data.set_index('Date'), color="#FF4B4B")
    else:
        st.write("Abhi graph ke liye data kam hai.")

# 5. RECENT TABLE (Bottom)
st.markdown("### 📋 Recent Logs")
st.dataframe(
    my_data.sort_values(by="Date", ascending=False).head(5),
    use_container_width=True,
    hide_index=True
)
