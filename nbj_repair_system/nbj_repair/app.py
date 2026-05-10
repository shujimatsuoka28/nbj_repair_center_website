from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = "nbjsecret"

# 1. Database Connection Configuration
def get_db_connection():
    return mysql.connector.connect(
        host="nbj-db-eac-90f2.k.aivencloud.com",
        port=15200,
        user="avnadmin",
        password="AVNS_MqFJx335YPQw4FubVkz",
        database="defaultdb"
    )

# 2. SELF-REPAIR: Runs once to ensure the table exists
def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                password VARCHAR(50) NOT NULL,
                fullname VARCHAR(100),
                role VARCHAR(20)
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO users (username, password, fullname, role) 
                VALUES ('admin', 'admin123', 'NBJ Admin', 'admin')
            """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database setup error: {e}")

setup_database()

# 3. ROUTES
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['fullname'] = user['fullname']
            
            if user['role'] == 'admin':
                return redirect('/admin-dashboard')
            else:
                return redirect('/customer-dashboard')

        flash('Invalid username or password', 'danger')
        return redirect('/')
    except Exception as e:
        return f"Database error: {e}"

@app.route('/admin-dashboard')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        return f"<h1>Admin Dashboard</h1><p>Welcome, {session.get('fullname')}!</p><a href='/logout'>Logout</a>"
    return redirect('/')

@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' in session:
        return f"<h1>Customer Dashboard</h1><p>Welcome, {session.get('fullname')}!</p><a href='/logout'>Logout</a>"
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
