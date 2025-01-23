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

    # Campo para controlar el estado inicial personalizado
    x_initial_status = fields.Selection(
        [
            ('order_completed', 'Orden Completada'),
            ('abandoned_cart', 'Carrito Abandonado'),
            ('whatsapp', 'Whatsapp'),
            ('confirmed', 'Confirmado'),
            ('esperando_adelanto', 'Esperando Adelanto'),
            ('pendiente', 'Pendiente'),
            ('in_transit', 'En Tránsito'),
            ('delivered', 'Entregado'),
            ('cancelled', 'Cancelado'),
            ('despachado', 'Despachado'),
            ('reprogramado', 'Reprogramado'),  # Nuevo estado
            ('no_entregado', 'No Entregado'),            
        ],
        string='Estado Inicial',
        help='Estado inicial personalizado según el origen de la orden.',
        default='whatsapp'  # Agregar default aquí
    )

    @api.model
    def create(self, vals):
        """
        Sobrescribimos create para asignar 'whatsapp' por defecto 
        cuando la orden no venga del webhook.
        """
        if 'x_initial_status' not in vals:
            vals['x_initial_status'] = 'whatsapp'
        return super(SaleOrder, self).create(vals)
