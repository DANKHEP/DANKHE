"""Raspagem (BeautifulSoup) do Cadastro Mineiro — SCM/ANM.

O SCM é uma aplicação ASP.NET WebForms: cada consulta exige um GET para
obter __VIEWSTATE/__EVENTVALIDATION e um POST (postback) com o formulário.
Para resistir a mudanças de layout, os campos do formulário e as tabelas de
resultado são localizados pelo *texto* (rótulos e cabeçalhos), e não por
IDs fixos.

Fornece: titular + CPF/CNPJ, situação (ativo/inativo), fase, municípios,
substâncias, eventos (data/descrição) e títulos (data de vencimento).
"""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag

from .models import Evento, ProcessoMinerario, formatar_processo, parse_processo

SCM_BASE = os.environ.get("SM_SCM_BASE", "https://sistemas.anm.gov.br/SCM/Extra/site/admin")
SCM_DETALHE_URL = f"{SCM_BASE}/dadosProcesso.aspx"
SCM_PESQUISA_URL = os.environ.get("SM_SCM_PESQUISA_URL", f"{SCM_BASE}/pesquisarProcessos.aspx")
TIMEOUT = float(os.environ.get("SM_TIMEOUT", "30"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 SM-SearchMining/1.0"
)

_PROC_TXT_RE = re.compile(r"\b(\d{3}\.\d{3}/\d{4})\b")
_DATA_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")


class ScmError(RuntimeError):
    pass


def norm(txt: str | None) -> str:
    """minúsculas, sem acentos e com espaços simples."""
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip().lower()


def _texto(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


# ---------------------------------------------------------------------- #
# ASP.NET WebForms
# ---------------------------------------------------------------------- #
def _dados_formulario(soup: BeautifulSoup) -> dict[str, str]:
    dados: dict[str, str] = {}
    for inp in soup.find_all("input"):
        nome = inp.get("name")
        tipo = (inp.get("type") or "text").lower()
        if not nome or tipo in ("submit", "button", "image", "reset", "file"):
            continue
        if tipo in ("checkbox", "radio") and not inp.has_attr("checked"):
            continue
        dados[nome] = inp.get("value", "")
    for sel in soup.find_all("select"):
        if not sel.get("name"):
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        dados[sel["name"]] = opt.get("value", _texto(opt)) if opt else ""
    return dados


def _rotulo_do_campo(soup: BeautifulSoup, campo: Tag, contexto: bool = True) -> str:
    partes = [campo.get("name", ""), campo.get("id", ""), campo.get("title", ""), campo.get("placeholder", "")]
    if campo.get("id"):
        lbl = soup.find("label", attrs={"for": campo["id"]})
        partes.append(_texto(lbl))
    if contexto:  # texto imediatamente anterior ao campo (rótulo "solto")
        prev = campo.find_previous(string=re.compile(r"\S"))
        if prev:
            partes.append(str(prev))
    return norm(" ".join(partes))


def _achar_campo_texto(soup: BeautifulSoup, padrao: re.Pattern) -> Tag | None:
    campos = [i for i in soup.find_all("input")
              if (i.get("type") or "text").lower() in ("text", "search", "tel", "")]
    # 1ª passada: nome/id/label explícito; 2ª: texto anterior ao campo
    for contexto in (False, True):
        for inp in campos:
            if padrao.search(_rotulo_do_campo(soup, inp, contexto)):
                return inp
    return None


def _achar_botao(soup: BeautifulSoup, padrao: re.Pattern) -> Tag | None:
    for b in soup.find_all(["input", "button"]):
        tipo = (b.get("type") or ("submit" if b.name == "button" else "")).lower()
        if tipo not in ("submit", "image", "button"):
            continue
        rotulo = norm(" ".join([b.get("name", ""), b.get("id", ""), b.get("value", ""), _texto(b)]))
        if padrao.search(rotulo) and b.get("name"):
            return b
    return None


def _selecionar_opcao(soup: BeautifulSoup, dados: dict[str, str], padrao: re.Pattern) -> None:
    """Marca rádio/opção cujo rótulo casa com o padrão (ex.: tipo de pesquisa 'CPF/CNPJ')."""
    for r in soup.find_all("input", attrs={"type": "radio"}):
        if r.get("name") and padrao.search(_rotulo_do_campo(soup, r) + " " + norm(r.get("value", ""))):
            dados[r["name"]] = r.get("value", "on")
            return
    for sel in soup.find_all("select"):
        for opt in sel.find_all("option"):
            if sel.get("name") and padrao.search(norm(_texto(opt))):
                dados[sel["name"]] = opt.get("value", _texto(opt))
                return


# ---------------------------------------------------------------------- #
# Parsing de tabelas / rótulos
# ---------------------------------------------------------------------- #
def tabelas(soup: BeautifulSoup) -> list[tuple[list[str], list[list[str]]]]:
    """Retorna [(cabeçalhos_normalizados, linhas)] para cada tabela 'de dados'."""
    out = []
    for tb in soup.find_all("table"):
        linhas = [tr for tr in tb.find_all("tr") if tr.find_parent("table") is tb]
        if len(linhas) < 2:
            continue
        cab = [norm(_texto(c)) for c in linhas[0].find_all(["th", "td"], recursive=False)]
        if not any(cab):
            continue
        dados = []
        for tr in linhas[1:]:
            cels = [_texto(c) for c in tr.find_all(["td", "th"], recursive=False)]
            if cels and any(cels) and len(cels) >= min(2, len(cab)):
                dados.append(cels)
        out.append((cab, dados))
    return out


def _achar_tabela(tabs, *obrigatorios: str, qualquer: tuple[str, ...] = ()):
    for cab, linhas in tabs:
        junto = " | ".join(cab)
        if all(o in junto for o in obrigatorios) and (not qualquer or any(q in junto for q in qualquer)):
            return cab, linhas
    return None


def _col(cab: list[str], *nomes: str) -> int | None:
    for nome in nomes:
        for i, c in enumerate(cab):
            if nome in c:
                return i
    return None


def _val(linha: list[str], idx: int | None) -> str:
    return linha[idx].strip() if idx is not None and idx < len(linha) else ""


def campos_rotulados(soup: BeautifulSoup) -> dict[str, str]:
    """Extrai pares 'Rótulo: valor' (spans lbl*, células rótulo/valor, <dt>/<dd>)."""
    campos: dict[str, str] = {}
    # 1) <span id="..._lblFase">valor</span>  -> chave 'fase'
    for el in soup.find_all(["span", "label"], id=True):
        m = re.search(r"lbl_?([A-Za-z0-9]+)$", el["id"])
        if m and _texto(el):
            campos.setdefault(norm(re.sub(r"(?<!^)(?=[A-Z])", " ", m.group(1))), _texto(el))
    # 2) <td>Fase Atual:</td><td>Lavra</td>
    for tr in soup.find_all("tr"):
        cels = tr.find_all(["td", "th"], recursive=False)
        for a, b in zip(cels, cels[1:]):
            ta = _texto(a)
            if ta.endswith(":") and len(ta) < 60:
                campos.setdefault(norm(ta.rstrip(":")), _texto(b))
    # 3) <dt>/<dd>
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            campos.setdefault(norm(_texto(dt).rstrip(":")), _texto(dd))
    return campos


def _campo(campos: dict[str, str], *chaves: str) -> str:
    for ch in chaves:
        if ch in campos and campos[ch]:
            return campos[ch]
    for ch in chaves:
        for k, v in campos.items():
            if ch in k and v:
                return v
    return ""


def _data_ord(d: str) -> datetime:
    try:
        return datetime.strptime(d[:10], "%d/%m/%Y")
    except (ValueError, TypeError):
        return datetime.min


def parse_detalhe(html: str, processo: str = "") -> ProcessoMinerario | None:
    """Converte a página de dados do processo (SCM) em ProcessoMinerario."""
    soup = BeautifulSoup(html, "html.parser")
    campos = campos_rotulados(soup)
    tabs = tabelas(soup)

    numero = _campo(campos, "numero processo", "processo", "numero")
    m = _PROC_TXT_RE.search(numero) or (_PROC_TXT_RE.search(processo) if processo else None)
    if not m and not tabs:
        return None
    p = ProcessoMinerario(processo=m.group(1) if m else processo, fontes=["Cadastro Mineiro/ANM"])

    p.fase = _campo(campos, "fase atual", "fase")
    ativo = norm(_campo(campos, "ativo", "situacao", "status"))
    if ativo:
        p.status = "Ativo" if ativo in ("sim", "ativo", "s") else ("Inativo" if ativo in ("nao", "inativo", "n") else ativo.capitalize())
    area = _campo(campos, "area ha", "area (ha)", "area")
    if area:
        try:
            p.area_ha = float(area.replace(".", "").replace(",", ".").split()[0])
        except ValueError:
            pass
    p.uso = _campo(campos, "tipo requerimento", "uso")

    # Pessoas (titular / requerente)
    t = _achar_tabela(tabs, "nome", qualquer=("cpf", "cnpj"))
    if t:
        cab, linhas = t
        i_nome, i_doc = _col(cab, "nome"), _col(cab, "cpf", "cnpj")
        i_tipo = _col(cab, "tipo", "relacao", "vinculo")
        escolhida = None
        for ln in linhas:
            tipo = norm(_val(ln, i_tipo))
            if any(k in tipo for k in ("titular", "requerente")) and not _val(ln, _col(cab, "data final", "fim")):
                escolhida = ln
                break
        escolhida = escolhida or (linhas[0] if linhas else None)
        if escolhida:
            p.titular, p.cpf_cnpj = _val(escolhida, i_nome), _val(escolhida, i_doc)

    # Substâncias
    t = _achar_tabela(tabs, "substancia") or _achar_tabela(tabs, "nome", qualquer=("tipo de uso", "uso"))
    if t:
        cab, linhas = t
        i = _col(cab, "substancia", "nome")
        p.substancias = list(dict.fromkeys(v for v in (_val(l, i) for l in linhas) if v))
        if not p.uso:
            p.uso = _val(linhas[0], _col(cab, "uso")) if linhas else ""

    # Municípios
    t = _achar_tabela(tabs, "municipio")
    if t:
        cab, linhas = t
        i_m, i_uf = _col(cab, "municipio"), _col(cab, "uf", "estado")
        for l in linhas:
            nome_m = _val(l, i_m)
            uf = _val(l, i_uf)
            if " - " in nome_m and not uf:  # "OURO PRETO - MG"
                nome_m, uf = nome_m.rsplit(" - ", 1)
            if nome_m:
                p.municipios.append(nome_m.strip())
                if uf and not p.uf:
                    p.uf = uf.strip()
        p.municipios = list(dict.fromkeys(p.municipios))

    # Eventos
    t = _achar_tabela(tabs, "evento", "data")
    if t:
        cab, linhas = t
        i_d = _col(cab, "data")
        i_desc = _col(cab, "descricao", "evento")
        i_cod = _col(cab, "codigo", "cod")
        for l in linhas:
            desc = _val(l, i_desc)
            cod = _val(l, i_cod) if i_cod != i_desc else ""
            mc = re.match(r"^(\d+)\s*-\s*(.*)$", desc)
            if mc and not cod:
                cod, desc = mc.group(1), mc.group(2)
            md = _DATA_RE.search(_val(l, i_d))
            p.eventos.append(Evento(codigo=cod, descricao=desc, data=md.group(1) if md else ""))
        p.eventos.sort(key=lambda e: _data_ord(e.data), reverse=True)
        if p.eventos:
            p.ultimo_evento = p.eventos[0]

    # Títulos / documentos -> data de vencimento
    t = _achar_tabela(tabs, "vencimento")
    if t:
        cab, linhas = t
        i_v = _col(cab, "vencimento")
        datas = [md.group(1) for l in linhas if (md := _DATA_RE.search(_val(l, i_v)))]
        if datas:
            p.data_vencimento = max(datas, key=_data_ord)
    if not p.data_vencimento:
        v = _campo(campos, "data de vencimento", "vencimento", "data vencimento")
        md = _DATA_RE.search(v)
        p.data_vencimento = md.group(1) if md else ""

    return p


def parse_lista_processos(html: str) -> list[dict[str, str]]:
    """Extrai processos da tabela de resultados de pesquisa do SCM."""
    soup = BeautifulSoup(html, "html.parser")
    achados: dict[str, dict[str, str]] = {}
    for cab, linhas in tabelas(soup):
        if not any("processo" in c for c in cab):
            continue
        i_p = _col(cab, "processo")
        i_n = _col(cab, "titular", "nome", "requerente")
        i_f = _col(cab, "fase")
        for l in linhas:
            m = _PROC_TXT_RE.search(_val(l, i_p)) or _PROC_TXT_RE.search(" ".join(l))
            if m:
                achados.setdefault(m.group(1), {"processo": m.group(1), "titular": _val(l, i_n), "fase": _val(l, i_f)})
    if not achados:  # layout sem cabeçalho: coleta qualquer número de processo em links
        for a in soup.find_all("a"):
            m = _PROC_TXT_RE.search(_texto(a))
            if m:
                achados.setdefault(m.group(1), {"processo": m.group(1), "titular": "", "fase": ""})
    return list(achados.values())


# ---------------------------------------------------------------------- #
# Cliente
# ---------------------------------------------------------------------- #
class ScmClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)

    def _postback(self, url: str, campo_re: re.Pattern, valor: str, botao_re: re.Pattern,
                  opcao_re: re.Pattern | None = None) -> str:
        try:
            r = self.session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise ScmError(f"Cadastro Mineiro indisponível: {exc}") from exc
        soup = BeautifulSoup(r.text, "html.parser")
        campo = _achar_campo_texto(soup, campo_re)
        if campo is None:
            raise ScmError("Formulário do Cadastro Mineiro não reconhecido (campo de pesquisa não encontrado).")
        dados = _dados_formulario(soup)
        if opcao_re:
            _selecionar_opcao(soup, dados, opcao_re)
        dados[campo["name"]] = valor
        botao = _achar_botao(soup, botao_re)
        if botao is not None:
            if (botao.get("type") or "").lower() == "image":
                dados[f"{botao['name']}.x"], dados[f"{botao['name']}.y"] = "10", "10"
            else:
                dados[botao["name"]] = botao.get("value", "")
        form = soup.find("form")
        destino = requests.compat.urljoin(url, form.get("action")) if form and form.get("action") else url
        try:
            r2 = self.session.post(destino, data=dados, timeout=TIMEOUT, headers={"Referer": url})
            r2.raise_for_status()
        except requests.RequestException as exc:
            raise ScmError(f"Falha na consulta ao Cadastro Mineiro: {exc}") from exc
        return r2.text

    def detalhe_processo(self, processo: str) -> ProcessoMinerario | None:
        numero, ano = parse_processo(processo)
        fmt = formatar_processo(numero, ano)
        html = self._postback(
            SCM_DETALHE_URL,
            re.compile(r"processo"),
            fmt,
            re.compile(r"consultar|pesquisar|buscar|ok"),
        )
        p = parse_detalhe(html, fmt)
        if p and not (p.fase or p.titular or p.eventos):
            return None  # página voltou sem dados (processo inexistente)
        return p

    def processos_por_documento(self, documento: str) -> list[dict[str, str]]:
        html = self._postback(
            SCM_PESQUISA_URL,
            re.compile(r"cpf|cnpj|documento"),
            documento,
            re.compile(r"consultar|pesquisar|buscar|ok"),
            opcao_re=re.compile(r"cpf|cnpj"),
        )
        return parse_lista_processos(html)
