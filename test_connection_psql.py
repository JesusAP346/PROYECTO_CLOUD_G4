import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,               # el que abriste con el túnel SSH
    dbname="cloud_proyecto",       # cambia si usas otra DB
    user="postgres",         # tu usuario de PostgreSQL
    password="#"   # contraseña del usuario
)

cur = conn.cursor()
cur.execute("SELECT version();")
print(cur.fetchone())

cur.close()
conn.close()
