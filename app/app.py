import json
import os
import time
import uuid
import requests

from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuração vinda do docker-compose (variáveis de ambiente)
INSTANCE_NAME = os.environ.get("INSTANCE_NAME", "app1")
DATA_DIR = os.environ.get("DATA_DIR", "./data")
LOG_FILE = os.path.join(DATA_DIR, f"{INSTANCE_NAME}.log")
# Lista de peers vinda do compose, ex.: PEERS="app2,app3"
PEERS = [p.strip() for p in os.environ.get("PEERS", "").split(",") if p.strip()]

os.makedirs(DATA_DIR, exist_ok=True)


def save_message(msg):
    """Acrescenta uma mensagem (dict) ao arquivo desta instância, uma linha JSON por mensagem."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def read_messages(path=LOG_FILE):
    """Lê todas as mensagens de um arquivo de log. Retorna lista vazia se não existir."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@app.route("/messages", methods=["GET"])
def get_messages():
    return jsonify({"instance": INSTANCE_NAME, "messages": read_messages()})

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "JSON com campo 'message' é obrigatório"}), 400

    msg = {
        "id": str(uuid.uuid4()),
        "origin": INSTANCE_NAME,
        "message": data["message"],
        "ts": time.time(),
    }
    save_message(msg)

    # Envia uma cópia para cada peer
    replication = {}
    for peer in PEERS:
        try:
            r = requests.post(f"http://{peer}:5000/replicate", json=msg, timeout=3)
            replication[peer] = "ok" if r.status_code == 200 else f"erro {r.status_code}"
        except requests.RequestException as e:
            replication[peer] = f"falhou: {type(e).__name__}"

    return jsonify({"stored": msg, "replication": replication}), 201


@app.route("/replicate", methods=["POST"])
def replicate():
    """Rota interna: só grava localmente, NÃO reenvia (evita loop infinito)."""
    msg = request.get_json(silent=True)
    if not msg or "id" not in msg:
        return jsonify({"error": "mensagem inválida"}), 400
    save_message(msg)
    return jsonify({"status": "replicated", "instance": INSTANCE_NAME}), 200


@app.route("/verify", methods=["GET"])
def verify():
    """Compara os IDs deste arquivo de log com os dos arquivos das outras instâncias."""
    mine = {m["id"] for m in read_messages()}
    report = {}
    for peer in PEERS:
        theirs = {m["id"] for m in read_messages(os.path.join(DATA_DIR, f"{peer}.log"))}
        report[peer] = {
            "missing_here": len(theirs - mine),
            "missing_there": len(mine - theirs),
            "in_sync": mine == theirs,
        }
    return jsonify({"instance": INSTANCE_NAME, "total": len(mine), "peers": report})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
