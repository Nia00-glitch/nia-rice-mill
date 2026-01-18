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

# Page Config
st.set_page_config(page_title="Nia Rice Mill AI", page_icon="🌾", layout="wide")

# --- CONNECT ---
try:
    conn_gsheets = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("⚠️ Internet Error.")
    st.stop()

# --- SESSION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pending_weight' not in st.session_state:
    st.session_state.pending_weight = None

# --- SPEAK ---
def speak(text):
    try:
        tts = gTTS(text=text, lang='hi')
        tts.save("temp.mp3")
        st.audio("temp.mp3", format="audio/mp3", autoplay=True)
    except:
        pass

# --- FUNCTION: ACTIVATE ACCOUNT (New) ---
def activate_account(mill_id, secret_code, new_user, new_pass, name):
    try:
        df = conn_gsheets.read(worksheet="Users")
        
        # Data Cleaning for matching
        df['Mill_ID'] = df['Mill_ID'].astype(str).str.strip()
        df['Secret_Code'] = df['Secret_Code'].astype(str).str.strip()
        
        # Check agar ye Mill ID aur Secret Code match karta hai
        mask = (df['Mill_ID'] == str(mill_id)) & (df['Secret_Code'] == str(secret_code))
        
        if df[mask].empty:
            return "INVALID_CODE"
        
        # Check agar pehle se Registered hai (Username bhara hua hai)
        current_user = df.loc[mask, 'Username'].values[0]
        if pd.notna(current_user) and str(current_user).strip() != "":
            return "ALREADY_REGISTERED"
            
        # UPDATE THE ROW
        # Hum puri row update karenge
        row_index = df[mask].index[0]
        df.at[row_index, 'Username'] = new_user
        df.at[row_index, 'Password'] = new_pass
        df.at[row_index, 'Name'] = name
        df.at[row_index, 'Is_Active'] = "TRUE" # Activate kar do
        
        # Wapas Sheet mein likho
        conn_gsheets.update(worksheet="Users", data=df)
        return "SUCCESS"
        
    except Exception as e:
        return f"Error: {str(e)}"

# --- FUNCTION: LOGIN ---
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
                if status_str in ['TRUE', '1', 'YES']:
                    return user.iloc[0].to_dict()
                else:
                    return "BLOCKED"
        return None
    except:
        return None

# --- FUNCTION: SAVE DATA ---
def save_data_secure(wazan, rate):
    now = datetime.datetime.now()
    d_date = now.strftime("%Y-%m-%d")
    d_time = now.strftime("%H:%M:%S")
    my_mill_id = st.session_state.user_info['Mill_ID']
    munim = st.session_state.user_info['Name']
    price = (wazan / 100.0) * rate

    try:
        conn = sqlite3.connect('rice_mill.db')
        conn.execute('INSERT INTO records (date, time, weight, price, mill_id) VALUES (?, ?, ?, ?, ?)', 
                  (d_date, d_time, wazan, price, my_mill_id))
        conn.commit()
        conn.close()
    except:
        pass

    try:
        new_data = pd.DataFrame([[my_mill_id, d_date, d_time, wazan, price, munim]], 
            columns=['Mill_ID', 'Date', 'Time', 'Weight', 'Price', 'EntryBy'])
        existing = conn_gsheets.read() 
        updated = pd.concat([existing, new_data], ignore_index=True)
        conn_gsheets.update(data=updated)
        st.toast("✅ Saved!", icon="💾")
        return True
    except:
        return False

# ==========================================
# 🔐 AUTHENTICATION SCREEN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🌾 Nia Rice Mill SaaS</h1>", unsafe_allow_html=True)
    
    # TABS: Login vs Activation
    tab1, tab2 = st.tabs(["🔑 Login (Purane User)", "✨ Account Activate (Naye User)"])
    
    # --- TAB 1: LOGIN ---
    with tab1:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login", type="primary", use_container_width=True):
                    res = check_login(u, p)
                    if res == "BLOCKED": st.error("Account Locked.")
                    elif res:
                        st.session_state.logged_in = True
                        st.session_state.user_info = res
                        st.session_state.current_rate = 2500.0
                        st.rerun()
                    else: st.error("Galat Username/Password")

    # --- TAB 2: ACTIVATION (Privacy Solution) ---
    with tab2:
        st.info("ℹ️ Agar aap pehli baar aaye hain, toh yahan apna account banayein.")
        ac1, ac2 = st.columns(2)
        
        with ac1:
            # Ye info hum denge (Onboarding Kit)
            act_mill_id = st.text_input("Mill ID (Provided by Admin)")
            act_code = st.text_input("Secret Code (Provided by Admin)", type="password")
        
        with ac2:
            # Ye user khud set karega (Privacy)
            new_user = st.text_input("Apna Naya Username Set Karein")
            new_pass = st.text_input("Apna Naya Password Set Karein", type="password")
            new_name = st.text_input("Aapka Naam (Display Name)")
            
        if st.button("🚀 Account Activate Karein", use_container_width=True):
            if act_mill_id and act_code and new_user and new_pass:
                status = activate_account(act_mill_id, act_code, new_user, new_pass, new_name)
                
                if status == "SUCCESS":
                    st.success("🎉 Account Ban Gaya! Ab 'Login' tab mein jakar login karein.")
                    st.balloons()
                elif status == "ALREADY_REGISTERED":
                    st.warning("Ye Account pehle se bana hua hai. Login karein.")
                elif status == "INVALID_CODE":
                    st.error("❌ Galat Mill ID ya Secret Code.")
            else:
                st.warning("Sabhi fields bharein.")
    
    st.stop()

# ==========================================
# 🏭 MAIN APP (Dashboard)
# ==========================================
st.markdown(f"### 🏭 {st.session_state.user_info['Mill_ID']} | 👤 {st.session_state.user_info['Name']}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()
st.divider()

# --- ENTRY & DASHBOARD ---
c1, c2 = st.columns([1, 2])

with c1:
    st.subheader("🎙️ Voice Entry")
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
            except: st.warning("Retry")
            
    elif st.session_state.step == 2:
        w = st.session_state.pending_weight
        st.success(f"⚖️ {w} kg")
        btn1, btn2 = st.columns(2)
        if btn1.button("✅ Save"):
            save_data_secure(w, st.session_state.current_rate)
            time.sleep(1)
            st.session_state.step = 1
            st.rerun()
        if btn2.button("❌ Cancel"):
            st.session_state.step = 1
            st.rerun()

with c2:
    st.subheader("📊 Live Data")
    try:
        df = conn_gsheets.read()
        my_df = df[df['Mill_ID'] == st.session_state.user_info['Mill_ID']]
        st.dataframe(my_df.tail(5), hide_index=True, use_container_width=True)
    except: pass
