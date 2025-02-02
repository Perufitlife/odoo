from odoo import models, fields, api
from odoo.exceptions import UserError

class DeliveryMethodWizard(models.TransientModel):
    _name = 'delivery.method.wizard'
    _description = 'Selección de Método de Entrega'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True
    )

    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier',
        required=True
    )

    delivery_type = fields.Selection([
        ('home', 'Entrega a Domicilio'),
        ('pickup', 'Recojo en Agencia')
    ], string='Tipo de Entrega', required=True)

    pickup_point_id = fields.Many2one(
        'pickup.point',
        string='Punto de Recojo',
        domain="[('carrier_id', '=', carrier_id)]"
    )

    @api.onchange('delivery_type')
    def _onchange_delivery_type(self):
        self.pickup_point_id = False
        if self.delivery_type == 'pickup' and self.sale_order_id.partner_id:
            partner = self.sale_order_id.partner_id
            domain = [('carrier_id', '=', self.carrier_id.id)]
            if partner.state_id:
                domain.append(('state_id', '=', partner.state_id.id))
            if partner.city_id:
                domain.append(('city_id', '=', partner.city_id.id))
            if partner.l10n_pe_district:
                domain.append(('district_id', '=', partner.l10n_pe_district.id))
            
            pickup_point = self.env['pickup.point'].search(domain, limit=1)
            if pickup_point:
                self.pickup_point_id = pickup_point.id

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get('active_model') == 'sale.order':
            sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
            res.update({
                'sale_order_id': sale_order.id,
                'carrier_id': sale_order.carrier_id.id,
                'delivery_type': 'home'
            })
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError('No se encontró la orden de venta.')

        if self.delivery_type == 'pickup' and not self.pickup_point_id:
            raise UserError('Debe seleccionar un punto de recojo.')

        sale_order = self.sale_order_id
        values = {
            'carrier_id': self.carrier_id.id,
        }

        if self.delivery_type == 'pickup':
            # Actualizar dirección de envío con la dirección del punto de recojo
            shipping_partner = sale_order.partner_shipping_id
            pickup_point = self.pickup_point_id
            
            shipping_partner.write({
                'street': pickup_point.name,
                'street2': pickup_point.address,
                'state_id': pickup_point.state_id.id,
                'city_id': pickup_point.city_id.id,
                'l10n_pe_district': pickup_point.district_id.id,
            })

            # Actualizar el precio de envío
            values['delivery_price'] = pickup_point.delivery_fee

        # Confirmar la orden
        sale_order.write(values)
        sale_order.action_confirm()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Éxito',
                'message': 'Método de entrega configurado y orden confirmada',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }