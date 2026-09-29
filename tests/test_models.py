import pytest

from sm.models import (DocumentoInvalido, ProcessoInvalido, formatar_documento,
                       normalizar_processo, parse_processo, validar_documento)


@pytest.mark.parametrize("entrada", ["830.123/2010", "830123/2010", "8301232010", " 830.123 / 2010 "])
def test_parse_processo(entrada):
    assert parse_processo(entrada) == (830123, 2010)
    assert normalizar_processo(entrada) == "830.123/2010"


def test_processo_com_zeros_a_esquerda():
    assert normalizar_processo("1.234/1998") == "001.234/1998"


@pytest.mark.parametrize("entrada", ["", "12", "830.123/20", "abc/2010", "830.123/1800"])
def test_processo_invalido(entrada):
    with pytest.raises(ProcessoInvalido):
        parse_processo(entrada)


def test_documentos():
    assert validar_documento("11.222.333/0001-81") == "11222333000181"
    assert validar_documento("111.444.777-35") == "11144477735"
    assert formatar_documento("11222333000181") == "11.222.333/0001-81"
    assert formatar_documento("11144477735") == "111.444.777-35"
    for ruim in ("11.222.333/0001-82", "111.111.111-11", "123"):
        with pytest.raises(DocumentoInvalido):
            validar_documento(ruim)
