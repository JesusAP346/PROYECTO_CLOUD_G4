import psycopg2

def listar_slices():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,   # o el que uses con SSH
            dbname="cloud_proyecto",
            user="postgres",
            password="#"
        )
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, status FROM slices;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[ERROR en listar_slices] {e}")
        return []
