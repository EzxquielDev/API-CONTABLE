"""Consultas de inventario actual contra Odoo."""

from odoo_client import get_odoo_client


def _many2one_name(value):
    """Obtiene el texto de un campo many2one que devuelve XML-RPC."""
    return value[1] if value else ""


def _datos_documentos_entrada(odoo, capas):
    """Relaciona cada capa con producto, proveedor y factura de compra.

    Las capas de valoración no guardan directamente el proveedor ni la factura.
    Se obtiene el documento de origen desde el movimiento, la orden de compra y
    finalmente la factura de proveedor asociada a esa orden.
    """
    producto_ids = list({capa["product_id"][0] for capa in capas if capa.get("product_id")})
    productos = {}
    if producto_ids:
        fichas = odoo.search_read(
            "product.product",
            domain=[["id", "in", producto_ids]],
            fields=["display_name", "default_code"],
        )
        productos = {
            ficha["id"]: {
                "codigo": ficha.get("default_code") or "",
                "descripcion": ficha.get("display_name") or "",
            }
            for ficha in fichas
        }

    move_ids = list({capa["stock_move_id"][0] for capa in capas if capa.get("stock_move_id")})
    movimientos = []
    if move_ids:
        movimientos = odoo.search_read(
            "stock.move",
            domain=[["id", "in", move_ids]],
            fields=["origin", "picking_id"],
        )

    picking_ids = list({movimiento["picking_id"][0] for movimiento in movimientos if movimiento.get("picking_id")})
    origenes_picking = {}
    if picking_ids:
        pickings = odoo.search_read(
            "stock.picking",
            domain=[["id", "in", picking_ids]],
            fields=["origin", "name"],
        )
        origenes_picking = {
            picking["id"]: picking.get("origin") or picking.get("name") or ""
            for picking in pickings
        }

    origenes_movimiento = {
        movimiento["id"]: movimiento.get("origin") or (
            origenes_picking.get(movimiento["picking_id"][0], "") if movimiento.get("picking_id") else ""
        )
        for movimiento in movimientos
    }
    ordenes_nombres = list({origen.strip() for origen in origenes_movimiento.values() if origen and origen.strip()})
    ordenes = []
    if ordenes_nombres:
        ordenes = odoo.search_read(
            "purchase.order",
            domain=[["name", "in", ordenes_nombres]],
            fields=["name", "partner_id"],
        )
    proveedor_por_orden = {orden["name"]: _many2one_name(orden.get("partner_id")) for orden in ordenes}

    facturas_por_orden = {}
    if ordenes_nombres:
        facturas = odoo.search_read(
            "account.move",
            domain=[["move_type", "=", "in_invoice"], ["invoice_origin", "in", ordenes_nombres]],
            fields=["name", "ref", "invoice_origin", "partner_id"],
        )
        for factura in facturas:
            orden = factura.get("invoice_origin")
            if not orden:
                continue
            facturas_por_orden[orden] = {
                "factura": factura.get("ref") or factura.get("name") or "",
                "proveedor": _many2one_name(factura.get("partner_id")),
            }

    return productos, origenes_movimiento, proveedor_por_orden, facturas_por_orden


def obtener_almacenes():
    """Almacenes disponibles para filtrar el reporte."""
    odoo = get_odoo_client()
    almacenes = odoo.search_read(
        "stock.warehouse",
        domain=[],
        fields=["name", "code"],
        order="name asc",
        limit=False,
    )
    return [
        {"id": almacen["id"], "nombre": almacen["name"], "codigo": almacen.get("code", "")}
        for almacen in almacenes
    ]


def _dominio_cuantos(almacen_id=None, producto=None):
    """Solo incluye stock físico que pertenece a ubicaciones internas."""
    domain = [["location_id.usage", "=", "internal"]]

    if almacen_id:
        odoo = get_odoo_client()
        almacen = odoo.search_read(
            "stock.warehouse",
            domain=[["id", "=", almacen_id]],
            fields=["view_location_id"],
            limit=1,
        )
        if not almacen:
            raise ValueError("El almacén indicado no existe.")
        vista_almacen = almacen[0].get("view_location_id")
        if not vista_almacen:
            raise ValueError("El almacén indicado no tiene ubicación raíz configurada.")
        domain.append(["location_id", "child_of", vista_almacen[0]])

    if producto:
        texto = producto.strip()
        if texto:
            # Incluye búsqueda por nombre y por referencia interna (SKU).
            domain.extend(["|", ["product_id.name", "ilike", texto], ["product_id.default_code", "ilike", texto]])

    return domain


def _datos_producto(producto_ids):
    if not producto_ids:
        return {}

    odoo = get_odoo_client()
    productos = odoo.search_read(
        "product.product",
        domain=[["id", "in", producto_ids]],
        fields=["display_name", "default_code", "categ_id", "uom_id", "standard_price", "list_price"],
        limit=False,
    )
    return {producto["id"]: producto for producto in productos}


