# -*- coding: utf-8 -*-
import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    uchat_api_token = fields.Char(
        string="UChat API Token",
        help="Introduce aquí tu token de UChat (Scope: Manage Flow)."
    )
    uchat_environment = fields.Selection([
        ('sandbox', 'Sandbox/Pruebas'),
        ('production', 'Producción')
    ], string='Entorno', default='sandbox',
        help="Selecciona el entorno de UChat a utilizar"
    )
    uchat_auto_sync = fields.Boolean(
        string="Sincronización Automática",
        help="Activar para sincronizar automáticamente los estados entre Odoo y UChat"
    )
    uchat_default_language = fields.Selection([
        ('es_PE', 'Español (Perú)'),
        ('en_US', 'Inglés (USA)')
    ], string='Idioma Predeterminado', default='es_PE')

    @api.model
    def get_values(self):
        """Lee valores desde ir.config_parameter."""
        res = super().get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        res.update({
            'uchat_api_token': ICPSudo.get_param('uchat.api_token', default=''),
            'uchat_environment': ICPSudo.get_param('uchat.environment', default='sandbox'),
            'uchat_auto_sync': ICPSudo.get_param('uchat.auto_sync', default=False),
            'uchat_default_language': ICPSudo.get_param('uchat.default_language', default='es_PE'),
        })
        return res

    def set_values(self):
        """Guarda valores en ir.config_parameter."""
        super().set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        ICPSudo.set_param('uchat.api_token', self.uchat_api_token or '')
        ICPSudo.set_param('uchat.environment', self.uchat_environment)
        ICPSudo.set_param('uchat.auto_sync', self.uchat_auto_sync)
        ICPSudo.set_param('uchat.default_language', self.uchat_default_language)
        # Si NO quieres manejar webhooks, no hacemos nada extra aquí.

    def action_test_connection(self):
        """
        Botón para probar la conexión con UChat:
        Hace GET /account según el entorno (sandbox / producción).
        """
        self.ensure_one()
        if not self.uchat_api_token:
            raise ValidationError(_("Primero configure el token de API"))

        try:
            headers = {
                'Authorization': f'Bearer {self.uchat_api_token}',
                'Content-Type': 'application/json'
            }
            base_url = 'https://www.uchat.com.au/api'
            if self.uchat_environment == 'sandbox':
                base_url = 'https://sandbox.uchat.com.au/api'

            response = requests.get(f'{base_url}/account', headers=headers)
            if response.status_code != 200:
                raise ValidationError(
                    _("Error de conexión con UChat: %s") % response.text
                )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': _('Conexión con UChat establecida correctamente'),
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error("Error al conectar con UChat: %s", str(e))
            raise ValidationError(
                _("Error al conectar con UChat: %s") % str(e)
            )

    @api.model
    def uchat_get_token(self):
        """Devuelve el token de UChat desde ir.config_parameter."""
        return self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')

    @api.model
    def uchat_get_base_url(self):
        """Devuelve la URL base según el entorno."""
        env = self.env['ir.config_parameter'].sudo().get_param('uchat.environment', 'sandbox')
        return (
            'https://sandbox.uchat.com.au/api'
            if env == 'sandbox'
            else 'https://www.uchat.com.au/api'
        )
