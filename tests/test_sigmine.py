import json

import pytest

from sm.sigmine import SigmineClient, SigmineError, parse_ult_evento


class FakeResp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, respostas):
        self.respostas, self.chamadas, self.headers = list(respostas), [], {}

    def post(self, url, data=None, timeout=None):
        self.chamadas.append(data)
        return FakeResp(self.respostas.pop(0))


FEATURE = {
    "attributes": {"PROCESSO": "830123/2010", "NUMERO": 830123, "ANO": 2010, "AREA_HA": 487.32,
                   "FASE": "CONCESSÃO DE LAVRA", "NOME": "MINERAÇÃO X", "SUBS": "MINÉRIO DE FERRO",
                   "USO": "Industrial", "UF": "MG",
                   "ULT_EVENTO": "414 - CONC LAV/RELATÓRIO ANUAL DE LAVRA APRESENTADO EM 15/03/2026"},
    "geometry": {"rings": [[[-43.5, -20.3], [-43.4, -20.3], [-43.4, -20.4], [-43.5, -20.3]]]},
}


def test_parse_ult_evento():
    e = parse_ult_evento("236 - AUT PESQ/PRORROGAÇÃO PRAZO ALVARÁ SOLICITADA EM 02/06/2026")
    assert (e.codigo, e.descricao, e.data) == ("236", "AUT PESQ/PRORROGAÇÃO PRAZO ALVARÁ SOLICITADA", "02/06/2026")
    assert parse_ult_evento(None).descricao == ""
    assert parse_ult_evento("texto livre").descricao == "texto livre"


def test_buscar_processo():
    s = FakeSession([{"features": [FEATURE]}])
    [p] = SigmineClient(session=s).buscar_processo(830123, 2010)
    assert p.processo == "830.123/2010" and p.titular == "MINERAÇÃO X" and p.uf == "MG"
    assert p.area_ha == 487.32 and p.status == "Ativo"
    assert p.ultimo_evento.data == "15/03/2026"
    assert p.poligonos[0][0] == [-43.5, -20.3]
    assert s.chamadas[0]["outSR"] == 4326 and "NUMERO = 830123 AND ANO = 2010" in s.chamadas[0]["where"]


def test_buscar_processo_tenta_outro_filtro_apos_erro():
    s = FakeSession([{"error": {"message": "Invalid field"}}, {"features": [FEATURE]}])
    assert len(SigmineClient(session=s).buscar_processo(830123, 2010)) == 1
    assert s.chamadas[1]["where"] == "PROCESSO = '830.123/2010'"


def test_buscar_processo_erro_total():
    s = FakeSession([{"error": {"message": "x"}}] * 3)
    with pytest.raises(SigmineError):
        SigmineClient(session=s).buscar_processo(830123, 2010)


def test_buscar_por_titular_escapa_aspas():
    s = FakeSession([{"features": []}])
    SigmineClient(session=s).buscar_por_titular("d'avila")
    assert "D''AVILA" in s.chamadas[0]["where"]
