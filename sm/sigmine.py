"""Cliente do SIGMINE (serviço ArcGIS REST público da ANM).

Camada: "Processos minerários ativos" — SIGMINE/dados_anm/MapServer/0
Campos usados: PROCESSO, NUMERO, ANO, AREA_HA, FASE, ULT_EVENTO, NOME, SUBS, USO, UF.
Fornece a geometria (polígonos) do título, em WGS84 (outSR=4326).
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable

import requests

from .models import Evento, ProcessoMinerario, formatar_processo

SIGMINE_URL = os.environ.get(
    "SM_SIGMINE_URL",
    "https://geo.anm.gov.br/arcgis/rest/services/SIGMINE/dados_anm/MapServer/0/query",
)
USER_AGENT = "SM-SearchMining/1.0 (DANKHE PROJETOS)"
TIMEOUT = float(os.environ.get("SM_TIMEOUT", "30"))

_ULT_EVENTO_RE = re.compile(
    r"^\s*(?P<cod>\d+)\s*-\s*(?P<desc>.*?)(?:\s+EM\s+(?P<data>\d{2}/\d{2}/\d{4}))?\s*$",
    re.IGNORECASE,
)


class SigmineError(RuntimeError):
    pass


def parse_ult_evento(texto: str | None) -> Evento:
    """'2305 - AUT PESQ/RELATORIO PESQ APROVADO EM 12/03/2020' -> Evento."""
    texto = (texto or "").strip()
    if not texto:
        return Evento()
    m = _ULT_EVENTO_RE.match(texto)
    if not m:
        return Evento(descricao=texto)
    return Evento(codigo=m.group("cod"), descricao=m.group("desc").strip(), data=m.group("data") or "")


class SigmineClient:
    def __init__(self, url: str = SIGMINE_URL, session: requests.Session | None = None):
        self.url = url
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)

    # ------------------------------------------------------------------ #
    def _query(self, where: str, geometria: bool = True, limite: int | None = None) -> list[dict]:
        params: dict[str, Any] = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true" if geometria else "false",
            "outSR": 4326,
            "f": "json",
        }
        if limite:
            params["resultRecordCount"] = limite
        try:
            resp = self.session.post(self.url, data=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise SigmineError(f"Falha ao consultar o SIGMINE/ANM: {exc}") from exc
        if "error" in data:
            raise SigmineError(f"SIGMINE retornou erro: {data['error'].get('message', data['error'])}")
        return data.get("features", [])

    # ------------------------------------------------------------------ #
    def buscar_processo(self, numero: int, ano: int) -> list[ProcessoMinerario]:
        """Busca um processo pelo número/ano. Tenta variações de filtro, pois o
        tipo/formatação dos campos já mudou entre versões da camada."""
        fmt = formatar_processo(numero, ano)
        tentativas = [
            f"NUMERO = {numero} AND ANO = {ano}",
            f"PROCESSO = '{fmt}'",
            f"PROCESSO = '{numero}/{ano}'",
        ]
        ultimo_erro: SigmineError | None = None
        alguma_ok = False
        for where in tentativas:
            try:
                feats = self._query(where)
            except SigmineError as exc:
                ultimo_erro = exc
                continue
            alguma_ok = True
            if feats:
                return _agrupar(feats)
        if not alguma_ok and ultimo_erro:
            raise ultimo_erro
        return []

    def buscar_processos(self, processos: Iterable[tuple[int, int]], geometria: bool = True) -> list[ProcessoMinerario]:
        """Busca vários processos (em lotes) — usado na pesquisa por CPF/CNPJ."""
        lista = list(dict.fromkeys(processos))
        resultado: list[ProcessoMinerario] = []
        for i in range(0, len(lista), 40):
            lote = lista[i : i + 40]
            where = " OR ".join(f"(NUMERO = {n} AND ANO = {a})" for n, a in lote)
            resultado.extend(_agrupar(self._query(where, geometria=geometria)))
        return resultado

    def buscar_por_titular(self, nome: str, limite: int = 200) -> list[ProcessoMinerario]:
        nome = re.sub(r"\s+", " ", nome.strip().upper()).replace("'", "''")
        if len(nome) < 3:
            raise ValueError("Informe ao menos 3 caracteres do nome do titular.")
        feats = self._query(f"UPPER(NOME) LIKE '%{nome}%'", geometria=False, limite=limite)
        return _agrupar(feats)


# ---------------------------------------------------------------------- #
def _attr(attrs: dict, nome: str, padrao: Any = "") -> Any:
    for k, v in attrs.items():
        if k.upper() == nome:
            return padrao if v is None else v
    return padrao


def _processo_de_attrs(attrs: dict) -> str:
    numero, ano = _attr(attrs, "NUMERO", None), _attr(attrs, "ANO", None)
    try:
        return formatar_processo(int(numero), int(ano))
    except (TypeError, ValueError):
        return str(_attr(attrs, "PROCESSO"))


def _agrupar(features: list[dict]) -> list[ProcessoMinerario]:
    """Converte features ArcGIS em ProcessoMinerario (um processo pode ter
    mais de uma feature/polígono)."""
    por_proc: dict[str, ProcessoMinerario] = {}
    for f in features:
        attrs = f.get("attributes", {}) or {}
        chave = _processo_de_attrs(attrs)
        p = por_proc.get(chave)
        if p is None:
            area = _attr(attrs, "AREA_HA", None)
            subs = str(_attr(attrs, "SUBS")).strip()
            p = ProcessoMinerario(
                processo=chave,
                titular=str(_attr(attrs, "NOME")).strip(),
                fase=str(_attr(attrs, "FASE")).strip(),
                substancias=[subs] if subs else [],
                uso=str(_attr(attrs, "USO")).strip(),
                area_ha=float(area) if area not in (None, "") else None,
                status="Ativo",  # a camada contém apenas processos ativos
                uf=str(_attr(attrs, "UF")).strip(),
                ultimo_evento=parse_ult_evento(_attr(attrs, "ULT_EVENTO")),
                fontes=["SIGMINE/ANM"],
            )
            por_proc[chave] = p
        geom = f.get("geometry") or {}
        for ring in geom.get("rings", []) or []:
            p.poligonos.append([[round(float(x), 7), round(float(y), 7)] for x, y, *_ in ring])
    return list(por_proc.values())
