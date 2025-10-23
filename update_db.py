import sqlite3

con = sqlite3.connect('src/backend/data/spm.db')

con.execute("UPDATE catalog_almacenes SET centro_codigo = '1500' WHERE id = 1")

con.commit()

con.close()

print("Updated")
