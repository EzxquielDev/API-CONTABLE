# API Contable — Odoo + Flask

Primer módulo: **Dashboard financiero**, listo para consumir desde Excel o Google Sheets.

## 1. Instalación

```powershell
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y completa tus datos reales:

```powershell
copy .env.example .env
```

## 2. Ejecutar la API

```powershell
python app.py
```

Se abrirá en `http://127.0.0.1:5000`. Visita esa URL en el navegador para confirmar que responde.

## 3. Endpoints disponibles

Todos requieren el header `X-API-Key` con el valor que pusiste en `FLASK_API_KEY`.

| Endpoint | Descripción |
|---|---|
| `GET /api/dashboard/resumen` | JSON con facturado, cobrado, gastos, resultado del mes |
| `GET /api/dashboard/facturas-pendientes` | JSON de facturas de cliente sin cobrar |
| `GET /api/dashboard/facturas-pendientes.csv` | Mismo dato, en CSV descargable |
| `GET /api/dashboard/gastos-pendientes` | JSON de facturas de proveedor sin pagar |
| `GET /api/inventario/almacenes` | Almacenes disponibles para filtrar el inventario |
| `GET /api/inventario/resumen?almacen_id=ID` | Totales de existencias, reservas y valor actual |
| `GET /api/inventario/reporte?almacen_id=ID&producto=TEXTO` | Existencias actuales por producto |
| `GET /api/inventario/reporte.csv` | Reporte completo en CSV |
| `GET /api/inventario/reporte.xlsx` | Reporte completo en Excel |

Prueba rápida con PowerShell:

```powershell
curl.exe -H "X-API-Key: tu-clave" http://127.0.0.1:5000/api/dashboard/resumen
```

## 4. Conectar desde Excel (Power Query)

1. Datos → Obtener datos → De otras fuentes → **Desde la Web**.
2. URL: `http://127.0.0.1:5000/api/dashboard/facturas-pendientes`
3. Clic en **Avanzado**, y en "Encabezados de solicitud HTTP" agrega:
   - Nombre: `X-API-Key`
   - Valor: tu clave
4. Power Query detecta el JSON automáticamente y te deja expandirlo en columnas.
5. Puedes programar la actualización automática (Datos → Propiedades de la consulta → Actualizar cada X minutos).

> Nota: mientras la API corra solo en tu máquina (`127.0.0.1`), esto solo funcionará en Excel de esa misma máquina. Si luego la subes a un servidor (Render, Railway, tu propio VPS), cambias la URL y funciona desde cualquier lado.

## 5. Conectar desde Google Sheets (Apps Script)

Como Sheets no puede llamar directo a `127.0.0.1` (tu máquina local), necesitas que la API esté publicada en un servidor accesible desde internet. Cuando la tengas desplegada, usa esto en **Extensiones → Apps Script**:

```javascript
function obtenerResumenContable() {
  const url = "https://tu-api-desplegada.com/api/dashboard/resumen";
  const opciones = {
    headers: { "X-API-Key": "tu-clave" }
  };
  const respuesta = UrlFetchApp.fetch(url, opciones);
  const datos = JSON.parse(respuesta.getContentText());

  const hoja = SpreadsheetApp.getActiveSheet();
  hoja.getRange("A1").setValue("Periodo");
  hoja.getRange("B1").setValue(datos.periodo);
  hoja.getRange("A2").setValue("Total facturado");
  hoja.getRange("B2").setValue(datos.total_facturado);
  hoja.getRange("A3").setValue("Por cobrar");
  hoja.getRange("B3").setValue(datos.total_por_cobrar);
  hoja.getRange("A4").setValue("Gastos");
  hoja.getRange("B4").setValue(datos.total_gastos);
  hoja.getRange("A5").setValue("Resultado estimado");
  hoja.getRange("B5").setValue(datos.resultado_estimado);
}
```

Puedes programar este script con un **trigger de tiempo** (Editor → reloj ⏰) para que se actualice solo, por ejemplo cada hora.

## 6. Siguiente paso: desplegar para que Sheets pueda alcanzarla

Por ahora la API corre solo en tu PC (`127.0.0.1`). Para usarla desde Google Sheets necesitas subirla a un servidor con IP/dominio público. Opciones simples y baratas: Render, Railway, Fly.io, o un VPS pequeño. Lo vemos cuando quieras avanzar a ese paso.

## Próximos módulos (pendientes)

- Flujo de caja proyectado
- Conciliación bancaria asistida
- Alertas de facturas vencidas
