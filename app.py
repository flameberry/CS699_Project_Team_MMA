from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from scraping import scrape_india_kanoon
import secrets
import sqlite3
import bcrypt
app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False     
app.config["SESSION_TYPE"] = "filesystem" 
app.secret_key = secrets.token_hex(32)  
Session(app)

def get_db_connection():
    return sqlite3.connect('users.db')

@app.route('/')
def index():
    email = None
    name = None
    if session.get("login_status") is None:
        session["login_status"] = False
    if session.get("email"):
        email = session["email"]
    if session.get("name"):
        name = session["name"]
    return render_template("index.html",login_status=session["login_status"],name=name,email=email)

@app.route('/search_query',methods=["GET","POST"])
def search_query():
    if request.method=="GET":
        query = request.args.get("query")
        print(query)
        cases = scrape_india_kanoon(query)
        return render_template('search-result.html',query=query,cases=cases,login_status=session.get("login_status",False),name=session.get("name",None))

@app.route('/login',methods=["GET","POST"])
def login():
    if request.method=="POST":
        data = request.get_json()
        email = data.get("email")
        pwd = data.get("pwd")
        print(email,pwd)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT name, pwd, dob FROM users WHERE email=?''',(email,))
        data = cursor.fetchone()
        stored_hash = data[1]
        if bcrypt.checkpw(pwd.encode('utf-8'), stored_hash):
            session["login_status"] = True
            session["email"] = email
            session["name"] = data[0]
            return jsonify({"login":session["login_status"],"name":session["name"], "email":session["email"]})
        else:
            session["login_status"] = False
            return jsonify({"login":session["login_status"]})
    
@app.route('/register',methods=["GET","POST"])
def register():
    if request.method=="POST":
        data = request.get_json()
        email = data.get("email")
        pwd = data.get("pwd")
        name = data.get("name")
        dob = data.get("dob")
        print(email,name,pwd,dob)
        hash = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt())
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT name, pwd, dob FROM users WHERE email=?''',(email,))
        data = cursor.fetchone()
        if data:
            return jsonify({"registration":0})
        cursor.execute('''
        INSERT INTO users (email,name,pwd,dob) VALUES(?, ?, ?, ?)''',(email,name,hash,dob))
        conn.commit()
        return jsonify({"registration":1})

@app.route('/logout',methods=["GET","POST"])
def logout():
    session.clear()
    session["login_status"] = False
    return jsonify({"login":session["login_status"]})

if __name__ == '__main__':
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY ,
    name TEXT NOT NULL,
    pwd TEXT NOT NULL,
    dob TEXT
    )
    ''')
    conn.commit()
    app.run(debug=True)