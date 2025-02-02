from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PickupPoint(models.Model):
    _name = 'pickup.point'
    _description = 'Punto de Recojo'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre de Agencia',
        required=True,
        tracking=True
    )

    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier',
        required=True,
        tracking=True,
        domain=[('has_pickup_points', '=', True)],
        ondelete='cascade'
    )

    # Campos de ubicación
    state_id = fields.Many2one(
        'res.country.state',
        string='Departamento',
        required=True,
        tracking=True,
        domain=[('country_id.code', '=', 'PE')]
    )

    city_id = fields.Many2one(
        'res.city',
        string='Provincia',
        required=True,
        tracking=True,
        domain="[('state_id', '=', state_id)]"
    )

    district_id = fields.Many2one(
        'l10n_pe.res.city.district',
        string='Distrito',
        required=True,
        tracking=True,
        domain="[('city_id', '=', city_id)]"
    )

    address = fields.Text(
        string='Dirección Detallada',
        required=True,
        tracking=True
    )

    delivery_fee = fields.Float(
        string='Costo de Envío',
        required=True,
        tracking=True,
        digits='Product Price'
    )

    active = fields.Boolean(
        default=True,
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    _sql_constraints = [
        ('unique_carrier_location',
         'UNIQUE(carrier_id, state_id, city_id, district_id, company_id)',
         'Ya existe un punto de recojo para esta ubicación y carrier!')
    ]

    @api.onchange('state_id')
    def _onchange_state_id(self):
        self.city_id = False
        self.district_id = False
        if self.state_id:
            return {'domain': {'city_id': [('state_id', '=', self.state_id.id)]}}
        return {'domain': {'city_id': []}}

    @api.onchange('city_id')
    def _onchange_city_id(self):
        self.district_id = False
        if self.city_id:
            return {'domain': {'district_id': [('city_id', '=', self.city_id.id)]}}
        return {'domain': {'district_id': []}}

    @api.constrains('delivery_fee')
    def _check_delivery_fee(self):
        for record in self:
            if record.delivery_fee < 0:
                raise ValidationError('El costo de envío no puede ser negativo.')

    def name_get(self):
        result = []
        for point in self:
            name = f"{point.name} ({point.district_id.name})"
            result.append((point.id, name))
        return result