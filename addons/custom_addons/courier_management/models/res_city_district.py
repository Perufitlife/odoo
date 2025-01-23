from odoo import models, fields, api

class ResCityDistrict(models.Model):
    _name = 'l10n_pe.res.city.district'
    _description = 'Distrito'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    city_id = fields.Many2one('res.city', string='Ciudad', required=True)
    state_id = fields.Many2one(
        'res.country.state', 
        related='city_id.state_id', 
        store=True, 
        string='Estado'
    )

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        
        if name:
            domain = [('name', operator, name)]
            
        if self._context.get('city_id'):
            domain += [('city_id', '=', self._context.get('city_id'))]
            
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)