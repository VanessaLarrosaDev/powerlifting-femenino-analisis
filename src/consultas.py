"""
Ejecuta las consultas de sql/consultas_analiticas.sql y muestra los resultados.

Sirve para dos cosas: comprobar que el SQL funciona y volcar los resultados a
CSV para poder citarlos en el informe.

Ejecucion:  python src/consultas.py            (todas)
            python src/consultas.py C3 C6      (solo las indicadas)
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg
from base_datos import BD

FICHERO_SQL = cfg.SQL / "consultas_analiticas.sql"
SALIDA = cfg.REPORTS / "resultados_sql"

# La consola de Windows usa cp1252 por defecto y falla al imprimir nombres de
# atletas con caracteres de alfabetos eslavos o nordicos. Los CSV se guardan
# siempre en UTF-8; esto solo afecta a lo que se ve por pantalla.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def trocear() -> list[tuple[str, str, str]]:
    """Parte el fichero .sql en consultas independientes.

    Devuelve una lista de (codigo, titulo, sentencia).
    """
    texto = FICHERO_SQL.read_text(encoding="utf-8")
    # Cada consulta empieza con una cabecera '-- Cn · Titulo'
    patron = re.compile(r"^-- (C\d+) · (.+?)$", re.MULTILINE)
    marcas = list(patron.finditer(texto))
    consultas = []
    for i, m in enumerate(marcas):
        inicio = m.end()
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        cuerpo = texto[inicio:fin]
        # Se descartan las lineas de comentario y se conserva la sentencia
        sentencia = "\n".join(
            l for l in cuerpo.splitlines()
            if not l.strip().startswith("--")).strip()
        if sentencia:
            consultas.append((m.group(1), m.group(2).strip(), sentencia))
    return consultas


def main() -> None:
    if not BD.exists():
        print(f"No existe la base de datos: {BD}")
        print("Ejecuta primero:  python src/base_datos.py")
        sys.exit(1)

    filtro = {a.upper() for a in sys.argv[1:]}
    SALIDA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BD)
    consultas = trocear()
    print(f"Consultas encontradas: {len(consultas)}\n")

    fallos = 0
    for codigo, titulo, sentencia in consultas:
        if filtro and codigo not in filtro:
            continue
        print("=" * 78)
        print(f"{codigo} · {titulo}")
        print("=" * 78)
        try:
            df = pd.read_sql_query(sentencia, con)
            print(df.to_string(index=False, max_rows=25))
            print(f"\n  ({len(df)} filas)")
            destino = SALIDA / f"{codigo.lower()}.csv"
            df.to_csv(destino, index=False, encoding="utf-8")
        except Exception as e:
            fallos += 1
            print(f"  ERROR: {type(e).__name__}: {e}")
        print()

    con.close()
    print("=" * 78)
    print(f"Completado. Resultados en {SALIDA.relative_to(cfg.RAIZ)}/")
    if fallos:
        print(f"ATENCION: {fallos} consultas fallaron.")
        sys.exit(1)


if __name__ == "__main__":
    main()
