# SM · Search Mining

**Consulta pública de processos minerários na ANM**, desenvolvida pela **DANKHE PROJETOS — Consultoria e Sustentabilidade**.

Pesquisa por **número do processo**, **CPF/CNPJ do interessado** ou **nome do titular** e apresenta um resumo com:

| Campo | Fonte ANM |
|---|---|
| Número do processo, nome do titular, fase, substância, área, UF | SIGMINE (ArcGIS REST) |
| Status (ativo/inativo), CPF/CNPJ, município, data de vencimento | Cadastro Mineiro (SCM) |
| Data e descrição do último evento (e histórico) | Cadastro Mineiro (SCM), com o `ULT_EVENTO` do SIGMINE como alternativa |
| Polígono de localização (vértices WGS84) e **download do KML** | SIGMINE |

Também gera um **relatório em PDF** (um processo ou vários selecionados da lista). Não há login.

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                   # http://localhost:5000
```

Modo demonstração (dados **fictícios**, sem acessar a ANM), útil para apresentar o layout:

```bash
SM_DEMO=1 python app.py         # Windows (PowerShell): $env:SM_DEMO=1; python app.py
```

Em produção: `gunicorn -w 2 -b 0.0.0.0:8000 app:app`.

## A função Python

```python
from sm import verificar_status_processo

info = verificar_status_processo("830.123/2010")
print(info["status"], info["fase"], info["ultimo_evento"])
```

Pela linha de comando: `python -m sm 830.123/2010`.

## Como funciona

- `sm/sigmine.py`: consulta a camada *Processos minerários ativos* do SIGMINE
  (`geo.anm.gov.br/arcgis/rest/services/SIGMINE/dados_anm/MapServer/0/query`) com `requests`,
  pedindo a geometria em WGS84 (`outSR=4326`). Tenta outros filtros (`NUMERO/ANO`, `PROCESSO`) se o primeiro falhar.
- `sm/scm.py`: raspagem do **Cadastro Mineiro** com **BeautifulSoup**. Como o SCM é ASP.NET WebForms, faz um GET
  para ler `__VIEWSTATE`/`__EVENTVALIDATION` e depois um POST (postback). Campos e tabelas são encontrados pelo
  **texto dos rótulos e cabeçalhos**, e não por IDs fixos, para aguentar pequenas mudanças de layout.
- `sm/service.py`: junta as duas fontes e guarda o resultado em cache por 15 min. Se uma das fontes falhar,
  devolve o que conseguiu e mostra um aviso.
- `sm/kml.py` / `sm/pdf.py`: exportação em KML (com atributos em `ExtendedData`) e relatório PDF (ReportLab) com a identidade visual DANKHE.
- `app.py` + `templates/` + `static/`: API Flask e interface web (Leaflet para o mapa, com o Leaflet incluído no repositório).

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/processo?numero=830.123/2010` | resumo completo (com polígono) |
| GET | `/api/documento?doc=11222333000181` | processos do CPF/CNPJ |
| GET | `/api/titular?nome=MINERACAO` | processos ativos por nome (SIGMINE) |
| GET | `/api/kml?numero=...` | download do KML |
| GET/POST | `/api/pdf?numero=...` / `{"processos": [...]}` | download do PDF (até 25 processos) |

### Configuração (variáveis de ambiente)

| Variável | Padrão |
|---|---|
| `SM_SIGMINE_URL` | URL de consulta da camada 0 do SIGMINE |
| `SM_SCM_BASE` | `https://sistemas.anm.gov.br/SCM/Extra/site/admin` |
| `SM_SCM_PESQUISA_URL` | `$SM_SCM_BASE/pesquisarProcessos.aspx` (pesquisa por CPF/CNPJ) |
| `SM_TIMEOUT` | `30` segundos |
| `SM_CACHE_TTL` | `900` segundos |
| `SM_DEMO` | `1` ativa os dados fictícios |

## Limitações conhecidas

- O SIGMINE só publica polígonos de **processos ativos**. Para processos inativos, o app mostra os dados do SCM sem mapa/KML.
- A pesquisa por **CPF/CNPJ** depende da página de pesquisa do Cadastro Mineiro, que não tem API oficial.
  Se a ANM mudar essa página, ajuste `SM_SCM_PESQUISA_URL` ou os padrões em `sm/scm.py`.
- Os sites da ANM às vezes ficam lentos ou fora do ar. O app avisa e mostra os dados da fonte que respondeu.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

---
Fonte dos dados: Agência Nacional de Mineração (ANM). As informações são apenas informativas e não substituem certidão oficial.
