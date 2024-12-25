import sqlite3
import pandas as pd

conn = sqlite3.connect('models_sorted.db')

query = "SELECT * FROM models_sorted ORDER BY last_online DESC"

df = pd.read_sql_query(query, conn)

df.to_excel('models_sorted.xlsx', index=False)

conn.close()

print("Data has been exported to 'models_sorted.xlsx'")
