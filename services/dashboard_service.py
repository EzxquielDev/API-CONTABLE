from datetime import date
import time
from odoo_client import get_odoo_client

_cache_dashboard = {}
CACHE_TTL = 300


def obtener_resumen_financiero():
    """Resumen general: facturación, cobros pendientes, gastos, pagos pendientes."""
    clave = "resumen_financiero"
    ahora = time.time()
    if clave in _cache_dashboard:
        datos, ts = _cache_dashboard[clave]
        if ahora - ts < CACHE_TTL:
            return datos

    odoo = get_odoo_client()
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1).isoformat()

    # Facturas de cliente (ventas) del mes actual, confirmadas
    facturas_venta = odoo.search_read(
        "account.move",
        domain=[
            ["move_type", "=", "out_invoice"],
            ["state", "=", "posted"],
            ["invoice_date", ">=", primer_dia_mes],
        ],
        fields=["amount_total", "amount_residual", "payment_state"],
    )

    # Facturas de proveedor (gastos) del mes actual, confirmadas
    facturas_compra = odoo.search_read(
        "account.move",
        domain=[
            ["move_type", "=", "in_invoice"],
            ["state", "=", "posted"],
            ["invoice_date", ">=", primer_dia_mes],
        ],
        fields=["amount_total", "amount_residual", "payment_state"],
    )

    total_facturado = sum(f["amount_total"] for f in facturas_venta)
    total_por_cobrar = sum(f["amount_residual"] for f in facturas_venta)
    total_gastos = sum(f["amount_total"] for f in facturas_compra)
    total_por_pagar = sum(f["amount_residual"] for f in facturas_compra)

    resultado = {
        "periodo": hoy.strftime("%Y-%m"),
        "total_facturado": round(total_facturado, 2),
        "total_por_cobrar": round(total_por_cobrar, 2),
        "total_gastos": round(total_gastos, 2),
        "total_por_pagar": round(total_por_pagar, 2),
        "resultado_estimado": round(total_facturado - total_gastos, 2),
        "cantidad_facturas_venta": len(facturas_venta),
        "cantidad_facturas_compra": len(facturas_compra),
    }
    _cache_dashboard[clave] = (resultado, ahora)
    return resultado


def obtener_estado_financiero(desde=None, hasta=None):
    """Estado financiero simple: ventas vs. compras en un rango de fechas.

    - Ventas: facturas de cliente confirmadas (account.move / out_invoice, posted).
      Es el ingreso ya reconocido/facturado.

    - Compras: Órdenes de Compra confirmadas (purchase.order, state in
      ['purchase', 'done']). Se usa la Orden de Compra y NO la factura de
      proveedor porque en la operación real las facturas de proveedor no
      siempre se validan en Facturación; la Orden de Compra sí se confirma
      de forma consistente. Esto mide el gasto COMPROMETIDO, no el gasto
      contablemente reconocido — si en el futuro empiezas a validar todas
      las facturas de proveedor, conviene volver a usar account.move para
      mayor exactitud.

    Si no se indica 'hasta', se usa la fecha de hoy.
    Si no se indica 'desde', se usa el primer día del mes de 'hasta'.
    """
    clave = f"estado_financiero_{desde}_{hasta}"
    ahora = time.time()
    if clave in _cache_dashboard:
        datos, ts = _cache_dashboard[clave]
        if ahora - ts < CACHE_TTL:
            return datos

    odoo = get_odoo_client()

    if not hasta:
        hasta = date.today().isoformat()
    if not desde:
        fecha_hasta = date.fromisoformat(hasta)
        desde = fecha_hasta.replace(day=1).isoformat()

    # ---- Ventas: facturas de cliente confirmadas ----
    facturas_venta = odoo.search_read(
        "account.move",
        domain=[
            ["move_type", "=", "out_invoice"],
            ["state", "=", "posted"],
            ["invoice_date", ">=", desde],
            ["invoice_date", "<=", hasta],
        ],
        fields=["amount_total", "amount_residual", "payment_state"],
    )

    total_facturado_ventas = sum(f["amount_total"] for f in facturas_venta)
    total_por_cobrar = sum(f["amount_residual"] for f in facturas_venta)
    total_cobrado = total_facturado_ventas - total_por_cobrar

    # ---- Compras: Órdenes de Compra confirmadas (módulo "Compra") ----
    ordenes_compra = odoo.search_read(
        "purchase.order",
        domain=[
            ["state", "in", ["purchase", "done"]],
            ["date_order", ">=", f"{desde} 00:00:00"],
            ["date_order", "<=", f"{hasta} 23:59:59"],
        ],
        fields=["amount_total", "invoice_status", "date_order", "partner_id"],
    )

    total_ordenado = sum(o["amount_total"] for o in ordenes_compra)
    ordenes_facturadas = [o for o in ordenes_compra if o.get("invoice_status") == "invoiced"]
    total_ya_facturado = sum(o["amount_total"] for o in ordenes_facturadas)
    total_por_facturar = total_ordenado - total_ya_facturado

    resultado = {
        "desde": desde,
        "hasta": hasta,
        "ventas": {
            "total_facturado": round(total_facturado_ventas, 2),
            "total_cobrado": round(total_cobrado, 2),
            "total_por_cobrar": round(total_por_cobrar, 2),
            "cantidad_facturas": len(facturas_venta),
        },
        "compras": {
            "total_ordenado": round(total_ordenado, 2),
            "total_facturado": round(total_ya_facturado, 2),
            "total_por_facturar": round(total_por_facturar, 2),
            "cantidad_ordenes": len(ordenes_compra),
        },
        "resultado_neto": round(total_facturado_ventas - total_ordenado, 2),
    }
    _cache_dashboard[clave] = (resultado, ahora)
    return resultado


