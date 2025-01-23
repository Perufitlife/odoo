# custom_addons/shopify/models/shopify_validation_rule.py
from odoo import models, fields, api
from datetime import timedelta

class ShopifyValidationRule(models.Model):
    _name = 'shopify.validation.rule'
    _description = 'Reglas de Validación Shopify'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)
    condition = fields.Selection([
        ('amount_high', 'Monto Alto'),
        ('new_customer', 'Cliente Nuevo'),
        ('multiple_orders', 'Múltiples Órdenes'),
        ('suspicious_email', 'Email Sospechoso'),
    ], string='Condición', required=True)
    threshold_amount = fields.Float(string='Monto Límite')

    @api.model
    def evaluate_order(self, order):
        """
        Evalúa una orden según las reglas configuradas
        Args:
            order: shopify.order record
        Returns:
            bool: True si la orden necesita revisión
        """
        if not self.active:
            return False
            
        if self.condition == 'amount_high':
            return order.total_price > self.threshold_amount
        elif self.condition == 'new_customer':
            shopify_orders = self.env['shopify.order'].search_count([
                ('partner_id', '=', order.partner_id.id),
                ('state', 'not in', ['cancelled', 'error'])
            ])
            return shopify_orders <= 1
        elif self.condition == 'multiple_orders':
            recent_orders = self.env['shopify.order'].search([
                ('partner_id', '=', order.partner_id.id),
                ('create_date', '>=', fields.Datetime.now() - timedelta(days=1)),
                ('state', 'not in', ['cancelled', 'error'])
            ])
            return len(recent_orders) > 3
        elif self.condition == 'suspicious_email':
            # Implementar lógica de detección de emails sospechosos
            return False
        return False