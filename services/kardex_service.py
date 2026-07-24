from odoo_client import get_odoo_client

# Datos EXACTOS de la bodega en Odoo (Inventario > Configuración > Almacenes).
# En Odoo el almacén se muestra como "CODIGO/Nombre", ej: "BCE/Bodega Central Bicimania".
BODEGA_CENTRAL_NOMBRE = "Bodega Central Bicimania"
BODEGA_CENTRAL_CODIGO = "BCE"

_cache_ubicaciones_bodega = {}


def _obtener_ubicaciones_bodega(odoo, nombre_bodega, codigo_bodega=None):
    """Devuelve el set de IDs de stock.location que pertenecen a una bodega
    (su ubicación raíz y todas las hijas: stock, entrada, salida, etc.).
    Busca por nombre exacto o por código, lo que encuentre primero."""
    clave_cache = f"{nombre_bodega}|{codigo_bodega}"
    if clave_cache in _cache_ubicaciones_bodega:
        return _cache_ubicaciones_bodega[clave_cache]

    domain = [["name", "=", nombre_bodega]]
    if codigo_bodega:
        domain = ["|", ["code", "=", codigo_bodega], ["name", "=", nombre_bodega]]

    bodegas = odoo.search_read(
        "stock.warehouse",
        domain=domain,
        fields=["id", "name", "code", "view_location_id"],
        limit=1,
    )
    if not bodegas:
        raise ValueError(
            f"No se encontró ninguna bodega con nombre '{nombre_bodega}' ni código "
            f"'{codigo_bodega}' en Odoo. Verifica en Inventario > Configuración > Almacenes."
        )

    view_location_id = bodegas[0]["view_location_id"][0]
    ubicaciones = odoo.search_read(
        "stock.location",
        domain=[["id", "child_of", view_location_id]],
        fields=["id"],
    )
    ids = {u["id"] for u in ubicaciones}
    _cache_ubicaciones_bodega[clave_cache] = ids
    return ids


def _extraer_codigo_nombre(display_name):
    """Odoo suele mostrar el producto como '[CODIGO] Nombre'. Separamos ambos."""
    if not display_name:
        return "", ""
    if display_name.startswith("[") and "]" in display_name:
        codigo, resto = display_name.split("]", 1)
        return codigo.strip("[ "), resto.strip()
    return "", display_name


def _buscar_producto_id_por_codigo(odoo, codigo):
    resultados = odoo.search_read(
        "product.product",
        domain=[["default_code", "=", codigo]],
        fields=["id"],
        limit=1,
    )
    return resultados[0]["id"] if resultados else None


