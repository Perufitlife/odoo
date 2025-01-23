# custom_addons/shopify/models/shopify_store.py

from odoo import models, fields, api

class ShopifyStore(models.Model):
    _name = 'shopify.store'
    _description = 'Shopify Store'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Store Name", required=True, tracking=True)
    shop_url = fields.Char(string="Shop URL", required=True, tracking=True, help="URL de la tienda Shopify")
    api_key = fields.Char(string="API Key", required=True)
    password = fields.Char(string="API Password", required=True)
    country = fields.Selection([
        ('pe', 'Perú'), 
        ('co', 'Colombia'), 
        ('ec', 'Ecuador')
    ], string="País", required=True, default='pe', tracking=True)
    active = fields.Boolean(string="Activo", default=True, tracking=True)

    # Nuevos campos para webhooks
    webhook_signature = fields.Char(string="Webhook Signature", required=False, help="Firma del webhook proporcionada por Shopify")
    webhook_url = fields.Char(string="Webhook URL", compute="_compute_webhook_url", store=True, help="URL pública para recibir webhooks")

    _sql_constraints = [
        ('unique_shop_url', 'unique(shop_url)', 'Ya existe una tienda con esta URL!'),
    ]

    @api.depends('shop_url')
    def _compute_webhook_url(self):
        """
        Genera automáticamente la URL del webhook basada en la URL pública global (e.g., ngrok).
        """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')  # URL pública configurada en Odoo
        for record in self:
            if record.shop_url:
                record.webhook_url = f"{base_url}/shopify/webhook/orders/create?store={record.id}"
            else:
                record.webhook_url = False
