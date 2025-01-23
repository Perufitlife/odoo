from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ReprogramarWizard(models.TransientModel):
    _name = 'reprogramar.wizard'
    _description = 'Wizard para Reprogramar Envío'

    shipment_id = fields.Many2one(
        'courier.shipment',
        string='Envío',
        required=True
    )
    new_delivery_date = fields.Datetime(
        string='Nueva Fecha de Entrega',
        required=True
    )
    notes = fields.Text(
        string='Motivo de Reprogramación',
        help='Indica el motivo por el cual se está reprogramando el envío'
    )

    def action_confirm_reprogramar(self):
        self.ensure_one()
        shipment = self.shipment_id

        # Actualizar fecha de entrega y estado
        values = {
            'delivery_date': self.new_delivery_date,
            'state': 'scheduled'  # Volvemos a estado programado
        }
        
        # Usar el contexto especial para evitar bucles
        shipment.with_context(no_propagate_to_sale_order=True).write(values)

        # Actualizar la orden de venta directamente
        if shipment.sale_order_id:
            shipment.sale_order_id.with_context(no_propagate_to_shipment=True).write({
                'x_initial_status': 'reprogramado',
                'commitment_date': self.new_delivery_date
            })

        # Registrar en el chatter
        message = f"""Envío reprogramado:
        Nueva fecha de entrega: {self.new_delivery_date}"""
        if self.notes:
            message += f"\nMotivo: {self.notes}"

        shipment.message_post(body=message)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
