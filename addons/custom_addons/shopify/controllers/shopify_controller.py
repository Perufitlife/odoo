# custom_addons/shopify/controllers/shopify_controller.py

from odoo import http
from odoo.http import Response
import json
import logging
import hmac
import hashlib
from base64 import b64encode

_logger = logging.getLogger(__name__)

class ShopifyController(http.Controller):
    @http.route([
        '/shopify/webhook/orders/create',
        '/shopify/webhook/draft_orders/create'
    ], type='http', auth='none', methods=['POST'], csrf=False)
    def webhook(self, **kwargs):
        try:
            _logger.info("=== Shopify Webhook Called ===")

            # Establecer el usuario administrador para las operaciones
            uid = http.request.env.ref('base.user_admin').id
            env = http.request.env(user=uid)

            # Obtener el ID de la tienda desde los parámetros de la URL
            store_id = kwargs.get('store')
            if not store_id:
                raise ValueError("No se proporcionó el ID de la tienda en la URL.")

            try:
                store_id = int(store_id)
            except ValueError:
                raise ValueError(f"El ID de la tienda ('{store_id}') no es válido. Debe ser un número entero.")

            # Buscar la tienda en shopify.store usando el env con usuario
            store = env['shopify.store'].sudo().search([('id', '=', store_id)], limit=1)
            if not store:
                raise ValueError(f"No se encontró una tienda con ID {store_id}.")

            _logger.info(f"Procesando webhook para la tienda: {store.name}")

            # Validar la firma del webhook
            shopify_hmac = http.request.httprequest.headers.get('X-Shopify-Hmac-Sha256')
            if not shopify_hmac:
                raise ValueError("No se encontró la firma HMAC en los headers.")

            secret = store.webhook_signature.encode()
            payload = http.request.httprequest.data
            computed_hmac = b64encode(hmac.new(secret, payload, hashlib.sha256).digest()).decode()

            if not hmac.compare_digest(shopify_hmac, computed_hmac):
                raise ValueError("La firma HMAC del webhook no es válida.")

            # Parsear los datos del webhook
            data = json.loads(payload)
            shopify_topic = http.request.httprequest.headers.get('X-Shopify-Topic', 'unknown')

            # Preparar valores para crear log
            data['store_id'] = store_id
            webhook_vals = {
                'name': f'Webhook {shopify_topic}',
                'payload': json.dumps(data, indent=2),  # Mejorado para mejor legibilidad
                'event_type': shopify_topic,
                'state': 'pending',
                'shopify_order_id': str(data.get('id', '')),
            }

            # Añadir información del cliente si está disponible
            customer_name = None
            shipping_address = data.get('shipping_address', {})
            if shipping_address:
                first_name = shipping_address.get('first_name', '').strip()
                last_name = shipping_address.get('last_name', '').strip()
                if first_name or last_name:
                    customer_name = f"{first_name} {last_name}".strip()

            if not customer_name and data.get('customer'):
                customer = data['customer']
                first_name = customer.get('first_name', '').strip()
                last_name = customer.get('last_name', '').strip()
                if first_name or last_name:
                    customer_name = f"{first_name} {last_name}".strip()

            if customer_name:
                webhook_vals['customer_name'] = customer_name

            # Crear registro de log
            ShopifyWebhookLog = env['shopify.webhook.log'].sudo()
            log = ShopifyWebhookLog.with_user(uid).create(webhook_vals)

            _logger.info(f"Webhook log creado con ID: {log.id}")

            # === PROCESAR AUTOMÁTICAMENTE EL WEBHOOK ===
            try:
                # Llamamos el método que procesa el webhook
                log.action_process_webhook()
                _logger.info(f"Webhook {log.id} procesado exitosamente")
                
                return Response(
                    json.dumps({
                        "status": "success",
                        "log_id": log.id,
                        "message": "Webhook recibido y procesado automáticamente.",
                        "customer_name": customer_name
                    }),
                    content_type='application/json',
                    status=200
                )
            except Exception as process_error:
                error_message = str(process_error)
                _logger.error("Error procesando webhook automáticamente: %s", error_message, exc_info=True)
                
                # Marcamos el log como fallido
                log.write({
                    'state': 'failed',
                    'error_message': error_message
                })
                
                return Response(
                    json.dumps({
                        "status": "error",
                        "log_id": log.id,
                        "message": error_message,
                        "customer_name": customer_name
                    }),
                    content_type='application/json',
                    status=500
                )

        except Exception as e:
            error_message = str(e)
            _logger.error("Error en el webhook: %s", error_message, exc_info=True)
            return Response(
                json.dumps({
                    "status": "error",
                    "message": error_message
                }),
                content_type='application/json',
                status=500
            )

    @http.route('/shopify/webhook/test', type='http', auth='none', methods=['GET'], csrf=False)
    def test_webhook(self, **kwargs):
        """Endpoint para probar la conectividad del webhook"""
        return Response(
            json.dumps({
                "status": "success",
                "message": "Webhook endpoint está funcionando correctamente"
            }),
            content_type='application/json',
            status=200
        )