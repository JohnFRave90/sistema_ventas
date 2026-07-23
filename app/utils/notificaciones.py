from app.utils.telegram import enviar_telegram
from flask_login import current_user

def notificar_accion(tipo, datos):
    try:
        usuario = current_user.nombre_usuario if current_user.is_authenticated else "sistema"

        if tipo == "crear_pedido":
            mensaje = f"📦 *Nuevo pedido* `{datos['consecutivo']}` creado por *{usuario}* para *{datos['vendedor']}* el `{datos['fecha']}`."

        elif tipo == "editar_pedido":
            mensaje = f"✏️ *Pedido* `{datos['consecutivo']}` fue *editado* por *{usuario}*."

        elif tipo == "eliminar_pedido":
            mensaje = f"🗑 *Pedido* `{datos['consecutivo']}` fue *eliminado* por *{usuario}*."

        elif tipo == "crear_extra":
            mensaje = f"➕ *Extra* `{datos['consecutivo']}` creado por *{usuario}* para *{datos['vendedor']}* el `{datos['fecha']}`."

        elif tipo == "editar_extra":
            mensaje = f"✏️ *Extra* `{datos['consecutivo']}` fue *editado* por *{usuario}*."

        elif tipo == "eliminar_extra":
            mensaje = f"🗑 *Extra* `{datos['consecutivo']}` fue *eliminado* por *{usuario}*."

        elif tipo == "crear_devolucion":
            mensaje = f"📤 *Devolución* `{datos['consecutivo']}` creada por *{usuario}* para *{datos['vendedor']}* el `{datos['fecha']}`."

        elif tipo == "editar_devolucion":
            mensaje = f"✏️ *Devolución* `{datos['consecutivo']}` fue *editada* por *{usuario}*."

        elif tipo == "eliminar_devolucion":
            mensaje = f"🗑 *Devolución* `{datos['consecutivo']}` fue *eliminada* por *{usuario}*."

        elif tipo == "crear_venta":
            mensaje = f"💰 *Venta* registrada por *{usuario}* para *{datos['vendedor']}* el `{datos['fecha']}`.\nValor: ${datos['total']:,.0f}"

        elif tipo == "eliminar_venta":
            mensaje = f"🗑 *Venta* `{datos['consecutivo']}` del *{datos['vendedor']}* el `{datos['fecha']}` fue *eliminada* por *{usuario}*."

        elif tipo == "crear_liquidacion":
            total_pagar = datos.get('total_pagar')
            valor = f"${total_pagar:,.0f}" if total_pagar is not None else "N/D"
            mensaje = f"📄 *Liquidación* generada por *{usuario}* para *{datos['vendedor']}* del `{datos['fecha_inicio']}`\nValor: `{valor}`."

        elif tipo == "editar_liquidacion":
            mensaje = f"✏️ *Liquidación* `{datos['codigo']}` fue *editada* por *{usuario}* para *{datos['vendedor']}* el `{datos['fecha']}`."

        elif tipo == "eliminar_liquidacion":
            mensaje = f"🗑 *Liquidación* `{datos['codigo']}` fue *eliminada* por *{usuario}* para *{datos['vendedor']}* el `{datos['fecha']}`."

        else:
            mensaje = f"🔔 Acción desconocida ejecutada por *{usuario}*: `{tipo}`"

        enviar_telegram(mensaje)

    except Exception as e:
        print(f"[notificar_accion] Error: {e}")
