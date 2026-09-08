from flask import Flask, redirect, render_template, request, url_for, send_file
import sqlite3
import qrcode
import io
import random
import string
import os

app = Flask(__name__)
DB = "database.db"

# ──────────────────────────────────────────
#  Banco de dados
# ──────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS placas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo    TEXT UNIQUE NOT NULL,
                cliente   TEXT NOT NULL,
                negocio   TEXT NOT NULL,
                url_google TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()

def gerar_codigo():
    """Gera um código único de 6 caracteres pra cada placa"""
    chars = string.ascii_uppercase + string.digits
    while True:
        codigo = ''.join(random.choices(chars, k=6))
        with get_db() as db:
            existe = db.execute("SELECT 1 FROM placas WHERE codigo = ?", (codigo,)).fetchone()
        if not existe:
            return codigo

# ──────────────────────────────────────────
#  Rota de redirect (o coração do sistema)
# ──────────────────────────────────────────

@app.route("/p/<codigo>")
def redirecionar(codigo):
    """Quando o cliente escaneia o QR ou aproxima o NFC, cai aqui"""
    with get_db() as db:
        placa = db.execute("SELECT * FROM placas WHERE codigo = ?", (codigo,)).fetchone()
    if not placa:
        return "Placa não encontrada.", 404
    return redirect(placa["url_google"])

# ──────────────────────────────────────────
#  Painel admin
# ──────────────────────────────────────────

@app.route("/admin")
def admin():
    with get_db() as db:
        placas = db.execute("SELECT * FROM placas ORDER BY criado_em DESC").fetchall()
    return render_template("admin.html", placas=placas)

@app.route("/admin/cadastrar", methods=["POST"])
def cadastrar():
    cliente   = request.form["cliente"].strip()
    negocio   = request.form["negocio"].strip()
    url_google = request.form["url_google"].strip()

    if not all([cliente, negocio, url_google]):
        return "Preencha todos os campos.", 400

    codigo = gerar_codigo()

    with get_db() as db:
        db.execute(
            "INSERT INTO placas (codigo, cliente, negocio, url_google) VALUES (?, ?, ?, ?)",
            (codigo, cliente, negocio, url_google)
        )
        db.commit()

    return redirect(url_for("admin"))

@app.route("/admin/deletar/<int:id>", methods=["POST"])
def deletar(id):
    with get_db() as db:
        db.execute("DELETE FROM placas WHERE id = ?", (id,))
        db.commit()
    return redirect(url_for("admin"))

# ──────────────────────────────────────────
#  Gerador de QR Code
# ──────────────────────────────────────────

@app.route("/qr/<codigo>")
def gerar_qr(codigo):
    """Retorna a imagem do QR code pra aquele código"""
    with get_db() as db:
        placa = db.execute("SELECT * FROM placas WHERE codigo = ?", (codigo,)).fetchone()
    if not placa:
        return "Placa não encontrada.", 404

    # URL que vai dentro do QR — aponta pro seu sistema, não pro Google direto
    base_url = request.host_url.rstrip("/")
    link = f"{base_url}/p/{codigo}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"qr_{codigo}.png")

# ──────────────────────────────────────────
#  Inicialização
# ──────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("✅ Sistema rodando em http://localhost:5000/admin")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
