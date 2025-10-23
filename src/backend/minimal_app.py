from flask import Flask

app = Flask(__name__)

@app.route("/api/health")
def health():
    try:
        return "ok"
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    try:
        app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
