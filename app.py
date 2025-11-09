from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_session import Session
# from scraping import scrape_india_kanoon
import pandas as pd
import secrets
import sqlite3
import bcrypt
from datetime import datetime
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
    past_queries = None
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
        cursor.execute('''SELECT query FROM history WHERE email=? ORDER BY created_at DESC LIMIT 5''',(session["email"],))
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
            cursor.execute('''SELECT query FROM history WHERE email=? ORDER BY created_at DESC LIMIT 1''',(session["email"],))
            top_query = cursor.fetchone()
            if top_query and len(top_query)>0 and top_query[0]==query:
                cursor.execute("UPDATE history SET created_at = CURRENT_TIMESTAMP where id = ( SELECT id FROM history WHERE email=? ORDER BY created_at DESC LIMIT 1)",(session["email"],))
            else:
                cursor.execute('''INSERT INTO history (email,query) VALUES (?,?)''',(session["email"],query))
            conn.commit()
        cursor.execute('''
        select id,case_id,case_title,citation,judgement_date,snippet from cases where case_title LIKE ? or citation LIKE ? or snippet LIKE ?
        ''',(f"%{query}%", f"%{query}%", f"%{query}%"))
        cases=[
            {
                "id":row[0],
                "case_id":row[1],
                "title":row[2],
                "citation":row[3],
                "judgment_date":row[4],
                "snippet":row[5]
            } for row in cursor.fetchall()
        ]
        past_queries = None
        if session["login_status"]:
            cursor.execute('''SELECT query FROM history WHERE email=? ORDER BY created_at DESC LIMIT 5''',(session["email"],))
            past_queries = cursor.fetchall()
        conn.close()
        return render_template('search-result.html',query=query,cases=cases,past_queries=past_queries,login_status=session.get("login_status",False),name=session.get("name",None))
    
@app.route('/doc_view/<id>',methods=["GET","POST"])
def doc_view(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    select case_id, case_title, citation, judgement_date, judges, pdf_path from cases where id = ?''',(id,))
    case_data = cursor.fetchone()
    conn.close()
    if not case_data:
        return "Document not found", 404
    data={
            "id":id,
            "case_id":case_data[0],
            "title":case_data[1],
            "citation":case_data[2],
            "judgement_date":case_data[3],
            "judges": case_data[4].replace("Coram : ","").split(','),
            "pdf_path": "../"+case_data[5]
        }
    return render_template(
        "Doc_view_page.html",
        case=data,
        login_status=session.get("login_status",False),
        name=session.get("name", None)
    )

@app.route('/pdfs/<filename>')
def serve_pdf(filename):
    return send_from_directory('static/pdfs', filename)

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

@app.route('/history', methods=['GET'])
def history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT query, created_at FROM history WHERE email=? ORDER BY created_at DESC''', (session["email"],))
    rows = cursor.fetchall()
    conn.close()

    past_queries = []
    for query, created_at in rows:
        if isinstance(created_at, str):
            try:
                created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            except:
                pass
        past_queries.append((query, created_at))

    return render_template("history.html", past_queries=past_queries, name=session.get("name", None), email=session.get("email", None))



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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_title TEXT NOT NULL,
    citation TEXT,
    judges TEXT,
    judgement_date TEXT,
    case_id TEXT,
    bench TEXT,
    pdf_path TEXT,
    snippet TEXT
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
    cursor.execute('''SELECT * FROM cases''')
    if len(cursor.fetchall())==0:
        df = pd.read_csv("merged_scraped_data.csv")
        for row_dict in df.to_dict(orient='records'):
            cursor.execute('''INSERT INTO cases (
                           case_title, citation, judges,
                            judgement_date, case_id, 
                           bench, pdf_path, snippet)
                           VALUES (?,?,?,?,?,?,?,?)''',(row_dict["title"],row_dict["citation"],row_dict["coram"],row_dict["decision_date"],row_dict["case_no"],row_dict["bench"],row_dict["pdf_path_or_url"],row_dict["snippet"]))

    conn.commit()
    conn.close()
    app.run(debug=True)
