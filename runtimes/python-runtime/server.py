from flask import Flask, request, jsonify
import sys
import io

app = Flask(__name__)


@app.route("/exec", methods=["POST"])
def execute():
    code = request.json.get("code")

    # Simple exec wrapper
    output = io.StringIO()
    sys.stdout = output
    try:
        exec(code)
        result = output.getvalue()
    except Exception as e:
        result = str(e)
    finally:
        sys.stdout = sys.__stdout__

    return jsonify({"result": result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
