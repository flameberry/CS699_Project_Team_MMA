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
    past_queries=[]
    if session.get("login_status") is None:
        session["login_status"] = False
    if session.get("email"):
        email = session["email"]
    if session.get("name"):
        name = session["name"]
    if session["login_status"]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT query FROM history WHERE email=? ORDER BY created_at DESC''',(session["email"],))
        past_queries = cursor.fetchall()
        conn.close()

    return render_template("index.html",login_status=session["login_status"],name=name,email=email,past_queries=past_queries)

@app.route('/search_query',methods=["GET","POST"])
def search_query():
    if request.method=="GET":
        query = request.args.get("query")
        conn = get_db_connection()
        cursor = conn.cursor()
        if session["login_status"]:
            cursor.execute('''SELECT query FROM history ORDER BY created_at DESC LIMIT 1''')
            top_query = cursor.fetchone()
            if top_query and len(top_query)>0 and top_query[0]==query:
                cursor.execute("UPDATE history SET created_at = CURRENT_TIMESTAMP where id = ( SELECT id FROM history ORDER BY created_at DESC LIMIT 1)")
            else:
                cursor.execute('''INSERT INTO history (email,query) VALUES (?,?)''',(session["email"],query))
            conn.commit()
        cursor.execute('''
        select id,case_title,citation,judgement_date,snippet from cases where case_title LIKE ? or citation LIKE ? or snippet LIKE ?
        ''',(f"%{query}%", f"%{query}%", f"%{query}%"))
        cases=[
            {
                "id":row[0],
                "title":row[1],
                "citation":row[2],
                "judgment_date":row[3],
                "snippet":row[4]
            } for row in cursor.fetchall()
        ]
        conn.close()
        return render_template('search-result.html',query=query,cases=cases,login_status=session.get("login_status",False),name=session.get("name",None))
    
@app.route('/doc-view/<case_id>',methods=["GET","POST"])
def doc_view(case_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    select case_title, citation, judgement_date, judges, full_text from cases where id = ?''',(case_id,))
    case_data = cursor.fetchone()
    conn.close()
    if not case_data:
        return "Document not found", 404
    data={
            "id":case_id,
            "title":case_data[0],
            "citation":case_data[1],
            "judgement_date":case_data[2],
            "judges": case_data[3].split(','),
            "full_text": case_data[4]
        }
    return render_template(
        "Doc_view_page.html",
        case=data,
        login_status=session.get("login_status",False),
        name=session.get("name", None)
    )

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

@app.route('/history',methods=['GET'])
def history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT query FROM history WHERE email=? ORDER BY created_at DESC''',(session["email"],))
    past_queries = cursor.fetchall()
    conn.close()
    return render_template("history.html",past_queries=past_queries,name=session.get("name",None),email=session.get("email",None))

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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY ,
    case_title TEXT NOT NULL,
    citation TEXT,
    judgement_date TEXT,
    judges TEXT,
    snippet TEXT,
    full_text TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL ,
    query TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    sample_cases = [
        ("doc001", "Union of India Vs. M/s G.S. Chatha Rice Mills", "Civil Appeal No(s). 2176 of 2021", "2021-03-10",
         "Hon'ble Mr. Justice D.Y. Chandrachud,Hon'ble Mr. Justice M.R. Shah",
         "The core issue revolves around the interpretation of customs tariffs...",
         "<p>The present appeal arises from a judgment...</p>"),
        ("doc002", "State of Punjab vs. Principal Secretary to the Governor", "Writ Petition (Civil) No. 1224 of 2023", "2023-11-10",
         "Hon'ble Chief Justice D.Y. Chandrachud,Hon'ble Mr. Justice J.B. Pardiwala",
         "This case addresses the constitutional powers of the Governor...",
         "<p>This is a significant case concerning the constitutional relationship...</p>"),
        ("doc003", "Competition Commission of India vs. Google LLC", "Civil Appeal No. 54 of 2023", "2023-04-19",
         "Hon'ble Chief Justice D.Y. Chandrachud,Hon'ble Mr. Justice P.S. Narasimha",
         "Examining the allegations of abuse of dominant position by Google...",
         "<p>This landmark case tests the application of Indian competition law...</p>")
    ]

    for c in sample_cases:
        cursor.execute("Select id from cases where id=?",(c[0],))
        if cursor.fetchone() is None:
            cursor.execute('''
            insert into cases (id,case_title,citation,judgement_date,judges,snippet,full_text)
            values (?,?,?,?,?,?,?)       
            ''',c)
    conn.commit()
    conn.close()
    app.run(debug=True)