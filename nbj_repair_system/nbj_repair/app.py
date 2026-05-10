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
            
            cols = [
                "ALTER TABLE repairs ADD COLUMN contact_number VARCHAR(50) AFTER customer_name",
                "ALTER TABLE repairs ADD COLUMN item_name VARCHAR(100) AFTER contact_number",
                "ALTER TABLE repairs ADD COLUMN item_brand VARCHAR(100) AFTER item_name",
                "ALTER TABLE repairs ADD COLUMN issue_description TEXT AFTER item_brand",
                "ALTER TABLE repairs ADD COLUMN date_received DATE AFTER issue_description",
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

# --- AUTH & LOGIN (FIXED) ---
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
        session.update({
            'user_id': user['id'], 
            'role': user['role'], 
            'fullname': user['fullname']
        })
        
        # This is the fix: routing based on role
        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('customer_dashboard'))
            
    return redirect(url_for('login_page'))

# --- CUSTOMER DASHBOARD ---
@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Fetch ONLY the logged-in user's repairs
        cursor.execute("SELECT * FROM repairs WHERE user_id = %s ORDER BY id DESC", (session['user_id'],))
        my_repairs = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return render_template('customer_dashboard.html', repairs=my_repairs)
    except Exception as e:
        return f"Customer Dashboard Error: {str(e)}"

# --- ADMIN ROUTES ---
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
            'waiting': sum(1 for r in rows if r.get('status') == 'Awaiting Parts'),
            'completed': sum(1 for r in rows if r.get('status') == 'Completed'),
            'recent': rows[:5],
            'admin_name': session.get('fullname', 'Administrator')
        }
        return render_template('dashboard.html', **stats)
    except Exception as e:
        return f"Dashboard Error: {str(e)}"

# --- 1. UPDATED MANAGE ACCOUNTS (Links when account is created) ---
@app.route('/manage-accounts', methods=['GET', 'POST'])
def manage_accounts():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'add':
                u = request.form.get('username')
                p = request.form.get('password')
                f = request.form.get('full_name') or request.form.get('fullname')
                
                # Create user
                cursor.execute("INSERT INTO users (username, password, fullname, role) VALUES (%s, %s, %s, 'customer')", (u, p, f))
                new_id = cursor.lastrowid
                
                # MAGIC LINK: Update all existing repairs with this name
                cursor.execute("UPDATE repairs SET user_id = %s WHERE customer_name = %s", (new_id, f))
                conn.commit()

            elif action == 'delete':
                cursor.execute("DELETE FROM users WHERE id=%s", (request.form.get('user_id'),))
                conn.commit()

        cursor.execute("SELECT id, username, fullname as full_name FROM users WHERE role='customer'")
        customers = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return render_template('manage_accounts.html', customers=customers)
    except Exception as e:
        return f"Account Error: {str(e)}"

# --- 2. UPDATED ADD REPAIR (Links if account already exists) ---
@app.route('/add-repair', methods=['GET', 'POST'])
def add_repair():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    if request.method == 'POST':
        try:
            track_id = "NBJ-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            c_name = request.form.get('customer_name')
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # CHECK: Does this name already have an account?
            cursor.execute("SELECT id FROM users WHERE fullname = %s AND role = 'customer'", (c_name,))
            existing_user = cursor.fetchone()
            u_id = existing_user['id'] if existing_user else None

            data = (
                track_id, c_name, request.form.get('contact_number'),
                request.form.get('item_name'), request.form.get('item_brand'),
                request.form.get('issue_description'), 'Received', 
                request.form.get('date_received'), request.form.get('estimated_completion') or None, 
                float(request.form.get('repair_cost') or 0), u_id
            )
            cursor.execute("""INSERT INTO repairs (tracking_number, customer_name, contact_number, item_name, 
                item_brand, issue_description, status, date_received, estimated_completion, repair_cost, user_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", data)
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        except Exception as e: return f"Job Error: {str(e)}"
    
    # Still fetch customer list just in case you want to see them
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, fullname as full_name FROM users WHERE role='customer'")
    customers = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('add_repair.html', customers=customers, today=date.today())
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
                request.form.get('issue_description'), 'Received', 
                request.form.get('date_received'), request.form.get('estimated_completion') or None, 
                float(request.form.get('repair_cost') or 0), request.form.get('customer_id') or None
            )
            cursor.execute("""INSERT INTO repairs (tracking_number, customer_name, contact_number, item_name, 
                item_brand, issue_description, status, date_received, estimated_completion, repair_cost, user_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", data)
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        except Exception as e: return f"Job Error: {str(e)}"
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, fullname as full_name, username FROM users WHERE role='customer'")
    customers = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('add_repair.html', customers=customers, today=date.today())

@app.route('/repair-history')
def repair_history():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs ORDER BY id DESC")
    repairs = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('repair_history.html', repairs=repairs)

@app.route('/repair-detail/<int:repair_id>')
def repair_detail(repair_id):
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs WHERE id = %s", (repair_id,))
    repair = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('repair_detail.html', repair=repair)

@app.route('/track')
def track(): return render_template('track.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- RECOVERY ---
@app.route('/reset-database')
def reset_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    cursor.execute("DROP TABLE IF EXISTS repairs")
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()
    setup_database()
    return "Database Rebuilt! Visit <a href='/force-admin'>/force-admin</a>"

@app.route('/force-admin')
def force_admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO users (id, username, password, fullname, role) VALUES (1, 'admin', '1234', 'System Admin', 'admin')")
    conn.commit()
    cursor.close()
    conn.close()
    return "Admin reset to admin/1234. <a href='/'>Login</a>"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), debug=True)
