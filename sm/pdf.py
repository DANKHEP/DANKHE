"""Relatório PDF do processo minerário (identidade visual DANKHE PROJETOS)."""

from __future__ import annotations

import io
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.graphics.shapes import Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import ProcessoMinerario

TEAL = colors.HexColor("#5FB8B3")
TEAL_CLARO = colors.HexColor("#E6F5F3")
AMARELO = colors.HexColor("#F9B122")
GRAFITE = colors.HexColor("#1F2D3A")
CINZA = colors.HexColor("#6B7A89")
LOGO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "img", "logo-dankhe.jpg")

_s = {
    "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=18, textColor=GRAFITE, leading=22),
    "sub": ParagraphStyle("s", fontName="Helvetica", fontSize=9.5, textColor=CINZA, leading=13),
    "sec": ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=11.5, textColor=TEAL, spaceBefore=10, spaceAfter=6),
    "rot": ParagraphStyle("r", fontName="Helvetica-Bold", fontSize=8, textColor=CINZA, leading=10),
    "val": ParagraphStyle("v", fontName="Helvetica", fontSize=9.5, textColor=GRAFITE, leading=12, alignment=TA_LEFT),
    "cel": ParagraphStyle("c", fontName="Helvetica", fontSize=8, textColor=GRAFITE, leading=10),
    "aviso": ParagraphStyle("a", fontName="Helvetica-Oblique", fontSize=8, textColor=CINZA, leading=10),
}


def _p(txt: str, estilo: str = "val") -> Paragraph:
    from xml.sax.saxutils import escape

    return Paragraph(escape(str(txt or "—")), _s[estilo])


