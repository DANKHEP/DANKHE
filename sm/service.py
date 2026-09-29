"""Consolida SIGMINE (geometria/atributos) + Cadastro Mineiro (situação, eventos,
municípios, vencimento) em um único resumo do processo minerário."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import replace

from .models import (
    ProcessoMinerario,
    formatar_documento,
    normalizar_processo,
    parse_processo,
    validar_documento,
)
from .scm import ScmClient, ScmError
from .sigmine import SigmineClient, SigmineError

log = logging.getLogger(__name__)
CACHE_TTL = float(os.environ.get("SM_CACHE_TTL", "900"))


class ConsultaError(RuntimeError):
    """Nenhuma fonte da ANM respondeu."""


class _Cache:
    def __init__(self, ttl: float, maximo: int = 256):
        self.ttl, self.maximo = ttl, maximo
        self._d: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, k: str):
        with self._lock:
            item = self._d.get(k)
            if item and time.time() - item[0] < self.ttl:
                return item[1]
            self._d.pop(k, None)
            return None

    def set(self, k: str, v) -> None:
        with self._lock:
            if len(self._d) >= self.maximo:
                self._d.pop(min(self._d, key=lambda x: self._d[x][0]))
            self._d[k] = (time.time(), v)


def _mesclar(sig: ProcessoMinerario | None, scm: ProcessoMinerario | None) -> ProcessoMinerario | None:
    if not sig and not scm:
        return None
    if not sig:
        return scm
    if not scm:
        sig.avisos.append("Cadastro Mineiro indisponível: município, eventos e vencimento podem estar incompletos.")
        return sig
    p = replace(sig)
    p.titular = scm.titular or sig.titular
    p.cpf_cnpj = scm.cpf_cnpj
    p.fase = sig.fase or scm.fase
    p.substancias = scm.substancias or sig.substancias
    p.uso = sig.uso or scm.uso
    p.area_ha = sig.area_ha if sig.area_ha is not None else scm.area_ha
    p.status = scm.status or sig.status
    p.municipios = scm.municipios
    p.uf = sig.uf or scm.uf
    p.data_vencimento = scm.data_vencimento
    p.eventos = scm.eventos
    p.ultimo_evento = scm.ultimo_evento if scm.ultimo_evento.descricao else sig.ultimo_evento
    p.fontes = sig.fontes + scm.fontes
    p.avisos = []
    return p


class SearchMiningService:
    def __init__(self, sigmine: SigmineClient | None = None, scm: ScmClient | None = None):
        self.sigmine = sigmine or SigmineClient()
        self.scm = scm or ScmClient()
        self._cache = _Cache(CACHE_TTL)

    # ------------------------------------------------------------------ #
    def consultar_processo(self, processo: str) -> ProcessoMinerario | None:
        fmt = normalizar_processo(processo)
        em_cache = self._cache.get(f"p:{fmt}")
        if em_cache is not None:
            return em_cache
        numero, ano = parse_processo(fmt)
        erros: list[str] = []

        sig = None
        try:
            achados = self.sigmine.buscar_processo(numero, ano)
            sig = achados[0] if achados else None
        except SigmineError as exc:
            log.warning("SIGMINE: %s", exc)
            erros.append(str(exc))

        scm = None
        try:
            scm = self.scm.detalhe_processo(fmt)
        except ScmError as exc:
            log.warning("SCM: %s", exc)
            erros.append(str(exc))

        if sig is None and scm is None and len(erros) == 2:
            raise ConsultaError("Os serviços da ANM não responderam. Tente novamente em instantes.")

        p = _mesclar(sig, scm)
        if p is not None:
            if sig is None:
                p.avisos.append("Polígono não disponível no SIGMINE (processo inativo ou sem geometria).")
            if p.cpf_cnpj and p.cpf_cnpj.isdigit():
                p.cpf_cnpj = formatar_documento(p.cpf_cnpj)
            self._cache.set(f"p:{fmt}", p)
        return p

    def buscar_por_documento(self, documento: str) -> list[ProcessoMinerario]:
        doc = validar_documento(documento)
        chave = f"d:{doc}"
        em_cache = self._cache.get(chave)
        if em_cache is not None:
            return em_cache
        try:
            lista = self.scm.processos_por_documento(formatar_documento(doc))
        except ScmError as exc:
            raise ConsultaError(str(exc)) from exc
        if not lista:
            return []
        resumos: dict[str, ProcessoMinerario] = {}
        try:
            pares = [parse_processo(i["processo"]) for i in lista]
            for p in self.sigmine.buscar_processos(pares, geometria=False):
                resumos[p.processo] = p
        except SigmineError as exc:
            log.warning("SIGMINE (lote): %s", exc)
        resultado = []
        for item in lista:
            p = resumos.get(item["processo"]) or ProcessoMinerario(
                processo=item["processo"], titular=item.get("titular", ""), fase=item.get("fase", ""),
                status="Inativo/sem polígono", fontes=["Cadastro Mineiro/ANM"],
            )
            p.cpf_cnpj = formatar_documento(doc)
            resultado.append(p)
        self._cache.set(chave, resultado)
        return resultado

    def buscar_por_titular(self, nome: str) -> list[ProcessoMinerario]:
        try:
            return self.sigmine.buscar_por_titular(nome)
        except SigmineError as exc:
            raise ConsultaError(str(exc)) from exc


def criar_servico() -> SearchMiningService:
    if os.environ.get("SM_DEMO") == "1":
        from .demo import DemoScm, DemoSigmine

        return SearchMiningService(DemoSigmine(), DemoScm())
    return SearchMiningService()


def verificar_status_processo(processo: str, servico: SearchMiningService | None = None) -> dict:
    """Verifica o status de um processo minerário no Cadastro Mineiro/SIGMINE da ANM.

    >>> verificar_status_processo("830.123/2010")  # doctest: +SKIP
    {'processo': '830.123/2010', 'titular': '...', 'fase': 'Lavra', 'status': 'Ativo', ...}

    Retorna um dicionário com o resumo (sem os vértices do polígono) ou levanta
    ValueError se o processo não for encontrado.
    """
    p = (servico or criar_servico()).consultar_processo(processo)
    if p is None:
        raise ValueError(f"Processo {normalizar_processo(processo)} não encontrado na base da ANM.")
    return p.to_dict(incluir_geometria=False)
