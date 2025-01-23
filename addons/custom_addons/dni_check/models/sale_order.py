from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_check_dni(self):
        self.ensure_one()
        dni = self.partner_id.vat or ''  # El campo vat suele usarse para DNI en Perú
        
        if not dni:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Por favor, ingrese un número de DNI válido',
                    'type': 'danger',
                }
            }
            
        return {
            'name': 'Consulta DNI',
            'type': 'ir.actions.act_window',
            'res_model': 'dni.check.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_dni': dni,
                'default_sale_id': self.id,
            }
        }