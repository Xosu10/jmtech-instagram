"""Rotación de temas y estilos, días laborables, festivos y campañas."""
from datetime import date

from jmtech.calendario import cargar_config, completar_config, planificar
from jmtech.contenido import cargar_temas

FIN = date(2029, 12, 31)


def config(**cambios):
    cfg = cargar_config()
    cfg.update(cambios)
    return completar_config(cfg)


def test_solo_lunes_a_viernes():
    plan = planificar(FIN, config())
    assert plan and all(p.fecha.weekday() < 5 for p in plan)


def test_empieza_en_la_fecha_de_inicio():
    plan = planificar(date(2026, 11, 30), config())
    assert plan[0].fecha == date(2026, 11, 2)
    assert len(plan) == 21          # noviembre de 2026 tiene 21 días laborables


def test_nunca_el_mismo_tema_dos_dias_seguidos():
    rot = [p for p in planificar(FIN, config()) if p.tipo == "rotacion"]
    assert all(a.tema_id != b.tema_id for a, b in zip(rot, rot[1:]))


def test_cada_ciclo_trae_los_56_temas_sin_repetir():
    ids = {t["id"] for t in cargar_temas()}
    assert len(ids) == 56
    rot = [p for p in planificar(FIN, config()) if p.tipo == "rotacion"]
    ciclos = {}
    for p in rot:
        ciclos.setdefault(p.ciclo, []).append(p.tema_id)
    completos = [v for v in ciclos.values() if len(v) == 56]
    assert len(completos) >= 12
    assert all(set(v) == ids for v in completos)
    assert all(set(v) == ids for v in completos)


def test_nunca_el_mismo_estilo_dos_dias_seguidos():
    plan = planificar(FIN, config())
    assert all(a.estilo != b.estilo for a, b in zip(plan, plan[1:]))
    assert {p.estilo for p in plan} == {"A", "B", "C"}


def test_orden_reproducible_y_depende_de_la_semilla():
    a = [p.tema_id for p in planificar(date(2027, 3, 31), config())]
    assert a == [p.tema_id for p in planificar(date(2027, 3, 31), config())]
    assert a != [p.tema_id for p in planificar(date(2027, 3, 31), config(semilla=7))]


def test_la_segunda_variante_sale_cuando_el_tema_se_repite():
    plan = planificar(date(2026, 12, 31), config())
    primeros = {}
    for p in plan:
        primeros.setdefault(p.tema_id, []).append(p.variante)
    assert all(v[0] == 0 for v in primeros.values())
    assert all(v[1] == 1 for v in primeros.values() if len(v) > 1)


def test_los_festivos_no_se_publican_y_no_rompen_la_rotacion():
    base = planificar(date(2026, 11, 30), config())
    con = planificar(date(2026, 11, 30), config(dias_sin_publicar=["2026-11-04", "2026-11-18"]))
    assert date(2026, 11, 4) not in {p.fecha for p in con}
    assert len(con) == len(base) - 2
    assert [p.tema_id for p in con] == [p.tema_id for p in base][:len(con)]


def test_la_pausa_no_cambia_el_calendario():
    assert planificar(date(2026, 11, 30), config(pausado=True)) == planificar(date(2026, 11, 30), config())


def test_las_campanas_sustituyen_a_la_rotacion_sin_gastar_turno():
    camp = [{"fecha": "2026-11-27", "id": "black_friday"}]
    base = planificar(date(2026, 11, 30), config())
    con = planificar(date(2026, 11, 30), config(campanas=camp))
    dia = next(p for p in con if p.fecha == date(2026, 11, 27))
    assert dia.tipo == "campana" and dia.campana_id == "black_friday" and dia.tema_id is None
    temas_con = [p.tema_id for p in con if p.tipo == "rotacion"]
    assert temas_con == [p.tema_id for p in base][:len(temas_con)]
    assert all(a.estilo != b.estilo for a, b in zip(con, con[1:]))
