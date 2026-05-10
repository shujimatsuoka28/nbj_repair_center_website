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

# --- ADMIN DASHBOARD ---
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
        return f"Dashboard Error: {e}"

# --- REPAIR HISTORY (This fixes your current error!) ---
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

# --- REPAIR DETAIL ---
@app.route('/repair-detail/<int:repair_id>')
def repair_detail(repair_id):
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs WHERE id = %s", (repair_id,))
    repair = cursor.fetchone()
    cursor.close()
    conn.close()
    if not repair: return "Repair Job Not Found", 404
    return render_template('repair_detail.html', repair=repair)

# --- MANAGE ACCOUNTS ---
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
    cursor.execute("SELECT id, username, fullname as full_name FROM users WHERE role='customer'")
    customers = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('manage_accounts.html', customers=customers)

# --- ADD REPAIR ---
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
                request.form.get('repair_cost') or 0.0, request.form.get('customer_id') or None
            )
            cursor.execute("""
                INSERT INTO repairs (tracking_number, customer_name, contact_number, item_name, 
                item_brand, issue_description, status, date_received, 
                estimated_completion, repair_cost, user_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", data)
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            return f"Job Error: {e}"
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, fullname as full_name, username FROM users WHERE role='customer'")
    customers = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('add_repair.html', customers=customers, today=date.today())

# --- CUSTOMER DASHBOARD ---
@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs WHERE user_id=%s", (session['user_id'],))
    repairs = cursor.fetchall() or []
    cursor.close()
    conn.close()
    return render_template('customer_dashboard.html', repairs=repairs)

# --- LOGIN & AUTH ---
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
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
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
