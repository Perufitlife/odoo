from odoo import models, fields, api
from odoo.exceptions import UserError

class QuickCourierWizard(models.TransientModel):
    _name = 'quick.courier.wizard'
    _description = 'Configuración Rápida de Courier'

    # Campos para selección de courier existente
    carrier_selection = fields.Selection([
        ('existing', 'Usar Courier Existente'),
        ('new', 'Crear Nuevo Courier')
    ], string='Opción', required=True, default='existing')

    existing_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier Existente'
    )

    # Campos para nuevo courier
    name = fields.Char(string='Nombre del Courier')
    delivery_type = fields.Selection([
        ('fixed', 'Precio Fijo')
    ], string='Tipo de Entrega', default='fixed')
    
    # Campos de ubicación
    country_id = fields.Many2one(
        'res.country',
        string='País',
        default=lambda self: self.env.ref('base.pe')
    )
    state_id = fields.Many2one(
        'res.country.state',
        string='Departamento',
        domain="[('country_id', '=', country_id)]"
    )
    city_id = fields.Many2one(
        'res.city',
        string='Provincia',
        domain="[('state_id', '=', state_id)]"
    )
    district_id = fields.Many2one(
        'l10n_pe.res.city.district',
        string='Distrito',
        domain="[('city_id', '=', city_id)]"
    )
    price = fields.Float(string='Precio de Envío')
    sale_order_id = fields.Many2one('sale.order', string='Orden de Venta')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self._context.get('active_model') == 'sale.order':
            sale_order = self.env['sale.order'].browse(self._context.get('active_id'))
            if sale_order.partner_id.l10n_pe_district:
                district = sale_order.partner_id.l10n_pe_district
                res.update({
                    'district_id': district.id,
                    'city_id': district.city_id.id,
                    'state_id': district.city_id.state_id.id,
                    'sale_order_id': sale_order.id
                })
                
                # Buscar carriers existentes para este distrito
                pricing_rules = self.env['courier.pricing.rule'].search([
                    ('district_id', '=', district.id)
                ])
                if pricing_rules:
                    res['carrier_selection'] = 'existing'
                    res['existing_carrier_id'] = pricing_rules[0].carrier_id.id
                else:
                    res['carrier_selection'] = 'new'
                    
        return res

    @api.onchange('carrier_selection')
    def _onchange_carrier_selection(self):
        if self.carrier_selection == 'existing':
            # Limpiar campos de nuevo courier
            self.name = False
            self.price = 0.0
        else:
            # Limpiar carrier existente
            self.existing_carrier_id = False

    @api.onchange('existing_carrier_id')
    def _onchange_existing_carrier(self):
        if self.existing_carrier_id and self.district_id:
            pricing_rule = self.env['courier.pricing.rule'].search([
                ('carrier_id', '=', self.existing_carrier_id.id),
                ('district_id', '=', self.district_id.id)
            ], limit=1)
            if pricing_rule:
                self.price = pricing_rule.price

    def action_confirm(self):
        self.ensure_one()
        
        if self.carrier_selection == 'existing':
            if not self.existing_carrier_id:
                raise UserError('Debe seleccionar un courier existente')
                
            carrier = self.existing_carrier_id
            
            # Verificar si ya existe una regla de precios
            pricing_rule = self.env['courier.pricing.rule'].search([
                ('carrier_id', '=', carrier.id),
                ('district_id', '=', self.district_id.id)
            ], limit=1)
            
            if not pricing_rule:
                # Crear nueva regla de precios para el carrier existente
                self.env['courier.pricing.rule'].create({
                    'carrier_id': carrier.id,
                    'state_id': self.state_id.id,
                    'city_id': self.city_id.id,
                    'district_id': self.district_id.id,
                    'price': self.price
                })
        else:
            if not self.name or not self.price:
                raise UserError('Debe completar todos los campos para crear un nuevo courier')
                
            # Crear nuevo courier
            carrier = self.env['delivery.carrier'].create({
                'name': self.name,
                'delivery_type': self.delivery_type,
                'product_id': self._create_delivery_product().id,
                'fixed_price': self.price
            })

            # Crear regla de precios
            self.env['courier.pricing.rule'].create({
                'carrier_id': carrier.id,
                'state_id': self.state_id.id,
                'city_id': self.city_id.id,
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
                'message': 'Courier asignado correctamente',
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