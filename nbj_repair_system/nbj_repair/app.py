from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
import os
import random
import string
from datetime import date

app = Flask(__name__)
app.secret_key = "nbjsecret"

# --- DATABASE CONNECTION ---
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="nbj-db-eac-90f2.k.aivencloud.com",
            port=15200,
            user="avnadmin",
            password="AVNS_MqFJx335YPQw4FubVkz",
            database="defaultdb",
            ssl_disabled=False # Required for Aiven Cloud
        )
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

# --- DATABASE SETUP ---
def setup_database():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY, 
                    username VARCHAR(50) UNIQUE, 
                    password VARCHAR(50), 
                    fullname VARCHAR(100), 
                    role VARCHAR(20)
                )""")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repairs (
                    id INT AUTO_INCREMENT PRIMARY KEY, 
                    tracking_number VARCHAR(50), 
                    customer_name VARCHAR(100), 
                    contact_number VARCHAR(50),
                    item_name VARCHAR(100), 
                    item_brand VARCHAR(100), 
                    item_model VARCHAR(100),
                    issue_description TEXT,
                    technician_notes TEXT,
                    status VARCHAR(50) DEFAULT 'Received', 
                    date_received DATE, 
                    estimated_completion DATE, 
                    repair_cost DECIMAL(10,2) DEFAULT 0.0, 
                    user_id INT
                )""")
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Setup Error: {e}")

# Initial run
setup_database()

# --- RECOVERY ROUTES ---

@app.route('/fix-db')
def fix_db():
    conn = get_db_connection()
    if not conn: return "Database connection failed. Check Aiven IP settings."
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS repairs")
    cursor.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    cursor.close()
    conn.close()
    setup_database()
    return "Database reset! Go to /force-admin next."

@app.route('/force-admin')
def force_admin():
    conn = get_db_connection()
    if not conn: return "Database connection failed."
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = 'admin'")
    cursor.execute("INSERT INTO users (username, password, fullname, role) VALUES (%s, %s, %s, 'admin')", 
                   ('admin', '1234', 'System Administrator'))
    conn.commit()
    cursor.close()
    conn.close()
    return "Admin reset to: admin / 1234. <a href='/'>Login here</a>"

# --- AUTHENTICATION ---

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    conn = get_db_connection()
    if not conn: return "Database Connection Error", 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['fullname'] = user['fullname']
        return redirect(url_for('admin_dashboard') if user['role'] == 'admin' else url_for('customer_dashboard'))
    flash('Invalid login', 'danger')
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- ADMIN DASHBOARD ---

@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
    if not conn: return "DB Error", 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    stats = {
        'total': len(rows),
        'ongoing': sum(1 for r in rows if r['status'] not in ['Released', 'Completed']),
        'completed': sum(1 for r in rows if r['status'] == 'Completed'),
        'released': sum(1 for r in rows if r['status'] == 'Released'),
        'recent': rows[:5] 
    }
    return render_template('dashboard.html', **stats)

# --- ADD REPAIR ---

@app.route('/add-repair', methods=['GET', 'POST'])
def add_repair():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    if request.method == 'POST':
        track_id = "NBJ-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        conn = get_db_connection()
        cursor = conn.cursor()
        data = (
            track_id, request.form.get('customer_name'), request.form.get('contact_number'),
            request.form.get('item_name'), request.form.get('item_brand'),
            request.form.get('item_model', ''), request.form.get('issue_description'),
            "", 'Received', date.today(), None, request.form.get('repair_cost') or 0, None
        )
        cursor.execute("""
            INSERT INTO repairs (tracking_number, customer_name, contact_number, item_name, 
            item_brand, item_model, issue_description, technician_notes, status, 
            date_received, estimated_completion, repair_cost, user_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", data)
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, fullname FROM users WHERE role='customer'")
    customers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('add_repair.html', customers=customers, today=date.today())

# --- TRACKING ---

@app.route('/track', methods=['GET', 'POST'])
def track():
    repair = None
    error = None
    if request.method == 'POST':
        tn = request.form.get('tracking_number', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM repairs WHERE tracking_number=%s", (tn,))
        repair = cursor.fetchone()
        if not repair: error = "Reference number not found."
        cursor.close()
        conn.close()
    return render_template('track.html', repair=repair, error=error)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
