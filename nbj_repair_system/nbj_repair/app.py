from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector
import os
import random
import string
from datetime import date

app = Flask(__name__)
app.secret_key = "nbj_repair_system_final"

# --- DATABASE CONNECTION ---
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="nbj-db-eac-90f2.k.aivencloud.com",
            port=15200,
            user="avnadmin",
            password="AVNS_MqFJx335YPQw4FubVkz",
            database="defaultdb",
            connection_timeout=10
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
            cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) UNIQUE, password VARCHAR(50), fullname VARCHAR(100), role VARCHAR(20))")
            cursor.execute("CREATE TABLE IF NOT EXISTS repairs (id INT AUTO_INCREMENT PRIMARY KEY, tracking_number VARCHAR(50) UNIQUE, customer_name VARCHAR(100), status VARCHAR(50) DEFAULT 'Received')")
            
            columns = [
                ("contact_number", "VARCHAR(50)"),
                ("item_name", "VARCHAR(100)"),
                ("item_brand", "VARCHAR(100)"),
                ("issue_description", "TEXT"),
                ("technician_notes", "TEXT"),
                ("date_received", "DATE"),
                ("estimated_completion", "DATE"),
                ("repair_cost", "DECIMAL(10,2) DEFAULT 0.0"),
                ("user_id", "INT")
            ]
            for col_name, col_type in columns:
                try: cursor.execute(f"ALTER TABLE repairs ADD COLUMN {col_name} {col_type}")
                except: pass 
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Database Repair Error: {e}")

setup_database()

# --- ROUTES ---

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    u, p = request.form.get('username', '').strip(), request.form.get('password', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        session.update({'user_id': user['id'], 'role': user['role'], 'fullname': user['fullname']})
        return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'customer_dashboard'))
    return redirect(url_for('login_page'))

@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM repairs ORDER BY id DESC")
        rows = cursor.fetchall() or []
        cursor.close()
        conn.close()

        stats = {
            'total': len(rows),
            'ongoing': sum(1 for r in rows if str(r.get('status')) == 'Received'),
            'waiting': sum(1 for r in rows if str(r.get('status')) == 'Waiting for Parts'),
            'completed': sum(1 for r in rows if str(r.get('status')) == 'Completed'),
            'repairs': rows,
            'recent': rows[:5],
            'admin_name': session.get('fullname', 'Administrator')
        }
        return render_template('dashboard.html', **stats)
    except Exception as e:
        return f"Dashboard Error: {str(e)}"

# --- ADD REPAIR ROUTE (FIXES YOUR ERROR) ---
@app.route('/add-repair', methods=['GET', 'POST'])
def add_repair():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    if request.method == 'POST':
        try:
            track_id = "NBJ-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            conn = get_db_connection()
            cursor = conn.cursor()
            data = (
                track_id, request.form.get('customer_name'), request.form.get('contact_number'),
                request.form.get('item_name'), request.form.get('item_brand'),
                request.form.get('issue_description'), 'Received', date.today()
            )
            cursor.execute("""INSERT INTO repairs (tracking_number, customer_name, contact_number, 
                            item_name, item_brand, issue_description, status, date_received) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", data)
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            return f"Error adding repair: {e}"
    return render_template('add_repair.html', today=date.today())

# --- MANAGE ACCOUNTS ROUTE ---
@app.route('/manage-accounts')
def manage_accounts():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    return render_template('manage_accounts.html')

# --- PUBLIC TRACKING ---
@app.route('/track', methods=['GET', 'POST'])
def track():
    repair, tracking_number, error = None, None, None
    if request.method == 'POST':
        tracking_number = request.form.get('tracking_number', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM repairs WHERE tracking_number = %s", (tracking_number,))
        repair = cursor.fetchone()
        cursor.close()
        conn.close()
        if not repair: error = "Invalid Tracking ID."
    return render_template('track.html', repair=repair, tracking_number=tracking_number, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000, debug=True)
