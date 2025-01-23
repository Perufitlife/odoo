from odoo import models, fields, api, _
from datetime import timedelta

class AddressWizardMixin(models.AbstractModel):
    _name = 'address.wizard.mixin'
    _description = 'Mixin para wizards de direcciones'

    sale_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        readonly=True
    )
    
    agency_address_id = fields.Many2one(
        'agency.address',
        string="Dirección de Agencia"
    )

    def action_confirm_address(self):
        self.ensure_one()
        if not self.sale_id:
            return

        sale = self.sale_id
        
        # Establecer fecha de compromiso si no existe
        if not sale.commitment_date:
            sale.commitment_date = fields.Datetime.now() + timedelta(days=1)

        # Actualizar carrier
        carrier = self.env['delivery.carrier'].search([('name', '=', self._get_carrier_name())], limit=1)
        if carrier:
            sale.carrier_id = carrier.id

        # Actualizar dirección de envío
        sale.partner_shipping_id.write({
            'street': self.agency_address_id.name,
            'street2': self.agency_address_id.address,
            'state_id': self.agency_address_id.state_id.id,
            'city_id': self.agency_address_id.city_id.id,
            'l10n_pe_district': self.agency_address_id.district_id.id,
        })

        # Confirmar orden
        sale.action_confirm()
        
        # Actualizar estado inicial
        if hasattr(sale, 'x_initial_status'):
            sale.x_initial_status = 'confirmed'

        # Desbloquear orden si es necesario
        if hasattr(sale, 'action_unlock'):
            sale.action_unlock()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Agencia asignada"),
                'message': _(f"Se ha configurado la dirección de {self._get_carrier_name()} y confirmado la orden."),
                'type': 'success',
            }
        }