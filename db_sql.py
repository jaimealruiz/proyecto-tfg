import sqlite3

conn = sqlite3.connect('datos.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS conocimiento (
    id INTEGER PRIMARY KEY,
    pregunta TEXT,
    respuesta TEXT
)
''')

cursor.execute('''
INSERT INTO conocimiento (pregunta, respuesta)
VALUES ('¿Cuál es la capital de España?', 'La capital de España es Madrid.')
''')

conn.commit()
conn.close()
