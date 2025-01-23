from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    def action_open_agency_wizard(self):
        """Abre el wizard para elegir la agencia de envío."""
        self.ensure_one()
        return {
            'name': "Elegir Agencia de Envío",
            'type': 'ir.actions.act_window',
            'res_model': 'choose.agency.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'sale.order',
                'default_sale_id': self.id,
            }
        }