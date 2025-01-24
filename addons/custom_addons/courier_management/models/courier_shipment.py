from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

SHIPMENT_STATES = [
    ('draft', 'Borrador'),
    ('scheduled', 'Programado'),
    ('in_transit', 'En Tránsito'),
    ('delivered', 'Entregado'),
    ('failed', 'No Entregado'),
    ('cancelled', 'Cancelado'),
    ('despachado', 'Despachado')
]

STATE_TRANSITIONS = {
    'draft': ['scheduled', 'cancelled', 'despachado', 'in_transit'],
    'scheduled': ['in_transit', 'cancelled'],
    'in_transit': ['delivered', 'failed', 'cancelled'],
    'delivered': [],
    'failed': ['scheduled'],
    'cancelled': ['draft'],
    'despachado': ['in_transit', 'cancelled']
}


class CourierShipment(models.Model):
    _name = 'courier.shipment'
    _description = 'Courier Shipment'
    _order = 'shipping_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    # Campos Básicos
    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id',
        store=True
    )
    
    # Campos Relacionales Principales
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    district_id = fields.Many2one(
        'l10n_pe.res.city.district',
        string='Distrito',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    
    # Campos de Estado y Fechas
    state = fields.Selection(
        SHIPMENT_STATES,
        default='draft',
        tracking=True,
        index=True
    )
    shipping_date = fields.Date(
        string='Fecha de Programación',
        tracking=True,
        index=True
    )
    delivery_date = fields.Datetime(
        string='Fecha de Entrega',
        required=True,
        tracking=True,
        index=True
    )
    
    # Campos de Seguimiento
    tracking_code = fields.Char(
        string='Código de Rastreo',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
        index=True
    )
    selected = fields.Boolean(
        string='Seleccionado',
        default=False
    )
    
    # Campos Financieros
    delivery_fee = fields.Float(
        string='Costo de Envío',
        digits='Product Price',
        tracking=True
    )
    actual_delivery_fee = fields.Float(
        string='Costo Real',
        digits='Product Price',
        tracking=True
    )
    
    # Campos Relacionados
    partner_id = fields.Many2one(
        'res.partner',
        related='sale_order_id.partner_id',
        store=True,
        index=True
    )
    user_id = fields.Many2one(
        'res.users',
        related='carrier_id.courier_user_id',
        store=True,
        index=True
    )
    initial_status = fields.Selection(
        related='sale_order_id.x_initial_status',
        store=True,
        readonly=True
    )
    order_amount_total = fields.Monetary(
        related='sale_order_id.amount_total',
        store=True
    )
    
    settlement_state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)


    notes = fields.Text(string="Notas")

    # Campos Computados
    deliverable_lines = fields.Many2many(
        'sale.order.line',
        'courier_shipment_order_line_rel',
        'shipment_id',
        'order_line_id',
        compute='_compute_deliverable_lines',
        store=True
    )
    
    courier_stats = fields.Json(
        compute='_compute_courier_stats',
        store=True
    )
    
    is_ready_for_dispatch = fields.Boolean(
        compute='_compute_ready_for_dispatch',
        store=True,
        index=True
    )

    # Constraint SQL
    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)', 
         'La referencia del envío debe ser única por compañía!')
    ]

    # Métodos Computados
    @api.depends('sale_order_id.order_line')
    def _compute_deliverable_lines(self):
        for shipment in self.filtered('sale_order_id'):
            shipment.deliverable_lines = shipment.sale_order_id.order_line.filtered(
                lambda l: l.product_id.type in ['product', 'consu']
            )

    @api.depends('carrier_id', 'deliverable_lines', 'order_amount_total', 'state')
    def _compute_courier_stats(self):
        for shipment in self:
            total_products = sum(line.product_uom_qty for line in shipment.deliverable_lines)
            shipment.courier_stats = {
                'total_products': total_products,
                'total_to_collect': shipment.order_amount_total,
                'pending_orders': 1 if shipment.state == 'draft' else 0
            }

    @api.depends('state', 'sale_order_id.state')
    def _compute_ready_for_dispatch(self):
        for shipment in self:
            shipment.is_ready_for_dispatch = (
                shipment.state == 'draft' and 
                shipment.sale_order_id.state == 'sale'
            )

    # Métodos ORM
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('courier.shipment') or 'New'
            if vals.get('tracking_code', 'New') == 'New':
                vals['tracking_code'] = self.env['ir.sequence'].next_by_code('courier.shipment.tracking') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals:
            self._validate_state_transition(vals['state'])
            
        result = super().write(vals)
        
        if not self._context.get('no_propagate_to_sale_order') and 'state' in vals:
            orders_to_update = self.mapped('sale_order_id')
            if orders_to_update:
                orders_to_update.with_context(
                    no_propagate_to_shipment=True
                ).write({'x_initial_status': vals['state']})
        
        return result

    # Métodos de Transición de Estado
    def _validate_state_transition(self, new_state):
        for record in self:
            if new_state not in STATE_TRANSITIONS.get(record.state, []):
                raise UserError(f'Transición no válida de {record.state} a {new_state}')

    def action_schedule(self):
        self._validate_state_transition('scheduled')
        return self.write({'state': 'scheduled'})

    def action_in_transit(self):
        self._validate_state_transition('in_transit')
        return self.write({'state': 'in_transit'})

    def action_deliver(self):
        self._validate_state_transition('delivered')
        return self.write({
            'state': 'delivered',
            'delivery_date': fields.Datetime.now()
        })

    def action_fail(self):
        self._validate_state_transition('failed')
        return self.write({'state': 'failed'})

    def action_cancel(self):
        self._validate_state_transition('cancelled')
        return self.write({'state': 'cancelled'})

    # Métodos de Negocio
    def _update_delivery_fee(self):
        PricingRule = self.env['courier.pricing.rule']
        for shipment in self:
            if not (shipment.carrier_id and shipment.district_id):
                continue

            domain = [
                ('carrier_id', '=', shipment.carrier_id.id),
                ('district_id', '=', shipment.district_id.id)
            ]
            
            if shipment.district_id.city_id:
                domain += [
                    ('city_id', '=', shipment.district_id.city_id.id),
                    ('state_id', '=', shipment.district_id.city_id.state_id.id)
                ]

            pricing_rule = PricingRule.search(domain, limit=1)
            
            if pricing_rule:
                shipment.delivery_fee = pricing_rule.price
                shipment.message_post(body=f"Tarifa actualizada a {pricing_rule.price}")
            else:
                shipment.delivery_fee = 0.0
                shipment.message_post(body="No se encontró regla de precio")

    @api.onchange('carrier_id', 'district_id')
    def _onchange_calculate_fee(self):
        self._update_delivery_fee()

    # Acciones especiales
    def action_dispatch_selected(self):
        """Marca los envíos seleccionados como despachados"""
        self.filtered(lambda s: s.state == 'draft' and s.sale_order_id).write({
            'state': 'despachado'
        })
        
        # Actualizar órdenes de venta en una sola operación
        orders_to_update = self.mapped('sale_order_id')
        if orders_to_update:
            orders_to_update.with_context(
                no_propagate_to_shipment=True
            ).write({'x_initial_status': 'despachado'})

    def action_print_carrier_labels(self):
        """Imprime las etiquetas de los envíos seleccionados"""
        self.ensure_one()
        if not self:
            raise UserError("Seleccione al menos un envío para imprimir etiquetas.")
        return self.env.ref('courier_management.action_labels_report').report_action(self)

    def _action_open_verification_wizard(self):
        """Abre el wizard de verificación de stock"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.verification.wizard',
            'view_mode': 'form',
            'name': 'Verificación de Envíos',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_ids': self.ids,
                'active_id': len(self) == 1 and self.id or False,
            }
        }

    def action_entregado_nuevo(self):
        """Marca el envío como entregado"""
        self.ensure_one()
        if self.state != 'in_transit':
            raise UserError("Solo puedes marcar como entregado envíos en tránsito.")
            
        values = {
            'state': 'delivered',
            'delivery_date': fields.Datetime.now()
        }
        
        self.write(values)
        
        if self.sale_order_id:
            self.sale_order_id.with_context(
                no_propagate_to_shipment=True
            ).write({'x_initial_status': 'entregado'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Éxito',
                'message': 'Envío marcado como entregado',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'}
            }
        }

    def action_reprogramar(self):
        """Abre el wizard de reprogramación"""
        self.ensure_one()
        if self.state not in ['in_transit', 'scheduled']:
            raise UserError(
                "Solo puedes reprogramar envíos en estado 'En Tránsito' o 'Programado'."
            )
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reprogramar.wizard',
            'view_mode': 'form',
            'name': 'Reprogramar Envío',
            'target': 'new',
            'context': {
                'default_shipment_id': self.id,
                'default_new_delivery_date': self.delivery_date
            }
        }

    def action_no_entregado_nuevo(self):
        """Abre el wizard de no entregado"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'no.entregado.wizard',
            'view_mode': 'form',
            'name': 'Marcar No Entregado',
            'target': 'new',
            'context': {'default_shipment_id': self.id}
        }

    def action_select_group(self):
        """Selecciona envíos del mismo grupo"""
        self.ensure_one()
        current_date = self.delivery_date.date()
        
        domain = [
            ('delivery_date', '>=', f"{current_date} 00:00:00"),
            ('delivery_date', '<=', f"{current_date} 23:59:59"),
            ('initial_status', 'in', ['confirmed', 'reprogramado'])
        ]
        
        self.search(domain).write({'selected': True})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

class CourierShipmentProductSummary(models.Model):
    _name = 'courier.shipment.product.summary'
    _description = 'Resumen de Productos por Courier'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company
    )
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier',
        required=True,
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        index=True
    )
    quantity_required = fields.Float(
        string='Cantidad Requerida'
    )
    quantity_available = fields.Float(
        string='Cantidad Disponible',
        related='product_id.qty_available'
    )
    shipped_quantity = fields.Float(
        string='Cantidad a Despachar'
    )
    summary_id = fields.Many2one(
        'courier.shipment',
        string='Resumen',
        required=True,
        ondelete='cascade',
        index=True
    )
    pending_shipment_ids = fields.Many2many(
        'courier.shipment',
        'shipment_summary_rel',
        'summary_id',
        'shipment_id',
        string='Envíos Pendientes'
    )

    @api.constrains('quantity_required', 'shipped_quantity')
    def _check_quantities(self):
        for record in self:
            if record.shipped_quantity > record.quantity_required:
                raise UserError(
                    f"La cantidad a despachar no puede ser mayor que la requerida "
                    f"para el producto {record.product_id.name}"
                )