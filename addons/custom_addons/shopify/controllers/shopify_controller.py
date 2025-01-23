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
    @http.route('/shopify/webhook/orders/create', 
                type='http',           
                auth='none', 
                methods=['POST'],
                csrf=False)
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

            # Preparar datos del webhook con usuario y tienda
            data['store_id'] = store_id
            webhook_vals = {
                'name': f'Webhook {shopify_topic}',
                'payload': json.dumps(data),
                'event_type': shopify_topic,
                'state': 'pending',  # Se mantiene en pendiente para procesamiento manual
                'shopify_order_id': str(data.get('id', '')),  # Guardar ID de la orden
            }

            # Solo crear el webhook log, sin procesarlo
            ShopifyWebhookLog = env['shopify.webhook.log'].sudo()
            log = ShopifyWebhookLog.with_user(uid).create(webhook_vals)

            return Response(
                json.dumps({
                    "status": "success",
                    "log_id": log.id,
                    "message": "Webhook recibido y pendiente de procesamiento"
                }),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            error_message = str(e)
            _logger.error("Error procesando webhook: %s", error_message)
            return Response(
                json.dumps({
                    "status": "error",
                    "message": error_message
                }),
                content_type='application/json',
                status=500
            )