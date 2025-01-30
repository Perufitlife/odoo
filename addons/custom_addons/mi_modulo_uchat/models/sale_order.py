# custom_addons/mi_modulo_uchat/models/sale_order.py
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import re

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_phone = fields.Char(
        string='Teléfono',
        related='partner_id.phone',
        store=True,
        readonly=True
    )
    partner_mobile = fields.Char(
        string='Móvil',
        related='partner_id.mobile',
        store=True,
        readonly=True
    )

    partner_city = fields.Char(
        related='partner_id.city',
        string='Ciudad',
        store=True
    )

    products_detail = fields.Text(  # Campo agregado
        string='Detalle de Productos',
        compute='_compute_products_summary',
        store=True
    )

    products_summary = fields.Char(
        string='Productos',
        compute='_compute_products_summary',
        store=True
    )

    simplified_message = fields.Char(
        string='Último mensaje',
        compute='_compute_simplified_message',
        store=True
    )

    message_detail = fields.Text(  # Campo agregado
        string='Detalle del mensaje',
        compute='_compute_simplified_message',
        store=True
    )

    @api.depends('order_line')
    def _compute_products_summary(self):
        for record in self:
            summary_items = []
            details = []
            for line in record.order_line:
                if line.product_id and line.product_uom_qty:
                    # Formato más legible: "2x Producto A"
                    summary_items.append(f"{int(line.product_uom_qty)}x {line.product_id.name}")
                    details.append(f"{line.product_id.name} (Cantidad: {int(line.product_uom_qty)})")
            
            record.products_summary = ' | '.join(summary_items) if summary_items else '/'
            record.products_detail = '\n'.join(details) if details else '/'

    @api.depends('message_ids')
    def _compute_simplified_message(self):
        for record in self:
            messages = record.message_ids.filtered(lambda m: 
                # Solo incluimos mensajes con cuerpo real
                m.body and 
                # Aseguramos que es un mensaje manual o una nota
                m.message_type in ['comment', 'email', 'notification'] and 
                # Excluimos mensajes específicos de Shopify
                'Orden de Shopify' not in (m.body or '') and
                # Verificamos que el mensaje tenga contenido real después de limpiar HTML
                len(re.sub(r'<[^>]+>', '', m.body).strip()) > 0
            ).sorted('date', reverse=True)

            if messages:
                last_message = messages[0]
                # Limpieza del mensaje
                clean_message = re.sub(r'<[^>]+>', '', last_message.body)
                clean_message = re.sub(r'\s+', ' ', clean_message).strip()
                
                # Para debugging
                _logger.info(f"Mensaje original: {last_message.body}")
                _logger.info(f"Mensaje limpio: {clean_message}")
                _logger.info(f"Tipo de mensaje: {last_message.message_type}")
                
                record.simplified_message = clean_message
                record.message_detail = last_message.body
            else:
                record.simplified_message = ''
                record.message_detail = ''

    def action_open_uchat(self):
        """
        Abre la ventana de conversación en UChat para el cliente relacionado a esta orden.
        Se basa en el phone o mobile del partner, y en el token configurado en ir.config_parameter.
        """
        self.ensure_one()

        # Verificar primero el móvil y si no existe, usar el teléfono.
        phone_raw = self.partner_id.mobile or self.partner_id.phone or ''
        if not phone_raw:
            raise UserError(_("El cliente no tiene un número de teléfono ni móvil configurado."))

        phone_clean = phone_raw.replace('+', '').replace(' ', '')

        # Leer el token de UChat desde la configuración.
        uchat_token = self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')
        if not uchat_token:
            raise UserError(_("No se ha configurado el token de UChat (uchat.api_token)."))

        url = "https://www.uchat.com.au/api/subscribers"
        headers = {
            "Authorization": f"Bearer {uchat_token}",
            "Content-Type": "application/json",
        }
        params = {"user_id": phone_clean}
        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            raise UserError(_("Error al consultar la API de UChat: %s") % response.text)

        data_json = response.json()
        subscribers = data_json.get('data', [])
        if not subscribers:
            raise UserError(_("No se encontró subscriber con user_id = %s") % phone_clean)

        user_ns = subscribers[0].get('user_ns')
        if not user_ns:
            raise UserError(_("No existe 'user_ns' en el subscriber de UChat."))

        uchat_url = f"https://www.uchat.com.au/inbox/{user_ns}"

        return {
            'type': 'ir.actions.act_url',
            'url': uchat_url,
            'target': 'new',
        }

    # -----------------------------
    # Métodos para cambiar de estado
    # -----------------------------
    def action_set_pendiente(self):
        """
        Abre el wizard para seleccionar la razón de pendiente
        """
        self.ensure_one()  # Asegura que solo estamos trabajando con un registro
        return {
            'name': 'Seleccionar Razón',
            'type': 'ir.actions.act_window',
            'res_model': 'pending.reason.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'sale.order',
            }
        }

    def action_set_esperando_adelanto(self):
        """
        Asignar tag 'EsperandoAdelanto' al cliente en UChat
        """
        self.ensure_one()
        try:
            # Obtener teléfono del cliente
            phone_raw = self.partner_id.mobile or self.partner_id.phone
            if not phone_raw:
                return self._show_notification('Error', 'El cliente no tiene teléfono configurado', 'warning')

            # Limpiar teléfono
            phone_clean = phone_raw.replace('+', '').replace(' ', '')
            _logger.info(f"Buscando cliente con teléfono: {phone_clean}")

            # Obtener token
            uchat_token = self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')
            if not uchat_token:
                return self._show_notification('Error', 'No se ha configurado el token de UChat', 'warning')

            # Preparar headers
            headers = {
                "Authorization": f"Bearer {uchat_token}",
                "Content-Type": "application/json",
            }

            # Buscar subscriber
            url = "https://www.uchat.com.au/api/subscribers"
            params = {"user_id": phone_clean}
            
            response = requests.get(url, params=params, headers=headers)
            if response.status_code != 200:
                return self._show_notification('Error UChat', 
                    f"Error al consultar UChat: {response.text}", 'warning')

            data_json = response.json()
            subscribers = data_json.get('data', [])
            
            if not subscribers:
                return self._show_notification(
                    'Cliente no encontrado', 
                    f'No se encontró el subscriber con user_id = {phone_clean}', 
                    'warning'
                )

            # Obtener user_ns del subscriber
            subscriber = subscribers[0]
            user_ns = subscriber.get('user_ns')
            if not user_ns:
                return self._show_notification(
                    'Error', 
                    'No existe user_ns en el subscriber de UChat', 
                    'warning'
                )

            # Crear el tag 'EsperandoAdelanto' si no existe
            create_url = "https://www.uchat.com.au/api/flow/create-tag"
            create_data = {
                "name": "EsperandoAdelanto"
            }
            
            create_response = requests.post(create_url, json=create_data, headers=headers)
            if create_response.status_code != 200:
                return self._show_notification('Error', f'Error al crear tag: {create_response.text}', 'warning')

            response_data = create_response.json()
            tag_ns = response_data.get('data', {}).get('tag_ns')
            if not tag_ns:
                return self._show_notification('Error', 'No se pudo obtener el tag_ns', 'warning')

            _logger.info(f"Tag creado/encontrado exitosamente: {tag_ns}")

            new_tag = create_response.json().get('data', {})
            tag_ns = new_tag.get('tag_ns')

            # Asignar tag
            tag_url = "https://www.uchat.com.au/api/subscriber/add-tag"
            tag_data = {
                "user_ns": user_ns,
                "tag_ns": tag_ns
            }
            
            _logger.info(f"Asignando tag {tag_ns} a subscriber {user_ns}")
            tag_response = requests.post(tag_url, json=tag_data, headers=headers)
            
            if tag_response.status_code != 200:
                return self._show_notification(
                    'Error', 
                    f'Error al asignar tag en UChat: {tag_response.text}', 
                    'warning'
                )

            # Verificar respuesta de asignación de tag
            tag_result = tag_response.json()
            if tag_result.get('status') != 'ok':
                return self._show_notification(
                    'Error',
                    f'Error inesperado al asignar tag: {tag_result}',
                    'warning'
                )

            self.write({
                'x_initial_status': 'esperando_adelanto'
            })
            
            return self._show_notification(
                'Estado actualizado',
                f'Se asignó el tag "EsperandoAdelanto" y se actualizó el estado a Esperando Adelanto',
                'success'
            )


        except Exception as e:
            _logger.error(f"Error completo: {str(e)}", exc_info=True)
            return self._show_notification(
                'Error',
                f'Error inesperado: {str(e)}',
                'danger'
            )


    def action_cancel(self):
        """
        Sobrescribir el método action_cancel para:
        1. Ejecutar la funcionalidad estándar de cancelación
        2. Cambiar el x_initial_status a 'cancelled'
        3. Asignar tag 'OrdenCancelada' en UChat
        """
        # 1. Ejecutar cancelación estándar de Odoo
        res = super(SaleOrder, self).action_cancel()

        try:
            # 2. Cambiar estado inicial
            self.write({
                'x_initial_status': 'cancelled'
            })

            # 3. Proceso de UChat
            phone_raw = self.partner_id.mobile or self.partner_id.phone
            if not phone_raw:
                return self._show_notification('Error', 'El cliente no tiene teléfono configurado', 'warning')

            phone_clean = phone_raw.replace('+', '').replace(' ', '')
            _logger.info(f"Buscando cliente con teléfono: {phone_clean}")

            uchat_token = self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')
            if not uchat_token:
                return self._show_notification('Error', 'No se ha configurado el token de UChat', 'warning')

            headers = {
                "Authorization": f"Bearer {uchat_token}",
                "Content-Type": "application/json",
            }

            # Buscar subscriber
            url = "https://www.uchat.com.au/api/subscribers"
            params = {"user_id": phone_clean}
            
            response = requests.get(url, params=params, headers=headers)
            if response.status_code != 200:
                return self._show_notification('Error UChat', 
                    f"Error al consultar UChat: {response.text}", 'warning')

            subscribers = response.json().get('data', [])
            if not subscribers:
                return self._show_notification(
                    'Cliente no encontrado', 
                    f'No se encontró el subscriber con user_id = {phone_clean}', 
                    'warning'
                )

            subscriber = subscribers[0]
            user_ns = subscriber.get('user_ns')
            if not user_ns:
                return self._show_notification(
                    'Error', 
                    'No existe user_ns en el subscriber de UChat', 
                    'warning'
                )

            # Crear el tag 'OrdenCancelada' si no existe
            create_url = "https://www.uchat.com.au/api/flow/create-tag"
            create_data = {
                "name": "OrdenCancelada"
            }
            
            create_response = requests.post(create_url, json=create_data, headers=headers)
            if create_response.status_code != 200:
                return self._show_notification('Error', f'Error al crear tag: {create_response.text}', 'warning')
                
            tag_ns = create_response.json().get('data', {}).get('tag_ns')

            # Asignar tag
            tag_url = "https://www.uchat.com.au/api/subscriber/add-tag"
            tag_data = {
                "user_ns": user_ns,
                "tag_ns": tag_ns
            }
            
            _logger.info(f"Asignando tag {tag_ns} a subscriber {user_ns}")
            tag_response = requests.post(tag_url, json=tag_data, headers=headers)
            
            if tag_response.status_code != 200:
                return self._show_notification(
                    'Error', 
                    f'Error al asignar tag en UChat: {tag_response.text}', 
                    'warning'
                )

            tag_result = tag_response.json()
            if tag_result.get('status') != 'ok':
                return self._show_notification(
                    'Error',
                    f'Error inesperado al asignar tag: {tag_result}',
                    'warning'
                )

            return self._show_notification(
                'Orden cancelada',
                f'Se canceló la orden y se asignó el tag en UChat',
                'success'
            )

        except Exception as e:
            _logger.error(f"Error al cancelar orden: {str(e)}", exc_info=True)
            return self._show_notification(
                'Error',
                f'Error inesperado al cancelar: {str(e)}',
                'danger'
            )

        return res

    def _get_tag_ns(self, headers):
        """
        Obtiene el tag_ns del tag 'OrdenConfirmada'.
        Si no existe, lo crea.
        """
        # 1. Buscar si el tag existe
        url = "https://www.uchat.com.au/api/flow/tags"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            raise UserError(f"Error al consultar tags: {response.text}")

        tags = response.json().get('data', [])
        for tag in tags:
            if tag.get('name') == 'OrdenConfirmada':
                return tag.get('tag_ns')

        # 2. Si no existe, crear el tag
        create_url = "https://www.uchat.com.au/api/flow/create-tag"
        create_data = {
            "name": "OrdenConfirmada"
        }
        
        create_response = requests.post(create_url, json=create_data, headers=headers)
        if create_response.status_code != 200:
            raise UserError(f"Error al crear tag: {create_response.text}")
            
        # Cambio aquí: la respuesta exitosa viene en data
        new_tag = create_response.json().get('data', {})
        _logger.info(f"Tag creado exitosamente: {new_tag}")
        return new_tag.get('tag_ns')


    def action_confirm(self):
        """
        Tercera etapa: Confirmar orden, buscar cliente y asignar tag en UChat
        """
        # 1) Ejecutar confirmación normal de Odoo
        res = super(SaleOrder, self).action_confirm()

        # 2) Buscar cliente y asignar tag en UChat
        for order in self:
            if order.state == 'sale':
                try:
                    # Obtener teléfono del cliente
                    phone_raw = order.partner_id.mobile or order.partner_id.phone
                    if not phone_raw:
                        return self._show_notification('Error', 'El cliente no tiene teléfono configurado', 'warning')

                    # Limpiar teléfono
                    phone_clean = phone_raw.replace('+', '').replace(' ', '')
                    _logger.info(f"Buscando cliente con teléfono: {phone_clean}")

                    # Obtener token
                    uchat_token = self.env['ir.config_parameter'].sudo().get_param('uchat.api_token')
                    if not uchat_token:
                        return self._show_notification('Error', 'No se ha configurado el token de UChat', 'warning')

                    # Preparar headers para todas las peticiones
                    headers = {
                        "Authorization": f"Bearer {uchat_token}",
                        "Content-Type": "application/json",
                    }

                    # Buscar subscriber
                    url = "https://www.uchat.com.au/api/subscribers"
                    params = {"user_id": phone_clean}
                    
                    _logger.info(f"Realizando petición a {url} con params={params}")
                    response = requests.get(url, params=params, headers=headers)
                    
                    if response.status_code != 200:
                        return self._show_notification('Error UChat', 
                            f"Error al consultar UChat: {response.text}", 'warning')

                    data_json = response.json()
                    subscribers = data_json.get('data', [])
                    
                    if not subscribers:
                        return self._show_notification(
                            'Cliente no encontrado', 
                            f'No se encontró el subscriber con user_id = {phone_clean}', 
                            'warning'
                        )

                    # Obtener user_ns del subscriber
                    subscriber = subscribers[0]
                    user_ns = subscriber.get('user_ns')
                    if not user_ns:
                        return self._show_notification(
                            'Error', 
                            'No existe user_ns en el subscriber de UChat', 
                            'warning'
                        )

                    # Obtener o crear tag
                    try:
                        tag_ns = self._get_tag_ns(headers)
                    except UserError as e:
                        return self._show_notification('Error', str(e), 'warning')

                    # Asignar tag
                    tag_url = "https://www.uchat.com.au/api/subscriber/add-tag"
                    tag_data = {
                        "user_ns": user_ns,
                        "tag_ns": tag_ns
                    }
                    
                    _logger.info(f"Asignando tag {tag_ns} a subscriber {user_ns}")
                    tag_response = requests.post(tag_url, json=tag_data, headers=headers)
                    
                    if tag_response.status_code != 200:
                        return self._show_notification(
                            'Error', 
                            f'Error al asignar tag en UChat: {tag_response.text}', 
                            'warning'
                        )

                    # Verificar respuesta de asignación de tag
                    tag_result = tag_response.json()
                    if tag_result.get('status') != 'ok':
                        return self._show_notification(
                            'Error',
                            f'Error inesperado al asignar tag: {tag_result}',
                            'warning'
                        )

                    return self._show_notification(
                        'Tag asignado correctamente',
                        f'Se asignó el tag "OrdenConfirmada" al cliente {subscriber.get("name")}',
                        'success'
                    )

                except Exception as e:
                    _logger.error(f"Error completo: {str(e)}", exc_info=True)
                    return self._show_notification(
                        'Error',
                        f'Error inesperado: {str(e)}',
                        'danger'
                    )

        return res

    def _show_notification(self, title, message, type='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _(title),
                'message': _(message),
                'type': type,
                'sticky': True,
            }
        }