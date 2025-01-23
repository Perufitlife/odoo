from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CourierPricingRule(models.Model):
    _name = 'courier.pricing.rule'
    _description = 'Courier Pricing Rule'
    _order = 'carrier_id, state_id, city_id, district_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # -------------------------------------------------------------------------
    # CAMPOS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Carrier',
        required=True,
        tracking=True,
        ondelete='cascade'
    )
    state_id = fields.Many2one(
        'res.country.state',
        string='Departamento',
        required=True,
        tracking=True,
        domain="[('country_id.code', '=', 'PE')]"
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
    price = fields.Float(
        string='Precio',
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
    notes = fields.Text(
        string='Notas',
        tracking=True
    )

    _sql_constraints = [
        (
            'unique_carrier_location',
            'UNIQUE(carrier_id, state_id, city_id, district_id, company_id)',
            'Ya existe una regla de precio para esta ubicación y carrier!'
        )
    ]

    # -------------------------------------------------------------------------
    # CÁLCULO DE CAMPO name
    # -------------------------------------------------------------------------
    @api.depends('carrier_id', 'state_id', 'city_id', 'district_id')
    def _compute_name(self):
        """Genera el nombre de la regla en base a la ubicación y el carrier."""
        for rule in self:
            if rule.carrier_id and rule.state_id and rule.city_id and rule.district_id:
                rule.name = (
                    f"{rule.carrier_id.name} - "
                    f"{rule.state_id.name} - "
                    f"{rule.city_id.name} - "
                    f"{rule.district_id.name}"
                )
            else:
                rule.name = "Nueva Regla"

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('state_id')
    def _onchange_state_id(self):
        """Al cambiar el departamento, limpiar la ciudad y el distrito."""
        self.city_id = False
        self.district_id = False
        if self.state_id:
            return {
                'domain': {
                    'city_id': [('state_id', '=', self.state_id.id)]
                }
            }
        return {
            'domain': {
                'city_id': []
            }
        }

    @api.onchange('city_id')
    def _onchange_city_id(self):
        """Al cambiar la ciudad, limpiar el distrito."""
        self.district_id = False
        if self.city_id:
            return {
                'domain': {
                    'district_id': [('city_id', '=', self.city_id.id)]
                }
            }
        return {
            'domain': {
                'district_id': []
            }
        }

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------
    @api.constrains('price')
    def _check_price(self):
        """Valida que el precio sea mayor que cero."""
        for rule in self:
            if rule.price <= 0:
                raise ValidationError('El precio debe ser mayor que 0')

    # -------------------------------------------------------------------------
    # MÉTODOS DE NOMBRE Y DUPLICACIÓN
    # -------------------------------------------------------------------------
    def name_get(self):
        """Personaliza el nombre que se muestra en menús/desplegables."""
        result = []
        for rule in self:
            if rule.carrier_id and rule.district_id:
                name = f"{rule.carrier_id.name} - {rule.district_id.name}"
            else:
                name = "Nueva Regla"
            result.append((rule.id, name))
        return result

    def copy(self, default=None):
        """Personaliza la duplicación de registros, agregando notas."""
        self.ensure_one()
        default = dict(default or {})
        if not default.get('notes'):
            default['notes'] = f"Copia de {self.name}"
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTIVACIÓN/DESACTIVACIÓN (toggle_active)
    # -------------------------------------------------------------------------
    def toggle_active(self):
        """Al activar, verifica que no exista otra regla activa idéntica."""
        for record in self:
            if record.active:
                # Verificar si ya existe una regla activa para la misma ubicación
                domain = [
                    ('carrier_id', '=', record.carrier_id.id),
                    ('state_id', '=', record.state_id.id),
                    ('city_id', '=', record.city_id.id),
                    ('district_id', '=', record.district_id.id),
                    ('company_id', '=', record.company_id.id),
                    ('active', '=', True),
                    ('id', '!=', record.id)
                ]
                if self.search_count(domain):
                    raise ValidationError(
                        'Ya existe una regla activa para esta ubicación y carrier. '
                        'Desactive la regla existente antes de activar esta.'
                    )
        return super(CourierPricingRule, self).toggle_active()
