"""Modo demonstração (SM_DEMO=1): dados FICTÍCIOS que passam pelos mesmos
parsers do SIGMINE e do Cadastro Mineiro. Útil para apresentar o app ou
testar sem acesso à rede da ANM."""

from __future__ import annotations

import os
from string import Template

from .models import ProcessoMinerario, formatar_processo, somente_digitos
from .scm import parse_detalhe, parse_lista_processos
from .sigmine import _agrupar

_DIR = os.path.join(os.path.dirname(__file__), "demo_data")

DEMO = [
    {
        "NUMERO": 830123, "ANO": 2010, "AREA_HA": 487.32, "FASE": "CONCESSÃO DE LAVRA",
        "NOME": "MINERAÇÃO EXEMPLO LTDA", "SUBS": "MINÉRIO DE FERRO", "USO": "Industrial", "UF": "MG",
        "ULT_EVENTO": "414 - CONC LAV/RELATÓRIO ANUAL DE LAVRA APRESENTADO EM 15/03/2026",
        "doc": "11.222.333/0001-81", "municipio": "OURO PRETO - MG", "uso_subs": "Industrial",
        "titulos": [("Portaria de Lavra", "123/2014", "20/05/2014", "")],
        "eventos": [("414 - CONC LAV/RELATÓRIO ANUAL DE LAVRA APRESENTADO", "15/03/2026"),
                    ("470 - CONC LAV/PAGAMENTO CFEM", "28/02/2026"),
                    ("401 - CONC LAV/PORTARIA DE LAVRA PUBLICADA", "20/05/2014")],
        "ring": [[-43.5412, -20.3871], [-43.5188, -20.3871], [-43.5188, -20.4065],
                 [-43.5301, -20.4065], [-43.5301, -20.3990], [-43.5412, -20.3990], [-43.5412, -20.3871]],
    },
    {
        "NUMERO": 831456, "ANO": 2021, "AREA_HA": 1250.0, "FASE": "AUTORIZAÇÃO DE PESQUISA",
        "NOME": "MINERAÇÃO EXEMPLO LTDA", "SUBS": "OURO", "USO": "Industrial", "UF": "MG",
        "ULT_EVENTO": "236 - AUT PESQ/PRORROGAÇÃO PRAZO ALVARÁ SOLICITADA EM 02/06/2026",
        "doc": "11.222.333/0001-81", "municipio": "MARIANA - MG", "uso_subs": "Industrial",
        "titulos": [("Alvará de Pesquisa", "4.512/2022", "10/08/2022", "10/08/2025"),
                    ("Prorrogação Alvará de Pesquisa", "1.020/2025", "05/08/2025", "05/08/2027")],
        "eventos": [("236 - AUT PESQ/PRORROGAÇÃO PRAZO ALVARÁ SOLICITADA", "02/06/2026"),
                    ("264 - AUT PESQ/PAGAMENTO TAH EFETUADO", "30/01/2026"),
                    ("209 - AUT PESQ/ALVARÁ DE PESQUISA PUBLICADO", "10/08/2022")],
        "ring": [[-43.4502, -20.3120], [-43.4180, -20.3120], [-43.4180, -20.3475],
                 [-43.4502, -20.3475], [-43.4502, -20.3120]],
    },
    {
        "NUMERO": 870987, "ANO": 2024, "AREA_HA": 49.87, "FASE": "REQUERIMENTO DE LICENCIAMENTO",
        "NOME": "JOÃO DA SILVA EXEMPLO", "SUBS": "AREIA", "USO": "Construção civil", "UF": "SP",
        "ULT_EVENTO": "1391 - REQ LICEN/DOCUMENTO DIVERSO PROTOCOLIZADO EM 12/09/2026",
        "doc": "111.444.777-35", "municipio": "PIRACICABA - SP", "uso_subs": "Construção civil",
        "titulos": [],
        "eventos": [("1391 - REQ LICEN/DOCUMENTO DIVERSO PROTOCOLIZADO", "12/09/2026"),
                    ("700 - REQ LICEN/REQUERIMENTO LICENCIAMENTO PROTOCOLIZADO", "03/04/2024")],
        "ring": [[-47.6590, -22.7010], [-47.6520, -22.7010], [-47.6520, -22.7075],
                 [-47.6590, -22.7075], [-47.6590, -22.7010]],
    },
]


def _html(nome: str) -> Template:
    with open(os.path.join(_DIR, nome), encoding="utf-8") as fh:
        return Template(fh.read().replace("$", "$$").replace("{", "${"))


def _feature(d: dict, geometria: bool = True) -> dict:
    attrs = {k: d[k] for k in ("NUMERO", "ANO", "AREA_HA", "FASE", "NOME", "SUBS", "USO", "UF", "ULT_EVENTO")}
    attrs["PROCESSO"] = f"{d['NUMERO']}/{d['ANO']}"
    return {"attributes": attrs, "geometry": {"rings": [d["ring"]]} if geometria else None}


def html_detalhe(d: dict) -> str:
    titulos = "".join(f"<tr><td>{t}</td><td>{n}</td><td>{p}</td><td>{v}</td></tr>" for t, n, p, v in d["titulos"])
    eventos = "".join(f"<tr><td>{e}</td><td>{dt}</td><td></td></tr>" for e, dt in d["eventos"])
    return _html("scm_detalhe.html").substitute(
        PROCESSO=formatar_processo(d["NUMERO"], d["ANO"]),
        AREA=f"{d['AREA_HA']:.2f}".replace(".", ","), USO=d["USO"], FASE=d["FASE"],
        DOC=d["doc"], TITULAR=d["NOME"], SUBS=d["SUBS"], USO_SUBS=d["uso_subs"],
        MUNICIPIO=d["municipio"], TITULOS=titulos, EVENTOS=eventos,
    )


def html_pesquisa(itens: list[dict]) -> str:
    linhas = "".join(
        f"<tr><td><a href='#'>{formatar_processo(d['NUMERO'], d['ANO'])}</a></td>"
        f"<td>{d['NOME']}</td><td>{d['FASE'].title()}</td><td>{d['SUBS']}</td></tr>" for d in itens
    )
    return _html("scm_pesquisa.html").substitute(LINHAS=linhas)


class DemoSigmine:
    def buscar_processo(self, numero: int, ano: int) -> list[ProcessoMinerario]:
        return _agrupar([_feature(d) for d in DEMO if (d["NUMERO"], d["ANO"]) == (numero, ano)])

    def buscar_processos(self, processos, geometria: bool = True) -> list[ProcessoMinerario]:
        alvo = set(processos)
        return _agrupar([_feature(d, geometria) for d in DEMO if (d["NUMERO"], d["ANO"]) in alvo])

    def buscar_por_titular(self, nome: str, limite: int = 200) -> list[ProcessoMinerario]:
        nome = nome.strip().upper()
        if len(nome) < 3:
            raise ValueError("Informe ao menos 3 caracteres do nome do titular.")
        return _agrupar([_feature(d, False) for d in DEMO if nome in d["NOME"]])


class DemoScm:
    def detalhe_processo(self, processo: str) -> ProcessoMinerario | None:
        for d in DEMO:
            if formatar_processo(d["NUMERO"], d["ANO"]) == processo:
                return parse_detalhe(html_detalhe(d), processo)
        return None

    def processos_por_documento(self, documento: str) -> list[dict[str, str]]:
        alvo = somente_digitos(documento)
        return parse_lista_processos(html_pesquisa([d for d in DEMO if somente_digitos(d["doc"]) == alvo]))
