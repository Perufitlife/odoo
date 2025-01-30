from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import ValidationError

class DeliveryDateWizard(models.TransientModel):
    _name = 'delivery.date.wizard'
    _description = 'Establecer Fecha de Entrega'

    delivery_date = fields.Datetime(
        string='Fecha de Entrega',
        required=True,
        default=fields.Datetime.now
    )

    @api.constrains('delivery_date')
    def _check_delivery_date(self):
        for record in self:
            if record.delivery_date < fields.Datetime.now():
                raise ValidationError('La fecha de entrega debe ser futura')

    def action_confirm(self):
        order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        order.write({'commitment_date': self.delivery_date})
        return order.action_quick_confirm()