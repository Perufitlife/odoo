# En models/no_delivery_reason.py
from odoo import models, fields

class NoDeliveryReason(models.Model):
    _name = 'no.delivery.reason'
    _description = 'Motivos de No Entrega'
    _order = 'name'

    name = fields.Char(
        string='Motivo',
        required=True
    )
    active = fields.Boolean(
        default=True
    )
    description = fields.Text(
        string='Descripción'
    )