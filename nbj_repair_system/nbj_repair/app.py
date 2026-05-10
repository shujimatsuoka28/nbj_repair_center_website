import os, random, sqlite3, string
from datetime import date
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nbj_repair_secret_2024")
DB_PATH = "/tmp/nbj_repair.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer', full_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS repairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_number TEXT UNIQUE NOT NULL, customer_id INTEGER,
        customer_name TEXT NOT NULL, contact_number TEXT,
        item_name TEXT NOT NULL, item_brand TEXT, item_model TEXT,
        issue_description TEXT, status TEXT DEFAULT 'Received',
        date_received TEXT NOT NULL, estimated_completion TEXT,
        date_completed TEXT, technician_notes TEXT,
        repair_cost REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES users(id))''')
    c.execute("INSERT OR IGNORE INTO users (username,password,role,full_name) VALUES (?,?,?,?)",
              ("admin","1234","admin","NBJ Administrator"))
    conn.commit(); conn.close()

def gen_tracking():
    return "NBJ-" + "".join(random.choices(string.ascii_uppercase,k=3)) + "".join(random.choices(string.digits,k=6))

@app.route("/", methods=["GET","POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard") if session.get("role")=="admin" else url_for("customer_dashboard"))
    login_error = None
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p)).fetchone()
        conn.close()
        if user:
            session["user_id"]=user["id"]; session["username"]=user["username"]
            session["role"]=user["role"]; session["full_name"]=user["full_name"] or user["username"]
            return redirect(url_for("dashboard") if user["role"]=="admin" else url_for("customer_dashboard"))
        login_error = "Incorrect username or password."
    return render_template("login.html", login_error=login_error)

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if session.get("role")!="admin": return redirect(url_for("login"))
    conn=get_db()
    ongoing=conn.execute("SELECT COUNT(*) as c FROM repairs WHERE status NOT IN ('Completed','Released')").fetchone()["c"]
    completed=conn.execute("SELECT COUNT(*) as c FROM repairs WHERE status='Completed'").fetchone()["c"]
    released=conn.execute("SELECT COUNT(*) as c FROM repairs WHERE status='Released'").fetchone()["c"]
    total=conn.execute("SELECT COUNT(*) as c FROM repairs").fetchone()["c"]
    recent=conn.execute("SELECT * FROM repairs ORDER BY created_at DESC LIMIT 6").fetchall()
    conn.close()
    return render_template("dashboard.html",ongoing=ongoing,completed=completed,released=released,total=total,recent=recent)

@app.route("/add-repair", methods=["GET","POST"])
def add_repair():
    if session.get("role")!="admin": return redirect(url_for("login"))
    conn=get_db()
    customers=conn.execute("SELECT * FROM users WHERE role='customer' ORDER BY full_name").fetchall()
    success_msg=form_error=new_tracking=None
    if request.method=="POST":
        cid=request.form.get("customer_id") or None
        cname=request.form.get("customer_name","").strip()
        contact=request.form.get("contact_number","").strip()
        iname=request.form.get("item_name","").strip()
        ibrand=request.form.get("item_brand","").strip()
        imodel=request.form.get("item_model","").strip()
        issue=request.form.get("issue_description","").strip()
        dr=request.form.get("date_received") or str(date.today())
        est=request.form.get("estimated_completion","").strip()
        try: cost=float(request.form.get("repair_cost",0))
        except: cost=0
        if not cname or not iname:
            form_error="Customer name and item name are required."
        else:
            t=gen_tracking()
            conn.execute("INSERT INTO repairs (tracking_number,customer_id,customer_name,contact_number,item_name,item_brand,item_model,issue_description,date_received,estimated_completion,repair_cost) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (t,cid,cname,contact,iname,ibrand,imodel,issue,dr,est,cost))
            conn.commit(); new_tracking=t; success_msg=f"Repair saved! Tracking: {t}"
    conn.close()
    return render_template("add_repair.html",customers=customers,today=str(date.today()),success_msg=success_msg,form_error=form_error,new_tracking=new_tracking)

@app.route("/repair-history")
def repair_history():
    if session.get("role")!="admin": return redirect(url_for("login"))
    sf=request.args.get("status",""); updated=request.args.get("updated","")
    conn=get_db()
    repairs=conn.execute("SELECT * FROM repairs WHERE status=? ORDER BY created_at DESC",(sf,)).fetchall() if sf else conn.execute("SELECT * FROM repairs ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("repair_history.html",repairs=repairs,status_filter=sf,updated=updated)

@app.route("/update-status/<int:repair_id>", methods=["POST"])
def update_status(repair_id):
    if session.get("role")!="admin": return redirect(url_for("login"))
    ns=request.form.get("status"); notes=request.form.get("technician_notes","")
    est=request.form.get("estimated_completion","")
    try: cost=float(request.form.get("repair_cost",0))
    except: cost=0
    dc=str(date.today()) if ns in ("Completed","Released") else None
    conn=get_db()
    conn.execute("UPDATE repairs SET status=?,technician_notes=?,estimated_completion=?,repair_cost=?,date_completed=? WHERE id=?",(ns,notes,est,cost,dc,repair_id))
    conn.commit(); conn.close()
    return redirect(url_for("repair_history")+"?updated=1")

@app.route("/repair/<int:repair_id>")
def repair_detail(repair_id):
    if "user_id" not in session: return redirect(url_for("login"))
    conn=get_db()
    repair=conn.execute("SELECT * FROM repairs WHERE id=?",(repair_id,)).fetchone()
    conn.close()
    return render_template("repair_detail.html",repair=repair)

@app.route("/manage-accounts", methods=["GET","POST"])
def manage_accounts():
    if session.get("role")!="admin": return redirect(url_for("login"))
    conn=get_db(); account_msg=account_error=None
    if request.method=="POST":
        action=request.form.get("action")
        if action=="add":
            u=request.form.get("username","").strip(); p=request.form.get("password","").strip(); fn=request.form.get("full_name","").strip()
            if not u or not p: account_error="Username and password required."
            else:
                try:
                    conn.execute("INSERT INTO users (username,password,role,full_name) VALUES (?,?,?,?)",(u,p,"customer",fn))
                    conn.commit(); account_msg=f"Account created for {fn or u}."
                except sqlite3.IntegrityError: account_error=f'Username "{u}" already taken.'
        elif action=="reset_password":
            uid=request.form.get("user_id"); pw=request.form.get("new_password","").strip()
            if not pw: account_error="Password cannot be empty."
            else:
                conn.execute("UPDATE users SET password=? WHERE id=? AND role='customer'",(pw,uid))
                conn.commit(); account_msg="Password reset successfully."
        elif action=="delete":
            uid=request.form.get("user_id")
            conn.execute("DELETE FROM users WHERE id=? AND role='customer'",(uid,))
            conn.commit(); account_msg="Account deleted."
    customers=conn.execute("SELECT * FROM users WHERE role='customer' ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("manage_accounts.html",customers=customers,account_msg=account_msg,account_error=account_error)

@app.route("/customer/dashboard")
def customer_dashboard():
    if "user_id" not in session or session.get("role")!="customer": return redirect(url_for("login"))
    conn=get_db()
    repairs=conn.execute("SELECT * FROM repairs WHERE customer_id=? ORDER BY created_at DESC",(session["user_id"],)).fetchall()
    conn.close()
    return render_template("customer_dashboard.html",repairs=repairs)

@app.route("/track", methods=["GET","POST"])
def track():
    repair=track_error=None
    if request.method=="POST":
        tn=request.form.get("tracking_number","").strip().upper()
        conn=get_db()
        repair=conn.execute("SELECT * FROM repairs WHERE tracking_number=?",(tn,)).fetchone()
        conn.close()
        if not repair: track_error="No record found. Please check the number and try again."
    return render_template("track.html",repair=repair,track_error=track_error)

init_db()

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
