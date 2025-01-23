from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    carrier_id = fields.Many2one('delivery.carrier', string='Carrier')
