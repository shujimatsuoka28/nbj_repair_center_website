from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
import os
import random
import string
from datetime import date

app = Flask(__name__)
app.secret_key = "nbj_repair_secret_key"

# --- DATABASE CONNECTION ---
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="nbj-db-eac-90f2.k.aivencloud.com",
            port=15200,
            user="avnadmin",
            password="AVNS_MqFJx335YPQw4FubVkz",
            database="defaultdb",
            # Use this to prevent connection timeouts
            connection_timeout=10
        )
    except Exception as e:
        print(f"Database Connection Failed: {e}")
        return None

# --- DATABASE AUTO-INITIALIZATION ---
def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # 1. Create Tables
            cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) UNIQUE, password VARCHAR(50), fullname VARCHAR(100), role VARCHAR(20))")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repairs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tracking_number VARCHAR(50) UNIQUE,
                    customer_name VARCHAR(100),
                    item_name VARCHAR(100),
                    item_brand VARCHAR(100),
                    technician_notes TEXT,
                    status VARCHAR(50) DEFAULT 'Received',
                    date_received DATE,
                    estimated_completion DATE,
                    repair_cost DECIMAL(10,2) DEFAULT 0.0,
                    user_id INT
                )
            """)
            
            # 2. Safety: Force check for the most common missing column
            try:
                cursor.execute("ALTER TABLE repairs ADD COLUMN technician_notes TEXT")
            except:
                pass # Column already exists
                
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Startup DB Error: {e}")

init_db()

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    u = request.form.get('username', '').strip()
    p = request.form.get('password', '').strip()
    conn = get_db_connection()
    if not conn: return "Database connection failed. Please check your credentials."
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user:
        session.update({'user_id': user['id'], 'role': user['role'], 'fullname': user['fullname']})
        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('customer_dashboard'))
    return redirect(url_for('index'))

@app.route('/track', methods=['GET', 'POST'])
def track():
    repair = None
    tracking_number = None
    error = None
    
    if request.method == 'POST':
        tracking_number = request.form.get('tracking_number', '').strip()
        try:
            conn = get_db_connection()
            if not conn:
                error = "Could not connect to the database."
            else:
                cursor = conn.cursor(dictionary=True)
                # We use a broad SELECT * but handle keys safely in the HTML
                cursor.execute("SELECT * FROM repairs WHERE tracking_number = %s", (tracking_number,))
                repair = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if not repair:
                    error = f"Ticket number '{tracking_number}' not found."
        except Exception as e:
            # THIS PREVENTS THE 500 INTERNAL SERVER ERROR
            # It sends the error message to the HTML instead of crashing
            error = f"System Error: {str(e)}"

    return render_template('track.html', repair=repair, tracking_number=tracking_number, error=error)

@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('dashboard.html', repairs=rows)

@app.route('/update-status/<int:repair_id>', methods=['POST'])
def update_status(repair_id):
    if session.get('role') != 'admin': return redirect(url_for('index'))
    s = request.form.get('status')
    n = request.form.get('technician_notes')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE repairs SET status=%s, technician_notes=%s WHERE id=%s", (s, n, repair_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    # Standard Flask port for local/cloud environments
    app.run(host='0.0.0.0', port=10000, debug=True)