def _desenho_poligono(p: ProcessoMinerario, largura: float, altura: float) -> Drawing:
    d = Drawing(largura, altura)
    d.add(Rect(0, 0, largura, altura, fillColor=TEAL_CLARO, strokeColor=None))
    pts = [pt for r in p.poligonos for pt in r]
    if not pts:
        d.add(String(largura / 2, altura / 2, "Polígono não disponível", textAnchor="middle", fontName="Helvetica", fillColor=CINZA))
        return d
    lat0 = sum(y for _, y in pts) / len(pts)
    kx = math.cos(math.radians(lat0))  # correção simples de aspecto
    xs, ys = [x * kx for x, _ in pts], [y for _, y in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    margem = 14
    esc = min((largura - 2 * margem) / ((maxx - minx) or 1e-9), (altura - 2 * margem) / ((maxy - miny) or 1e-9))
    ox = (largura - (maxx - minx) * esc) / 2
    oy = (altura - (maxy - miny) * esc) / 2
    for r in p.poligonos:
        coords = []
        for x, y in r:
            coords += [ox + (x * kx - minx) * esc, oy + (y - miny) * esc]
        d.add(Polygon(coords, fillColor=colors.Color(0.37, 0.72, 0.70, 0.35), strokeColor=AMARELO, strokeWidth=2))
    d.add(String(6, 6, f"Lat {min(ys):.5f} a {max(ys):.5f} | Lon {min(x for x, _ in pts):.5f} a {max(x for x, _ in pts):.5f}",
                 fontName="Helvetica", fontSize=6.5, fillColor=CINZA))
    d.add(String(largura - 6, altura - 12, "N", fontName="Helvetica-Bold", fontSize=9, textAnchor="end", fillColor=GRAFITE))
    return d


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(AMARELO)
    canvas.rect(0, 0, A4[0], 4, stroke=0, fill=1)
    canvas.setFillColor(TEAL)
    canvas.rect(0, 4, A4[0], 2, stroke=0, fill=1)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(CINZA)
    canvas.drawString(18 * mm, 10 * mm, "SM (Search Mining) · DANKHE PROJETOS — Consultoria e Sustentabilidade")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Fonte: ANM (SIGMINE / Cadastro Mineiro) · pág. {doc.page}")
    canvas.restoreState()


def gerar_pdf(itens: list[ProcessoMinerario]) -> bytes:
    """Gera PDF com um ou mais processos (um bloco por processo)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=14 * mm, bottomMargin=18 * mm,
                            title="SM - Relatório de Processo Minerário", author="DANKHE PROJETOS")
    W = A4[0] - 36 * mm
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
    story = []

    logo = Image(LOGO, width=38 * mm, height=38 * mm * 347 / 580) if os.path.exists(LOGO) else _p("DANKHE PROJETOS")
    cab = Table([[logo, [Paragraph("SM <font color='#F9B122'>·</font> Search Mining", _s["titulo"]),
                         _p(f"Relatório de processo minerário — consulta em {agora}", "sub")]]],
                colWidths=[44 * mm, W - 44 * mm])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LINEBELOW", (0, 0), (-1, 0), 2, AMARELO),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [cab, Spacer(1, 6)]

    for n, p in enumerate(itens):
        if n:
            story.append(Spacer(1, 14))
        story.append(Paragraph(f"Processo {p.processo}", _s["sec"]))
        area = f"{p.area_ha:,.2f} ha".replace(",", "X").replace(".", ",").replace("X", ".") if p.area_ha is not None else "—"
        pares = [
            ("NÚMERO DO PROCESSO", p.processo), ("STATUS", p.status),
            ("TITULAR", p.titular), ("CPF/CNPJ", p.cpf_cnpj),
            ("FASE", p.fase), ("SUBSTÂNCIA MINERAL", p.substancia),
            ("ÁREA", area), ("USO", p.uso),
            ("MUNICÍPIO", p.municipio), ("ESTADO (UF)", p.uf),
            ("DATA DE VENCIMENTO", p.data_vencimento), ("DATA DO ÚLTIMO EVENTO", p.ultimo_evento.data),
        ]
        linhas = []
        for i in range(0, len(pares), 2):
            (r1, v1), (r2, v2) = pares[i], pares[i + 1]
            linhas.append([[_p(r1, "rot"), _p(v1)], [_p(r2, "rot"), _p(v2)]])
        ev = " - ".join(x for x in (p.ultimo_evento.codigo, p.ultimo_evento.descricao) if x)
        linhas.append([[_p("DESCRIÇÃO DO ÚLTIMO EVENTO", "rot"), _p(ev)], ""])
        t = Table(linhas, colWidths=[W / 2, W / 2])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("SPAN", (0, len(linhas) - 1), (1, len(linhas) - 1)),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#DDE7E6")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CFE4E2")),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(t)

        if p.poligonos:
            story.append(KeepTogether([Paragraph("Polígono de localização (SIGMINE · WGS84)", _s["sec"]),
                                       _desenho_poligono(p, W, 58 * mm)]))
            abertos = [r[:-1] if len(r) > 1 and r[0] == r[-1] else r for r in p.poligonos]
            vert = [(i + 1, y, x) for i, (x, y) in enumerate(pt for r in abertos for pt in r)]
            limite = 40
            dados = [["#", "Latitude", "Longitude"]] + [[str(i), f"{la:.6f}", f"{lo:.6f}"] for i, la, lo in vert[:limite]]
            meio = (len(dados) + 1) // 2
            col1, col2 = dados[:meio], [dados[0]] + dados[meio:]
            while len(col2) < len(col1):
                col2.append(["", "", ""])
            tv = Table([a + [""] + b for a, b in zip(col1, col2)],
                       colWidths=[9 * mm, 30 * mm, 30 * mm, 8 * mm, 9 * mm, 30 * mm, 30 * mm])
            tv.setStyle(TableStyle([
                ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 0), (2, 0), TEAL), ("BACKGROUND", (4, 0), (6, 0), TEAL),
                ("ROWBACKGROUNDS", (0, 1), (2, -1), [colors.white, TEAL_CLARO]),
                ("ROWBACKGROUNDS", (4, 1), (6, -1), [colors.white, TEAL_CLARO]),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story += [Paragraph(f"Vértices ({len(vert)} no total)", _s["sec"]), tv]
            if len(vert) > limite:
                story.append(_p(f"Exibidos os primeiros {limite} vértices. Baixe o KML para a geometria completa.", "aviso"))

        if p.eventos:
            ev_rows = [["Data", "Cód.", "Evento"]] + [[e.data, e.codigo, _p(e.descricao, "cel")] for e in p.eventos[:12]]
            te = Table(ev_rows, colWidths=[22 * mm, 14 * mm, W - 36 * mm])
            te.setStyle(TableStyle([
                ("FONT", (0, 0), (-1, -1), "Helvetica", 8), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                ("TEXTCOLOR", (0, 0), (-1, 0), GRAFITE), ("BACKGROUND", (0, 0), (-1, 0), AMARELO),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TEAL_CLARO]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story += [Paragraph("Eventos recentes (Cadastro Mineiro)", _s["sec"]), te]

        for a in p.avisos:
            story.append(_p(f"Aviso: {a}", "aviso"))

    story += [Spacer(1, 10), _p(
        "Informações obtidas das bases públicas da Agência Nacional de Mineração (ANM). "
        "Este relatório tem caráter informativo e não substitui certidão oficial.", "aviso")]
    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
