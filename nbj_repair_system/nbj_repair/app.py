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
    return mysql.connector.connect(
        host="nbj-db-eac-90f2.k.aivencloud.com",
        port=15200,
        user="avnadmin",
        password="AVNS_MqFJx335YPQw4FubVkz",
        database="defaultdb"
    )

# --- DATABASE SETUP ---
def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY, 
                username VARCHAR(50) UNIQUE, 
                password VARCHAR(50), 
                fullname VARCHAR(100), 
                role VARCHAR(20)
            )""")
            
        # Repairs Table - Updated to include all necessary columns
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
        print(f"Database Error: {e}")

setup_database()

# --- MAINTENANCE ROUTES (Run these in browser if error occurs) ---

@app.route('/fix-db')
def fix_db():
    """Wipes and recreates tables to fix Internal Server Errors caused by column mismatches."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS repairs")
        cursor.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        cursor.close()
        conn.close()
        setup_database()
        return "Database tables have been reset! Now go to <a href='/force-admin'>/force-admin</a> to recreate your account."
    except Exception as e:
        return f"Error resetting database: {e}"

@app.route('/force-admin')
def force_admin():
    """Resets the admin account."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = 'admin'")
        cursor.execute("""
            INSERT INTO users (username, password, fullname, role) 
            VALUES (%s, %s, %s, %s)""", 
            ('admin', '1234', 'System Administrator', 'admin'))
        conn.commit()
        cursor.close()
        conn.close()
        return "Admin reset to: <b>admin / 1234</b>. <a href='/'>Go to Login</a>"
    except Exception as e:
        return f"Error: {e}"

# --- AUTHENTICATION ---

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username').strip()
    password = request.form.get('password').strip()
    
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
        return redirect(url_for('admin_dashboard') if user['role'] == 'admin' else url_for('customer_dashboard'))
    
    flash('Invalid username or password', 'danger')
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- ADMIN ROUTES ---

@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
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

@app.route('/add-repair', methods=['GET', 'POST'])
def add_repair():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    
    if request.method == 'POST':
        track_id = "NBJ-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        received_date = request.form.get('date_received') or date.today()

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Exactly matching the 12 columns required by the INSERT
        data = (
            track_id, 
            request.form.get('customer_name'), 
            request.form.get('contact_number'),
            request.form.get('item_name'), 
            request.form.get('item_brand'),
            request.form.get('item_model'), # Added
            request.form.get('issue_description'),
            "", # technician_notes starts empty
            'Received', 
            received_date,
            request.form.get('estimated_completion') or None,
            request.form.get('repair_cost') or 0, 
            request.form.get('customer_id') or None
        )
        
        cursor.execute("""
            INSERT INTO repairs (
                tracking_number, customer_name, contact_number, item_name, 
                item_brand, item_model, issue_description, technician_notes, 
                status, date_received, estimated_completion, repair_cost, user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", data)
            
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

@app.route('/repair-history')
def repair_history():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    status_filter = request.args.get('status')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if status_filter:
        cursor.execute("SELECT * FROM repairs WHERE status=%s ORDER BY id DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM repairs ORDER BY id DESC")
    
    repairs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('repair_history.html', repairs=repairs, status_filter=status_filter)

@app.route('/update-status/<int:repair_id>', methods=['POST'])
def update_status(repair_id):
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE repairs SET status=%s, estimated_completion=%s, technician_notes=%s, repair_cost=%s 
        WHERE id=%s""", (
            request.form.get('status'), 
            request.form.get('estimated_completion') or None,
            request.form.get('technician_notes'), 
            request.form.get('repair_cost'), 
            repair_id
        ))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('repair_history'))

@app.route('/manage-accounts', methods=['GET', 'POST'])
def manage_accounts():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            cursor.execute("INSERT INTO users (username, password, fullname, role) VALUES (%s, %s, %s, 'customer')", 
                           (request.form.get('username'), request.form.get('password'), request.form.get('full_name')))
        elif action == 'delete':
            cursor.execute("DELETE FROM users WHERE id=%s", (request.form.get('user_id'),))
        conn.commit()

    cursor.execute("SELECT * FROM users WHERE role='customer'")
    customers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('manage_accounts.html', customers=customers)

# --- CUSTOMER & PUBLIC ---

@app.route('/track', methods=['GET', 'POST'])
def track():
    repair = None
    error = None
    if request.method == 'POST':
        tn = request.form.get('tracking_number').strip()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM repairs WHERE tracking_number=%s", (tn,))
        repair = cursor.fetchone()
        if not repair: error = "Reference number not found."
        cursor.close()
        conn.close()
    return render_template('track.html', repair=repair, error=error)

@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs WHERE user_id=%s ORDER BY id DESC", (session['user_id'],))
    repairs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('customer_dashboard.html', repairs=repairs)

@app.route('/repair/<int:repair_id>')
def repair_detail(repair_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs WHERE id=%s", (repair_id,))
    repair = cursor.fetchone()
    cursor.close()
    conn.close()
    if not repair: return "Repair not found", 404
    return render_template('repair_detail.html', repair=repair)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
