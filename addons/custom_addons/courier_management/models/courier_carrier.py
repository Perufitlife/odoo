from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class CourierCarrier(models.Model):
    _inherit = 'delivery.carrier'
    _description = 'Courier Carrier'

    # [INICIO CAMBIO] =========================================================
    auto_in_transit = fields.Boolean(
        string="Despacho Inmediato",
        help="Si se activa, tras verificar stock, el envío pasa directamente a 'in_transit'. "
             "Si está desactivado, pasa primero a 'despachado'."
    )
    # [FIN CAMBIO] ============================================================

    courier_user_id = fields.Many2one(
        'res.users',
        string='Usuario Courier',
        tracking=True,
        help="Usuario que tendrá acceso a los envíos asignados a este courier"
    )
    active = fields.Boolean(
        default=True,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company.id,
        tracking=True
    )
    pricing_rule_count = fields.Integer(
        string='Reglas de Precio',
        compute='_compute_pricing_rule_count',
        store=False
    )
    shipment_count = fields.Integer(
        string='Envíos',
        compute='_compute_shipment_count',
        store=False
    )

    # -------------------------------------------------------------------------
    # MÉTODOS DE ODOO (Create, Write, Unlink, etc.)
    # -------------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        """Establece la compañía por defecto al crear un carrier."""
        res = super().default_get(fields_list)
        if 'company_id' not in res:
            res['company_id'] = self.env.company.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Crea carriers y asigna el usuario al grupo courier si corresponde."""
        for vals in vals_list:
            if 'company_id' not in vals:
                vals['company_id'] = self.env.company.id
        records = super().create(vals_list)

        # Añadir el usuario courier al grupo específico
        courier_group = self.env.ref('courier_management.group_courier_user', raise_if_not_found=False)
        if courier_group:
            for record in records:
                if record.courier_user_id:
                    courier_group.write({'users': [(4, record.courier_user_id.id)]})
        return records

    def write(self, vals):
        """Gestiona los cambios de usuario courier y actualiza el grupo."""
        # Guardar usuarios antiguos para comparar
        old_user_ids = {carrier.id: carrier.courier_user_id.id for carrier in self if carrier.courier_user_id}

        result = super().write(vals)

        # Si se cambió el courier_user_id, actualizar el grupo
        if 'courier_user_id' in vals:
            courier_group = self.env.ref('courier_management.group_courier_user', raise_if_not_found=False)
            if courier_group:
                # Remover usuarios antiguos si ya no están asignados a ningún carrier
                for carrier in self:
                    old_user_id = old_user_ids.get(carrier.id)
                    # Si había usuario anterior y es diferente del nuevo
                    if old_user_id and old_user_id != carrier.courier_user_id.id:
                        other_carriers = self.search([
                            ('courier_user_id', '=', old_user_id),
                            ('id', '!=', carrier.id)
                        ])
                        # Si no hay otro carrier con ese usuario, removerlo del grupo
                        if not other_carriers:
                            courier_group.write({'users': [(3, old_user_id)]})
                    
                    # Agregar el nuevo usuario al grupo si existe
                    if carrier.courier_user_id:
                        courier_group.write({'users': [(4, carrier.courier_user_id.id)]})

        return result

    def unlink(self):
        """Al eliminar carriers, remover sus usuarios del grupo si corresponde."""
        user_ids = self.mapped('courier_user_id').ids
        result = super().unlink()

        # Remover usuarios del grupo si ya no están asignados a ningún carrier
        if user_ids:
            courier_group = self.env.ref('courier_management.group_courier_user', raise_if_not_found=False)
            if courier_group:
                for user_id in user_ids:
                    other_carriers = self.search([('courier_user_id', '=', user_id)])
                    if not other_carriers:
                        courier_group.write({'users': [(3, user_id)]})
        return result

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------
    @api.constrains('courier_user_id')
    def _check_courier_user_unique(self):
        """Evita que un mismo usuario sea asignado a dos couriers en la misma empresa."""
        for carrier in self:
            if carrier.courier_user_id:
                other_carriers = self.search([
                    ('courier_user_id', '=', carrier.courier_user_id.id),
                    ('id', '!=', carrier.id),
                    ('company_id', '=', carrier.company_id.id)
                ])
                if other_carriers:
                    raise ValidationError(
                        f'El usuario {carrier.courier_user_id.name} '
                        'ya está asignado a otro courier en esta compañía.'
                    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('courier_user_id')
    def _compute_pricing_rule_count(self):
        """Calcula la cantidad de reglas de precio asociadas."""
        for carrier in self:
            carrier.pricing_rule_count = self.env['courier.pricing.rule'].search_count([
                ('carrier_id', '=', carrier.id)
            ])

    @api.depends('courier_user_id')
    def _compute_shipment_count(self):
        """Calcula la cantidad de envíos asociada a este carrier."""
        for carrier in self:
            carrier.shipment_count = self.env['courier.shipment'].search_count([
                ('carrier_id', '=', carrier.id)
            ])

    # -------------------------------------------------------------------------
    # ACCIONES
    # -------------------------------------------------------------------------
    def action_view_pricing_rules(self):
        """Abre la vista de reglas de precio filtrada por este carrier."""
        self.ensure_one()
        return {
            'name': 'Reglas de Precio',
            'type': 'ir.actions.act_window',
            'res_model': 'courier.pricing.rule',
            'view_mode': 'list,form',
            'domain': [('carrier_id', '=', self.id)],
            'context': {
                'default_carrier_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

    def action_view_shipments(self):
        """Abre la vista de envíos filtrada por este carrier."""
        self.ensure_one()
        return {
            'name': 'Envíos',
            'type': 'ir.actions.act_window',
            'res_model': 'courier.shipment',
            'view_mode': 'list,form',
            'domain': [('carrier_id', '=', self.id)],
            'context': {
                'default_carrier_id': self.id,
                'default_company_id': self.company_id.id
            },
        }
