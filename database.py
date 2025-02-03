import sqlite3

def init_db():
    conn = sqlite3.connect('stations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stations (
            user_id INTEGER,
            stop_number TEXT,
            stop_name TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            user_id INTEGER,
            message_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def add_station(user_id, stop_number, stop_name):
    conn = sqlite3.connect('stations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO stations (user_id, stop_number, stop_name) VALUES (?, ?, ?)',
                   (user_id, stop_number, stop_name))
    conn.commit()
    conn.close()

def get_stations(user_id):
    conn = sqlite3.connect('stations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stop_number, stop_name FROM stations WHERE user_id = ?', (user_id,))
    stations = cursor.fetchall()
    conn.close()
    return stations

def delete_station(user_id, stop_number):
    conn = sqlite3.connect('stations.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM stations WHERE user_id = ? AND stop_number = ?', (user_id, stop_number))
    conn.commit()
    conn.close()

def add_message(user_id, message_id):
    conn = sqlite3.connect('stations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (user_id, message_id) VALUES (?, ?)',
                   (user_id, message_id))
    conn.commit()
    conn.close()

def get_message_id(user_id):
    conn = sqlite3.connect('stations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_id FROM messages WHERE user_id = ?', (user_id,))
    message_id = cursor.fetchone()
    conn.close()
    return message_id

def delete_message_id(user_id):
    conn = sqlite3.connect('stations.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
