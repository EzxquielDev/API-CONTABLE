"""
Diagnóstico: por qué el Estado Financiero muestra 0 en compras.

Este script consulta las facturas de proveedor (account.move / in_invoice)
SIN filtrar por fecha ni por estado, para que veas qué existe realmente
en tu Odoo y en qué 'state' están.

Ejecutar con:  python diagnostico_compras.py
"""

from collections import Counter
from odoo_client import get_odoo_client


def main():
    odoo = get_odoo_client()

    # Traemos TODAS las facturas de proveedor, sin filtrar por estado ni fecha
    facturas = odoo.search_read(
        "account.move",
        domain=[["move_type", "=", "in_invoice"]],
        fields=["name", "state", "invoice_date", "amount_total", "partner_id"],
        order="invoice_date desc",
        limit=50,
    )

    print(f"Total de facturas de proveedor encontradas (sin filtros): {len(facturas)}\n")

    if not facturas:
        print(">> No existe NINGUNA factura de proveedor (account.move, in_invoice) en Odoo.")
        print(">> Verifica: ¿las creas como 'Factura de proveedor' en Facturación,")
        print(">> o solo quedan como Orden de Compra sin convertir a factura?")
        return

    estados = Counter(f["state"] for f in facturas)
    print("Distribución por estado (state):")
    for estado, cantidad in estados.items():
        print(f"   - {estado}: {cantidad}")

    if estados.get("posted", 0) == 0:
        print("\n>> Ninguna factura está en estado 'posted' (Validada/Publicada).")
        print(">> Por eso el Estado Financiero las muestra en 0: solo cuenta")
        print(">> facturas confirmadas, no borradores ('draft').")
        print(">> Solución: en Odoo, abre la factura de proveedor y dale clic")
        print(">> a 'Confirmar' / 'Validar' (según tu versión de Odoo).")

    print("\nÚltimas facturas encontradas:")
    print(f"{'Número':<15}{'Estado':<12}{'Fecha':<14}{'Total':>12}  Proveedor")
    for f in facturas[:15]:
        proveedor = f["partner_id"][1] if f.get("partner_id") else "-"
        fecha = f.get("invoice_date") or "(sin fecha)"
        print(f"{f['name']:<15}{f['state']:<12}{fecha:<14}{f['amount_total']:>12,.2f}  {proveedor}")


if __name__ == "__main__":
    main()
