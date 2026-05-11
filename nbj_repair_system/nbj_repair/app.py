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
            ssl_disabled=False 
        )
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

# --- DATABASE AUTO-REPAIR ---
def setup_database():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) UNIQUE, password VARCHAR(50), fullname VARCHAR(100), role VARCHAR(20))")
            cursor.execute("CREATE TABLE IF NOT EXISTS repairs (id INT AUTO_INCREMENT PRIMARY KEY, tracking_number VARCHAR(50), customer_name VARCHAR(100), status VARCHAR(50) DEFAULT 'Received')")
            
            # Ensure all columns match the Tracking Portal requirements
            cols = [
                "ALTER TABLE repairs ADD COLUMN contact_number VARCHAR(50) AFTER customer_name",
                "ALTER TABLE repairs ADD COLUMN item_name VARCHAR(100) AFTER contact_number",
                "ALTER TABLE repairs ADD COLUMN item_brand VARCHAR(100) AFTER item_name",
                "ALTER TABLE repairs ADD COLUMN issue_description TEXT AFTER item_brand",
                "ALTER TABLE repairs ADD COLUMN technician_notes TEXT AFTER issue_description",
                "ALTER TABLE repairs ADD COLUMN date_received DATE AFTER technician_notes",
                "ALTER TABLE repairs ADD COLUMN estimated_completion DATE AFTER date_received",
                "ALTER TABLE repairs ADD COLUMN repair_cost DECIMAL(10,2) DEFAULT 0.0 AFTER estimated_completion",
                "ALTER TABLE repairs ADD COLUMN user_id INT AFTER repair_cost"
            ]
            for col in cols:
                try: cursor.execute(col)
                except: pass
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Database Setup Error: {e}")

setup_database()

# --- AUTH & LOGIN ---
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    u = request.form.get('username', '').strip()
    p = request.form.get('password', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        session.update({'user_id': user['id'], 'role': user['role'], 'fullname': user['fullname']})
        return redirect(url_for('admin_dashboard') if user['role'] == 'admin' else url_for('customer_dashboard'))
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- DASHBOARDS ---
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
            'ongoing': sum(1 for r in rows if r.get('status') == 'Received'),
            'waiting': sum(1 for r in rows if r.get('status') == 'Waiting for Parts'),
            'completed': sum(1 for r in rows if r.get('status') == 'Completed'),
            'recent': rows[:5],
            'admin_name': session.get('fullname', 'Administrator')
        }
        return render_template('dashboard.html', **stats)
    except Exception as e: return f"Error: {e}"

@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM repairs WHERE user_id = %s ORDER BY id DESC", (session['user_id'],))
        my_repairs = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return render_template('customer_dashboard.html', repairs=my_repairs)
    except Exception as e: return f"Error: {e}"

# --- ACCOUNTS & REPAIRS ---
@app.route('/manage-accounts', methods=['GET', 'POST'])
def manage_accounts():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'add':
                u, p = request.form.get('username'), request.form.get('password')
                f = request.form.get('full_name') or request.form.get('fullname')
                f_clean = f.strip()
                cursor.execute("INSERT INTO users (username, password, fullname, role) VALUES (%s, %s, %s, 'customer')", (u, p, f_clean))
                new_id = cursor.lastrowid
                cursor.execute("UPDATE repairs SET user_id = %s WHERE TRIM(customer_name) = %s", (new_id, f_clean))
                conn.commit()
            elif action == 'delete':
                cursor.execute("DELETE FROM users WHERE id=%s", (request.form.get('user_id'),))
                conn.commit()
        cursor.execute("SELECT id, username, fullname as full_name FROM users WHERE role='customer'")
        customers = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return render_template('manage_accounts.html', customers=customers)
    except Exception as e: return f"Error: {e}"

@app.route('/add-repair', methods=['GET', 'POST'])
def add_repair():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    if request.method == 'POST':
        try:
            track_id = "NBJ-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            c_name = request.form.get('customer_name').strip()
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE TRIM(fullname) = %s AND role = 'customer'", (c_name,))
            ex_user = cursor.fetchone()
            u_id = ex_user['id'] if ex_user else None

            data = (
                track_id, c_name, request.form.get('contact_number'),
                request.form.get('item_name'), request.form.get('item_brand'),
                request.form.get('issue_description'), 'Received', 
                date.today(), request.form.get('estimated_completion') or None, 
                float(request.form.get('repair_cost') or 0), u_id
            )
            cursor.execute("""INSERT INTO repairs (tracking_number, customer_name, contact_number, item_name, 
                item_brand, issue_description, status, date_received, estimated_completion, repair_cost, user_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", data)
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        except Exception as e: return f"Error: {e}"
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, fullname as full_name FROM users WHERE role='customer'")
    customers = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('add_repair.html', customers=customers, today=date.today())

@app.route('/update-status/<int:repair_id>', methods=['POST'])
def update_status(repair_id):
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    status = request.form.get('status')
    est = request.form.get('estimated_completion') or None
    cost = request.form.get('repair_cost') or 0
    notes = request.form.get('technician_notes')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""UPDATE repairs SET status=%s, estimated_completion=%s, 
                          repair_cost=%s, technician_notes=%s WHERE id=%s""", 
                       (status, est, cost, notes, repair_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e: print(f"Update Error: {e}")
    return redirect(url_for('repair_history'))

# --- REPAIR HISTORY ---
@app.route('/repair-history')
def repair_history():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    status_filter = request.args.get('status')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if status_filter:
            cursor.execute("SELECT * FROM repairs WHERE status = %s ORDER BY id DESC", (status_filter,))
        else:
            cursor.execute("SELECT * FROM repairs ORDER BY id DESC")
        repairs = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return render_template('repair_history.html', repairs=repairs, status_filter=status_filter)
    except Exception as e: return f"Error: {e}"

# --- PUBLIC TRACKING (FULLY WORKING WITH YOUR HTML) ---
@app.route('/track', methods=['GET', 'POST'])
def track():
    repair = None
    tracking_number = None
    error = None
    
    if request.method == 'POST':
        tracking_number = request.form.get('tracking_number', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM repairs WHERE tracking_number = %s", (tracking_number,))
        repair = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not repair:
            error = f"The tracking number '{tracking_number}' was not found in our system."

    return render_template('track.html', repair=repair, tracking_number=tracking_number, error=error)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), debug=True)
