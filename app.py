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

# --- FUNCTION 1: SMART LOGIN CHECK (Updated) ---
def check_login(username, password):
    try:
        # 'Users' tab se data padho
        users_df = conn_gsheets.read(worksheet="Users")
        
        # Username match karo
        users_df['Username'] = users_df['Username'].astype(str)
        user = users_df[users_df['Username'] == str(username)]
        
        if not user.empty:
            stored_password = str(user.iloc[0]['Password'])
            
            # --- SMART ACTIVE CHECK ---
            raw_active = user.iloc[0]['Is_Active']
            # Ye convert karega: Tick/True/1 -> 'TRUE'
            status_str = str(raw_active).strip().upper()
            
            # Password Match
            if str(password) == stored_password:
                # Agar TRUE, 1, 1.0, YES ya Tick hai -> Login OK
                if status_str in ['TRUE', '1', '1.0', 'YES', 'ON']:
                    return user.iloc[0].to_dict()
                else:
                    return "BLOCKED" # Agar FALSE ya Khali hai
                    
        return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

# --- FUNCTION 2: SAVE DATA ---
def save_data_secure(wazan, price):
    now = datetime.datetime.now()
    d_date = now.strftime("%Y-%m-%d")
    d_time = now.strftime("%H:%M:%S")
    
    my_mill_id = st.session_state.user_info['Mill_ID']
    munim_name = st.session_state.user_info['Name']

    try:
        conn = sqlite3.connect('rice_mill.db')
        conn.execute('INSERT INTO records (date, time, weight, price, mill_id) VALUES (?, ?, ?, ?, ?)', 
                  (d_date, d_time, wazan, price, my_mill_id))
        conn.commit()
        conn.close()
    except:
        pass

    try:
        new_data = pd.DataFrame(
            [[my_mill_id, d_date, d_time, wazan, price, munim_name]], 
            columns=['Mill_ID', 'Date', 'Time', 'Weight', 'Price', 'EntryBy']
        )
        existing_data = conn_gsheets.read() 
        updated_df = pd.concat([existing_data, new_data], ignore_index=True)
        conn_gsheets.update(data=updated_df)
        st.toast(f"✅ Entry Saved by {munim_name}", icon="☁️")
        return True
    except Exception as e:
        st.error(f"Cloud Save Error: {e}")
        return False

# ==========================================
# 🔐 LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔒 Nia Rice Mill Login</h1>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login 🚀", type="primary", use_container_width=True)
            
            if submit:
                user_data = check_login(username, password)
                
                if user_data == "BLOCKED":
                    st.error("🚫 Aapka account Active nahi hai. (Is_Active check karein)")
                elif user_data:
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_data
                    st.success(f"Swagat hai {user_data['Name']}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Galat Username ya Password")
    st.stop()

# ==========================================
# 🌾 MAIN DASHBOARD
# ==========================================
st.markdown(f"### 🏭 {st.session_state.user_info['Mill_ID']} | 👤 {st.session_state.user_info['Name']}")
if st.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()
st.markdown("---")

# Entry Section
if st.session_state.user_info['Role'] in ['Munim', 'Owner', 'Operator']:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.info("🎙️ Entry ke liye mic dabayein...")
        if st.session_state.step == 1:
            audio = mic_recorder(start_prompt="🔴 Start", stop_prompt="⏹️ Stop", key='rec1')
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
                    st.error("Awaaz saaf nahi thi.")

        elif st.session_state.step == 2:
            w = st.session_state.pending_weight
            msg = f"Kya {w} kilo save karoon?"
            st.success(f"🗣️ AI: {msg}")
            speak(msg)
            col_a, col_b = st.columns(2)
            if col_a.button("✅ HAAN", use_container_width=True, type="primary"):
                save_data_secure(w, w * 25.0)
                speak("Entry ho gayi.")
                time.sleep(2)
                st.session_state.step = 1
                st.rerun()
            if col_b.button("❌ NAHI", use_container_width=True):
                st.session_state.step = 1
                st.rerun()

# Data View
st.markdown("---")
try:
    all_data = conn_gsheets.read()
    my_data = all_data[all_data['Mill_ID'] == st.session_state.user_info['Mill_ID']]
    if not my_data.empty:
        st.subheader("📋 Recent Entries")
        st.dataframe(my_data.tail(5))
except:
    pass
