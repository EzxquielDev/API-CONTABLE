from flask import Blueprint, request, jsonify
from config import _valor_configuracion
from openai import OpenAI
import json
import uuid
import threading
import time
import hashlib
from datetime import date, timedelta
from services.ventas_service import obtener_productos_mas_vendidos
from services.dashboard_service import obtener_resumen_financiero, obtener_facturas_pendientes

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

_chat_tasks = {}
_query_cache = {}
CACHE_DURATION = 60 * 60  # 1 hora de caché

def get_current_date_info():
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    return f"Hoy es {hoy.isoformat()}. El primer día del mes es {primer_dia_mes.isoformat()}."

from odoo_client import get_odoo_client

def consultar_odoo_generico(modelo, dominio, campos, limite=10):
    """Permite a la IA hacer consultas genéricas a cualquier tabla de Odoo."""
    try:
        odoo = get_odoo_client()
        registros = odoo.search_read(
            modelo,
            domain=dominio,
            fields=campos,
            limit=limite
        )
        return {"registros": registros}
    except Exception as e:
        return {"error": str(e)}

# Mapeo de herramientas a funciones reales
AVAILABLE_FUNCTIONS = {
    "obtener_productos_mas_vendidos": obtener_productos_mas_vendidos,
    "obtener_resumen_financiero": obtener_resumen_financiero,
    "consultar_odoo_generico": consultar_odoo_generico,
    "obtener_facturas_pendientes": obtener_facturas_pendientes
}

# Esquema de herramientas
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "obtener_productos_mas_vendidos",
            "description": "Obtiene el ranking de los productos más vendidos en un rango de fechas especificado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha_desde": {
                        "type": "string",
                        "description": "Fecha de inicio en formato YYYY-MM-DD"
                    },
                    "fecha_hasta": {
                        "type": "string",
                        "description": "Fecha de fin en formato YYYY-MM-DD"
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Cantidad máxima de productos a devolver (ej: 5, 10, 20)"
                    }
                },
                "required": ["fecha_desde", "fecha_hasta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_resumen_financiero",
            "description": "Obtiene el resumen financiero general (total facturado, por cobrar, gastos, por pagar). Si no se pasan fechas, usa el mes actual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "desde": {
                        "type": "string",
                        "description": "Fecha de inicio en formato YYYY-MM-DD"
                    },
                    "hasta": {
                        "type": "string",
                        "description": "Fecha de fin en formato YYYY-MM-DD"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_facturas_pendientes",
            "description": "Lista todas las facturas que tienen un saldo pendiente por pagar (estado_pago: not_paid o partial).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "description": "El tipo de factura a consultar: 'cliente' (ventas) o 'proveedor' (compras)",
                        "enum": ["cliente", "proveedor"]
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_odoo_generico",
            "description": "Ejecuta una consulta genérica a la base de datos de Odoo usando search_read. Útil para consultar clientes (res.partner), productos (product.template), inventario (stock.quant), ventas (sale.order), facturas (account.move) u otros modelos. Retorna un máximo de 'limite' registros.",
            "parameters": {
                "type": "object",
                "properties": {
                    "modelo": {
                        "type": "string",
                        "description": "El nombre del modelo de Odoo, ej: 'res.partner', 'product.product', 'account.move'"
                    },
                    "dominio": {
                        "type": "array",
                        "items": { "type": "array" },
                        "description": "El dominio de búsqueda de Odoo (ej: [['is_company','=',true]])"
                    },
                    "campos": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Lista de campos a retornar (ej: ['name', 'phone', 'email'])"
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Cantidad de resultados a retornar (por defecto 10, máximo 20)"
                    }
                },
                "required": ["modelo", "dominio", "campos"]
            }
        }
    }
]

import uuid
import threading

_chat_tasks = {}

