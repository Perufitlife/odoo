from odoo import models, api
import requests
import logging

_logger = logging.getLogger(__name__)

class UChatMixin(models.AbstractModel):
    _name = 'uchat.mixin'
    _description = 'UChat Integration Mixin'

    def _get_uchat_config(self):
        """Obtiene configuración de UChat"""
        params = self.env['ir.config_parameter'].sudo()
        return {
            'token': params.get_param('uchat.api_token'),
            'base_url': 'https://www.uchat.com.au',
            'headers': {
                "Authorization": f"Bearer {params.get_param('uchat.api_token')}",
                "Content-Type": "application/json"
            }
        }

    def _clean_phone(self, phone):
        """Limpia número de teléfono"""
        return (phone or '').replace('+', '').replace(' ', '')

    def assign_uchat_tag_and_carrier(self, partner, carrier_name, tag_name="Despachado"):
        """Asigna tag y transportadora en UChat"""
        if not partner:
            return False

        phone = self._clean_phone(partner.mobile or partner.phone)
        if not phone:
            _logger.warning(f"Partner {partner.name} sin teléfono")
            return False

        config = self._get_uchat_config()
        if not config['token']:
            _logger.warning("Token UChat no configurado")
            return False

        try:
            # 1. Obtener subscriber
            subscriber = self._get_uchat_subscriber(phone, config)
            if not subscriber:
                return False

            # 2. Asignar tag
            if not self._assign_uchat_tag(subscriber, tag_name, config):
                return False

            # 3. Asignar transportadora
            if not self._set_uchat_carrier(subscriber, carrier_name, config):
                return False

            return True

        except Exception as e:
            _logger.error(f"Error UChat: {str(e)}")
            return False

    def _get_uchat_subscriber(self, phone, config):
        """Obtiene subscriber de UChat"""
        response = requests.get(
            f"{config['base_url']}/api/subscribers",
            params={"user_id": phone},
            headers=config['headers']
        )
        if response.status_code != 200:
            return False
        
        subscribers = response.json().get('data', [])
        return subscribers[0] if subscribers else False

    def _assign_uchat_tag(self, subscriber, tag_name, config):
        """Crea y asigna tag en UChat"""
        # Crear tag
        create_response = requests.post(
            f"{config['base_url']}/api/flow/create-tag",
            json={"name": tag_name},
            headers=config['headers']
        )
        if create_response.status_code != 200:
            return False

        tag_ns = create_response.json().get('data', {}).get('tag_ns')
        if not tag_ns:
            return False

        # Asignar tag
        assign_response = requests.post(
            f"{config['base_url']}/api/subscriber/add-tag",
            json={
                "user_ns": subscriber['user_ns'],
                "tag_ns": tag_ns
            },
            headers=config['headers']
        )
        return assign_response.status_code == 200

    def _set_uchat_carrier(self, subscriber, carrier_name, config):
        """Configura el campo transportadora en UChat"""
        # Crear campo si no existe
        field_response = requests.post(
            f"{config['base_url']}/api/flow/create-user-field",
            json={
                "name": "transportadora",
                "var_type": "text",
                "description": "Transportadora asignada desde Odoo"
            },
            headers=config['headers']
        )

        # Asignar valor
        set_response = requests.put(
            f"{config['base_url']}/api/subscriber/set-user-field-by-name",
            json={
                "user_ns": subscriber['user_ns'],
                "field_name": "transportadora",
                "value": carrier_name or "SinTransportadora"
            },
            headers=config['headers']
        )
        return set_response.status_code == 200