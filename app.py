import os
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_session import Session
from dotenv import load_dotenv 
import pandas as pd
import secrets
import sqlite3
import bcrypt
from datetime import datetime
import google.generativeai as genai
import numpy as np
import json
import concurrent.futures
import requests
import random

load_dotenv()

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False     
app.config["SESSION_TYPE"] = "filesystem" 
app.secret_key = secrets.token_hex(32)
Session(app)

api_keys = [os.getenv("GEMINI_API_KEY1"),os.getenv("GEMINI_API_KEY2"),os.getenv("GEMINI_API_KEY3")]
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

n_apis = len(api_keys)
genai.configure(api_key=api_keys[0])
if not api_keys[0] or not api_keys[1] or not api_keys[2]:
    print("WARNING: GEMINI_API_KEY1 or GEMINI_API_KEY2 not found in .env file. AI features will fail.")

MODEL_NAME = "gemini-flash-latest"
EMBEDDING_MODEL = "models/text-embedding-004"

def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_embedding(text):
    try:
        if not text or not isinstance(text, str):
            return []
            
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="RETRIEVAL_DOCUMENT"
        )
        return result['embedding']
    except Exception as e:
        print(f"Embedding Error: {e}")
        return []

def generate_summary(text, query, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        You are a legal assistant. Summarize the following legal case snippet in 2 sentences, 
        focusing specifically on what the case is about: "{query}".
        
        Case Text: "{text}"
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Summary Error: {e}")
        return text

def get_practice_area_keywords(query, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Extract the main legal practice area from this query: "{query}". 
        Return ONLY the single word or short phrase (e.g., "Divorce", "Criminal", "Property", "Corporate", "Cheque Bounce").
        If no specific area matches, return "General".
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Practice Area Extraction Error: {e}")
        return "General"

@app.route('/')
def index():
    email = session.get("email")
    name = session.get("name")
    past_queries = []
    if session.get("login_status"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT query FROM history WHERE email=? ORDER BY created_at DESC LIMIT 5''',(email,))
        past_queries = [row for row in cursor.fetchall()]
        conn.close()
    return render_template("index.html", login_status=session.get("login_status", False), name=name, email=email, past_queries=past_queries)

@app.route('/news')
def news():
    topic = request.args.get('topic','legal')
    indian_sources = 'livelaw.in,barandbench.com,timesofindia.indiatimes.com,thehindu.com,hindustantimes.com,indianexpress.com,ndtv.com,indiatoday.in,theprint.in'
    url = f"https://newsapi.org/v2/everything"
    params = {'q': topic, 'domains': indian_sources, 'searchIn': 'title,description','apiKey': NEWS_API_KEY,'language': 'en','sortBy': 'relevancy','pageSize': 100}
    
    articles = []
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get('status') == 'ok':
            articles = data.get('articles', [])
            articles.sort(key=lambda x: x['publishedAt'], reverse=True)
    except:
        articles = []

    return render_template('news.html', articles=articles, topic=topic,login_status=session.get("login_status", False), name=session.get("name"))

@app.route('/search_query/<int:page_num>', methods=["GET", "POST"])
def search_query(page_num):
    if request.method == "GET":
        query = request.args.get("query",'')
        past_queries = []
        
        conn = get_db_connection()
        cursor = conn.cursor()
        if session.get("login_status"):
            email = session["email"]
            cursor.execute('''SELECT id, query FROM history WHERE email=? AND query=?''', (email,query))
            top_query = cursor.fetchone()
            if top_query and top_query['query'] == query:
                cursor.execute("UPDATE history SET created_at = CURRENT_TIMESTAMP WHERE id = ?", (top_query['id'],))
            else:
                cursor.execute('''INSERT INTO history (email, query) VALUES (?, ?)''', (email, query))
            conn.commit()
            cursor.execute('''SELECT query FROM history WHERE email=? ORDER BY created_at DESC LIMIT 5''', (email,))
            past_queries = [row for row in cursor.fetchall()]
        suggested_lawyers = []
        try:
            practice_area = get_practice_area_keywords(query, api_keys[0])
            print(f"Extracted Practice Area: {practice_area}")
            search_term = practice_area if practice_area != "General" else ""
            
            cursor.execute("SELECT * FROM lawyers WHERE specialization LIKE ? ORDER BY rating DESC LIMIT 10", (f'%{search_term}%',))
            top_matches = cursor.fetchall()
            
            if len(top_matches) > 3:
                suggested_lawyers = random.sample(top_matches, 3)
            else:
                suggested_lawyers = top_matches
                
        except Exception as e:
            print(f"Lawyer Suggestion Error: {e}")

        try:
            query_res = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=query,
                task_type="RETRIEVAL_QUERY"
            )
            q_vec = np.array(query_res['embedding'])
            
            cursor.execute("SELECT id, case_title, citation, judgement_date, snippet, case_id, embedding FROM cases")
            rows = cursor.fetchall()
            
            valid_rows = []
            valid_embeddings = []
            
            for r in rows:
                if r['embedding']:
                    try:
                        vec = json.loads(r['embedding'])
                        valid_embeddings.append(vec)
                        valid_rows.append(r)
                    except:
                        continue
            
            if not valid_embeddings:
                top_results = []
            else:
                doc_matrix = np.array(valid_embeddings)
                norms = np.linalg.norm(doc_matrix, axis=1) * np.linalg.norm(q_vec)
                norms[norms == 0] = 1 
                scores = np.dot(doc_matrix, q_vec) / norms
                results = list(zip(scores, valid_rows))
                results.sort(key=lambda x: x[0], reverse=True)
                top_results = results
                print(len(top_results))

        except Exception as e:
            print(f"Search Error: {e}")
            top_results = []
        page_nums = (page_num,int(np.ceil(len(top_results)/10)))
        ai_batch = top_results[(page_num-1)*10:page_num*10]
        
        ai_results_fixed = [None] * len(ai_batch)

        def process_ai_item(data, api_key):
            index, item = data
            score, row = item
            summary = generate_summary(row['snippet'], query, api_key)
            return index, {"id": row['id'],"case_id": row['case_id'],"case_title": row['case_title'],"title": row['case_title'],"citation": row['citation'],"judgement_date": row['judgement_date'],"snippet": summary}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_idx = {
                executor.submit(process_ai_item, (i, item, api_keys[i%n_apis])): i 
                for i, item in enumerate(ai_batch)
            }
            
            for future in concurrent.futures.as_completed(future_to_idx):
                try:
                    idx, result = future.result()
                    ai_results_fixed[idx] = result
                except Exception as e:
                    original_idx = future_to_idx[future]
                    orig_row = ai_batch[original_idx][1]
                    ai_results_fixed[original_idx] = {
                        "id": orig_row['id'],"case_id": orig_row['case_id'],"case_title": orig_row['case_title'],"title": orig_row['case_title'],"citation": orig_row['citation'],"judgement_date": orig_row['judgement_date'],"snippet": orig_row['snippet']
                    }

        final_cases = [x for x in ai_results_fixed if x is not None]
        conn.close()
        return render_template('search-result.html', query=query, cases=final_cases, past_queries=past_queries, page_nums=page_nums, login_status=session.get("login_status", False), name=session.get("name"), suggested_lawyers=suggested_lawyers)

@app.route('/doc_view/<id>')
def doc_view(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT case_id, case_title, citation, judgement_date, judges, pdf_path FROM cases WHERE id = ?', (id,))
    case_data = cursor.fetchone()
    conn.close()
    if not case_data:
        return "Document not found", 404
    
    judges_list = case_data['judges'].replace("Coram : ","").split(',') if case_data['judges'] else []
    
    data = {
        "id": id,
        "case_id": case_data['case_id'],
        "title": case_data['case_title'],
        "citation": case_data['citation'],
        "judgement_date": case_data['judgement_date'],
        "judges": judges_list,
        "pdf_path": "../" + (case_data['pdf_path'] if case_data['pdf_path'] else "")
    }
    return render_template("Doc_view_page.html", case=data, login_status=session.get("login_status", False), name=session.get("name"))

@app.route('/login', methods=["POST"])
def login():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, pwd FROM users WHERE email=?', (data.get("email"),))
    user = cursor.fetchone()
    conn.close()
    if user and bcrypt.checkpw(data.get("pwd").encode('utf-8'), user['pwd'].encode('utf-8')):
        session["login_status"] = True
        session["email"] = data.get("email")
        session["name"] = user['name']
        return jsonify({"login": True})
    return jsonify({"login": False})

@app.route('/register', methods=["POST"])
def register():
    data = request.get_json()
    hashed = bcrypt.hashpw(data.get("pwd").encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (email,name,pwd,dob) VALUES(?,?,?,?)', 
                       (data.get("email"), data.get("name"), hashed, data.get("dob")))
        conn.commit()
        res = 1
    except:
        res = 0
    conn.close()
    return jsonify({"registration": res})

@app.route('/logout', methods=["POST"])
def logout():
    session.clear()
    return jsonify({"login": False})

@app.route('/pdfs/<filename>')
def serve_pdf(filename):
    return send_from_directory('static/pdfs', filename)

@app.route('/lawyers')
def lawyers():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = request.args.get('query', '').strip()
    city = request.args.get('city', '').strip()
    
    sql = "SELECT * FROM lawyers WHERE 1=1"
    params = []
    
    if query:
        sql += " AND (name LIKE ? OR specialization LIKE ?)"
        params.extend([f'%{query}%', f'%{query}%'])
    if city:
        sql += " AND city LIKE ?"
        params.append(f'%{city}%')
        
    cursor.execute(sql, params)
    lawyers_data = cursor.fetchall()
    conn.close()
    
    return render_template("lawyers.html", lawyers=lawyers_data, query=query, city=city, 
                           login_status=session.get("login_status", False), name=session.get("name"))

@app.route('/history', methods=['GET'])
def history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT query, created_at FROM history WHERE email=? ORDER BY created_at DESC''', (session.get("email"),))
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, name TEXT NOT NULL, pwd TEXT NOT NULL, dob TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        case_title TEXT NOT NULL, 
        citation TEXT, 
        judges TEXT, 
        judgement_date TEXT, 
        case_id TEXT, 
        bench TEXT, 
        pdf_path TEXT, 
        snippet TEXT,
        embedding TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, query TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('DROP TABLE IF EXISTS lawyers')
    cursor.execute('''CREATE TABLE IF NOT EXISTS lawyers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        url TEXT,
        image_url TEXT,
        city TEXT,
        state TEXT,
        address TEXT,
        specialization TEXT,
        experience TEXT,
        rating TEXT
    )''')
    conn.commit()
    
    cursor.execute('SELECT count(*) FROM cases')
    count = cursor.fetchone()[0]
    
    if count == 0 and os.path.exists("merged_scraped_data.csv"):
        print("--- FIRST RUN DETECTED ---")
        print("Reading CSV and generating AI Embeddings. This will take a few minutes...")
        
        df = pd.read_csv("merged_scraped_data.csv")
        records = df.to_dict(orient='records')
        
        for i, row in enumerate(records):
            if i % 5 == 0:
                print(f"Processing record {i+1}/{len(records)}...")
            content_to_embed = f"{row.get('title', '')} {row.get('snippet', '')}"
            vector = get_embedding(content_to_embed)
            vector_json = json.dumps(vector) 
            
            cursor.execute('''INSERT INTO cases (case_title, citation, judges, judgement_date, case_id, bench, pdf_path, snippet, embedding)
                           VALUES (?,?,?,?,?,?,?,?,?)''', 
                           (row.get("title"), row.get("citation"), row.get("coram"), row.get("decision_date"), 
                            row.get("case_no"), row.get("bench"), row.get("pdf_path_or_url"), 
                            row.get("snippet"), vector_json))
        conn.commit()
        print("--- DATABASE INITIALIZED SUCCESSFULLY ---")

    print("Loading lawyers from CSV...")
    if os.path.exists("lawyers.csv"):
        l_df = pd.read_csv("lawyers.csv")
        l_df = l_df.where(pd.notnull(l_df), None)
        l_records = l_df.to_dict(orient='records')
        for row in l_records:
            cursor.execute('''INSERT INTO lawyers (name, url, image_url, city, state, address, specialization, experience, rating)
                           VALUES (?,?,?,?,?,?,?,?,?)''',
                           (row.get("name"), row.get("url"), row.get("image_url"), row.get("city"), 
                            row.get("state"), row.get("address"), row.get("specialization"), 
                            row.get("experience"), row.get("rating")))
        conn.commit()

    conn.close()
    app.run(debug=True)
