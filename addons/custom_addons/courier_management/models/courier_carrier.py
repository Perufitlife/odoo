from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CourierCarrier(models.Model):
    _inherit = 'delivery.carrier'
    _description = 'Courier Carrier'

    # Campos principales
    courier_user_id = fields.Many2one(
        'res.users',
        string='Usuario Courier',
        tracking=True,
        index=True,
        help="Usuario que tendrá acceso a los envíos asignados a este courier"
    )
    
    auto_in_transit = fields.Boolean(
        string="Despacho Inmediato",
        help="Envío pasa directamente a 'in_transit' después de verificar stock"
    )
    
    # Campos computados
    pricing_rule_count = fields.Integer(
        string='Reglas de Precio',
        compute='_compute_counts'
    )
    
    shipment_count = fields.Integer(
        string='Envíos',
        compute='_compute_counts'
    )

    # Optimización: Combinar los computes para reducir queries
    @api.depends('courier_user_id')
    def _compute_counts(self):
        for carrier in self:
            carrier.pricing_rule_count = self.env['courier.pricing.rule'].search_count(
                [('carrier_id', '=', carrier.id)]
            )
            carrier.shipment_count = self.env['courier.shipment'].search_count(
                [('carrier_id', '=', carrier.id)]
            )

    @api.model
    def create(self, vals_list):
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
            
        records = super().create(vals_list)
        self._update_courier_group_users(records)
        return records

    def write(self, vals):
        old_users = self.mapped('courier_user_id')
        result = super().write(vals)
        
        if 'courier_user_id' in vals:
            self._update_courier_group_users(self, old_users)
        return result

    def _update_courier_group_users(self, records, old_users=None):
        """Gestiona usuarios en el grupo courier de manera eficiente"""
        courier_group = self.env.ref('courier_management.group_courier_user', raise_if_not_found=False)
        if not courier_group:
            return

        # Usuarios a agregar
        users_to_add = records.mapped('courier_user_id')
        
        # Usuarios a posiblemente remover
        users_to_check = old_users if old_users else self.env['res.users']
        
        # Actualizar en una sola operación
        if users_to_add:
            courier_group.write({'users': [(4, user.id) for user in users_to_add]})
            
        for user in users_to_check:
            if not self.search_count([('courier_user_id', '=', user.id)]):
                courier_group.write({'users': [(3, user.id)]})

    @api.constrains('courier_user_id', 'company_id')
    def _check_courier_user_unique(self):
        for carrier in self.filtered('courier_user_id'):
            if self.search_count([
                ('courier_user_id', '=', carrier.courier_user_id.id),
                ('company_id', '=', carrier.company_id.id),
                ('id', '!=', carrier.id)
            ]) > 0:
                raise ValidationError(
                    f'Usuario {carrier.courier_user_id.name} ya asignado a otro courier en esta compañía.'
                )

    def action_view_pricing_rules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reglas de Precio',
            'res_model': 'courier.pricing.rule',
            'view_mode': 'list,form',
            'domain': [('carrier_id', '=', self.id)],
            'context': {'default_carrier_id': self.id}
        }

    def action_view_shipments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Envíos',
            'res_model': 'courier.shipment',
            'view_mode': 'list,form',
            'domain': [('carrier_id', '=', self.id)],
            'context': {'default_carrier_id': self.id}
        }