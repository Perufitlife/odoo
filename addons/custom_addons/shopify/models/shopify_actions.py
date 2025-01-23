# custom_addons/shopify/models/shopify_actions.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class ShopifyWebhookLogActions(models.Model):
    _inherit = 'shopify.webhook.log'

    def _validate_shopify_data(self, data):
        """
        Valida que los datos básicos del webhook estén presentes
        """
        if not data:
            raise ValidationError(_("No se recibieron datos del webhook"))
        
        required_fields = ['id', 'total_price', 'customer']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            raise ValidationError(_(
                "Faltan campos requeridos en el webhook: %s"
            ) % ', '.join(missing_fields))

    def _notify_validation_team(self, sale_order, message):
        """
        Notifica al equipo de validación sobre una orden que necesita revisión
        """
        validation_team = self.env.ref('shopify.group_shopify_validator', raise_if_not_found=False)
        if validation_team and validation_team.users:
            sale_order.message_subscribe(partner_ids=validation_team.users.partner_id.ids)
            sale_order.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def _handle_shopify_order(self, data, store):
        """
        Maneja la creación/actualización de la orden en shopify.order
        """
        ShopifyOrder = self.env['shopify.order'].sudo()
        
        # Obtener ID del usuario admin o usuario actual de manera segura
        admin_user_id = False
        try:
            admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
            if admin_user and admin_user.exists():
                admin_user_id = admin_user.id
        except Exception:
            _logger.warning("No se pudo obtener el usuario admin, usando usuario actual")
        
        if not admin_user_id:
            admin_user_id = self.env.user.id
                
        # Verificar si ya existe una orden con ese ID y tienda
        shopify_order = ShopifyOrder.search([
            ('shopify_order_id', '=', str(data['id'])),
            ('store_id', '=', store.id)
        ], limit=1)

        if shopify_order and shopify_order.state == 'processed':
            raise ValidationError(_(
                "La orden de Shopify %s ya fue procesada anteriormente para esta tienda."
            ) % data['id'])

        order_vals = {
            'shopify_order_id': str(data['id']),
            'store_id': store.id,
            'email': data.get('customer', {}).get('email'),
            'total_price': float(data.get('total_price', 0)),
            'currency': data.get('currency', 'PEN'),
            'date_order': fields.Datetime.now(),
            'state': 'draft',
            'needs_review': False,
            'review_reason': False,
            'processed_by': admin_user_id
        }

        try:
            if shopify_order:
                shopify_order.sudo().write(order_vals)
                _logger.info(f"Orden Shopify actualizada: {shopify_order.name}")
            else:
                order_vals['name'] = f"SHOP-{data['id']}"
                shopify_order = ShopifyOrder.sudo().create(order_vals)
                _logger.info(f"Orden Shopify creada: {shopify_order.name}")
            
            return shopify_order

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Error al procesar orden Shopify: {error_msg}")
            if shopify_order:
                try:
                    shopify_order.sudo().write({
                        'state': 'error',
                        'needs_review': True,
                        'review_reason': error_msg
                    })
                except Exception as write_error:
                    _logger.error(f"Error adicional al marcar orden como fallida: {str(write_error)}")
            raise ValidationError(_("Error al procesar orden Shopify: %s") % error_msg)


    def action_process_webhook(self):
        """
        Procesa un webhook recibido de Shopify
        """
        self.ensure_one()
        try:
            # Obtener usuario admin de manera segura
            admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
            if not admin_user:
                admin_user = self.env['res.users'].sudo().search([('id', '=', 2)], limit=1)
            if not admin_user:
                admin_user = self.env.user
                
            _logger.info("=== Iniciando procesamiento de webhook con ID: %s ===", self.id)
            
            # Parsear y validar datos
            try:
                data = json.loads(self.payload)
                self._validate_shopify_data(data)
            except json.JSONDecodeError:
                raise ValidationError(_("El payload no es un JSON válido"))
            
            # Obtener el ID de la tienda desde el payload o contexto
            store_id = data.get('store_id') or self.env.context.get('store_id')
            if not store_id:
                raise ValidationError(_("No se proporcionó el ID de la tienda en el webhook"))
            
            # Buscar la tienda correspondiente
            store = self.env['shopify.store'].sudo().browse(store_id)
            if not store.exists():
                raise ValidationError(_("La tienda asociada al ID %s no existe.") % store_id)

            # Manejar la orden con el usuario correcto
            with self.env.cr.savepoint():
                shopify_order = self._handle_shopify_order(data, store)
                
                # Crear la orden de venta
                sale_order = self.process_order(data, store)
                if sale_order:
                    # Vincular la orden de venta con la orden de Shopify
                    shopify_order.write({
                        'sale_order_id': sale_order.id,
                        'state': 'processed'
                    })
                    # Vincular la orden de venta en el registro del webhook
                    self.write({
                        'sale_order_id': sale_order.id,
                        'state': 'processed',
                        'error_message': False
                    })
                else:
                    raise ValidationError(_("No se pudo crear la orden de venta"))

            # Notificar éxito
            self._notify_success(shopify_order)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': _('Orden procesada correctamente'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_message = str(e)
            _logger.error("Error procesando webhook: %s", error_message)
            
            self.write({
                'state': 'failed',
                'error_message': error_message
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': error_message,
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
    def _handle_payment(self, sale_order, data):
        """
        Maneja el registro del pago de la orden si viene pagada desde Shopify
        """
        if not sale_order or sale_order.invoice_status == 'invoiced':
            return

        try:
            # Confirmar orden primero
            if sale_order.state == 'draft':
                sale_order.action_confirm()

            # Crear factura
            invoice = self._create_invoice(sale_order)
            if not invoice:
                raise ValidationError(_("No se pudo crear la factura"))

            # Registrar pago
            payment_method = self._get_payment_method(data)
            if payment_method:
                self._register_payment(invoice, payment_method, data)

        except Exception as e:
            _logger.error("Error procesando pago: %s", str(e))
            message = _(
                "⚠️ Error al procesar el pago de la orden:\n%s"
            ) % str(e)
            self._notify_validation_team(sale_order, message)

    def _create_invoice(self, sale_order):
        """
        Crea la factura para la orden de venta
        """
        invoice = sale_order._create_invoices()
        if invoice:
            invoice = invoice[0]  # Tomar la primera factura creada
            invoice.action_post()  # Validar factura
            _logger.info(f"Factura creada y validada: {invoice.name}")
            return invoice
        return False

    def _get_payment_method(self, data):
        """
        Obtiene el método de pago basado en los datos de Shopify
        """
        payment_gateway = data.get('payment_gateway_names', [])
        if not payment_gateway:
            return False

        # Mapeo de métodos de pago de Shopify a Odoo
        payment_mapping = {
            'cash': 'efectivo',
            'cash_on_delivery': 'contraentrega',
            'credit_card': 'tarjeta',
            'bank_transfer': 'transferencia',
        }

        payment_method = self.env['account.payment.method'].sudo().search([
            ('name', 'ilike', payment_mapping.get(payment_gateway[0].lower(), ''))
        ], limit=1)

        return payment_method

    def _register_payment(self, invoice, payment_method, data):
        """
        Registra el pago de la factura
        """
        payment_date = fields.Date.today()
        if data.get('processed_at'):
            try:
                payment_date = datetime.strptime(
                    data['processed_at'], '%Y-%m-%dT%H:%M:%S%z'
                ).date()
            except:
                pass

        # Crear el registro de pago
        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids
        ).create({
            'payment_date': payment_date,
            'journal_id': payment_method.journal_id.id if payment_method else False,
            'payment_method_id': payment_method.id if payment_method else False,
            'amount': invoice.amount_total,
        })

        payment = payment_register._create_payments()
        _logger.info(f"Pago registrado: {payment.name}")
        return payment

    def _notify_success(self, shopify_order):
        """
        Envía notificación de éxito al equipo de ventas
        """
        message = _("""
            ✅ Orden de Shopify procesada exitosamente
            - Número de orden: %s
            - Total: %s %s
        """) % (
            shopify_order.name,
            shopify_order.total_price,
            shopify_order.currency
        )

        if shopify_order.sale_order_id:
            message = _("""
                ✅ Orden de Shopify procesada exitosamente
                - Número de orden Shopify: %s
                - Número de orden Odoo: %s
                - Total: %s %s
            """) % (
                shopify_order.name,
                shopify_order.sale_order_id.name,
                shopify_order.total_price,
                shopify_order.currency
            )

        # Si hay una orden de venta asociada, postear el mensaje ahí
        if shopify_order.sale_order_id:
            shopify_order.sale_order_id.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        else:
            # Si no hay orden de venta, postear en la orden de Shopify
            shopify_order.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_retry_process(self):
        """
        Permite reintentar el procesamiento de webhooks fallidos
        """
        self.ensure_one()
        if self.state != 'failed':
            raise UserError(_('Solo se pueden reprocesar webhooks en estado fallido'))
        
        # Limpiar mensaje de error
        self.write({
            'state': 'pending',
            'error_message': False
        })
        
        # Reprocesar
        return self.action_process_webhook()

    def action_view_sale_order(self):
        """
        Acción para ver la orden de venta relacionada
        """
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No hay orden de venta asociada'))
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }        