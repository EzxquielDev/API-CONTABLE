from datetime import date
from odoo_client import get_odoo_client


def obtener_resumen_financiero():
    """Resumen general: facturación, cobros pendientes, gastos, pagos pendientes."""
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

    return {
        "periodo": hoy.strftime("%Y-%m"),
        "total_facturado": round(total_facturado, 2),
        "total_por_cobrar": round(total_por_cobrar, 2),
        "total_gastos": round(total_gastos, 2),
        "total_por_pagar": round(total_por_pagar, 2),
        "resultado_estimado": round(total_facturado - total_gastos, 2),
        "cantidad_facturas_venta": len(facturas_venta),
        "cantidad_facturas_compra": len(facturas_compra),
    }


def obtener_facturas_pendientes(tipo="cliente"):
    """Lista de facturas con saldo pendiente (cliente o proveedor)."""
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

    return resultado
