import sqlite3
import bcrypt

conn = sqlite3.connect('backend/test.db')
cursor = conn.cursor()

# Проверяем system_users
cursor.execute('SELECT COUNT(*) FROM system_users')
count = cursor.fetchone()[0]
print(f'System users count: {count}')

if count == 0:
    # Создаем админа
    password = 'admin123'
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    cursor.execute('''
        INSERT INTO system_users (username, email, hashed_password, full_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('admin', 'admin@example.com', hashed, 'Administrator', 'operations_manager', True))

    conn.commit()
    print('Admin user created')
else:
    cursor.execute('SELECT username, role FROM system_users')
    users = cursor.fetchall()
    print('Existing users:', users)

conn.close()
