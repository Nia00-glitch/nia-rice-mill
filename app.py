import streamlit as st
import sqlite3
import datetime
import pandas as pd
import speech_recognition as sr
import io
import os
import time  # Time library jodi hai rukne ke liye
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
from gtts import gTTS
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Nia Rice Mill AI Debug", page_icon="🐞", layout="wide")

# --- GOOGLE SHEETS CONNECTION ---
try:
    conn_gsheets = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection Error: {e}")

# --- SESSION STATE ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pending_weight' not in st.session_state:
    st.session_state.pending_weight = None

# --- SAVE DATA FUNCTION (With Error Reporting) ---
def save_data_everywhere(wazan, price):
    status_box = st.empty() # Khali dabba status ke liye
    status_box.info("⏳ Saving data... Please wait.")
    
    now = datetime.datetime.now()
    d_date = now.strftime("%Y-%m-%d")
    d_time = now.strftime("%H:%M:%S")

    # 1. Local Database
    try:
        conn = sqlite3.connect('rice_mill.db')
        conn.execute('INSERT INTO records (date, time, weight, price) VALUES (?, ?, ?, ?)', 
                  (d_date, d_time, wazan, price))
        conn.commit()
        conn.close()
        st.write("✅ Local Database: OK")
    except Exception as e:
        st.error(f"❌ Local DB Error: {e}")

    # 2. Google Sheets (Most likely issue here)
    try:
        new_data = pd.DataFrame(
            [[d_date, d_time, wazan, price]], 
            columns=['Date', 'Time', 'Weight', 'Price']
        )
        # Read Data
        status_box.info("⏳ Reading Google Sheet...")
        existing_data = conn_gsheets.read()
        
        # Update Data
        status_box.info("⏳ Updating Google Sheet...")
        updated_df = pd.concat([existing_data, new_data], ignore_index=True)
        conn_gsheets.update(data=updated_df)
        
        st.success("✅ Google Sheet: OK! (Saved Successfully)")
        return True # Sab sahi hai
    except Exception as e:
        status_box.empty()
        st.error(f"❌ Google Sheet Error: {e}")
        st.warning("Note: Agar '403' ya 'Permission' error hai, toh Sheet Public Editor honi chahiye.")
        return False # Gadbad hai

# --- HELPER: SPEAK ---
def speak(text):
    try:
        tts = gTTS(text=text, lang='hi')
        tts.save("temp.mp3")
        st.audio("temp.mp3", format="audio/mp3", autoplay=True)
    except:
        pass

# --- MAIN APP ---
st.title("🐞 Debug Mode: Nia Rice Mill")

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
            st.error("Awaaz samajh nahi aayi.")

elif st.session_state.step == 2:
    w = st.session_state.pending_weight
    msg = f"Kya main {w} kilo save kar doon?"
    st.info(f"🗣️ AI: {msg}")
    
    c1, c2 = st.columns(2)
    
    # HAAN BUTTON
    if c1.button("✅ HAAN (Save)", type="primary", use_container_width=True):
        # Result ka wait karenge
        is_success = save_data_everywhere(w, w * 25.0)
        
        if is_success:
            speak("Save ho gaya.")
            time.sleep(3) # 3 second ruko taaki user "Success" dekh sake
            st.session_state.step = 1
            st.rerun()
        else:
            speak("Error aaya hai. Screen dekhein.")
            # Hum rerun NAHI karenge taaki aap error padh sakein

    # NAHI BUTTON
    if c2.button("❌ NAHI", use_container_width=True):
        st.session_state.step = 1
        st.rerun()
