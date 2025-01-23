from odoo import api, fields, models
import json

class ResCity(models.Model):
    _inherit = 'res.city'

    def name_get(self):
        result = []
        for city in self:
            try:
                # Si city.name es un JSON tipo {"en_US": "..."} lo parseamos
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
        """
        name: texto que el usuario escribe para filtrar (ej: city name)
        args: posible dominio adicional
        operator: tipo de comparación (ilike, =, etc.)
        limit: # de resultados
        name_get_uid: para controlar permisos si se usa
        """
        args = args or []  # Asegurarnos de no tener None
        domain = []

        # 1) Si el usuario escribió algo en 'name', construimos un filtro:
        if name:
            domain = [
                '|',
                ('name', operator, name),
                ('name', 'ilike', f'{{"en_US": "{name}"}}')
            ]

        # 2) Chequeamos si hay un 'state_id' en el contexto
        state_id = self._context.get('state_id')
        if state_id:
            # Si el domain ya tenía contenido, unimos con '&'
            # (por ejemplo, state_id + búsquedas por nombre).
            if domain:
                # Equivalente a: AND([('state_id', '=', state_id)], domain)
                domain = ['&', ('state_id', '=', state_id)] + domain
            else:
                # Si domain estaba vacío, simplemente lo definimos
                domain = [('state_id', '=', state_id)]

        # 3) Unimos (si existen) 'domain' y 'args'
        #    Sólo metemos '&' si ambos tienen contenido.
        if domain and args:
            domain = ['&'] + domain + args
        elif args:  
            # si domain está vacío, nos quedamos con args
            domain = args
        # si domain no está vacío pero args sí, no tocamos domain

        print("Domain:", domain)  # Log para debugging

        return self._search(domain, limit=limit, access_rights_uid=name_get_uid)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []

        if name:
            domain = [
                '|',
                ('name', operator, name),
                ('name', 'ilike', f'{{"en_US": "{name}"}}')
            ]

        state_id = self._context.get('state_id')
        if state_id:
            state_domain = [('state_id', '=', state_id)]
            if domain:
                domain = ['&'] + state_domain + domain
            else:
                domain = state_domain

        if domain and args:
            domain = domain + args

        return self._search(domain, limit=limit, access_rights_uid=name_get_uid)

