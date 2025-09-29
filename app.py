from flask import Flask, render_template, request
from scraping import scrape_india_kanoon

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search_query',methods=["POST"])
def search_query():
    if request.method == 'POST':
        query = request.form.get("query")
        print(query)
        cases = scrape_india_kanoon(query)
        return render_template('index.html',cases=cases)

if __name__ == '__main__':
    app.run(debug=True)