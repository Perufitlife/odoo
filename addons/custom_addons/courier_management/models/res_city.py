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

        # Construir el dominio base
        if name:
            domain = ['|',
                     ('name', operator, name),
                     ('name', 'ilike', f'{{"en_US": "{name}"}}')]

        # Obtener state_id del contexto o de los args
        state_id = self._context.get('state_id')
        if state_id:
            domain = [('state_id', '=', state_id)] + domain

        # Combinar con args existentes
        if args:
            domain = ['&'] + domain + args

        print("Domain:", domain)  # Para debugging
        
        return self._search(domain, limit=limit, access_rights_uid=name_get_uid)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        # Añadir filtro de state_id si está en el contexto
        if self._context.get('state_id'):
            domain = domain or []
            domain.append(('state_id', '=', self._context.get('state_id')))
        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)