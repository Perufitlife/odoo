from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    city_id = fields.Many2one(
        'res.city',
        string='Ciudad',
        domain="[('state_id', '=', state_id)]"
    )

    # Usamos únicamente el campo oficial de la localización peruana:
    l10n_pe_district = fields.Many2one(
        'l10n_pe.res.city.district',
        string="Distrito (PE)",
        domain="[('city_id', '=', city_id)]",
        tracking=True,
        help="Distrito oficial para localización en Perú."
    )

    preferred_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier Preferido',
        tracking=True,
        help="Courier preferido para los envíos de este cliente"
    )

    shipment_count = fields.Integer(
        string='Cantidad de Envíos',
        compute='_compute_shipment_count',
        help="Número total de envíos realizados para este cliente"
    )

    total_shipment_amount = fields.Monetary(
        string='Total en Envíos',
        compute='_compute_shipment_stats',
        help="Monto total gastado en envíos"
    )

    last_shipment_date = fields.Date(
        string='Último Envío',
        compute='_compute_shipment_stats',
        help="Fecha del último envío realizado"
    )

    # =========================================================================
    # Cálculos para conteo y estadísticas de envíos
    # =========================================================================
    @api.depends('write_date')
    def _compute_shipment_count(self):
        for partner in self:
            partner.shipment_count = self.env['courier.shipment'].search_count([
                ('partner_id', '=', partner.id)
            ])

    @api.depends('write_date')
    def _compute_shipment_stats(self):
        for partner in self:
            shipments = self.env['courier.shipment'].search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'delivered')
            ])
            partner.total_shipment_amount = sum(shipments.mapped('delivery_fee'))
            partner.last_shipment_date = max(shipments.mapped('delivery_date'), default=False)

    # =========================================================================
    # Onchange para limpiar campos de localización cuando se cambie otro superior
    # =========================================================================
    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Al cambiar país, limpiar state, city y distrito PE."""
        self.state_id = False
        self.city_id = False
        self.l10n_pe_district = False

    @api.onchange('state_id')
    def _onchange_state_id(self):
        """Al cambiar estado, limpiar ciudad y distrito PE."""
        self.city_id = False
        self.l10n_pe_district = False

    @api.onchange('city_id')
    def _onchange_city_id(self):
        """Al cambiar city_id, forzamos city y limpiamos distrito."""
        self.l10n_pe_district = False
        if self.city_id:
            # Copiar city_id.name a city
            self.city = self.city_id.name

            if self.city_id.state_id:
                self.state_id = self.city_id.state_id
                if self.state_id.country_id:
                    self.country_id = self.state_id.country_id
            else:
                self.state_id = False
                self.country_id = False
        else:
            self.city = False

    # =========================================================================
    # Acción para ver envíos asociados a este partner
    # =========================================================================
    def action_view_shipments(self):
        """Acción para ver los envíos relacionados al cliente."""
        self.ensure_one()
        action = {
            'name': 'Envíos',
            'type': 'ir.actions.act_window',
            'res_model': 'courier.shipment',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
                'default_carrier_id': self.preferred_carrier_id.id,
                'default_l10n_pe_district': self.l10n_pe_district.id,
            }
        }

        shipment_count = self.env['courier.shipment'].search_count([
            ('partner_id', '=', self.id)
        ])
        if shipment_count == 1:
            shipment = self.env['courier.shipment'].search([
                ('partner_id', '=', self.id)
            ], limit=1)
            action.update({
                'view_mode': 'form',
                'res_id': shipment.id,
            })
        return action

    # =========================================================================
    # Métodos CREATE / WRITE unificados
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """
        1) Valida l10n_pe_district y city_id pertenecientes a Perú, 
        2) Copia city_id.name a city si no está definido, 
        para manejar casos en que se crea sin pasar por onchange (webhooks).
        """
        for vals in vals_list:

            # --- (A) Validaciones de distrito
            if vals.get('l10n_pe_district'):
                district = self.env['l10n_pe.res.city.district'].browse(vals['l10n_pe_district'])
                # Validar país = Perú
                if (
                    district.city_id
                    and district.city_id.state_id
                    and district.city_id.state_id.country_id.code != 'PE'
                ):
                    raise ValidationError('El distrito debe pertenecer a Perú.')

                # Validar ciudad
                if vals.get('city_id') and district.city_id.id != vals['city_id']:
                    raise ValidationError('El distrito debe pertenecer a la ciudad seleccionada.')

            # --- (B) city_id -> city
            if vals.get('city_id'):
                city_rec = self.env['res.city'].browse(vals['city_id'])
                if city_rec and not vals.get('city'):
                    vals['city'] = city_rec.name

        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        """
        1) Valida l10n_pe_district y city_id, 
        2) city_id -> city si no está definido,
        cuando se editan partners existentes.
        """
        # --- (A) Validaciones de distrito
        if 'l10n_pe_district' in vals and vals['l10n_pe_district']:
            district = self.env['l10n_pe.res.city.district'].browse(vals['l10n_pe_district'])
            # Validar país = Perú
            if (
                district.city_id
                and district.city_id.state_id
                and district.city_id.state_id.country_id.code != 'PE'
            ):
                raise ValidationError('El distrito debe pertenecer a Perú.')

            # Validar que el distrito pertenezca a la ciudad dada
            if 'city_id' in vals and vals['city_id']:
                if district.city_id.id != vals['city_id']:
                    raise ValidationError('El distrito debe pertenecer a la ciudad seleccionada.')

        # --- (B) city_id -> city
        if 'city_id' in vals and vals['city_id']:
            city_rec = self.env['res.city'].browse(vals['city_id'])
            if city_rec and not vals.get('city'):
                vals['city'] = city_rec.name

        return super(ResPartner, self).write(vals)
