"""Elección de assets: sin repetir dos días seguidos, cambia cuando el tema se repite, respeta el estilo."""
from datetime import date

import pytest

from jmtech.assets import DIBUJO, Asset, Selector, cargar_catalogo
from jmtech.calendario import cargar_config, completar_config, planificar
from jmtech.contenido import cargar_temas

CATALOGO = cargar_catalogo()
NOMBRES = {a.archivo for a in CATALOGO}
FIN = date(2029, 12, 31)


def plan():
    cfg = completar_config(cargar_config())
    return planificar(FIN, cfg, catalogo=CATALOGO)


def test_nunca_el__mismo_asset_dos_dias_seguidos():
    p = [x for x in plan() if x.tipo == "rotacion"]
    repetidos = [(a.fecha, a.asset) for a, b in zip(p, p[1:]) if a.asset == b.asset and a.asset != DIBUJO]
    assert repetidos == []


def test_cuando_un_tema_se_repite_cambia_el_asset_o_el_diseno():
    ultimo = {}
    for x in plan():
        previo = ultimo.get(x.tema_id)
        if previo and len(Selector(CATALOGO, 2026).candidatos(x.tema_id, x.estilo)) >= 2:
            assert (x.asset, x.estilo) != previo, (x.fecha, x.tema_id)
        ultimo[x.tema_id] = (x.asset, x.estilo)


def test_el_asset_elegido_existe_pertenece_al_tema_y_admite_el_estilo():
    por_nombre = {a.archivo: a for a in CATALOGO}
    for x in plan():
        if x.asset == DIBUJO:
            continue
        a = por_nombre[x.asset]
        assert x.tema_id in a.temas and x.estilo in a.estilos, x


def test_la_eleccion_es_reproducible():
    assert [x.asset for x in plan()] == [x.asset for x in plan()]


def test_si_faltan_assets_la_ilustracion_dibujada_hace_de_segunda_opcion():
    s = Selector([], 1)
    assert s.candidatos("asesoramiento", "A") == [DIBUJO]
    una = [Asset("a.png", "aislado", "pc", ("t",), ("A", "B", "C"), None)]
    assert set(Selector(una, 1).candidatos("t", "A")) == {"a.png", DIBUJO}


def test_con_dos_assets_alterna_sin_repetir():
    dos = [Asset(f"{n}.png", "aislado", "pc", ("t",), ("A",), None) for n in "ab"]
    s = Selector(dos, 1)
    seguidos = [s.elegir("t", "A") for _ in range(8)]
    assert all(a != b for a, b in zip(seguidos, seguidos[1:]))


@pytest.mark.parametrize("tema", [t["id"] for t in cargar_temas()])
def test_los_temas_del_catalogo_existen(tema):
    ids = {t["id"] for t in cargar_temas()}
    assert all(tt in ids for a in CATALOGO for tt in a.temas)


@pytest.mark.xfail(reason="Pendiente del lote de la otra IA: cada publicación debe tener al menos 2 assets", strict=False)
def test_cada_publicacion_tiene_al_menos_dos_assets_aprobados():
    escasos = {t["id"]: sum(1 for a in CATALOGO if t["id"] in a.temas) for t in cargar_temas()}
    assert {k: v for k, v in escasos.items() if v < 2} == {}