def obtener_kardex(fecha_desde, fecha_hasta, codigo_producto=None, bodega=None, codigo_bodega=None):
    odoo = get_odoo_client()
    nombre_bodega = bodega or BODEGA_CENTRAL_NOMBRE
    cod_bodega = codigo_bodega or (BODEGA_CENTRAL_CODIGO if not bodega else None)
    ubicaciones_bodega = _obtener_ubicaciones_bodega(odoo, nombre_bodega, cod_bodega)

    domain_producto = []
    if codigo_producto:
        producto_id = _buscar_producto_id_por_codigo(odoo, codigo_producto)
        if not producto_id:
            return {"desde": fecha_desde, "hasta": fecha_hasta, "productos": [],
                    "aviso": f"No se encontró ningún producto con código '{codigo_producto}'"}
        domain_producto = [["product_id", "=", producto_id]]

    # --- Saldo inicial: todo lo acumulado ANTES de la fecha de inicio ---
    capas_previas = odoo.search_read(
        "stock.valuation.layer",
        domain=domain_producto + [["create_date", "<", fecha_desde]],
        fields=["product_id", "quantity", "value", "stock_move_id"],
    )

    # --- Movimientos dentro del rango solicitado ---
    capas = odoo.search_read(
        "stock.valuation.layer",
        domain=domain_producto + [
            ["create_date", ">=", fecha_desde],
            ["create_date", "<=", f"{fecha_hasta} 23:59:59"],
        ],
        fields=["product_id", "quantity", "unit_cost", "value", "create_date",
                 "description", "stock_move_id"],
        order="product_id asc, create_date asc",
    )

    # --- Filtramos ambas listas para quedarnos SOLO con capas cuyo movimiento
    # entra o sale de la bodega solicitada (por defecto, Bodega Central) ---
    todos_move_ids = list({
        c["stock_move_id"][0] for c in (capas_previas + capas) if c.get("stock_move_id")
    })
    ubicacion_por_move = {}
    if todos_move_ids:
        info_moves = odoo.search_read(
            "stock.move",
            domain=[["id", "in", todos_move_ids]],
            fields=["location_id", "location_dest_id"],
        )
        for m in info_moves:
            loc_o = m["location_id"][0] if m.get("location_id") else None
            loc_d = m["location_dest_id"][0] if m.get("location_dest_id") else None
            ubicacion_por_move[m["id"]] = (loc_o, loc_d)

    def _es_de_la_bodega(capa):
        move_id = capa["stock_move_id"][0] if capa.get("stock_move_id") else None
        if move_id is None:
            # Sin movimiento asociado (ej. ajuste manual de valorización):
            # no podemos confirmar la bodega, así que se excluye.
            return False
        loc_o, loc_d = ubicacion_por_move.get(move_id, (None, None))
        return loc_o in ubicaciones_bodega or loc_d in ubicaciones_bodega

    capas_previas = [c for c in capas_previas if _es_de_la_bodega(c)]
    capas = [c for c in capas if _es_de_la_bodega(c)]

    saldo_inicial = {}
    for c in capas_previas:
        pid, nombre = c["product_id"]
        if pid not in saldo_inicial:
            saldo_inicial[pid] = {"nombre": nombre, "cantidad": 0.0, "valor": 0.0}
        saldo_inicial[pid]["cantidad"] += c["quantity"]
        saldo_inicial[pid]["valor"] += c["value"]

    # --- Documento origen de cada movimiento (campo "origin") ---
    # Lo buscamos primero en stock.move; si viene vacío, lo tomamos de su transferencia (stock.picking),
    # que es donde tú lo confirmaste visualmente en Odoo.
    move_ids_todos = [c["stock_move_id"][0] for c in capas if c.get("stock_move_id")]
    origenes_por_move = {}
    if move_ids_todos:
        moves_origen = odoo.search_read(
            "stock.move",
            domain=[["id", "in", move_ids_todos]],
            fields=["origin", "picking_id"],
        )

        picking_ids = list({m["picking_id"][0] for m in moves_origen if m.get("picking_id")})
        origen_por_picking = {}
        if picking_ids:
            pickings = odoo.search_read(
                "stock.picking",
                domain=[["id", "in", picking_ids]],
                fields=["origin"],
            )
            origen_por_picking = {p["id"]: p.get("origin") for p in pickings}

        for m in moves_origen:
            origen = m.get("origin")
            if not origen and m.get("picking_id"):
                origen = origen_por_picking.get(m["picking_id"][0])
            origenes_por_move[m["id"]] = origen

    # --- Precio de venta: match EXACTO vía el número de factura contenido en "Documento origen" ---
    # El origin viene como "DTE01|INV/2026/2759" -> nos interesa la parte "INV/2026/2759"
    salidas = [c for c in capas if c["quantity"] < 0]
    precios_venta_por_capa = {}

    if salidas:
        nombres_factura_por_move = {}
        for move_id, origin in origenes_por_move.items():
            if origin and "|" in origin:
                nombres_factura_por_move[move_id] = origin.split("|")[-1].strip()
            elif origin:
                nombres_factura_por_move[move_id] = origin.strip()

        nombres_factura = list(set(nombres_factura_por_move.values()))
        if nombres_factura:
            facturas = odoo.search_read(
                "account.move",
                domain=[["name", "in", nombres_factura]],
                fields=["name"],
            )
            id_por_nombre_factura = {f["name"]: f["id"] for f in facturas}

            invoice_ids = list(id_por_nombre_factura.values())
            lineas_factura = odoo.search_read(
                "account.move.line",
                domain=[["move_id", "in", invoice_ids], ["product_id", "!=", False]],
                fields=["product_id", "price_unit", "move_id"],
            )
            # Precio por (factura, producto) — así distinguimos si la misma factura
            # tiene el mismo producto en más de una línea (raro, pero por si acaso)
            precio_por_factura_producto = {}
            for l in lineas_factura:
                clave = (l["move_id"][0], l["product_id"][0])
                precio_por_factura_producto[clave] = l["price_unit"]

            for c in salidas:
                move_id = c["stock_move_id"][0] if c.get("stock_move_id") else None
                nombre_factura = nombres_factura_por_move.get(move_id)
                invoice_id = id_por_nombre_factura.get(nombre_factura) if nombre_factura else None
                if invoice_id:
                    clave = (invoice_id, c["product_id"][0])
                    precio = precio_por_factura_producto.get(clave)
                    if precio is not None:
                        precios_venta_por_capa[move_id if move_id else id(c)] = precio

    # --- Respaldo: precio de lista configurado en la ficha del producto ---
    # Se usa solo cuando no se pudo encontrar el precio exacto de la factura.
    precio_lista_por_producto = {}
    productos_ids_todos = list({c["product_id"][0] for c in capas})
    if productos_ids_todos:
        fichas = odoo.search_read(
            "product.product",
            domain=[["id", "in", productos_ids_todos]],
            fields=["list_price"],
        )
        precio_lista_por_producto = {f["id"]: f["list_price"] for f in fichas}

    # --- Armamos el Kardex por producto, con saldo corriendo ---
    productos = {}
    orden_productos = []

    for pid, datos in saldo_inicial.items():
        codigo, nombre = _extraer_codigo_nombre(datos["nombre"])
        productos[pid] = {
            "codigo": codigo,
            "descripcion": nombre,
            "existencia_inicial": round(datos["cantidad"], 2),
            "saldo_inicial": round(datos["valor"], 2),
            "movimientos": [],
        }
        orden_productos.append(pid)

    existencia_corrida = {pid: d["existencia_inicial"] for pid, d in productos.items()}
    saldo_corrido = {pid: d["saldo_inicial"] for pid, d in productos.items()}

    for c in capas:
        pid, nombre = c["product_id"]
        if pid not in productos:
            codigo, desc = _extraer_codigo_nombre(nombre)
            productos[pid] = {
                "codigo": codigo, "descripcion": desc,
                "existencia_inicial": 0.0, "saldo_inicial": 0.0,
                "movimientos": [],
            }
            orden_productos.append(pid)
            existencia_corrida[pid] = 0.0
            saldo_corrido[pid] = 0.0

        cantidad = c["quantity"]
        es_entrada = cantidad > 0

        existencia_corrida[pid] += cantidad
        saldo_corrido[pid] += c["value"]

        clave_precio = c["stock_move_id"][0] if c.get("stock_move_id") else id(c)
        precio_unitario_venta = None
        precio_es_estimado = False
        if not es_entrada:
            precio_unitario_venta = precios_venta_por_capa.get(clave_precio)
            if precio_unitario_venta is None:
                precio_unitario_venta = precio_lista_por_producto.get(pid)
                precio_es_estimado = precio_unitario_venta is not None

        # El "precio de venta" del kardex debe reflejar el costo TOTAL de las
        # unidades que salieron (precio unitario x cantidad), no el precio unitario.
        precio_venta = None
        if precio_unitario_venta is not None:
            precio_venta = precio_unitario_venta * (-cantidad)

        productos[pid]["movimientos"].append({
            "fecha": c["create_date"][:10] if c.get("create_date") else "",
            "qty_entrada": round(cantidad, 2) if es_entrada else 0,
            "costo_unitario": round(c["unit_cost"], 2) if es_entrada else None,
            "costo_total": round(c["value"], 2) if es_entrada else None,
            "qty_salida": round(-cantidad, 2) if not es_entrada else 0,
            "precio_venta": round(precio_venta, 2) if precio_venta is not None else None,
            "precio_estimado": precio_es_estimado,
            "existencia": round(existencia_corrida[pid], 2),
            "saldo": round(saldo_corrido[pid], 2),
            "referencia": origenes_por_move.get(
                c["stock_move_id"][0] if c.get("stock_move_id") else None
            ) or "(sin documento origen)",
        })

    resultado = []
    for pid in orden_productos:
        p = productos[pid]
        if p["movimientos"]:  # omitimos productos sin movimiento en el rango
            resultado.append(p)

    return {"desde": fecha_desde, "hasta": fecha_hasta, "productos": resultado}
