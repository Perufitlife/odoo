# quick_courier_wizard.py
from odoo import models, fields, api
from odoo.exceptions import UserError

class QuickCourierWizard(models.TransientModel):
    _name = 'quick.courier.wizard'
    _description = 'Configuración Rápida de Courier'
    _description = 'Configuración Rápida de Courier'

    name = fields.Char(
        string='Nombre del Courier',
        required=True
    )
    delivery_type = fields.Selection([
        ('fixed', 'Precio Fijo')
    ], string='Tipo de Entrega', default='fixed', required=True)
    price = fields.Float(
        string='Precio de Envío',
        required=True
    )
    district_id = fields.Many2one(
        'l10n_pe.res.city.district',
        string='Distrito',
        required=True
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta'
    )

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self._context.get('active_model') == 'sale.order':
            sale_order = self.env['sale.order'].browse(self._context.get('active_id'))
            if sale_order.partner_id.l10n_pe_district:
                res['district_id'] = sale_order.partner_id.l10n_pe_district.id
            res['sale_order_id'] = sale_order.id
        return res

    def action_confirm(self):
        self.ensure_one()
        
        # Crear el courier
        carrier = self.env['delivery.carrier'].create({
            'name': self.name,
            'delivery_type': self.delivery_type,
            'product_id': self._create_delivery_product().id,
            'fixed_price': self.price
        })

        # Crear la regla de precios
        self.env['courier.pricing.rule'].create({
            'carrier_id': carrier.id,
            'state_id': self.district_id.city_id.state_id.id,
            'city_id': self.district_id.city_id.id,
            'district_id': self.district_id.id,
            'price': self.price
        })

        # Actualizar la orden de venta
        if self.sale_order_id:
            self.sale_order_id.write({
                'carrier_id': carrier.id
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Éxito',
                'message': 'Courier creado correctamente',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }

    def _create_delivery_product(self):
        """Crea o recupera el producto de envío"""
        Product = self.env['product.product']
        delivery_product = Product.search([('default_code', '=', 'SHIP')], limit=1)
        
        if not delivery_product:
            delivery_product = Product.create({
                'name': 'Cargo por Envío',
                'type': 'service',
                'default_code': 'SHIP',
                'sale_ok': True,
                'purchase_ok': False,
                'invoice_policy': 'order'
            })
        
        return delivery_product