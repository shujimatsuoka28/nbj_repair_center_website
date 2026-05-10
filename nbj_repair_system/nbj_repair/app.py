from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
import os
from datetime import date

app = Flask(__name__)
app.secret_key = "nbjsecret"

# 1. Database Connection
def get_db_connection():
    return mysql.connector.connect(
        host="nbj-db-eac-90f2.k.aivencloud.com",
        port=15200,
        user="avnadmin",
        password="AVNS_MqFJx335YPQw4FubVkz",
        database="defaultdb"
    )

# 2. Database Initialization (Creates tables if they don't exist)
def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(50) NOT NULL,
                fullname VARCHAR(100),
                role VARCHAR(20)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repairs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tracking_number VARCHAR(50),
                customer_name VARCHAR(100),
                item_name VARCHAR(100),
                item_brand VARCHAR(100),
                status VARCHAR(50) DEFAULT 'Repairing',
                date_received DATE,
                estimated_completion DATE,
                repair_cost DECIMAL(10,2) DEFAULT 0.0,
                user_id INT
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, password, fullname, role) VALUES ('admin', 'admin123', 'NBJ Admin', 'admin')")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"DB Setup Error: {e}")

setup_database()

# --- ROUTES ---

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
            # Redirect to the function names defined below
            return redirect(url_for('admin_dashboard') if user['role'] == 'admin' else url_for('customer_dashboard'))
        
        flash('Invalid username or password', 'danger')
        return redirect(url_for('login_page'))
    except Exception as e:
        return f"Database Error: {e}"

@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs")
    repairs = cursor.fetchall()
    
    # Logic for the stat cards in your dashboard.html
    stats = {
        'total': len(repairs),
        'ongoing': sum(1 for r in repairs if r['status'] == 'Repairing'),
        'completed': sum(1 for r in repairs if r['status'] == 'Completed'),
        'released': sum(1 for r in repairs if r['status'] == 'Released')
    }
    cursor.close()
    conn.close()
    # This renders your actual dashboard.html file
    return render_template('dashboard.html', repairs=repairs, **stats)

@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs WHERE user_id=%s", (session['user_id'],))
    repairs = cursor.fetchall()
    cursor.close()
    conn.close()
    # This renders your actual customer_dashboard.html file
    return render_template('customer_dashboard.html', repairs=repairs)

@app.route('/add-repair')
def add_repair():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    return render_template('add_repair.html', today=date.today())

@app.route('/repair-history')
def repair_history():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    return render_template('repair_history.html')

@app.route('/manage-accounts')
def manage_accounts():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    return render_template('manage_accounts.html')

@app.route('/track')
def track():
    return render_template('track.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
