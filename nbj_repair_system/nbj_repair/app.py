from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
import os
from datetime import date

app = Flask(__name__)
app.secret_key = "nbjsecret"

# Database Connection
def get_db_connection():
    return mysql.connector.connect(
        host="nbj-db-eac-90f2.k.aivencloud.com",
        port=15200,
        user="avnadmin",
        password="AVNS_MqFJx335YPQw4FubVkz",
        database="defaultdb"
    )

# Logic to make sure tables exist in your DB
def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50) UNIQUE, password VARCHAR(50), fullname VARCHAR(100), role VARCHAR(20))")
        cursor.execute("CREATE TABLE IF NOT EXISTS repairs (id INT AUTO_INCREMENT PRIMARY KEY, tracking_number VARCHAR(50), customer_name VARCHAR(100), item_name VARCHAR(100), item_brand VARCHAR(100), status VARCHAR(50) DEFAULT 'Repairing', date_received DATE, estimated_completion DATE, repair_cost DECIMAL(10,2) DEFAULT 0.0, user_id INT)")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

setup_database()

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
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
    
    flash('Invalid credentials', 'danger')
    return redirect(url_for('login_page'))

@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # These stats are used by the 'Cards' in your dashboard.html
    stats = {
        'total': len(rows),
        'ongoing': sum(1 for r in rows if r['status'] == 'Repairing'),
        'completed': sum(1 for r in rows if r['status'] == 'Completed'),
        'released': sum(1 for r in rows if r['status'] == 'Released')
    }
    return render_template('dashboard.html', repairs=rows, **stats)

@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM repairs WHERE user_id=%s", (session['user_id'],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('customer_dashboard.html', repairs=rows)

# The following routes match the links in your sidebar (base.html)
@app.route('/add-repair')
def add_repair():
    return render_template('add_repair.html', today=date.today())

@app.route('/repair-history')
def repair_history():
    return render_template('repair_history.html')

@app.route('/manage-accounts')
def manage_accounts():
    return render_template('manage_accounts.html')

@app.route('/track')
def track():
    return render_template('track.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# Route for details (used in your dashboard links)
@app.route('/repair/<int:repair_id>')
def repair_detail(repair_id):
    # This is a placeholder logic to prevent errors when clicking "Details"
    return render_template('repair_detail.html')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