def process_chat(task_id, client, model, valid_messages, cache_key=None):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=valid_messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        response_message = response.choices[0].message

        # Si el modelo decidió llamar a una herramienta
        if response_message.tool_calls:
            valid_messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                
                if function_to_call:
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                        function_response = function_to_call(**function_args)
                            
                        valid_messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(function_response)
                        })
                    except Exception as func_err:
                        valid_messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({"error": str(func_err)})
                        })

            # Llamamos de nuevo al modelo con el resultado de la herramienta
            second_response = client.chat.completions.create(
                model=model,
                messages=valid_messages
            )
            final_message = second_response.choices[0].message.content
            _chat_tasks[task_id] = {"status": "done", "reply": final_message}
            if cache_key:
                _query_cache[cache_key] = {"reply": final_message, "timestamp": time.time()}
            return

        # Si no hubo llamadas a herramientas
        final_message = response_message.content
        _chat_tasks[task_id] = {"status": "done", "reply": final_message}
        if cache_key:
            _query_cache[cache_key] = {"reply": final_message, "timestamp": time.time()}

    except Exception as e:
        _chat_tasks[task_id] = {"status": "error", "error": str(e)}

@chat_bp.route("/", methods=["POST"])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    messages = data.get("messages", [])
    if not messages:
        if "message" in data:
            messages = [{"role": "user", "content": data["message"]}]
        else:
            return jsonify({"error": "No messages provided"}), 400

    openai_key = _valor_configuracion("OPENAI_API_KEY")
    gemini_key = _valor_configuracion("GEMINI_API_KEY")
    openrouter_key = _valor_configuracion("OPENROUTER_API_KEY")

    if openrouter_key and openrouter_key != "tu_clave_aqui":
        client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=60.0
        )
        model = "openrouter/free"
    elif openai_key and openai_key != "tu_clave_aqui":
        client = OpenAI(api_key=openai_key)
        model = "gpt-4o-mini"
    elif gemini_key and gemini_key != "tu_clave_aqui":
        client = OpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        model = "gemini-1.5-flash"
    else:
        return jsonify({"error": "API Key no configurada"}), 500

    # System message muy corto para ahorrar tokens, pero incluyendo la fecha para las herramientas
    system_message = {
        "role": "system", 
        "content": (
            f"Eres asistente financiero. Tus respuestas deben ser EXTREMADAMENTE CORTAS Y DIRECTAS, sin saludos, despedidas ni rodeos. "
            f"Ejemplo de formato ideal: '300 facturas y ganaste $9,000.00'. "
            f"DEBES invocar SIEMPRE tus herramientas (tools/function call) para obtener los datos reales antes de responder. "
            f"NUNCA respondas con texto simulando una consulta (ej: no escribas '[Consulta Odoo...]'). Usa la integración de herramientas nativa. "
            f"Si te piden una lista de 10, da exactamente 10 de forma súper resumida (ej: '1. Bici - $100'). "
            f"Si te piden los que 'menos se venden' o 'menos ganancia', simplemente da los últimos lugares de tu lista, no des explicaciones de si califican o no. "
            f"NUNCA pidas formatos como YYYY-MM-DD. Formatea el dinero SIEMPRE con el símbolo '$' y separadores de miles y decimales (ej: $7,699.12). "
            f"NO des gastos ni ganancias si no los piden. SOLO lo solicitado. {get_current_date_info()}"
        )
    }
    
    valid_messages = [system_message]
    for m in messages:
        if m["role"] in ["user", "assistant", "tool"]:
            valid_messages.append(m)

    # Revisar si la consulta ya está en caché
    messages_str = json.dumps(valid_messages)
    cache_key = hashlib.md5(messages_str.encode()).hexdigest()
    now = time.time()

    if cache_key in _query_cache:
        cached_data = _query_cache[cache_key]
        if now - cached_data["timestamp"] < CACHE_DURATION:
            # Respuesta instantánea desde caché
            task_id = str(uuid.uuid4())
            _chat_tasks[task_id] = {"status": "done", "reply": cached_data["reply"]}
            return jsonify({"task_id": task_id})

    task_id = str(uuid.uuid4())
    _chat_tasks[task_id] = {"status": "pending"}

    # Iniciar hilo
    thread = threading.Thread(target=process_chat, args=(task_id, client, model, valid_messages, cache_key))
    thread.daemon = True
    thread.start()

    return jsonify({"task_id": task_id})

@chat_bp.route("/status/<task_id>", methods=["GET"])
def chat_status(task_id):
    task = _chat_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)
