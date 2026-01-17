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

# --- CONNECTION ---
try:
    conn_gsheets = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Internet connection check karein.")

# --- SESSION ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pending_weight' not in st.session_state:
    st.session_state.pending_weight = None

# --- SAVE FUNCTION (Silent & Fast) ---
def save_data_final(wazan, price):
    now = datetime.datetime.now()
    d_date = now.strftime("%Y-%m-%d")
    d_time = now.strftime("%H:%M:%S")

    # 1. Local DB
    try:
        conn = sqlite3.connect('rice_mill.db')
        conn.execute('INSERT INTO records (date, time, weight, price) VALUES (?, ?, ?, ?)', 
                  (d_date, d_time, wazan, price))
        conn.commit()
        conn.close()
    except:
        pass

    # 2. Google Sheet (Live)
    try:
        new_data = pd.DataFrame(
            [[d_date, d_time, wazan, price]], 
            columns=['Date', 'Time', 'Weight', 'Price']
        )
        existing_data = conn_gsheets.read()
        updated_df = pd.concat([existing_data, new_data], ignore_index=True)
        conn_gsheets.update(data=updated_df)
        st.toast("✅ Data Cloud par Save ho gaya!", icon="☁️")
        return True
    except Exception as e:
        st.error(f"Backup Error: {e}")
        return False

# --- SPEAK FUNCTION ---
def speak(text):
    try:
        tts = gTTS(text=text, lang='hi')
        tts.save("temp.mp3")
        st.audio("temp.mp3", format="audio/mp3", autoplay=True)
    except:
        pass

# --- MAIN UI ---
st.title("🌾 Nia Rice Mill AI")

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
                else:
                    st.toast("Number sunayi nahi diya.", icon="⚠️")
        except:
            st.toast("Awaaz saaf nahi thi.", icon="⚠️")

elif st.session_state.step == 2:
    w = st.session_state.pending_weight
    msg = f"Kya main {w} kilo save kar doon?"
    st.success(f"🗣️ {msg}")
    speak(msg)
    
    c1, c2 = st.columns(2)
    
    if c1.button("✅ HAAN (Save)", type="primary", use_container_width=True):
        save_data_final(w, w * 25.0)
        speak("Save ho gaya.")
        import time
        time.sleep(2) # Audio sunne ke liye chota pause
        st.session_state.step = 1
        st.rerun()
        
    if c2.button("❌ NAHI", use_container_width=True):
        st.session_state.step = 1
        st.rerun()

# --- RECENT ENTRIES ---
st.markdown("---")
st.subheader("📋 Aakhri 5 Entries")
try:
    conn = sqlite3.connect('rice_mill.db')
    st.table(pd.read_sql("SELECT * FROM records ORDER BY id DESC LIMIT 5", conn))
    conn.close()
except:
    st.write("Abhi koi data nahi hai.")