def obtener_libro_diario(desde=None, hasta=None):
    """Libro Diario: listado cronológico de los apuntes contables (débito/crédito)
    de todos los asientos CONFIRMADOS (posted) en el rango de fechas.

    Se lee de account.move.line (apuntes contables), que es lo que genera Odoo
    automáticamente al confirmar una factura de cliente, una factura de
    proveedor, o cualquier otro asiento. No depende de tener el módulo
    Contabilidad completo: basta con Facturación.

    Si no se indica 'hasta', se usa la fecha de hoy.
    Si no se indica 'desde', se usa el primer día del mes de 'hasta'.
    """
    clave = f"libro_diario_{desde}_{hasta}"
    ahora = time.time()
    if clave in _cache_dashboard:
        datos, ts = _cache_dashboard[clave]
        if ahora - ts < CACHE_TTL:
            return datos

    odoo = get_odoo_client()

    if not hasta:
        hasta = date.today().isoformat()
    if not desde:
        fecha_hasta = date.fromisoformat(hasta)
        desde = fecha_hasta.replace(day=1).isoformat()

    dominio = [
        ["parent_state", "=", "posted"],
        ["date", ">=", desde],
        ["date", "<=", hasta],
    ]
    campos_base = ["date", "move_name", "account_id", "journal_id", "name", "partner_id", "debit", "credit"]

    try:
        # display_type filtra líneas de sección/nota que no son apuntes reales
        lineas = odoo.search_read(
            "account.move.line",
            domain=dominio + [["display_type", "not in", ["line_section", "line_note"]]],
            fields=campos_base,
            order="date asc, move_name asc, id asc",
        )
    except Exception:
        # Compatibilidad con versiones de Odoo donde 'display_type' no existe
        lineas = odoo.search_read(
            "account.move.line",
            domain=dominio,
            fields=campos_base,
            order="date asc, move_name asc, id asc",
        )

    movimientos = []
    total_debe = 0.0
    total_haber = 0.0

    for linea in lineas:
        cuenta = linea["account_id"][1] if linea.get("account_id") else ""
        diario = linea["journal_id"][1] if linea.get("journal_id") else ""
        socio = linea["partner_id"][1] if linea.get("partner_id") else ""
        etiqueta = linea.get("name") or socio or ""
        debe = linea.get("debit") or 0.0
        haber = linea.get("credit") or 0.0

        total_debe += debe
        total_haber += haber

        movimientos.append({
            "fecha": linea.get("date"),
            "asiento": linea.get("move_name"),
            "diario": diario,
            "cuenta": cuenta,
            "etiqueta": etiqueta,
            "debe": round(debe, 2),
            "haber": round(haber, 2),
        })

    resultado = {
        "desde": desde,
        "hasta": hasta,
        "movimientos": movimientos,
        "total_debe": round(total_debe, 2),
        "total_haber": round(total_haber, 2),
        "diferencia": round(total_debe - total_haber, 2),
        "cantidad_lineas": len(movimientos),
    }
    _cache_dashboard[clave] = (resultado, ahora)
    return resultado


def obtener_facturas_pendientes(tipo="cliente"):
    """Lista de facturas con saldo pendiente (cliente o proveedor)."""
    clave = f"facturas_pendientes_{tipo}"
    ahora = time.time()
    if clave in _cache_dashboard:
        datos, ts = _cache_dashboard[clave]
        if ahora - ts < CACHE_TTL:
            return datos

    odoo = get_odoo_client()
    move_type = "out_invoice" if tipo == "cliente" else "in_invoice"

    facturas = odoo.search_read(
        "account.move",
        domain=[
            ["move_type", "=", move_type],
            ["state", "=", "posted"],
            ["payment_state", "in", ["not_paid", "partial"]],
        ],
        fields=[
            "name", "partner_id", "invoice_date", "invoice_date_due",
            "amount_total", "amount_residual", "payment_state",
        ],
        order="invoice_date_due asc",
    )

    resultado = []
    hoy = date.today()
    for f in facturas:
        vencida = False
        dias_vencida = 0
        if f.get("invoice_date_due"):
            fecha_venc = date.fromisoformat(f["invoice_date_due"])
            if fecha_venc < hoy:
                vencida = True
                dias_vencida = (hoy - fecha_venc).days

        resultado.append({
            "numero": f["name"],
            "cliente_proveedor": f["partner_id"][1] if f["partner_id"] else "",
            "fecha_factura": f.get("invoice_date"),
            "fecha_vencimiento": f.get("invoice_date_due"),
            "monto_total": f["amount_total"],
            "monto_pendiente": f["amount_residual"],
            "estado_pago": f["payment_state"],
            "vencida": vencida,
            "dias_vencida": dias_vencida,
        })

    _cache_dashboard[clave] = (resultado, ahora)
    return resultado
