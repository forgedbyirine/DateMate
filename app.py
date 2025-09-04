from flask import Flask, jsonify
from flask_cors import CORS
from db import init_db, mysql

app = Flask(__name__)
CORS(app)   # allow frontend to connect

# Initialize DB
init_db(app)

@app.route("/health")
def health():
    return {"status": "ok"}



if __name__ == "__main__":
    app.run(debug=True)
