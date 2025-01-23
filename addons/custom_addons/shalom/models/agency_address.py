from odoo import models, fields, api

class AgencyAddress(models.Model):
    _name = 'agency.address'
    _description = 'Direcciones de Agencias de Envío'

    name = fields.Char("Agencia", required=True)
    agency_type = fields.Selection([
        ('shalom', 'Shalom'),
        ('olva', 'Olva')
    ], string='Tipo de Agencia', required=True)
    state_id = fields.Many2one(
        'res.country.state',
        string='Departamento',
        domain=[('country_id.code', '=', 'PE')]
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
    address = fields.Text("Dirección")

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