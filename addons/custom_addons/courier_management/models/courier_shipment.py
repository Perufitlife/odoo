from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class CourierShipmentProductSummary(models.Model):
    _name = 'courier.shipment.product.summary'
    _description = 'Resumen de Productos por Courier'

    carrier_id = fields.Many2one('delivery.carrier', string='Courier')
    product_id = fields.Many2one('product.product', string='Producto')
    quantity_required = fields.Float(string='Cantidad Requerida')
    quantity_available = fields.Float(
        string='Cantidad Disponible', 
        related='product_id.qty_available'
    )
    shipped_quantity = fields.Float(string='Cantidad a Despachar')
    summary_id = fields.Many2one(
        'courier.shipment',
        string='Resumen'
    )
    pending_shipment_ids = fields.Many2many(
        'courier.shipment',
        'shipment_summary_rel',
        'summary_id',
        'shipment_id',
        string='Envíos Pendientes'
    )


class CourierShipment(models.Model):
    _name = 'courier.shipment'
    _description = 'Courier Shipment'
    _order = 'shipping_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # -------------------------------------------------------------------------
    # CAMPOS PRINCIPALES
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        tracking=True
    )
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier',
        required=True,
        tracking=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Courier',
        related='carrier_id.courier_user_id',
        store=True,
        tracking=True
    )
    shipping_date = fields.Date(
        string='Fecha de Programación',
        tracking=True
    )
    delivery_date = fields.Datetime(
        string='Fecha de Entrega',
        required=True,
        tracking=True
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('scheduled', 'Programado'),
            ('in_transit', 'En Tránsito'),
            ('delivered', 'Entregado'),
            ('failed', 'No Entregado'),
            ('cancelled', 'Cancelado'),
            ('despachado', 'Despachado')  # <--- NUEVO ESTADO
        ],
        string='Estado',
        default='draft',
        tracking=True
    )

    district_id = fields.Many2one(
        'l10n_pe.res.city.district',
        string='Distrito',
        required=True,
        tracking=True
    )
    delivery_fee = fields.Float(
        string='Costo de Envío',
        digits='Product Price',
        tracking=True
    )

    tracking_code = fields.Char(
        string='Código de Rastreo',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )

    selected = fields.Boolean(
        string='Seleccionado',
        default=False,
        help='Campo para selección múltiple de envíos'
    )

    initial_status = fields.Selection(
        related='sale_order_id.x_initial_status',
        string='Estado Inicial',
        store=True,
        readonly=True
    )

    pending_orders_count = fields.Integer(
        string='Pedidos Pendientes',
        compute='_compute_courier_stats',
        store=True,
    )
    total_products = fields.Integer(
        string='Total Productos',
        compute='_compute_courier_stats',
        store=True,
    )
    total_to_collect = fields.Monetary(
        string='Total a Cobrar',
        compute='_compute_courier_stats',
        currency_field='currency_id',
        store=True,
    )

    # -------------------------------------------------------------------------
    # RELACIONES CON CLIENTE / ORDEN DE VENTA
    # -------------------------------------------------------------------------
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='sale_order_id.partner_id',
        store=True,
        tracking=True
    )
    customer_street = fields.Char(
        string='Dirección',
        related='sale_order_id.partner_id.street'
    )
    customer_city = fields.Char(
        string='Ciudad',
        related='sale_order_id.partner_id.city'
    )
    customer_state = fields.Char(
        string='Departamento',
        related='sale_order_id.partner_id.state_id.name'
    )
    customer_country = fields.Char(
        string='País',
        related='sale_order_id.partner_id.country_id.name'
    )

    # -------------------------------------------------------------------------
    # CAMPOS ADICIONALES (notas, liquidación, producto de envío)
    # -------------------------------------------------------------------------
    notes = fields.Text(
        string='Notas',
        tracking=True
    )
    actual_delivery_fee = fields.Float(
        string='Costo Real',
        digits='Product Price',
        tracking=True
    )
    settlement_state = fields.Selection(
        [
            ('pending', 'Pendiente'),
            ('settled', 'Liquidado')
        ],
        string='Estado de Liquidación',
        default='pending',
        tracking=True
    )
    settlement_date = fields.Date(
        string='Fecha de Liquidación',
        tracking=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto de Envío',
        domain="[('type', '=', 'service')]",
        tracking=True
    )

    deliverable_lines = fields.Many2many(
        'sale.order.line',
        'courier_shipment_order_line_rel',
        'shipment_id',
        'order_line_id',
        string='Líneas a Entregar',
        compute='_compute_deliverable_lines',
        store=True
    )

    order_amount_total = fields.Monetary(
        string='Total de la Orden',
        related='sale_order_id.amount_total',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='sale_order_id.currency_id'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )

    is_ready_for_dispatch = fields.Boolean(
        string='Listo para Despacho',
        compute='_compute_ready_for_dispatch',
        store=True,
        help='Indica si el envío está listo para ser despachado'
    )

    @api.depends('state', 'sale_order_id.state')
    def _compute_ready_for_dispatch(self):
        for shipment in self:
            shipment.is_ready_for_dispatch = (
                shipment.state == 'draft'
                and shipment.sale_order_id.state == 'sale'
            )

    # -------------------------------------------------------------------------
    # RESTRICCIONES Y CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        (
            'name_uniq',
            'unique(name, company_id)',
            'La referencia del envío debe ser única por compañía!'
        )
    ]

    # -------------------------------------------------------------------------
    # MÉTODOS CREATE/WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Generar un nombre único basado en la secuencia
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('courier.shipment') or 'New'

            # Generar un código de rastreo único si no está configurado
            if not vals.get('tracking_code') or vals['tracking_code'] == 'New':
                vals['tracking_code'] = self.env['ir.sequence'].next_by_code('courier.shipment.tracking') or 'New'
        return super(CourierShipment, self).create(vals_list)

    # -------------------------------------------------------------------------
    # CÓMPUTO DE LÍNEAS A ENTREGAR (deliverable_lines)
    # -------------------------------------------------------------------------
    @api.depends('sale_order_id.order_line')
    def _compute_deliverable_lines(self):
        """Filtra líneas de venta que sean de tipo 'product' o 'consu'."""
        for shipment in self:
            if shipment.sale_order_id:
                lines = shipment.sale_order_id.order_line.filtered(
                    lambda l: l.product_id.type in ['product', 'consu']
                )
                shipment.deliverable_lines = lines
            else:
                shipment.deliverable_lines = False

    # -------------------------------------------------------------------------
    # ACCIONES DE CAMBIO DE ESTADO
    # -------------------------------------------------------------------------
    def action_schedule(self):
        for shipment in self:
            if shipment.state != 'draft':
                raise UserError("Solo puedes programar envíos en estado Borrador.")
            shipment.state = 'scheduled'
            shipment.message_post(body="Envío programado.")

    def action_in_transit(self):
        for shipment in self:
            if shipment.state != 'scheduled':
                raise UserError("Solo puedes marcar como 'En Tránsito' envíos programados.")
            shipment.state = 'in_transit'
            shipment.message_post(body="Envío en tránsito.")

    def action_deliver(self):
        for shipment in self:
            if shipment.state != 'in_transit':
                raise UserError("Solo puedes marcar como 'Entregado' envíos en tránsito.")
            shipment.write({
                'state': 'delivered',
                'delivery_date': fields.Datetime.now()
            })
            shipment.message_post(body="Envío entregado.")

    def action_fail(self):
        for shipment in self:
            if shipment.state != 'in_transit':
                raise UserError("Solo puedes marcar como 'No Entregado' envíos en tránsito.")
            shipment.state = 'failed'
            shipment.message_post(body="Envío no entregado.")

    def action_cancel(self):
        for shipment in self:
            if shipment.state in ['delivered', 'failed', 'cancelled']:
                raise UserError("No puedes cancelar un envío que ya está entregado, fallido o cancelado.")
            shipment.state = 'cancelled'
            shipment.message_post(body="Envío cancelado.")

    def action_reset_to_draft(self):
        """Devuelve el envío al estado Borrador, si no ha sido entregado o fallido."""
        self.ensure_one()
        if self.state in ['delivered', 'failed']:
            raise UserError("No se puede restablecer a borrador un envío entregado o fallido.")
        self.state = 'draft'
        self.message_post(body="Envío restablecido a borrador.")

    # -------------------------------------------------------------------------
    # CÁLCULO DE FEE AL CAMBIAR CARRIER O DISTRITO
    # -------------------------------------------------------------------------
    @api.onchange('carrier_id', 'district_id')
    def _onchange_calculate_fee(self):
        """Actualiza el delivery_fee con base a la regla de precio."""
        self._update_delivery_fee()

    def _update_delivery_fee(self):
        """Busca la regla de precio según carrier/distrito y actualiza el delivery_fee."""
        for shipment in self:
            if shipment.carrier_id and shipment.district_id:
                domain = [
                    ('carrier_id', '=', shipment.carrier_id.id),
                    (
                        'state_id',
                        '=',
                        shipment.district_id.city_id.state_id.id
                        if shipment.district_id.city_id
                           and shipment.district_id.city_id.state_id
                        else False
                    ),
                    (
                        'city_id',
                        '=',
                        shipment.district_id.city_id.id
                        if shipment.district_id.city_id
                        else False
                    ),
                    ('district_id', '=', shipment.district_id.id)
                ]
                pricing_rule = self.env['courier.pricing.rule'].search(domain, limit=1)
                if pricing_rule:
                    shipment.delivery_fee = pricing_rule.price
                    if shipment.id:
                        shipment.message_post(body=f"Tarifa actualizada a {pricing_rule.price}")
                else:
                    shipment.delivery_fee = 0.0
                    if shipment.id:
                        shipment.message_post(body="No se encontró regla de precio para esta configuración")

    # -------------------------------------------------------------------------
    # MARCAR ENVIOS COMO DESPACHADOS
    # -------------------------------------------------------------------------
    def action_dispatch_selected(self):
        """Marca los envíos seleccionados como despachados"""
        for shipment in self:
            if shipment.state == 'draft' and shipment.sale_order_id:
                _logger.info(f'Procesando envío {shipment.name}')
                _logger.info(f'Estado inicial actual: {shipment.sale_order_id.x_initial_status}')

                # Actualizar el estado del envío
                shipment.write({'state': 'despachado'})

                # Actualizar el estado inicial de la orden de venta
                try:
                    shipment.sale_order_id.write({
                        'x_initial_status': 'despachado'
                    })
                    _logger.info(f'Estado inicial actualizado a: {shipment.sale_order_id.x_initial_status}')
                except Exception as e:
                    _logger.error(f'Error al actualizar estado inicial: {str(e)}')

                shipment.message_post(body="Envío y estado inicial marcados como despachado")

    def action_print_carrier_labels(self):
        """Imprime las etiquetas de los envíos seleccionados agrupados por courier"""
        if not self:
            raise UserError("Debe seleccionar al menos un envío para imprimir etiquetas.")

        return self.env.ref('courier_management.action_labels_report').report_action(self)

    @api.depends('carrier_id', 'deliverable_lines', 'order_amount_total', 'state')
    def _compute_courier_stats(self):
        for shipment in self:
            # Contar productos
            total_products = 0
            for line in shipment.deliverable_lines:
                total_products += line.product_uom_qty

            shipment.total_products = total_products
            shipment.total_to_collect = shipment.order_amount_total
            shipment.pending_orders_count = 1 if shipment.state == 'draft' else 0

    # [INICIO CAMBIO] =========================================================
    def _action_open_verification_wizard(self):
        """
        Retorna la acción para abrir el wizard 'shipment.verification.wizard',
        pasándole los IDs de los envíos seleccionados.
        (Lo usaremos para un botón "Verificar Stock" en el Panel de Despacho)
        """
        ctx = {
            'active_model': 'courier.shipment',
            'active_ids': self.ids,
            'active_id': len(self) == 1 and self.id or False,
        }

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.verification.wizard',
            'view_mode': 'form',
            'name': 'Verificación de Envíos',
            'target': 'new',
            'context': ctx,
        }
    # [FIN CAMBIO] =========================================================

    # [INICIO ETAPA 2: Métodos Nuevos]
    def action_entregado_nuevo(self):
        """Marcar envío como entregado y actualizar estado inicial"""
        self.ensure_one()
        
        if self.state != 'in_transit':
            raise UserError("Solo puedes marcar como entregado envíos en tránsito.")

        # Actualizar estado del envío
        self.write({
            'state': 'delivered',
            'delivery_date': fields.Datetime.now()
        })

        # Actualizar estado inicial en orden de venta
        if self.sale_order_id:
            self.sale_order_id.write({
                'x_initial_status': 'entregado'
            })

        # Registrar en el chatter
        self.message_post(body="El envío ha sido entregado correctamente")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Éxito',
                'message': 'El envío ha sido marcado como entregado',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }

    def action_reprogramar(self):
        """Abre el wizard de reprogramación"""
        self.ensure_one()
        
        if self.state not in ['in_transit', 'scheduled']:
            raise UserError("Solo puedes reprogramar envíos en estado 'En Tránsito' o 'Programado'.")

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

    def write(self, vals):
        """Sobrescribimos write para evitar bucles infinitos"""
        # Si estamos actualizando el estado, no queremos que se propague al sale_order
        if 'state' in vals and self._context.get('no_propagate_to_sale_order'):
            return super().write(vals)
        
        result = super().write(vals)
        
        # Solo propagamos cambios a la orden de venta si no estamos en un contexto especial
        if not self._context.get('no_propagate_to_sale_order'):
            for record in self:
                if record.sale_order_id and 'state' in vals:
                    # Usamos un nuevo contexto para evitar el bucle
                    record.sale_order_id.with_context(no_propagate_to_shipment=True).write({
                        'x_initial_status': vals.get('state', record.state)
                    })
        
        return result

    def action_no_entregado_nuevo(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'no.entregado.wizard',
            'view_mode': 'form',
            'name': 'Marcar No Entregado',
            'target': 'new',
            'context': {
                'default_shipment_id': self.id
            }
        }

    def action_consultas(self):
        """Botón 'Consultas' (placeholder). Podríamos abrir un wizard."""
        self.ensure_one()
        self.message_post(body="Se presionó el botón Consultas (placeholder).")
        return
    # [FIN ETAPA 2: Métodos Nuevos]


    def action_select_group(self):
        """Selecciona todos los registros del grupo actual."""
        # Obtener la fecha del registro actual
        current_date = self.delivery_date.date()
        
        # Buscar todos los registros del mismo día
        domain = [
            ('delivery_date', '>=', current_date.strftime('%Y-%m-%d 00:00:00')),
            ('delivery_date', '<=', current_date.strftime('%Y-%m-%d 23:59:59')),
            '|',
            ('initial_status', '=', 'confirmed'),
            ('initial_status', '=', 'reprogramado')
        ]
        
        records = self.search(domain)
        records.write({'selected': True})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }