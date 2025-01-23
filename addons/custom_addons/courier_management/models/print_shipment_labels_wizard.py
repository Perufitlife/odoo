from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import date_utils

class PrintShipmentLabelsWizard(models.TransientModel):
    _name = 'print.shipment.labels.wizard'
    _description = 'Print Shipment Labels Wizard'

    delivery_date = fields.Date(
        string="Fecha de Envío",
        required=True
    )

    def action_print_labels(self):
        shipments = self.env['courier.shipment'].search([
            ('delivery_date', '>=', date_utils.start_of(self.delivery_date, 'day')),
            ('delivery_date', '<=', date_utils.end_of(self.delivery_date, 'day')),
        ])
        if not shipments:
            raise UserError("No hay envíos para la fecha seleccionada.")

        pdf_action = self.env.ref('courier_management.action_labels_report').report_action(shipments)
        
        # Update state to 'scheduled'
        shipments.write({'state': 'scheduled'})
        
        # Post message per shipment
        for sh in shipments:
            sh.message_post(body="El envío ha pasado al estado 'Programado' tras imprimir etiquetas.")
        
        return pdf_action
