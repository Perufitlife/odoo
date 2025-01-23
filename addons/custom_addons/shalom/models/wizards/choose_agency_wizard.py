from odoo import models, fields, api

class ChooseAgencyWizard(models.TransientModel):
    _name = 'choose.agency.wizard'
    _description = 'Wizard para elegir agencia de envío'

    agency_type = fields.Selection([
        ('shalom', 'Shalom'),
        ('olva', 'Olva')
    ], string='Agencia de Envío', required=True)
    
    sale_id = fields.Many2one('sale.order', string='Orden de Venta', readonly=True)

    def action_confirm_agency(self):
        self.ensure_one()
        return {
            'name': f"Elegir Dirección de {dict(self._fields['agency_type'].selection).get(self.agency_type)}",
            'type': 'ir.actions.act_window',
            'res_model': 'choose.address.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_id': self.sale_id.id,
                'default_agency_type': self.agency_type,
                'active_id': self.sale_id.id,
                'active_model': 'sale.order',
            }
        }

