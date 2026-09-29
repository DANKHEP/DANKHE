"""Modelos de dados e utilitários de validação do SM (Search Mining)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

# Anel = lista de [longitude, latitude] (WGS84 / EPSG:4326)
Ring = list[list[float]]


class ProcessoInvalido(ValueError):
    """Número de processo em formato não reconhecido."""


class DocumentoInvalido(ValueError):
    """CPF ou CNPJ inválido."""


@dataclass
class Evento:
    codigo: str = ""
    descricao: str = ""
    data: str = ""  # dd/mm/aaaa


@dataclass
class ProcessoMinerario:
    processo: str  # formato ANM: 830.123/2010
    titular: str = ""
    cpf_cnpj: str = ""
    fase: str = ""
    substancias: list[str] = field(default_factory=list)
    uso: str = ""
    area_ha: float | None = None
    status: str = ""  # Ativo / Inativo
    municipios: list[str] = field(default_factory=list)
    uf: str = ""
    data_vencimento: str = ""
    ultimo_evento: Evento = field(default_factory=Evento)
    eventos: list[Evento] = field(default_factory=list)
    poligonos: list[Ring] = field(default_factory=list)
    fontes: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def substancia(self) -> str:
        return ", ".join(self.substancias)

    @property
    def municipio(self) -> str:
        return ", ".join(self.municipios)

    @property
    def total_vertices(self) -> int:
        return sum(len(r) for r in self.poligonos)

    @property
    def centroide(self) -> tuple[float, float] | None:
        pts = [p for r in self.poligonos for p in r]
        if not pts:
            return None
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    def to_dict(self, incluir_geometria: bool = True) -> dict[str, Any]:
        d = asdict(self)
        d["substancia"] = self.substancia
        d["municipio"] = self.municipio
        d["total_vertices"] = self.total_vertices
        d["centroide"] = self.centroide
        if not incluir_geometria:
            d.pop("poligonos")
        return d


# --------------------------------------------------------------------------- #
# Número do processo
# --------------------------------------------------------------------------- #
_PROC_RE = re.compile(r"^\s*(\d{1,3})\.?(\d{3})\s*/\s*(\d{4})\s*$")
_PROC_DIGITS_RE = re.compile(r"^\s*(\d{6})(\d{4})\s*$")


def parse_processo(valor: str) -> tuple[int, int]:
    """Converte '830.123/2010', '830123/2010' ou '8301232010' em (830123, 2010)."""
    valor = (valor or "").strip()
    m = _PROC_RE.match(valor)
    if m:
        numero, ano = int(m.group(1) + m.group(2)), int(m.group(3))
    else:
        m = _PROC_DIGITS_RE.match(re.sub(r"[.\-/\s]", "", valor))
        if not m:
            raise ProcessoInvalido(
                f"Processo '{valor}' inválido. Use o formato 000.000/0000 (ex.: 830.123/2010)."
            )
        numero, ano = int(m.group(1)), int(m.group(2))
    if not 1900 <= ano <= 2100:
        raise ProcessoInvalido(f"Ano do processo inválido: {ano}.")
    return numero, ano


def formatar_processo(numero: int, ano: int) -> str:
    s = f"{numero:06d}"
    return f"{s[:3]}.{s[3:]}/{ano}"


def normalizar_processo(valor: str) -> str:
    return formatar_processo(*parse_processo(valor))


# --------------------------------------------------------------------------- #
# CPF / CNPJ
# --------------------------------------------------------------------------- #
def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _cpf_valido(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if int(d[n]) != (s * 10 % 11) % 10:
            return False
    return True


def _cnpj_valido(d: str) -> bool:
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        p = pesos if n == 12 else [6] + pesos
        s = sum(int(d[i]) * p[i] for i in range(n))
        r = s % 11
        if int(d[n]) != (0 if r < 2 else 11 - r):
            return False
    return True


def validar_documento(valor: str) -> str:
    """Retorna somente os dígitos de um CPF/CNPJ válido ou levanta DocumentoInvalido."""
    d = somente_digitos(valor)
    if len(d) == 11 and _cpf_valido(d):
        return d
    if len(d) == 14 and _cnpj_valido(d):
        return d
    raise DocumentoInvalido(f"'{valor}' não é um CPF ou CNPJ válido.")


def formatar_documento(d: str) -> str:
    d = somente_digitos(d)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return d
