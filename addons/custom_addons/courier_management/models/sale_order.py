from datetime import timedelta
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shipment_ids = fields.One2many(
        'courier.shipment',
        'sale_order_id',
        string='Envíos'
    )
    shipment_count = fields.Integer(
        string='Cantidad de Envíos',
        compute='_compute_shipment_count'
    )
    delivery_count = fields.Integer(
        string='Delivery Orders',
        compute='_compute_delivery_count'
    )
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Transportista'
    )

    partner_phone = fields.Char(
        string='Teléfono del Cliente',
        related='partner_id.phone',
        readonly=True,
        store=True
    )

    partner_district = fields.Many2one(
        'l10n_pe.res.city.district',
        string='Distrito del Cliente',
        related='partner_id.l10n_pe_district',
        readonly=True,
        store=True
    )


    # Campo de estado inicial para tu flujo personalizado
    x_initial_status = fields.Selection([
        ('draft', 'Borrador'),
        ('whatsapp', 'Whatsapp'),
        ('abandoned_cart', 'Carrito Abandonado'),
        ('order_completed', 'Orden Completa'),
        ('scheduled', 'Programado'),  # Se mantiene aquí por si necesitas en otro punto
        ('pending', 'Pendiente'),  # Se mantiene aquí por si necesitas en otro punto
        ('confirmed', 'Confirmado'),
        ('esperando_adelanto', 'Esperando Adelanto'),
        ('despachado', 'Despachado'),
        ('in_transit', 'En Tránsito'),
        ('delivered', 'Entregado'),
        ('failed', 'No Entregado'),
        ('cancelled', 'Cancelado'),
        ('reprogramado', 'Reprogramado'),
    ], string='Estado Inicial', default='whatsapp', tracking=True)

    # =========================================================================
    # Cómputos de conteo de Envíos y Delivery
    # =========================================================================
    @api.depends('shipment_ids')
    def _compute_shipment_count(self):
        for order in self:
            order.shipment_count = len(order.shipment_ids)

    def action_view_shipments(self):
        """Abre la vista de Envíos filtrada por esta orden de venta."""
        self.ensure_one()
        action = {
            'name': 'Envíos',
            'type': 'ir.actions.act_window',
            'res_model': 'courier.shipment',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }
        if self.shipment_count == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.shipment_ids.id,
            })
        return action

    @api.depends('picking_ids')
    def _compute_delivery_count(self):
        """Cuenta las transferencias (picking) relacionadas."""
        for order in self:
            order.delivery_count = len(order.picking_ids)

    # =========================================================================
    # Onchange para asignar automáticamente un carrier según la regla de precios
    # =========================================================================
    @api.onchange('partner_id')
    def _onchange_partner_id_custom(self):
        """Si el partner tiene distrito configurado, buscar reglas de precios
           y asignar el carrier más barato como predeterminado."""
        if self.partner_id and self.partner_id.l10n_pe_district:
            district = self.partner_id.l10n_pe_district
            pricing_rules = self.env['courier.pricing.rule'].search([
                ('district_id', '=', district.id)
            ])
            if pricing_rules:
                carriers = pricing_rules.mapped('carrier_id')
                cheapest_rule = pricing_rules.sorted(key=lambda rule: rule.price, reverse=False)[:1]
                if cheapest_rule:
                    self.carrier_id = cheapest_rule.carrier_id

                return {
                    'domain': {
                        'carrier_id': [('id', 'in', carriers.ids)]
                    }
                }
            else:
                self.carrier_id = False
                return {
                    'domain': {
                        'carrier_id': [('id', '=', False)]
                    }
                }
        else:
            self.carrier_id = False
            return {
                'domain': {
                    'carrier_id': [('id', '=', False)]
                }
            }

    @api.onchange('carrier_id')
    def _onchange_carrier_id_custom(self):
        """Si se cambia manualmente el carrier, recalcular el costo de envío y establecer fecha de entrega."""
        if self.carrier_id:
            if not self.commitment_date:
                self.commitment_date = fields.Datetime.now() + timedelta(days=1)
            self._compute_shipping_cost()

    # =========================================================================
    # Confirmación de la Orden => Crear courier.shipment
    # =========================================================================
    def action_confirm(self):
        """
        Valida que se asigne un transportista antes de confirmar la orden.
        Crea un registro en courier.shipment para que el transportista pueda verlo.
        """
        for order in self:
            if not order.commitment_date:
                raise UserError(
                    "Debe establecer una fecha de entrega antes de confirmar la orden."
                )

            # Validar que el cliente tenga un distrito configurado
            if not order.partner_id.l10n_pe_district:
                raise UserError(
                    "El cliente no tiene un distrito configurado. Por favor, actualiza la dirección del cliente antes de confirmar la orden."
                )

            # Intentar asignar transportista si no está configurado
            if not order.carrier_id:
                district = order.partner_id.l10n_pe_district
                pricing_rules = self.env['courier.pricing.rule'].search([
                    ('district_id', '=', district.id)
                ])

                if pricing_rules:
                    cheapest_rule = pricing_rules.sorted(key=lambda rule: rule.price, reverse=False)[:1]
                    if cheapest_rule:
                        order.carrier_id = cheapest_rule.carrier_id
                        _logger.info(
                            f"Transportista asignado automáticamente: {cheapest_rule.carrier_id.name} para la orden {order.name}"
                        )
                    else:
                        raise UserError(
                            f"No se encontró un transportista para el distrito {district.name}. "
                            "Por favor, configure una regla de precios para este distrito."
                        )
                else:
                    raise UserError(
                        f"No se encontró una regla de precios para el distrito {district.name}. "
                        "Por favor, configure una regla de precios antes de confirmar la orden."
                    )

            if not order.carrier_id:
                raise UserError(
                    "No se pudo asignar un transportista a la orden. Por favor, configure las reglas de precios o asigne un transportista manualmente."
                )

        # 1) Lógica nativa de confirmación (pasa a state='sale')
        res = super(SaleOrder, self).action_confirm()

        # 2) Si la orden pasó a 'sale', marcamos x_initial_status='confirmed'
        for order in self:
            if order.state == 'sale':
                if order.x_initial_status != 'confirmed':
                    order.x_initial_status = 'confirmed'

                # Verificar si ya existe un envío para esta orden
                existing_shipment = self.env['courier.shipment'].search([
                    ('sale_order_id', '=', order.id)
                ], limit=1)

                if not existing_shipment and order.carrier_id and order.partner_id.l10n_pe_district:
                    # Crear producto de envío si no existe
                    shipping_product = self.env['product.product'].search(
                        [('default_code', '=', 'SHIP')], limit=1
                    )
                    if not shipping_product:
                        shipping_product = self.env['product.product'].create({
                            'name': 'Cargo por Envío',
                            'type': 'service',
                            'default_code': 'SHIP',
                            'invoice_policy': 'order',
                            'purchase_ok': False,
                            'sale_ok': True,
                            'lst_price': 0.0,
                            'uom_id': self.env.ref('uom.product_uom_unit').id,
                            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                        })

                    # Crear el envío
                    shipment = self.env['courier.shipment'].create({
                        'sale_order_id': order.id,
                        'carrier_id': order.carrier_id.id,
                        'district_id': order.partner_id.l10n_pe_district.id,
                        'shipping_date': fields.Date.today(),
                        'product_id': shipping_product.id,
                        'delivery_date': order.commitment_date or False,
                        'name': self.env['ir.sequence'].next_by_code('courier.shipment') or 'New',
                    })

                    # Actualizar costos (una sola vez)
                    shipment._update_delivery_fee()
                    order._compute_shipping_cost()

                    _logger.info(f"Envío creado para la orden {order.name} con el transportista {order.carrier_id.name}")
                else:
                    _logger.info(f"No se creó courier.shipment para la orden {order.name} porque ya existe uno o faltan datos.")

        # 3) Desbloquear la orden
        self.action_unlock()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'flags': {'mode': 'readonly'},
        }

    @api.onchange('commitment_date')
    def _onchange_commitment_date(self):
        """
        Cuando cambia commitment_date en la orden, actualizar delivery_date en los envíos
        """
        for order in self:
            if order.shipment_ids:
                order.shipment_ids.write({
                    'delivery_date': order.commitment_date
                })
                _logger.info(f"Actualizada fecha de entrega en envíos de la orden {order.name}")

    def write(self, vals):
        """Sobrescribimos write para:
        1) Manejar x_initial_status si quieres forzar ciertos cambios.
        2) Sincronizar commitment_date en los courier.shipments.
        """
        x_initial_status_nuevo = vals.get('x_initial_status', False)
        commitment_date_changed = 'commitment_date' in vals

        res = super(SaleOrder, self).write(vals)

        # Si x_initial_status se cambia a 'confirmed' desde la vista, creamos el shipment si no existía
        if x_initial_status_nuevo == 'confirmed':
            for order in self:
                existing_shipments = self.env['courier.shipment'].search([
                    ('sale_order_id', '=', order.id)
                ])
                if not existing_shipments:
                    carrier = order.carrier_id or self.env.ref('courier_management.default_carrier_shipment')
                    shipment = self.env['courier.shipment'].create({
                        'name': self.env['ir.sequence'].next_by_code('courier.shipment') or 'New',
                        'sale_order_id': order.id,
                        'carrier_id': carrier.id if carrier else False,
                        'partner_id': order.partner_id.id,
                        'delivery_date': order.commitment_date,
                        'district_id': order.partner_id.l10n_pe_district.id,
                    })
                    shipment._update_delivery_fee()

        # Si cambió el commitment_date, actualizar en los envíos
        if commitment_date_changed:
            for order in self:
                if order.shipment_ids:
                    order.shipment_ids.write({
                        'delivery_date': order.commitment_date
                    })

        return res


    def _compute_shipping_cost(self):
        """Busca la regla de precio y actualiza o crea la línea SHIP en la orden."""
        for order in self:
            if not order.carrier_id or not order.partner_id:
                continue

            district = order.partner_id.l10n_pe_district
            if not district:
                continue

            # Buscar una regla de precio que coincida con carrier + distrito
            domain = [
                ('carrier_id', '=', order.carrier_id.id),
                ('district_id', '=', district.id)
            ]
            pricing_rule = self.env['courier.pricing.rule'].search(domain, limit=1)

            if pricing_rule:
                price = pricing_rule.price
                # Buscar si ya existe la línea de envío (default_code='SHIP')
                shipping_lines = order.order_line.filtered(
                    lambda line: line.product_id.default_code == 'SHIP'
                )
                # Buscar el producto 'SHIP'
                shipping_product = self.env['product.product'].search(
                    [('default_code', '=', 'SHIP')],
                    limit=1
                )
                if not shipping_product:
                    # Crear el producto si no existe
                    shipping_product = self.env['product.product'].create({
                        'name': 'Cargo por Envío',
                        'type': 'service',
                        'default_code': 'SHIP',
                        'invoice_policy': 'order',
                        'purchase_ok': False,
                        'sale_ok': True,
                        'lst_price': 0.0,
                        'uom_id': self.env.ref('uom.product_uom_unit').id,
                        'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                    })

                if shipping_lines:
                    # Si existe, actualizamos el precio
                    shipping_lines[0].price_unit = price
                else:
                    # Si no existe, creamos la línea 'SHIP'
                    new_line_vals = {
                        'order_id': order.id,
                        'product_id': shipping_product.id,
                        'name': shipping_product.name,
                        'product_uom_qty': 1.0,
                        'price_unit': price,
                        'customer_lead': 0.0,
                    }
                    order.write({'order_line': [(0, 0, new_line_vals)]})
            else:
                # No se encontró regla => podrías poner precio 0 o dejarla así
                pass
