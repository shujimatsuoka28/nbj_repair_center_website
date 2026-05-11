from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector
import os
import random
import string
from datetime import date

app = Flask(__name__)
app.secret_key = "nbj_repair_system_2024"

# --- DATABASE CONNECTION ---
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="nbj-db-eac-90f2.k.aivencloud.com",
            port=15200,
            user="avnadmin",
            password="AVNS_MqFJx335YPQw4FubVkz",
            database="defaultdb",
            ssl_disabled=False
        )
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

# --- DATABASE SETUP & AUTO-REPAIR ---
def setup_database():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Tables
            cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) UNIQUE, password VARCHAR(50), fullname VARCHAR(100), role VARCHAR(20))")
            cursor.execute("CREATE TABLE IF NOT EXISTS repairs (id INT AUTO_INCREMENT PRIMARY KEY, tracking_number VARCHAR(50) UNIQUE, customer_name VARCHAR(100), status VARCHAR(50) DEFAULT 'Received')")
            
            # Ensure all columns match the HTML requirements
            cols = [
                "ALTER TABLE repairs ADD COLUMN contact_number VARCHAR(50)",
                "ALTER TABLE repairs ADD COLUMN item_name VARCHAR(100)",
                "ALTER TABLE repairs ADD COLUMN item_brand VARCHAR(100)",
                "ALTER TABLE repairs ADD COLUMN issue_description TEXT",
                "ALTER TABLE repairs ADD COLUMN technician_notes TEXT", # Matches HTML
                "ALTER TABLE repairs ADD COLUMN date_received DATE",
                "ALTER TABLE repairs ADD COLUMN estimated_completion DATE",
                "ALTER TABLE repairs ADD COLUMN repair_cost DECIMAL(10,2) DEFAULT 0.0",
                "ALTER TABLE repairs ADD COLUMN user_id INT"
            ]
            for col in cols:
                try: cursor.execute(col)
                except: pass # Column already exists
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Database Setup Error: {e}")

setup_database()

# --- AUTH ROUTES ---
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

# --- TRACKING ROUTE (FIXED FOR YOUR HTML) ---
@app.route('/track', methods=['GET', 'POST'])
def track():
    repair = None
    tracking_number = None
    error = None
    
    if request.method == 'POST':
        tracking_number = request.form.get('tracking_number', '').strip()
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                # Find repair by tracking number
                cursor.execute("SELECT * FROM repairs WHERE tracking_number = %s", (tracking_number,))
                repair = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if not repair:
                    error = f"Tracking ID '{tracking_number}' not found in our system."
            else:
                error = "Server database connection failed."
        except Exception as e:
            error = f"System Error: {str(e)}"
            
    return render_template('track.html', repair=repair, tracking_number=tracking_number, error=error)

# --- ADMIN DASHBOARD ---
@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs ORDER BY id DESC")
    rows = cursor.fetchall() or []
    cursor.close()
    conn.close()
    
    stats = {
        'total': len(rows),
        'ongoing': sum(1 for r in rows if r.get('status') == 'Received'),
        'completed': sum(1 for r in rows if r.get('status') == 'Completed'),
        'repairs': rows
    }
    return render_template('dashboard.html', **stats)

# --- UPDATE STATUS ---
@app.route('/update-status/<int:repair_id>', methods=['POST'])
def update_status(repair_id):
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    
    status = request.form.get('status')
    est = request.form.get('estimated_completion') or None
    notes = request.form.get('technician_notes') # Matches HTML requirement
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE repairs 
        SET status=%s, estimated_completion=%s, technician_notes=%s 
        WHERE id=%s
    """, (status, est, notes, repair_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000, debug=True)