def obtener_reporte_inventario(almacen_id=None, producto=None, pagina=1, por_pagina=100):
    """Existencia actual consolidada por producto.

    ``stock.quant`` es la fuente de verdad del inventario actual. Se excluyen
    ubicaciones de proveedores, clientes, tránsito e inventario virtual.
    """
    if pagina < 1 or por_pagina < 1 or por_pagina > 500:
        raise ValueError("Los parámetros de paginación son inválidos.")

    domain = _dominio_cuantos(almacen_id=almacen_id, producto=producto)
    odoo = get_odoo_client()
    grupos = odoo.read_group(
        "stock.quant",
        domain=domain,
        fields=["product_id", "quantity:sum", "reserved_quantity:sum"],
        groupby=["product_id"],
        orderby="product_id",
        offset=(pagina - 1) * por_pagina,
        limit=por_pagina,
        lazy=False,
    )

    # read_group puede devolver grupos de producto vacío en bases con datos
    # incompletos; no representan una ficha inventariable.
    grupos = [grupo for grupo in grupos if grupo.get("product_id")]
    producto_ids = [grupo["product_id"][0] for grupo in grupos]
    productos = _datos_producto(producto_ids)

    detalle = []
    for grupo in grupos:
        producto_id = grupo["product_id"][0]
        ficha = productos.get(producto_id)
        if not ficha:
            continue

        existencia = float(grupo.get("quantity", 0) or 0)
        reservado = float(grupo.get("reserved_quantity", 0) or 0)
        disponible = existencia - reservado
        costo = float(ficha.get("standard_price", 0) or 0)

        detalle.append({
            "producto_id": producto_id,
            "producto": ficha.get("display_name") or _many2one_name(grupo["product_id"]),
            "sku": ficha.get("default_code") or "",
            "categoria": _many2one_name(ficha.get("categ_id")),
            "unidad_medida": _many2one_name(ficha.get("uom_id")),
            "existencia": round(existencia, 2),
            "reservado": round(reservado, 2),
            "disponible": round(disponible, 2),
            "costo_unitario": round(costo, 2),
            "precio_venta": round(float(ficha.get("list_price", 0) or 0), 2),
            "valor_inventario": round(existencia * costo, 2),
        })

    return {
        "pagina": pagina,
        "por_pagina": por_pagina,
        "almacen_id": almacen_id,
        "producto_filtro": producto or "",
        "productos": detalle,
    }


def obtener_productos_inventario(almacen_id=None, producto=None):
    """Obtiene el detalle completo en bloques, útil para la vista y exportaciones."""
    productos = []
    pagina = 1
    while True:
        bloque = obtener_reporte_inventario(
            almacen_id=almacen_id,
            producto=producto,
            pagina=pagina,
            por_pagina=500,
        )["productos"]
        productos.extend(bloque)
        if len(bloque) < 500:
            return productos
        pagina += 1


def obtener_resumen_inventario(almacen_id=None, producto=None):
    """Totales globales del mismo universo del reporte detallado."""
    # Se obtienen todos los productos para no aplicar paginación a los totales.
    productos = obtener_productos_inventario(almacen_id=almacen_id, producto=producto)

    return {
        "almacen_id": almacen_id,
        "cantidad_productos": len(productos),
        "existencia_total": round(sum(producto["existencia"] for producto in productos), 2),
        "reservado_total": round(sum(producto["reservado"] for producto in productos), 2),
        "disponible_total": round(sum(producto["disponible"] for producto in productos), 2),
        "valor_inventario_total": round(sum(producto["valor_inventario"] for producto in productos), 2),
    }


def obtener_entradas_inventario(desde, hasta, limite=200, desplazamiento=0):
    """Devuelve las entradas de productos ya valorizadas por Odoo.

    Las capas de valoración son la fuente usada también por el Kardex: una
    cantidad positiva representa una entrada y permite mostrar su costo real.
    """
    if limite < 1 or limite > 500:
        raise ValueError("El límite debe estar entre 1 y 500.")

    odoo = get_odoo_client()
    capas = odoo.search_read(
        "stock.valuation.layer",
        domain=[
            ["quantity", ">", 0],
            ["create_date", ">=", desde],
            ["create_date", "<=", f"{hasta} 23:59:59"],
        ],
        fields=["product_id", "quantity", "unit_cost", "value", "create_date", "description", "stock_move_id"],
        order="create_date desc, id desc",
        limit=limite,
        offset=desplazamiento,
    )

    productos, referencias, proveedores, facturas = _datos_documentos_entrada(odoo, capas)
    entradas = []
    for capa in capas:
        movimiento_id = capa["stock_move_id"][0] if capa.get("stock_move_id") else None
        referencia = referencias.get(movimiento_id, "")
        documento = facturas.get(referencia, {})
        producto = productos.get(capa["product_id"][0], {}) if capa.get("product_id") else {}
        entradas.append({
            "fecha": capa.get("create_date", "")[:10],
            "proveedor": proveedores.get(referencia) or documento.get("proveedor", ""),
            # Si la compra aún no tiene factura registrada, se muestra la orden
            # de origen para conservar la trazabilidad del movimiento.
            "factura": documento.get("factura") or referencia,
            "codigo": producto.get("codigo", ""),
            "producto": producto.get("descripcion") or _many2one_name(capa.get("product_id")),
            "cantidad": round(float(capa.get("quantity", 0) or 0), 2),
            "costo_unitario": round(float(capa.get("unit_cost", 0) or 0), 2),
            "valor_total": round(float(capa.get("value", 0) or 0), 2),
            "referencia": referencia,
            "descripcion": capa.get("description") or "",
        })
    return entradas


def obtener_todas_entradas_inventario(desde, hasta):
    """Recupera todas las entradas por bloques compatibles con Odoo."""
    entradas = []
    desplazamiento = 0
    limite = 500
    while True:
        bloque = obtener_entradas_inventario(desde, hasta, limite, desplazamiento)
        entradas.extend(bloque)
        if len(bloque) < limite:
            return entradas
        desplazamiento += limite
