from sm.demo import DEMO, html_detalhe, html_pesquisa
from sm.scm import ScmClient, parse_detalhe, parse_lista_processos


def test_parse_detalhe():
    p = parse_detalhe(html_detalhe(DEMO[1]))
    assert p.processo == "831.456/2021"
    assert p.titular == "MINERAÇÃO EXEMPLO LTDA" and p.cpf_cnpj == "11.222.333/0001-81"
    assert p.status == "Ativo" and p.fase == "AUTORIZAÇÃO DE PESQUISA"
    assert p.municipios == ["MARIANA"] and p.uf == "MG"
    assert p.substancias == ["OURO"] and p.area_ha == 1250.0
    assert p.data_vencimento == "05/08/2027"  # maior data entre os títulos
    assert (p.ultimo_evento.codigo, p.ultimo_evento.data) == ("236", "02/06/2026")
    assert len(p.eventos) == 3


def test_parse_lista():
    itens = parse_lista_processos(html_pesquisa(DEMO[:2]))
    assert [i["processo"] for i in itens] == ["830.123/2010", "831.456/2021"]
    assert itens[0]["titular"] == "MINERAÇÃO EXEMPLO LTDA"


class Resp:
    def __init__(self, text):
        self.text, self.status_code = text, 200

    def raise_for_status(self):
        pass


class Sessao:
    def __init__(self, get_html, post_html):
        self.get_html, self.post_html, self.headers, self.posts = get_html, post_html, {}, []

    def get(self, url, timeout=None):
        return Resp(self.get_html)

    def post(self, url, data=None, timeout=None, headers=None):
        self.posts.append((url, data))
        return Resp(self.post_html)


def test_postback_detalhe_monta_formulario_aspnet():
    pagina = html_detalhe(DEMO[0])
    s = Sessao(pagina, pagina)
    p = ScmClient(session=s).detalhe_processo("830123/2010")
    url, dados = s.posts[0]
    assert url.endswith("dadosProcesso.aspx")
    assert dados["__VIEWSTATE"] == "abc" and dados["__EVENTVALIDATION"] == "def"
    assert dados["ctl00$conteudo$txtNumeroProcesso"] == "830.123/2010"
    assert dados["ctl00$conteudo$btnConsultarProcesso"] == "Consultar"
    assert p.municipios == ["OURO PRETO"]


def test_postback_pesquisa_documento_seleciona_opcao():
    s = Sessao(html_pesquisa([]), html_pesquisa(DEMO[:2]))
    itens = ScmClient(session=s).processos_por_documento("11.222.333/0001-81")
    _, dados = s.posts[0]
    assert dados["ctl00$conteudo$txtCPFCNPJ"] == "11.222.333/0001-81"
    assert dados["ctl00$conteudo$rblTipo"] == "CPFCNPJ"
    assert len(itens) == 2
