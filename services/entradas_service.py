from odoo_client import get_odoo_client


def obtener_todas_entradas_inventario(desde, hasta):
    """
    Obtiene las entradas de productos registradas en Odoo (movimientos de almacén
    de entrada / recepciones de compras 'incoming') y facturas de compra.
    """
    odoo = get_odoo_client()

    hasta_fin_dia = f"{hasta} 23:59:59" if len(hasta) == 10 else hasta

    # 1. Buscar todos los movimientos de entrada de productos (stock.move)
    domain_stock = [
        ["state", "=", "done"],
        ["date", ">=", desde],
        ["date", "<=", hasta_fin_dia],
        "|",
        ["picking_id.picking_type_id.code", "=", "incoming"],
        "&", ["location_dest_id.usage", "=", "internal"], ["location_id.usage", "=", "supplier"],
    ]

    campos_stock = [
        "id", "date", "reference", "picking_id", "product_id",
        "product_qty", "price_unit", "partner_id", "origin",
    ]

    moves = odoo.search_read(
        "stock.move",
        domain=domain_stock,
        fields=campos_stock,
        order="date desc",
    )

    # Si hay movimientos, obtener información adicional del picking para proveedor u orden de origen
    picking_ids = list({m["picking_id"][0] for m in moves if m.get("picking_id")})
    picking_info = {}
    if picking_ids:
        pickings = odoo.search_read(
            "stock.picking",
            domain=[["id", "in", picking_ids]],
            fields=["partner_id", "origin", "name"],
        )
        picking_info = {p["id"]: p for p in pickings}

    entradas = []
    for m in moves:
        p_id = m["picking_id"][0] if m.get("picking_id") else None
        p_data = picking_info.get(p_id, {})

        proveedor = m.get("partner_id") or p_data.get("partner_id")
        proveedor_nombre = (
            proveedor[1]
            if isinstance(proveedor, (list, tuple)) and len(proveedor) == 2
            else "N/A"
        )

        factura = m.get("origin") or p_data.get("origin") or m.get("reference") or "—"

        producto_info = m.get("product_id")
        nombre_producto_completo = (
            producto_info[1]
            if isinstance(producto_info, (list, tuple)) and len(producto_info) == 2
            else "N/A"
        )

        codigo = ""
        producto = nombre_producto_completo
        if "]" in nombre_producto_completo and nombre_producto_completo.startswith("["):
            partes = nombre_producto_completo.split("]", 1)
            codigo = partes[0].replace("[", "").strip()
            producto = partes[1].strip()

        cant = float(m.get("product_qty", 0.0))
        costo = float(m.get("price_unit", 0.0))
        total = round(cant * costo, 2)

        fecha_str = m.get("date", "")[:10] if m.get("date") else ""

        entradas.append({
            "fecha": fecha_str,
            "proveedor": proveedor_nombre,
            "factura": factura,
            "codigo": codigo,
            "producto": producto,
            "cantidad": cant,
            "costo_unitario": costo,
            "valor_total": total,
        })

    # Si no hay recepciones de almacén, como respaldo buscar en facturas contables de proveedor
    if not entradas:
        facturas = odoo.search_read(
            "account.move",
            domain=[
                ["move_type", "in", ["in_invoice", "in_refund"]],
                ["state", "=", "posted"],
                "|",
                "&", ["date", ">=", desde], ["date", "<=", hasta],
                "&", ["invoice_date", ">=", desde], ["invoice_date", "<=", hasta],
            ],
            fields=["id"],
        )
        factura_ids = [f["id"] for f in facturas]
        if factura_ids:
            lineas_factura = odoo.search_read(
                "account.move.line",
                domain=[
                    ["move_id", "in", factura_ids],
                    ["product_id", "!=", False],
                    ["display_type", "=", False],
                ],
                fields=['move_id', 'date', 'partner_id', 'product_id', 'name', 'quantity', 'price_unit', 'price_subtotal'],
                order="date DESC",
            )
            for linea in lineas_factura:
                producto_info = linea.get('product_id')
                nombre_producto_completo = producto_info[1] if isinstance(producto_info, (list, tuple)) and len(producto_info) == 2 else "N/A"
                codigo = ""
                producto = nombre_producto_completo
                if "]" in nombre_producto_completo and nombre_producto_completo.startswith("["):
                    partes = nombre_producto_completo.split("]", 1)
                    codigo = partes[0].replace("[", "").strip()
                    producto = partes[1].strip()

                proveedor = linea.get('partner_id')
                proveedor_nombre = proveedor[1] if isinstance(proveedor, (list, tuple)) and len(proveedor) == 2 else "N/A"
                factura = linea.get('move_id')
                factura_nombre = factura[1] if isinstance(factura, (list, tuple)) and len(factura) == 2 else "N/A"

                entradas.append({
                    "fecha": linea.get('date'),
                    "proveedor": proveedor_nombre,
                    "factura": factura_nombre,
                    "codigo": codigo,
                    "producto": producto,
                    "cantidad": float(linea.get('quantity', 0.0)),
                    "costo_unitario": float(linea.get('price_unit', 0.0)),
                    "valor_total": float(linea.get('price_subtotal', 0.0)),
                })

    return entradas


