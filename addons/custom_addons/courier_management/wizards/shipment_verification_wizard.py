from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)

class ShipmentVerificationWizard(models.TransientModel):
    _name = 'shipment.verification.wizard'
    _description = 'Asistente de Verificación de Envíos'

    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier',
        required=True
    )
    
    product_summary_ids = fields.One2many(
        'shipment.verification.line',
        'wizard_id',                  
        string='Resumen de Productos'
    )
    
    shipment_ids = fields.Many2many(
        'courier.shipment',
        'shipment_verification_rel',
        'wizard_id',
        'shipment_id',
        string='Envíos a Procesar'
    )

    def action_verify(self):
        """
        1. Verificar stock.
        2. Según carrier.auto_in_transit, marcar envíos como 'in_transit' o 'despachado'.
        3. Asignar tag "Despachado" al cliente en UChat.
        4. Setear user field "transportadora" con el nombre del carrier.
        5. Mostrar notificación final y cerrar wizard.
        """
        # 1) Validar stock
        for line in self.product_summary_ids:
            if line.quantity_to_ship > line.quantity_available:
                product_name = line.product_id.display_name
                raise UserError((
                    "No hay stock suficiente para el producto '%s'.\n"
                    "Disponible: %s, requerido: %s"
                ) % (product_name, line.quantity_available, line.quantity_to_ship))

        # [INICIO CAMBIO auto_in_transit] ====================================
        # 2) Marcar los envíos según auto_in_transit
        for shipment in self.shipment_ids:
            # Verificamos si el carrier de este shipment tiene despacho inmediato
            if shipment.carrier_id.auto_in_transit:
                # Pasa directamente a 'in_transit'
                shipment.write({'state': 'in_transit'})
                if shipment.sale_order_id:
                    shipment.sale_order_id.write({'x_initial_status': 'in_transit'})
            else:
                # Caso normal: pasa a 'despachado'
                shipment.write({'state': 'despachado'})
                if shipment.sale_order_id:
                    shipment.sale_order_id.write({'x_initial_status': 'despachado'})
        # [FIN CAMBIO auto_in_transit] =======================================

        # 3) Asignar tag "Despachado" y setear user field "transportadora" en cada partner
        partners = self.shipment_ids.mapped('partner_id')
        for partner in partners:
            self._assign_uchat_tag_despachado(partner)
        
        # 4) Notificación final y cerrar
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Verificación Exitosa",
                'message': ("Stock verificado y pedidos marcados como 'in_transit' o 'despachado' "
                            "según el carrier. Tag y user field en UChat asignados."),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _assign_uchat_tag_despachado(self, partner):
        """
        1) Busca/crea el subscriber en UChat a partir del teléfono.
        2) Crea (si no existe) y asigna el tag "Despachado".
        3) Crea (si no existe) y setea el user field "transportadora" con self.carrier_id.name
        """
        phone_raw = partner.mobile or partner.phone
        if not phone_raw:
            _logger.warning(f"No se asignó tag ni user field en UChat porque el partner {partner.name} no tiene teléfono.")
            return

        phone_clean = phone_raw.replace('+', '').replace(' ', '')

        # Tomamos el token y el entorno
        uchat_token = self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')
        environment = self.env['ir.config_parameter'].sudo().get_param('uchat.environment', 'production')
        base_url = 'https://www.uchat.com.au'

        if not uchat_token:
            _logger.warning("No se ha configurado uchat.api_token. Tag y user field no asignados.")
            return

        headers = {
            "Authorization": f"Bearer {uchat_token}",
            "Content-Type": "application/json",
        }

        # ----------------------------------------------------------------------------
        # (A) Buscar el subscriber segun user_id=phone_clean
        # ----------------------------------------------------------------------------
        url_subs = f"{base_url}/api/subscribers"
        params = {"user_id": phone_clean}
        resp_subs = requests.get(url_subs, params=params, headers=headers)
        if resp_subs.status_code != 200:
            _logger.warning(
                f"Error al consultar subscriber en UChat (status {resp_subs.status_code}): {resp_subs.text}")
            return

        data_subs = resp_subs.json()
        subscribers = data_subs.get('data', [])
        if not subscribers:
            _logger.warning(f"No se encontró subscriber con user_id = {phone_clean} en UChat.")
            return

        subscriber = subscribers[0]
        user_ns = subscriber.get('user_ns')
        if not user_ns:
            _logger.warning(f"El subscriber en UChat no tiene user_ns. Tag no asignado para {partner.name}.")
            return

        # ----------------------------------------------------------------------------
        # (B) Crear/Obtener el tag "Despachado"
        # ----------------------------------------------------------------------------
        create_tag_url = f"{base_url}/api/flow/create-tag"
        create_tag_data = {"name": "Despachado"}
        create_resp = requests.post(create_tag_url, json=create_tag_data, headers=headers)
        if create_resp.status_code != 200:
            _logger.warning(f"Error al crear tag 'Despachado': {create_resp.text}")
            return
        tag_ns = create_resp.json().get('data', {}).get('tag_ns')
        if not tag_ns:
            _logger.warning("No se pudo obtener tag_ns al crear tag 'Despachado' en UChat.")
            return

        # Asignar el tag al subscriber
        tag_url = f"{base_url}/api/subscriber/add-tag"
        tag_data = {
            "user_ns": user_ns,
            "tag_ns": tag_ns
        }
        tag_resp = requests.post(tag_url, json=tag_data, headers=headers)
        if tag_resp.status_code != 200:
            _logger.warning(f"Error al asignar tag 'Despachado' en UChat: {tag_resp.text}")

        tag_result = tag_resp.json()
        if tag_result.get('status') != 'ok':
            _logger.warning(f"Respuesta inesperada al asignar tag 'Despachado': {tag_result}")

        _logger.info(f"Se asignó el tag 'Despachado' a {phone_clean} (partner: {partner.name}) en UChat.")

        # ----------------------------------------------------------------------------
        # (C) [INICIO - Asignar user field transportadora]
        # ----------------------------------------------------------------------------
        carrier_name = self.carrier_id.name or "SinTransportadora"

        # Ver si el user field 'transportadora' ya existe
        user_fields_url = f"{base_url}/api/flow/user-fields"
        field_params = {"name": "transportadora"}
        resp_fields = requests.get(user_fields_url, params=field_params, headers=headers)
        field_exists = False
        if resp_fields.status_code == 200:
            existing_fields = resp_fields.json().get('data', [])
            for f in existing_fields:
                if f.get('name') == 'transportadora':
                    field_exists = True
                    break
        
        # Si no existe, crearlo
        if not field_exists:
            create_field_url = f"{base_url}/api/flow/create-user-field"
            field_data = {
                "name": "transportadora",
                "var_type": "text",  
                "description": "Transportadora asignada desde Odoo"
            }
            cf_resp = requests.post(create_field_url, json=field_data, headers=headers)
            if cf_resp.status_code != 200:
                _logger.warning("No se pudo crear user field 'transportadora': %s", cf_resp.text)

        # Ponerle valor "carrier_name" a ese campo
        set_field_url = f"{base_url}/api/subscriber/set-user-field-by-name"
        set_data = {
            "user_ns": user_ns,
            "field_name": "transportadora",
            "value": carrier_name
        }
        set_resp = requests.put(set_field_url, json=set_data, headers=headers)
        if set_resp.status_code != 200:
            _logger.warning("Error al setear user field 'transportadora': %s", set_resp.text)
        else:
            sr_json = set_resp.json()
            if sr_json.get('status') == 'ok':
                _logger.info(f"Seteado user field 'transportadora={carrier_name}' a {phone_clean} (partner: {partner.name})")
            else:
                _logger.warning(f"Respuesta inesperada al asignar user field 'transportadora': {sr_json}")
        # ----------------------------------------------------------------------------
        # (D) [FIN - Asignar user field transportadora]
        # ----------------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            shipments = self.env['courier.shipment'].browse(active_ids)
            carriers = shipments.mapped('carrier_id')
            if len(carriers) == 1:
                res['carrier_id'] = carriers.id
            else:
                res['carrier_id'] = carriers[:1].id if carriers else False

            res['shipment_ids'] = [(6, 0, shipments.ids)]

            product_dict = {}
            for sh in shipments:
                for line in sh.deliverable_lines:
                    product = line.product_id
                    qty = line.product_uom_qty
                    if product not in product_dict:
                        product_dict[product] = 0.0
                    product_dict[product] += qty

            lines_vals = []
            for product, total_qty in product_dict.items():
                lines_vals.append((0, 0, {
                    'product_id': product.id,
                    'quantity_required': total_qty,
                    'quantity_to_ship': total_qty,
                }))
            res['product_summary_ids'] = lines_vals

        return res


class ShipmentVerificationLine(models.TransientModel):
    _name = 'shipment.verification.line'
    _description = 'Línea de Verificación de Envío'

    wizard_id = fields.Many2one(
        'shipment.verification.wizard',
        string='Wizard'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True
    )
    quantity_required = fields.Float(
        string='Cantidad Requerida',
        readonly=True
    )
    quantity_available = fields.Float(
        string='Cantidad Disponible',
        related='product_id.qty_available',
        readonly=True
    )
    quantity_to_ship = fields.Float(
        string='Cantidad a Despachar'
    )
