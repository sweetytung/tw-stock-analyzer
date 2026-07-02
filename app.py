from flask import Flask, request, jsonify, render_template
from services.stock_service import get_top20_volume, get_top20_detail

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/top20")
def top20():
    date = request.args.get("date")
    return jsonify(get_top20_volume(date))

@app.route("/top20/detail")
def top20_detail():
    date = request.args.get("date")
    return jsonify(get_top20_detail(date))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
