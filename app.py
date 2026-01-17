import streamlit as st
import sqlite3
import datetime
import pandas as pd
import speech_recognition as sr
import io
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment

st.set_page_config(page_title="Nia Rice Mill Pro", page_icon="🌾", layout="wide")

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

# --- SIDEBAR (SETTINGS) ---
with st.sidebar:
    st.header("⚙️ Settings")
    rate = st.number_input("Aaj ka Rate (₹/kg)", value=25.0, step=0.5)
    st.info(f"Current Rate: ₹{rate}/kg")
    if st.button("🗑️ Reset Database (DANGER)"):
        conn = get_connection()
        conn.execute("DELETE FROM records")
        conn.commit()
        conn.close()
        st.warning("Sab kuch delete ho gaya!")

# --- MAIN APP ---
st.title("🌾 Nia Rice Mill Manager")
st.markdown(f"**Date:** {datetime.date.today().strftime('%d-%m-%Y')}")

# --- 1. DASHBOARD (AAJ KA HISAAB) ---
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM records", conn)
conn.close()

# Sirf Aaj ka data filter karo
today_str = datetime.date.today().strftime("%Y-%m-%d")
df_today = df[df['date'] == today_str]

# Metrics dikhao
col1, col2, col3 = st.columns(3)
total_weight = df_today['weight'].sum()
total_money = df_today['price'].sum()
trucks = len(df_today)

col1.metric("📦 Aaj ka Dhaan", f"{total_weight} Kg")
col2.metric("💰 Aaj ki Dindari", f"₹{total_money:,.0f}")
col3.metric("🚚 Total Entries", f"{trucks}")

st.markdown("---")

# --- 2. VOICE ENTRY SECTION ---
c1, c2 = st.columns([1, 2])

with c1:
    st.subheader("🎙️ Bolkar Entry")
    audio = mic_recorder(start_prompt="🔴 Start (Mic)", stop_prompt="⏹️ Stop", key='recorder')

with c2:
    st.subheader("⌨️ Likhkar Entry")
    manual_w = st.number_input("Wazan (Kg)", min_value=0.0, step=0.5, label_visibility="collapsed")
    if st.button("Save Manual Entry"):
        if manual_w > 0:
            conn = get_connection()
            t_price = manual_w * rate
            now = datetime.datetime.now()
            conn.execute('INSERT INTO records (date, time, weight, price) VALUES (?, ?, ?, ?)', 
                      (now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), manual_w, t_price))
            conn.commit()
            conn.close()
            st.success("Saved!")
            st.rerun()

# --- VOICE LOGIC ---
if audio:
    try:
        # Convert WebM -> WAV
        webm_data = audio['bytes']
        sound = AudioSegment.from_file(io.BytesIO(webm_data))
        wav_buffer = io.BytesIO()
        sound.export(wav_buffer, format="wav")
        wav_buffer.seek(0)

        # Listen
        r = sr.Recognizer()
        with sr.AudioFile(wav_buffer) as source:
            audio_file = r.record(source)
            text = r.recognize_google(audio_file, language="hi-IN")
            
            # Number Logic
            numbers = [float(s) for s in text.split() if s.replace('.', '', 1).isdigit()]
            
            if numbers:
                wazan = numbers[0]
                total_price = wazan * rate
                
                # Save to DB
                conn = get_connection()
                now = datetime.datetime.now()
                conn.execute('INSERT INTO records (date, time, weight, price) VALUES (?, ?, ?, ?)', 
                          (now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), wazan, total_price))
                conn.commit()
                conn.close()
                
                st.toast(f"✅ Saved: {wazan} kg", icon="🎉")
                st.rerun() # Page refresh karo taaki table update ho jaye
            else:
                st.error(f"❌ Number nahi mila. Suna: '{text}'")
    except Exception as e:
        st.error(f"Error: {e}")

# --- 3. RECENT ENTRIES & DELETE ---
st.markdown("---")
st.subheader("📜 Haal Hi Ki Entries (Delete karne ke liye box tick karein)")

if not df.empty:
    # Delete Logic
    for index, row in df.sort_values(by='id', ascending=False).head(10).iterrows():
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
        c1.write(f"**{row['time']}**")
        c2.write(f"{row['weight']} Kg")
        c3.write(f"₹{row['price']}")
        
        # Har row ke aage delete button
        if c5.button("❌", key=row['id']):
            conn = get_connection()
            conn.execute("DELETE FROM records WHERE id=?", (row['id'],))
            conn.commit()
            conn.close()
            st.warning("Entry Delete Ho Gayi!")
            st.rerun()
else:
    st.info("Abhi koi data nahi hai.")
