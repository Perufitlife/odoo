# En wizards/no_entregado_wizard.py
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class NoEntregadoWizard(models.TransientModel):
    _name = 'no.entregado.wizard'
    _description = 'Wizard para marcar el envío como No Entregado'

    shipment_id = fields.Many2one(
        'courier.shipment',
        string='Envío',
        required=True
    )
    reason_id = fields.Many2one(
        'no.delivery.reason',
        string='Motivo de No Entrega',
        required=True
    )
    additional_notes = fields.Text(
        string='Notas Adicionales'
    )

    def action_confirm_no_entregado(self):
        self.ensure_one()
        shipment = self.shipment_id

        if shipment.state != 'in_transit':
            raise UserError("Solo puedes marcar como 'No Entregado' envíos en tránsito.")

        # Actualizar estados
        shipment.write({
            'state': 'failed'
        })
        
        if shipment.sale_order_id:
            shipment.sale_order_id.write({
                'x_initial_status': 'no_entregado'
            })

        # Registrar en el chatter
        reason_msg = f"Motivo: {self.reason_id.name}"
        if self.additional_notes:
            reason_msg += f"\nNotas adicionales: {self.additional_notes}"

        shipment.message_post(body=f"El envío se marcó como No Entregado.\n{reason_msg}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }