import streamlit as st
import sqlite3
import datetime
import pandas as pd
import speech_recognition as sr
import io
import os
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
from gtts import gTTS
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Nia Rice Mill AI", page_icon="🌾", layout="wide")

# --- CONNECT TO GOOGLE SHEET ---
conn_gsheets = st.connection("gsheets", type=GSheetsConnection)

# --- SESSION STATE ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pending_weight' not in st.session_state:
    st.session_state.pending_weight = None

# --- FUNCTION: SAVE DATA (Local + Google Sheet) ---
def save_data_everywhere(wazan, price):
    now = datetime.datetime.now()
    d_date = now.strftime("%Y-%m-%d")
    d_time = now.strftime("%H:%M:%S")

    # 1. Local Database (App ke liye)
    conn = sqlite3.connect('rice_mill.db')
    conn.execute('INSERT INTO records (date, time, weight, price) VALUES (?, ?, ?, ?)', 
              (d_date, d_time, wazan, price))
    conn.commit()
    conn.close()

    # 2. Google Sheet (Permanent Backup)
    try:
        # Naya data create karo
        new_data = pd.DataFrame(
            [[d_date, d_time, wazan, price]], 
            columns=['Date', 'Time', 'Weight', 'Price']
        )
        
        # Purana data padho
        existing_data = conn_gsheets.read()
        
        # Dono ko jodo
        updated_df = pd.concat([existing_data, new_data], ignore_index=True)
        
        # Wapas Sheet par update kar do
        conn_gsheets.update(data=updated_df)
        st.toast("✅ Google Sheet Updated!", icon="☁️")
        
    except Exception as e:
        st.error(f"⚠️ Sheet Error: {e}")

# --- HELPER: AI SPEAK ---
def speak(text):
    try:
        tts = gTTS(text=text, lang='hi')
        tts.save("temp.mp3")
        st.audio("temp.mp3", format="audio/mp3", autoplay=True)
    except:
        pass

# --- MAIN APP UI ---
st.title("🌾 Nia Rice Mill AI")

# --- STEP 1: SUNO ---
if st.session_state.step == 1:
    st.info("🎙️ Mic dabayein aur bolein...")
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
            st.error("Samajh nahi aaya.")

# --- STEP 2: PUCHO ---
elif st.session_state.step == 2:
    w = st.session_state.pending_weight
    msg = f"Kya main {w} kilo save kar doon?"
    st.success(f"🗣️ AI: {msg}")
    speak(msg)
    
    c1, c2 = st.columns(2)
    if c1.button("✅ HAAN (Save)", type="primary", use_container_width=True):
        # Yahan humne naya function lagaya hai
        save_data_everywhere(w, w * 25.0) 
        
        speak("Save ho gaya.")
        st.session_state.step = 1
        st.rerun()
        
    if c2.button("❌ NAHI", use_container_width=True):
        st.session_state.step = 1
        st.rerun()

# --- TABLE ---
st.markdown("---")
conn = sqlite3.connect('rice_mill.db')
st.table(pd.read_sql("SELECT * FROM records DESC LIMIT 5", conn))
conn.close()
