from odoo_client import get_odoo_client


def obtener_reporte_ventas(fecha_desde, fecha_hasta):
    """Facturas de cliente confirmadas en un rango de fechas, con totales agregados.

    fecha_desde / fecha_hasta: strings 'YYYY-MM-DD'
    """
    odoo = get_odoo_client()

    domain = [
        ["move_type", "=", "out_invoice"],
        ["state", "=", "posted"],
        ["invoice_date", ">=", fecha_desde],
        ["invoice_date", "<=", fecha_hasta],
    ]

    facturas = odoo.search_read(
        "account.move",
        domain=domain,
        fields=[
            "name", "partner_id", "invoice_date",
            "amount_untaxed", "amount_tax", "amount_total", "payment_state",
        ],
        order="invoice_date asc",
    )

    total_sin_iva = sum(f["amount_untaxed"] for f in facturas)
    total_iva = sum(f["amount_tax"] for f in facturas)
    total_con_iva = sum(f["amount_total"] for f in facturas)

    detalle = [{
        "numero": f["name"],
        "cliente": f["partner_id"][1] if f["partner_id"] else "",
        "fecha": f.get("invoice_date"),
        "subtotal_sin_iva": round(f["amount_untaxed"], 2),
        "iva": round(f["amount_tax"], 2),
        "total": round(f["amount_total"], 2),
        "estado_pago": f["payment_state"],
    } for f in facturas]

    return {
        "desde": fecha_desde,
        "hasta": fecha_hasta,
        "cantidad_facturas": len(facturas),
        "total_sin_iva": round(total_sin_iva, 2),
        "total_iva": round(total_iva, 2),
        "total_con_iva": round(total_con_iva, 2),
        "facturas": detalle,
    }


def obtener_productos_mas_vendidos(fecha_desde, fecha_hasta, limite=20):
    """Ranking de productos por monto vendido en un rango de fechas.

    Se basa en las líneas de las facturas de cliente confirmadas del período.
    """
    odoo = get_odoo_client()

    # 1. IDs de facturas de cliente confirmadas en el rango
    facturas = odoo.search_read(
        "account.move",
        domain=[
            ["move_type", "=", "out_invoice"],
            ["state", "=", "posted"],
            ["invoice_date", ">=", fecha_desde],
            ["invoice_date", "<=", fecha_hasta],
        ],
        fields=["id"],
    )
    factura_ids = [f["id"] for f in facturas]

    if not factura_ids:
        return {"desde": fecha_desde, "hasta": fecha_hasta, "productos": []}

    # 2. Líneas de esas facturas, excluyendo secciones/notas (sin product_id)
    lineas = odoo.search_read(
        "account.move.line",
        domain=[
            ["move_id", "in", factura_ids],
            ["product_id", "!=", False],
            ["display_type", "=", False],
        ],
        fields=["product_id", "quantity", "price_subtotal"],
    )

    # 3. Agregamos por producto en Python (más simple y confiable que read_group aquí)
    agregados = {}
    for linea in lineas:
        prod_id, prod_nombre = linea["product_id"]
        if prod_id not in agregados:
            agregados[prod_id] = {"producto": prod_nombre, "cantidad": 0.0, "total_vendido": 0.0}
        agregados[prod_id]["cantidad"] += linea["quantity"]
        agregados[prod_id]["total_vendido"] += linea["price_subtotal"]

    ranking = sorted(agregados.values(), key=lambda p: p["total_vendido"], reverse=True)[:limite]
    for p in ranking:
        p["cantidad"] = round(p["cantidad"], 2)
        p["total_vendido"] = round(p["total_vendido"], 2)

    return {"desde": fecha_desde, "hasta": fecha_hasta, "productos": ranking}
