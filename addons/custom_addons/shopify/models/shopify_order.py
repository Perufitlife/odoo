# custom_addons/shopify/models/shopify_order.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ShopifyOrder(models.Model):
    _name = 'shopify.order'
    _description = 'Shopify Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, tracking=True)
    shopify_order_id = fields.Char(string='Shopify Order ID', required=True)
    email = fields.Char(string='Customer Email')
    total_price = fields.Float(string='Total Price')
    currency = fields.Char(string='Currency', default='USD')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente Revisión'),
        ('validated', 'Validado'),
        ('processed', 'Procesado'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
        ('error', 'Error'),
        ('failed', 'Fallido')  # Agregado
    ], string='Status', default='draft', tracking=True)
    date_order = fields.Datetime(string='Order Date', tracking=True)
    date_created = fields.Datetime(string='Created On', default=fields.Datetime.now)
    processed_by = fields.Many2one('res.users', string='Procesado por', default=lambda self: self.env.user)
    notes = fields.Text(string='Notas de procesamiento')
    needs_review = fields.Boolean(string='Necesita Revisión', default=False)
    review_reason = fields.Text(string='Motivo de Revisión')
    store_id = fields.Many2one(
    'shopify.store',
    string='Shopify Store',
    required=True,
    ondelete='cascade',
    tracking=True
)


    # Campos relacionales
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer')

    _sql_constraints = [
        ('unique_shopify_order', 'unique(shopify_order_id, store_id)', 
        'Ya existe una orden con este ID de Shopify para esta tienda!')
    ]


    def action_validate(self):
        self.ensure_one()
        if not self.env.user.has_group('shopify.group_shopify_validator'):
            raise UserError(_('No tienes permisos para validar órdenes.'))
        self.write({
            'state': 'validated',
            'processed_by': self.env.user.id  # Usar el usuario actual en lugar de ID hardcodeado
        })

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'validated':
            raise UserError(_('La orden debe estar validada antes de confirmar.'))
        # Confirmar orden de venta asociada
        if self.sale_order_id:
            self.sale_order_id.action_confirm()
        self.write({'state': 'confirmed'})