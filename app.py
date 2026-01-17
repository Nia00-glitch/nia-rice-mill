import streamlit as st
import sqlite3
import datetime
import pandas as pd
import speech_recognition as sr
import io
import os
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
from gtts import gTTS # App ki Awaaz

st.set_page_config(page_title="Nia Rice Mill AI", page_icon="🌾", layout="wide")

# --- SESSION STATE (App ki Yaadasht) ---
if 'step' not in st.session_state:
    st.session_state.step = 1  # 1 = Sunna, 2 = Confirm karna
if 'pending_weight' not in st.session_state:
    st.session_state.pending_weight = None

# --- DATABASE CONNECTION ---
def get_connection():
    return sqlite3.connect('rice_mill.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT, time TEXT, weight REAL, price REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER: App Bolegi ---
def speak(text):
    try:
        tts = gTTS(text=text, lang='hi')
        filename = "temp_audio.mp3"
        tts.save(filename)
        # Hidden audio player jo khud bajega
        st.audio(filename, format="audio/mp3", autoplay=True)
    except:
        pass # Agar audio fail ho jaye toh error mat dikhao

# --- SIDEBAR (Admin) ---
with st.sidebar:
    if st.button("🔄 Refresh / Reset App"):
        st.session_state.step = 1
        st.session_state.pending_weight = None
        st.rerun()

# --- MAIN APP ---
st.title("🌾 Nia Rice Mill AI")

# --- STEP 1: VOICE INPUT (Sunne ka kaam) ---
if st.session_state.step == 1:
    st.info("🎙️ Niche Mic dabayein aur Wazan bolein...")
    
    # Mic Button
    c1, c2 = st.columns([1, 4])
    with c1:
        audio = mic_recorder(start_prompt="🔴 Start", stop_prompt="⏹️ Stop", key='recorder_step1')
    
    if audio:
        try:
            # Convert Audio
            webm_data = audio['bytes']
            sound = AudioSegment.from_file(io.BytesIO(webm_data))
            wav_buffer = io.BytesIO()
            sound.export(wav_buffer, format="wav")
            wav_buffer.seek(0)

            # Recognize
            r = sr.Recognizer()
            with sr.AudioFile(wav_buffer) as source:
                audio_file = r.record(source)
                text = r.recognize_google(audio_file, language="hi-IN")
                
                # Number Logic
                numbers = [float(s) for s in text.split() if s.replace('.', '', 1).isdigit()]
                
                if numbers:
                    wazan = numbers[0]
                    # STATE CHANGE: Ab Step 2 par jao
                    st.session_state.pending_weight = wazan
                    st.session_state.step = 2
                    st.rerun() # Page reload karo taaki Step 2 dikhe
                else:
                    st.error(f"Number nahi mila. (Suna: {text})")
        except Exception as e:
            st.error("Awaaz saaf nahi thi. Dobara koshish karein.")

# --- STEP 2: CONFIRMATION (Puchne ka kaam) ---
elif st.session_state.step == 2:
    wazan = st.session_state.pending_weight
    
    # App Bolegi
    msg = f"Kya main {wazan} kilo save kar doon?"
    st.success(f"🗣️ AI Puch raha hai: **'{msg}'**")
    speak(msg)
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    # HAAN Button
    if c1.button("✅ HAAN (Save)", type="primary", use_container_width=True):
        conn = get_connection()
        rate = 25 # Rate fix kar sakte hain ya DB se le sakte hain
        total_price = wazan * rate
        now = datetime.datetime.now()
        conn.execute('INSERT INTO records (date, time, weight, price) VALUES (?, ?, ?, ?)', 
                  (now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), wazan, total_price))
        conn.commit()
        conn.close()
        
        st.toast(f"Saved: {wazan} kg")
        speak(f"Theek hai, {wazan} kilo save ho gaya.")
        
        # Reset to Step 1
        st.session_state.step = 1
        st.session_state.pending_weight = None
        import time
        time.sleep(2) # Thoda ruko taaki audio sunayi de
        st.rerun()

    # NAHI Button
    if c2.button("❌ NAHI (Cancel)", use_container_width=True):
        speak("Cancel kar diya.")
        st.session_state.step = 1
        st.session_state.pending_weight = None
        st.rerun()

# --- DATA TABLE ---
st.markdown("---")
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM records ORDER BY id DESC LIMIT 5", conn)
conn.close()
st.table(df)
