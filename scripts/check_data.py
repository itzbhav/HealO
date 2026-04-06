# Save as scripts/check_data.py
import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('healo.db')
df = pd.read_sql_query("""
    SELECT * FROM messages 
    ORDER BY timestamp DESC 
    LIMIT 50
""", conn)

print("📱 Recent messages:")
print(df[['phone', 'message', 'direction', 'timestamp']])

# Basic stats
print("\n📊 Patient activity:")
phone_stats = df.groupby('phone').agg({
    'timestamp': ['count', 'nunique'],
    'direction': lambda x: (x=='outbound').sum()
}).round(0)
print(phone_stats)