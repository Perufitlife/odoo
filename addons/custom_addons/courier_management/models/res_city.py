from odoo import api, fields, models
import json

class ResCity(models.Model):
    _inherit = 'res.city'

    def name_get(self):
        result = []
        for city in self:
            try:
                if city.name and isinstance(city.name, str) and city.name.startswith('{'):
                    name_dict = json.loads(city.name)
                    name = name_dict.get('en_US', '')
                else:
                    name = city.name
            except:
                name = city.name
            result.append((city.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []

        if name:
            json_search = json.dumps({"en_US": name})
            domain = [
                '|',
                ('name', operator, name),
                ('name', 'ilike', json_search)
            ]

        state_id = self._context.get('state_id')
        if state_id:
            if domain:
                domain = ['&', ('state_id', '=', state_id)] + domain
            else:
                domain = [('state_id', '=', state_id)]

        final_domain = domain + args if args else domain
        return self._search(final_domain, limit=limit, access_rights_uid=name_get_uid)
        
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if self._context.get('state_id'):
            domain = domain or []
            domain.append(('state_id', '=', self._context.get('state_id')))
        return super(ResCity, self).search_read(domain=domain, fields=fields,
                                              offset=offset, limit=limit, order=order)