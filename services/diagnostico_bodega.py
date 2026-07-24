"""
Diagnóstico: por qué un producto muestra existencia/saldo negativo o en 0
cuando debería tener stock, tras aplicar el filtro de Bodega Central.

Muestra TODAS las capas de valorización de un producto (sin filtro de fecha),
y para cada una indica:
  - si tiene stock_move_id o no
  - la ubicación origen y destino del movimiento
  - si PASA o NO PASA el filtro de la bodega configurada (BODEGA_CENTRAL_NOMBRE / CODIGO)
  - el motivo exacto por el que pasa o no pasa

Uso:
    python diagnostico_bodega.py 5400974019926 [otro_codigo ...]

Ejecutar en el mismo entorno donde corre kardex_service.py.
"""
import os
import sys

# Hace que el script funcione sin importar si lo corres desde la raíz del
# proyecto o desde dentro de la carpeta services/.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
for _p in (_THIS_DIR, _PARENT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from odoo_client import get_odoo_client
try:
    from services.kardex_service import (
        BODEGA_CENTRAL_NOMBRE,
        BODEGA_CENTRAL_CODIGO,
        _obtener_ubicaciones_bodega,
    )
except ImportError:
    from kardex_service import (
        BODEGA_CENTRAL_NOMBRE,
        BODEGA_CENTRAL_CODIGO,
        _obtener_ubicaciones_bodega,
    )


def diagnosticar(codigo):
    odoo = get_odoo_client()

    producto = odoo.search_read(
        "product.product",
        domain=[["default_code", "=", codigo]],
        fields=["id", "display_name"],
        limit=1,
    )
    if not producto:
        print(f"\n[{codigo}] No se encontró ningún producto con ese código.")
        return
    pid = producto[0]["id"]
    nombre = producto[0]["display_name"]

    ubicaciones_bodega = _obtener_ubicaciones_bodega(
        odoo, BODEGA_CENTRAL_NOMBRE, BODEGA_CENTRAL_CODIGO
    )
    print(f"\nBodega objetivo: {BODEGA_CENTRAL_CODIGO}/{BODEGA_CENTRAL_NOMBRE}")
    print(f"Ubicaciones que cuentan como 'de la bodega': {sorted(ubicaciones_bodega)}")

    print("\n" + "=" * 110)
    print(f"PRODUCTO: [{codigo}] {nombre}  (id={pid})")
    print("=" * 110)

    capas = odoo.search_read(
        "stock.valuation.layer",
        domain=[["product_id", "=", pid]],
        fields=["id", "create_date", "quantity", "value", "stock_move_id"],
        order="create_date asc, id asc",
    )
    if not capas:
        print("No tiene capas de valorización registradas.")
        return

    move_ids = list({c["stock_move_id"][0] for c in capas if c.get("stock_move_id")})
    info_moves = {}
    if move_ids:
        moves = odoo.search_read(
            "stock.move",
            domain=[["id", "in", move_ids]],
            fields=["location_id", "location_dest_id", "origin", "picking_id"],
        )
        for m in moves:
            info_moves[m["id"]] = m

    encabezado = (
        f"{'FECHA':<20} {'ID':>8} {'CANT':>8} {'VALUE':>10}  {'MOVE_ID':>8}  "
        f"{'UBIC. ORIGEN':<28} {'UBIC. DESTINO':<28} FILTRO"
    )
    print(encabezado)
    print("-" * len(encabezado))

    saldo = 0.0
    for c in capas:
        saldo += c["value"]
        move_id = c["stock_move_id"][0] if c.get("stock_move_id") else None

        if move_id is None:
            loc_o_nombre = "-"
            loc_d_nombre = "-"
            resultado = "NO PASA (sin stock_move_id -> se excluye por seguridad)"
        else:
            m = info_moves.get(move_id, {})
            loc_o = m.get("location_id")
            loc_d = m.get("location_dest_id")
            loc_o_nombre = loc_o[1] if loc_o else "-"
            loc_d_nombre = loc_d[1] if loc_d else "-"
            loc_o_id = loc_o[0] if loc_o else None
            loc_d_id = loc_d[0] if loc_d else None
            en_bodega = (loc_o_id in ubicaciones_bodega) or (loc_d_id in ubicaciones_bodega)
            resultado = "PASA" if en_bodega else "NO PASA (ninguna ubicación pertenece a la bodega)"

        print(
            f"{(c['create_date'] or '')[:19]:<20} {c['id']:>8} {c['quantity']:>8.2f} "
            f"{c['value']:>10.2f}  {str(move_id):>8}  {loc_o_nombre[:28]:<28} {loc_d_nombre[:28]:<28} {resultado}"
        )

    print("-" * len(encabezado))
    print(f"Saldo total (SIN filtrar por bodega): {saldo:.2f}")


if __name__ == "__main__":
    codigos = sys.argv[1:]
    if not codigos:
        print("Uso: python diagnostico_bodega.py CODIGO1 [CODIGO2 ...]")
        sys.exit(1)
    for codigo in codigos:
        diagnosticar(codigo)
