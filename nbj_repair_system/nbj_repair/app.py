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

# --- DATABASE SETUP (FORCING COLUMNS) ---
def setup_database():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Create basic tables
            cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) UNIQUE, password VARCHAR(50), fullname VARCHAR(100), role VARCHAR(20))")
            cursor.execute("CREATE TABLE IF NOT EXISTS repairs (id INT AUTO_INCREMENT PRIMARY KEY, tracking_number VARCHAR(50), customer_name VARCHAR(100), status VARCHAR(50) DEFAULT 'Received')")
            
            # THE FIX: Force missing columns into Aiven
            columns = [
                "ALTER TABLE repairs ADD COLUMN contact_number VARCHAR(50) AFTER customer_name",
                "ALTER TABLE repairs ADD COLUMN item_name VARCHAR(100) AFTER contact_number",
                "ALTER TABLE repairs ADD COLUMN item_brand VARCHAR(100) AFTER item_name",
                "ALTER TABLE repairs ADD COLUMN issue_description TEXT AFTER item_brand",
                "ALTER TABLE repairs ADD COLUMN date_received DATE AFTER issue_description",
                "ALTER TABLE repairs ADD COLUMN estimated_completion DATE AFTER date_received",
                "ALTER TABLE repairs ADD COLUMN repair_cost DECIMAL(10,2) DEFAULT 0.0 AFTER estimated_completion",
                "ALTER TABLE repairs ADD COLUMN user_id INT AFTER repair_cost"
            ]
            for col in columns:
                try:
                    cursor.execute(col)
                except:
                    pass # Skip if column already exists
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Setup Error: {e}")

setup_database()

# --- RECOVERY ---
@app.route('/reset-database')
def reset_db():
    try:
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
        return "Database Cleaned & Rebuilt! Visit <a href='/force-admin'>/force-admin</a>"
    except Exception as e:
        return f"Reset Error: {e}"

@app.route('/force-admin')
def force_admin():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = 'admin'")
        cursor.execute("INSERT INTO users (username, password, fullname, role) VALUES (%s, %s, %s, 'admin')", ('admin', '1234', 'System Administrator'))
        conn.commit()
        cursor.close()
        conn.close()
        return "Admin reset! <a href='/'>Login</a>"
    except Exception as e: return f"Error: {e}"

# --- MAIN ROUTES ---
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
            'admin_name': session.get('fullname', 'Admin')
        }
        return render_template('dashboard.html', **stats)
    except Exception as e: return f"Dashboard Error: {e}"

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
        except Exception as e: return f"Job Error: {e}"
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, fullname as full_name, username FROM users WHERE role='customer'")
    customers = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('add_repair.html', customers=customers, today=date.today())

@app.route('/manage-accounts', methods=['GET', 'POST'])
def manage_accounts():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            # We look for 'action' OR 'add' to decide what to do
            action = request.form.get('action')
            
            if action == 'add' or 'username' in request.form:
                # This handles both 'full_name' and 'fullname' from HTML
                u_name = request.form.get('username')
                p_word = request.form.get('password')
                f_name = request.form.get('full_name') or request.form.get('fullname') or "New Customer"
                
                cursor.execute("""
                    INSERT INTO users (username, password, fullname, role) 
                    VALUES (%s, %s, %s, 'customer')""", 
                    (u_name, p_word, f_name))
                conn.commit()
                flash("Account added successfully!")
                
            elif action == 'delete':
                user_id = request.form.get('user_id')
                cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
                conn.commit()
                flash("Account deleted.")
                
        except Exception as e:
            # This will show you exactly WHAT is wrong on the screen
            return f"Account Error: {e}"
    
    # Fetch the list
    cursor.execute("SELECT id, username, fullname as full_name FROM users WHERE role='customer'")
    customers = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('manage_accounts.html', customers=customers)
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

@app.route('/')
def login_page(): return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username, password = request.form.get('username', '').strip(), request.form.get('password', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), debug=True)
