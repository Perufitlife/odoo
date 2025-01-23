from odoo import models, fields, api, _
from datetime import timedelta
import requests
import logging

_logger = logging.getLogger(__name__)

class ChooseAddressWizard(models.TransientModel):
    _name = 'choose.address.wizard'
    _description = 'Wizard para elegir dirección de agencia'

    sale_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        readonly=True
    )
    
    agency_type = fields.Selection([
        ('shalom', 'Shalom'),
        ('olva', 'Olva')
    ], string='Tipo de Agencia', readonly=True)
    
    agency_address_id = fields.Many2one(
        'agency.address',
        string="Dirección de Agencia",
        domain="[('agency_type', '=', agency_type)]",
        help="Selecciona la dirección de la agencia sugerida o elige otra."
    )

    @api.model
    def default_get(self, fields_list):
        """Sugerir la dirección en base al distrito del partner."""
        res = super().default_get(fields_list)
        sale_id = self.env.context.get('active_id')
        agency_type = self.env.context.get('default_agency_type')
        
        if sale_id and agency_type:
            sale = self.env['sale.order'].browse(sale_id)
            res.update({
                'sale_id': sale_id,
                'agency_type': agency_type
            })

            # Tomar distrito del partner
            district_id = sale.partner_id.l10n_pe_district.id
            if district_id:
                # Buscar direcciones que coincidan con ese distrito
                addresses = self.env['agency.address'].search([
                    ('district_id', '=', district_id),
                    ('agency_type', '=', agency_type)
                ])
                if addresses:
                    res['agency_address_id'] = addresses[0].id
        return res

    def action_confirm(self):
        """Asigna el carrier, actualiza dirección y confirma la orden."""
        self.ensure_one()
        if not self.sale_id:
            return

        sale = self.sale_id

        # 1) Establecer fecha de compromiso si no existe
        if not sale.commitment_date:
            sale.commitment_date = fields.Datetime.now() + timedelta(days=1)

        # 2) Asignar el transportista
        carrier_name = 'Shalom' if self.agency_type == 'shalom' else 'Olva'
        carrier = self.env['delivery.carrier'].search([('name', '=', carrier_name)], limit=1)
        if carrier:
            sale.carrier_id = carrier.id

        # 3) Actualizar la dirección del partner con la dirección de la agencia
        sale.partner_shipping_id.write({
            'street': self.agency_address_id.name,  # Agencia en street (address 1)
            'street2': self.agency_address_id.address,  # Dirección en street2 (address 2)
            'state_id': self.agency_address_id.state_id.id,  # Departamento
            'city_id': self.agency_address_id.city_id.id,  # Provincia
            'l10n_pe_district': self.agency_address_id.district_id.id,  # Distrito
        })

        # 4) Confirmar la orden
        sale.action_confirm()

        # 5) Actualizar estado inicial
        if hasattr(sale, 'x_initial_status'):
            sale.x_initial_status = 'confirmed'

        # 6) Forzar desbloqueo
        if hasattr(sale, 'action_unlock'):
            sale.action_unlock()

        # 7) Agregar tag en UChat (solo para Shalom)
        if self.agency_type == 'shalom':
            self._update_uchat_tag(sale)

        # 8) Mostrar notificación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Agencia asignada"),
                'message': _(f"Se ha configurado la dirección de {carrier_name} y confirmado la orden."),
                'type': 'success',
            }
        }

    def _update_uchat_tag(self, sale):
        """Actualiza el tag en UChat."""
        phone_raw = sale.partner_id.mobile or sale.partner_id.phone
        if not phone_raw:
            return

        phone_clean = phone_raw.replace('+', '').replace(' ', '')
        uchat_token = self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')
        if not uchat_token:
            return

        tag_name = 'ShalomDelivery' if self.agency_type == 'shalom' else 'OlvaDelivery'
        
        headers = {
            "Authorization": f"Bearer {uchat_token}",
            "Content-Type": "application/json",
        }

        try:
            # 1) Buscar subscriber
            url = "https://www.uchat.com.au/api/subscribers"
            params = {"user_id": phone_clean}
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data_json = response.json()
                subscribers = data_json.get('data', [])
                
                if subscribers:
                    user_ns = subscribers[0].get('user_ns')
                    if user_ns:
                        # 2) Crear tag
                        create_url = "https://www.uchat.com.au/api/flow/create-tag"
                        create_data = {"name": tag_name}
                        create_response = requests.post(create_url, json=create_data, headers=headers)
                        
                        if create_response.status_code == 200:
                            new_tag = create_response.json().get('data', {})
                            tag_ns = new_tag.get('tag_ns')
                            
                            if tag_ns:
                                # 3) Asignar tag
                                tag_url = "https://www.uchat.com.au/api/subscriber/add-tag"
                                tag_data = {
                                    "user_ns": user_ns,
                                    "tag_ns": tag_ns
                                }
                                tag_response = requests.post(tag_url, json=tag_data, headers=headers)
                                if tag_response.status_code == 200:
                                    _logger.info(f"Se asignó el tag {tag_name} al usuario {user_ns}.")
        except Exception as e:
            _logger.error(f"Error en la comunicación con UChat: {str(e)}")