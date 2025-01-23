# custom_addons/shopify/models/res_partner.py
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    _sql_constraints = [
        ('unique_email', 'unique(email)', 'Ya existe un contacto con este email'),
        ('unique_phone', 'unique(phone)', 'Ya existe un contacto con este teléfono')
    ]