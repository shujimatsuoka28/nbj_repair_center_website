from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = "nbjsecret"

# 1. Database Connection Configuration using your Aiven details
def get_db_connection():
    return mysql.connector.connect(
        host="nbj-db-eac-90f2.k.aivencloud.com",
        port=15200,
        user="avnadmin",
        password="AVNS_MqFJx335YPQw4FubVkz",
        database="defaultdb"
    )

# 2. SELF-REPAIR: This creates your table automatically so you don't have to find Aiven settings
def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                password VARCHAR(50) NOT NULL,
                fullname VARCHAR(100),
                role VARCHAR(20)
            )
        """)
        # Add the default admin user if the table is empty
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO users (username, password, fullname, role) 
                VALUES ('admin', 'admin123', 'NBJ Admin', 'admin')
            """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database is ready and table is created!")
    except Exception as e:
        print(f"❌ Database setup failed: {e}")

# Run the setup before the app starts
setup_database()

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Check credentials
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['fullname'] = user['fullname']
            
            if user['role'] == 'admin':
                return redirect('/admin-dashboard')
            else:
                return redirect('/customer-dashboard')

        flash('Invalid username or password', 'danger')
        return redirect('/')
    except Exception as e:
        return f"Database Error: {e}"

# Placeholder routes for dashboards so you don't get a 404
@app.route('/admin-dashboard')
def admin_dashboard():
    if 'user_id' not in session: return redirect('/')
    return f"Welcome {session['fullname']}! This is the Admin Dashboard."

@app.route('/customer-dashboard')
def customer_dashboard():
    if 'user_id' not in session: return redirect('/')
    return f"Welcome {session['fullname']}! This is the Customer Dashboard."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
