import sqlite3
import datetime

# --- DATABASE SETUP ---
# 1. Database se connect karo (Agar file nahi hai to khud ban jayegi)
conn = sqlite3.connect('rice_mill.db')
cursor = conn.cursor()

# 2. Table banao (Jisme data save hoga)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        time TEXT,
        weight REAL,
        price REAL
    )
''')
conn.commit()

print("--- Nia Rice Mill (Smart Database Manager) ---")

try:
    # --- INPUT ---
    weight = float(input("🌾 Dhaan ka wazan (kg mein) batayein: "))
    rate = 25  # Rate fix hai
    price = weight * rate
    
    # --- DATE & TIME ---
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    # --- SAVE TO DATABASE ---
    cursor.execute('INSERT INTO records (date, time, weight, price) VALUES (?, ?, ?, ?)', 
                   (date_str, time_str, weight, price))
    conn.commit()
    
    print(f"\n✅ Data Save Ho Gaya!")
    print(f"💰 Total Daam: ₹{price}")
    print(f"📅 Date: {date_str} | ⏰ Time: {time_str}")

    # --- SHOW HISTORY (BONUS) ---
    # Ye niche wala code pichle 3 record dikhayega taaki confirm ho jaye
    print("\n📜 --- Pichle 3 Entries ---")
    cursor.execute('SELECT * FROM records ORDER BY id DESC LIMIT 3')
    rows = cursor.fetchall()
    
    if not rows:
        print("Abhi koi purana record nahi hai.")
    else:
        for row in rows:
            # Row format: (id, date, time, weight, price)
            print(f"ID:{row[0]} | {row[1]} | {row[3]} kg | ₹{row[4]}")

except ValueError:
    print("❌ Galti: Kripya sahi number daalein.")
finally:
    conn.close()
