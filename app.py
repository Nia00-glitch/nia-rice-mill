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

st.set_page_config(page_title="Nia Rice Mill AI", page_icon="🌾", layout="wide")

try:
    conn_gsheets = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("⚠️ Internet Error.")
    st.stop()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pending_weight' not in st.session_state:
    st.session_state.pending_weight = None

def speak(text):
    try:
        tts = gTTS(text=text, lang='hi')
        tts.save("temp.mp3")
        st.audio("temp.mp3", format="audio/mp3", autoplay=True)
    except:
        pass

# --- ROBUST ACTIVATION FUNCTION ---
def activate_account(mill_id, secret_code, new_user, new_pass, name):
    try:
        df = conn_gsheets.read(worksheet="Users")
        
        # 1. Header Cleaning (Space hatana)
        df.columns = df.columns.str.strip()
        
        # 2. Handle Spelling Mistake (Secret_Cod vs Secret_Code)
        if 'Secret_Code' not in df.columns and 'Secret_Cod' in df.columns:
            df.rename(columns={'Secret_Cod': 'Secret_Code'}, inplace=True)
            
        # 3. Data Cleaning (1234.0 -> 1234 fix)
        df['Mill_ID'] = df['Mill_ID'].astype(str).str.strip()
        
        # Convert Secret Code to string, remove .0, and strip spaces
        df['Secret_Code'] = df['Secret_Code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        # Input Cleaning
        input_mill = str(mill_id).strip()
        input_code = str(secret_code).strip()
        
        # Debugging Info (Screen par dikhega agar error aaye)
        # st.write("Searching for:", input_mill, input_code)
        # st.write("Data in Sheet:", df[['Mill_ID', 'Secret_Code']].head())
        
        # Matching
        mask = (df['Mill_ID'] == input_mill) & (df['Secret_Code'] == input_code)
        
        if df[mask].empty:
            return "INVALID_CODE"
        
        row_index = df[mask].index[0]
        
        # Check if already registered
        current_user = str(df.at[row_index, 'Username'])
        if current_user != "nan" and current_user.strip() != "":
            return "ALREADY_REGISTERED"
            
        # Update Data
        df.at[row_index, 'Username'] = new_user
        df.at[row_index, 'Password'] = new_pass
        df.at[row_index, 'Name'] = name
        df.at[row_index, 'Is_Active'] = "TRUE"
        
        conn_gsheets.update(worksheet="Users", data=df)
        return "SUCCESS"
        
    except Exception as e:
        return f"Error: {str(e)}"

# --- LOGIN ---
def check_login(username, password):
    try:
        users_df = conn_gsheets.read(worksheet="Users")
        users_df.columns = users_df.columns.str.strip() # Header fix
        
        users_df['Username'] = users_df['Username'].astype(str).str.strip()
        user = users_df[users_df['Username'] == str(username).strip()]
        
        if not user.empty:
            stored_password = str(user.iloc[0]['Password']).strip()
            raw_active = user.iloc[0]['Is_Active']
            status_str = str(raw_active).strip().upper()
            
            # Smart Active Check (TRUE/Tick/1)
            is_active_bool = status_str in ['TRUE', '1', '1.0', 'YES', 'ON']
            
            if str(password).strip() == stored_password:
                if is_active_bool:
                    return user.iloc[0].to_dict()
                else:
                    return "BLOCKED"
        return None
    except:
        return None

# --- SAVE DATA ---
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
    except: pass

    try:
        new_data = pd.DataFrame([[my_mill_id, d_date, d_time, wazan, price, munim]], 
            columns=['Mill_ID', 'Date', 'Time', 'Weight', 'Price', 'EntryBy'])
        existing = conn_gsheets.read() 
        updated = pd.concat([existing, new_data], ignore_index=True)
        conn_gsheets.update(data=updated)
        st.toast("✅ Saved!", icon="💾")
        return True
    except: return False

# ==========================================
# AUTH SCREEN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🌾 Nia Rice Mill SaaS</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔑 Login", "✨ Activate Account"])
    
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

    with tab2:
        st.info("ℹ️ Naye user yahan setup karein.")
        ac1, ac2 = st.columns(2)
        with ac1:
            act_mill_id = st.text_input("Mill ID")
            act_code = st.text_input("Secret Code", type="password")
        with ac2:
            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            new_name = st.text_input("Your Name")
            
        if st.button("🚀 Activate"):
            if act_mill_id and act_code and new_user and new_pass:
                with st.spinner("Checking..."):
                    status = activate_account(act_mill_id, act_code, new_user, new_pass, new_name)
                    if status == "SUCCESS":
                        st.balloons()
                        st.success("✅ Account Activated! Ab Login karein.")
                    elif status == "ALREADY_REGISTERED":
                        st.warning("Ye account pehle se bana hua hai.")
                    elif status == "INVALID_CODE":
                        st.error("❌ Invalid ID or Code. Check Sheet spelling.")
                    else:
                        st.error(status)
            else:
                st.warning("Sabhi fields bharein.")
    st.stop()

# ==========================================
# MAIN DASHBOARD
# ==========================================
st.markdown(f"### 🏭 {st.session_state.user_info['Mill_ID']} | 👤 {st.session_state.user_info['Name']}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()
st.divider()

c1, c2 = st.columns([1, 2])
with c1:
    st.subheader("🎙️ Entry")
    if st.session_state.step == 1:
        audio = mic_recorder(start_prompt="🔴 Rec", stop_prompt="⏹️ Stop", key='rec1')
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
            except: pass
            
    elif st.session_state.step == 2:
        w = st.session_state.pending_weight
        st.success(f"⚖️ {w} kg")
        if st.button("✅ SAVE"):
            save_data_secure(w, st.session_state.current_rate)
            time.sleep(1)
            st.session_state.step = 1
            st.rerun()
        if st.button("❌ CANCEL"):
            st.session_state.step = 1
            st.rerun()

with c2:
    try:
        df = conn_gsheets.read()
        my_df = df[df['Mill_ID'] == st.session_state.user_info['Mill_ID']]
        st.dataframe(my_df.tail(5), hide_index=True)
    except: pass
