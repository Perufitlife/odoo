# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class PendingReasonWizard(models.TransientModel):
    _name = 'pending.reason.wizard'
    _description = 'Selección de Razón de Pendiente'

    @api.model
    def _register_hook(self):
        _logger.info("Registering PendingReasonWizard model")
        return super()._register_hook()


    def _set_tag_and_status(self, tag_name):
        """Método helper para asignar tag y cambiar estado"""
        order_id = self.env.context.get('active_id')
        if not order_id:
            return
        
        order = self.env['sale.order'].browse(order_id)
        
        # Primero asignamos el tag específico
        self._assign_uchat_tag(order, tag_name)
        
        # Luego cambiamos el estado a pendiente
        order.write({
            'x_initial_status': 'pending'
        })

    def _assign_uchat_tag(self, order, tag_name):
        """Método helper para asignar tag en UChat"""
        try:
            phone_raw = order.partner_id.mobile or order.partner_id.phone
            if not phone_raw:
                return order._show_notification('Error', 'El cliente no tiene teléfono configurado', 'warning')

            phone_clean = phone_raw.replace('+', '').replace(' ', '')
            uchat_token = self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')
            
            if not uchat_token:
                return order._show_notification('Error', 'No se ha configurado el token de UChat', 'warning')

            headers = {
                "Authorization": f"Bearer {uchat_token}",
                "Content-Type": "application/json",
            }

            url = "https://www.uchat.com.au/api/subscribers"
            params = {"user_id": phone_clean}
            response = requests.get(url, params=params, headers=headers)
            
            subscribers = response.json().get('data', [])
            if not subscribers:
                return order._show_notification('Cliente no encontrado', 'No se encontró el cliente en UChat', 'warning')

            subscriber = subscribers[0]
            user_ns = subscriber.get('user_ns')

            # Crear el tag específico
            create_url = "https://www.uchat.com.au/api/flow/create-tag"
            create_data = {"name": tag_name}
            create_response = requests.post(create_url, json=create_data, headers=headers)
            tag_ns = create_response.json().get('data', {}).get('tag_ns')

            # Asignar tag
            tag_url = "https://www.uchat.com.au/api/subscriber/add-tag"
            tag_data = {
                "user_ns": user_ns,
                "tag_ns": tag_ns
            }
            tag_response = requests.post(tag_url, json=tag_data, headers=headers)

            return order._show_notification(
                'Tag asignado',
                f'Se asignó el tag "{tag_name}" y se actualizó el estado',
                'success'
            )

        except Exception as e:
            return order._show_notification('Error', str(e), 'danger')

    def action_solicitar_direccion(self):
        self._set_tag_and_status('SolicitarDireccion')
        return {'type': 'ir.actions.act_window_close'}

    def action_solicitar_fecha(self):
        self._set_tag_and_status('SolicitarFechaEntrega')
        return {'type': 'ir.actions.act_window_close'}

    def action_solicitar_referencia(self):
        self._set_tag_and_status('SolicitarReferencia')
        return {'type': 'ir.actions.act_window_close'}

    def action_solicitar_confirmacion(self):
        self._set_tag_and_status('SolicitarConfirmacion')
        return {'type': 'ir.actions.act_window_close'}

    def action_enviar_info_producto(self):
        self._set_tag_and_status('EnviarInfoProducto')
        return {'type': 'ir.actions.act_window_close'}

    def action_enviar_precios(self):
        self._set_tag_and_status('EnviarPrecios')
        return {'type': 'ir.actions.act_window_close'}