# custom_addons/shopify/models/sale_order_inherit.py

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Campo que relaciona la orden de venta con la tienda de Shopify
    shopify_store_id = fields.Many2one(
        'shopify.store',
        string='Shopify Store',
        help='La tienda de Shopify de la cual proviene este pedido.'
    )

    # Campo de estado inicial para tu flujo personalizado
    x_initial_status = fields.Selection([
        ('draft', 'Borrador'),
        ('whatsapp', 'Whatsapp'),
        ('abandoned_cart', 'Carrito Abandonado'),
        ('order_completed', 'Orden Completa'),
        ('scheduled', 'Programado'),  # Se mantiene aquí por si necesitas en otro punto
        ('pending', 'Pendiente'),  # Se mantiene aquí por si necesitas en otro punto
        ('confirmed', 'Confirmado'),
        ('esperando_adelanto', 'Esperando Adelanto'),
        ('despachado', 'Despachado'),
        ('in_transit', 'En Tránsito'),
        ('delivered', 'Entregado'),
        ('failed', 'No Entregado'),
        ('cancelled', 'Cancelado'),
        ('reprogramado', 'Reprogramado'),
    ], string='Estado Inicial', default='whatsapp', tracking=True)

    @api.model
    def create(self, vals):
        """
        Sobrescribimos create para asignar 'whatsapp' por defecto 
        cuando la orden no venga del webhook.
        """
        if 'x_initial_status' not in vals:
            vals['x_initial_status'] = 'whatsapp'
        return super(SaleOrder, self).create(vals)
