"""SM (Search Mining) — DANKHE PROJETOS.

Consulta pública de processos minerários na ANM (Cadastro Mineiro + SIGMINE),
por número do processo, CPF/CNPJ ou nome do titular. Sem login.

    pip install -r requirements.txt
    python app.py              # http://localhost:5000
    SM_DEMO=1 python app.py    # dados fictícios, sem acessar a ANM
"""

from __future__ import annotations

import logging
import os

from flask import Flask, Response, jsonify, render_template, request

from sm.kml import gerar_kml, nome_arquivo
from sm.models import DocumentoInvalido, ProcessoInvalido
from sm.pdf import gerar_pdf
from sm.service import ConsultaError, criar_servico

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
servico = criar_servico()
MAX_PDF_LOTE = 25


def _erro(msg: str, status: int):
    return jsonify({"erro": msg}), status


@app.errorhandler(ProcessoInvalido)
@app.errorhandler(DocumentoInvalido)
@app.errorhandler(ValueError)
def _entrada_invalida(exc):
    return _erro(str(exc), 400)


@app.errorhandler(ConsultaError)
def _anm_indisponivel(exc):
    return _erro(str(exc), 502)


class NaoEncontrado(Exception):
    pass


def _obter(numero: str):
    p = servico.consultar_processo(numero)
    if p is None:
        raise NaoEncontrado(numero)
    return p


@app.errorhandler(NaoEncontrado)
def _nao_encontrado(exc):
    return _erro(f"Processo {exc.args[0]} não encontrado na base da ANM.", 404)


@app.get("/")
def index():
    return render_template("index.html", demo=os.environ.get("SM_DEMO") == "1")


@app.get("/api/processo")
def api_processo():
    return jsonify(_obter(request.args.get("numero", "")).to_dict())


@app.get("/api/documento")
def api_documento():
    itens = servico.buscar_por_documento(request.args.get("doc", ""))
    return jsonify([p.to_dict(incluir_geometria=False) for p in itens])


@app.get("/api/titular")
def api_titular():
    itens = servico.buscar_por_titular(request.args.get("nome", ""))
    return jsonify([p.to_dict(incluir_geometria=False) for p in itens])


@app.get("/api/kml")
def api_kml():
    p = _obter(request.args.get("numero", ""))
    try:
        kml = gerar_kml(p)
    except ValueError as exc:
        return _erro(str(exc), 404)
    return Response(kml, mimetype="application/vnd.google-earth.kml+xml",
                    headers={"Content-Disposition": f'attachment; filename="{nome_arquivo(p, "kml")}"'})


@app.route("/api/pdf", methods=["GET", "POST"])
def api_pdf():
    if request.method == "POST":
        numeros = (request.get_json(silent=True) or {}).get("processos", [])
    else:
        numeros = request.args.getlist("numero")
    numeros = [n for n in dict.fromkeys(numeros) if n][:MAX_PDF_LOTE]
    if not numeros:
        return _erro("Informe ao menos um processo.", 400)
    itens = [p for n in numeros if (p := servico.consultar_processo(n))]
    if not itens:
        return _erro("Nenhum processo encontrado.", 404)
    nome = nome_arquivo(itens[0], "pdf") if len(itens) == 1 else "SM_relatorio_processos.pdf"
    return Response(gerar_pdf(itens), mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("SM_DEBUG") == "1")
