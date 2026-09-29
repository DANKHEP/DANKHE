import xml.etree.ElementTree as ET

import pytest

import app as sm_app


@pytest.fixture()
def client():
    return sm_app.app.test_client()


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200 and "Search Mining" in r.get_data(as_text=True)


def test_processo(client):
    d = client.get("/api/processo?numero=830.123/2010").get_json()
    for chave in ("processo", "titular", "fase", "substancia", "area_ha", "status", "municipio", "uf",
                  "poligonos", "data_vencimento", "ultimo_evento"):
        assert chave in d
    assert d["municipio"] == "OURO PRETO" and d["status"] == "Ativo" and d["poligonos"]


def test_erros(client):
    assert client.get("/api/processo?numero=abc").status_code == 400
    assert client.get("/api/processo?numero=999.999/2020").status_code == 404
    assert client.get("/api/documento?doc=123").status_code == 400
    assert client.post("/api/pdf", json={"processos": []}).status_code == 400


def test_documento_e_titular(client):
    assert len(client.get("/api/documento?doc=11222333000181").get_json()) == 2
    assert client.get("/api/documento?doc=11144477735").get_json()[0]["processo"] == "870.987/2024"
    assert len(client.get("/api/titular?nome=exemplo").get_json()) == 3


def test_kml(client):
    r = client.get("/api/kml?numero=830.123/2010")
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    root = ET.fromstring(r.data)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    coords = root.find(".//k:coordinates", ns).text.split()
    assert coords[0] == coords[-1]  # anel fechado


def test_pdf(client):
    r = client.get("/api/pdf?numero=830.123/2010")
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
    r = client.post("/api/pdf", json={"processos": ["830.123/2010", "831.456/2021"]})
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
