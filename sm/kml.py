"""Geração do KML do polígono do título minerário (dados do SIGMINE/ANM)."""

from __future__ import annotations

from xml.sax.saxutils import escape

from .models import ProcessoMinerario


def _fechar(ring: list[list[float]]) -> list[list[float]]:
    return ring if ring and ring[0] == ring[-1] else ring + ring[:1]


def gerar_kml(p: ProcessoMinerario) -> str:
    if not p.poligonos:
        raise ValueError("Processo sem polígono disponível na base da ANM.")
    dados = {
        "Processo": p.processo,
        "Titular": p.titular,
        "CPF/CNPJ": p.cpf_cnpj,
        "Fase": p.fase,
        "Substancia": p.substancia,
        "Uso": p.uso,
        "Area (ha)": f"{p.area_ha:.2f}" if p.area_ha is not None else "",
        "Status": p.status,
        "Municipio": p.municipio,
        "UF": p.uf,
        "Data de vencimento": p.data_vencimento,
        "Ultimo evento": " - ".join(x for x in (p.ultimo_evento.codigo, p.ultimo_evento.descricao) if x),
        "Data do ultimo evento": p.ultimo_evento.data,
        "Fonte": "ANM - SIGMINE / Cadastro Mineiro | SM (Search Mining) - DANKHE PROJETOS",
    }
    extended = "".join(
        f'<Data name="{escape(k)}"><value>{escape(str(v))}</value></Data>' for k, v in dados.items() if v
    )
    descricao = "".join(f"<b>{escape(k)}:</b> {escape(str(v))}<br/>" for k, v in dados.items() if v)
    # Cada anel vira um Polygon; anéis no sentido anti-horário no ArcGIS são buracos,
    # mas para simplicidade e compatibilidade, cada anel é exportado como polígono.
    poligonos = "".join(
        "<Polygon><tessellate>1</tessellate><outerBoundaryIs><LinearRing><coordinates>"
        + " ".join(f"{x:.7f},{y:.7f},0" for x, y in _fechar(r))
        + "</coordinates></LinearRing></outerBoundaryIs></Polygon>"
        for r in p.poligonos
    )
    nome = escape(f"{p.processo} - {p.titular}".strip(" -"))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n'
        f"<name>SM - Processo {escape(p.processo)}</name>\n"
        '<Style id="anm"><LineStyle><color>ff22b1f9</color><width>3</width></LineStyle>'
        "<PolyStyle><color>66c2cb7f</color></PolyStyle></Style>\n"
        f"<Placemark><name>{nome}</name><description><![CDATA[{descricao}]]></description>"
        f"<styleUrl>#anm</styleUrl><ExtendedData>{extended}</ExtendedData>"
        f"<MultiGeometry>{poligonos}</MultiGeometry></Placemark>\n"
        "</Document>\n</kml>\n"
    )


def nome_arquivo(p: ProcessoMinerario, ext: str) -> str:
    return f"SM_processo_{p.processo.replace('.', '').replace('/', '-')}.{ext}"
