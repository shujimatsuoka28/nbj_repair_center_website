from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = "nbjsecret"

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="nbj_repair"
)

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (username, password)
    )

    user = cursor.fetchone()

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