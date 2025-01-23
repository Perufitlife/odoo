from odoo import models, fields, api
from odoo.exceptions import UserError

class ShipmentVerificationWizard(models.TransientModel):
    _name = 'shipment.verification.wizard'
    _description = 'Asistente de Verificación de Envíos'
    _inherit = ['uchat.mixin']

    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Courier',
        required=True
    )
    
    product_summary_ids = fields.One2many(
        'shipment.verification.line',
        'wizard_id',
        string='Resumen de Productos'
    )
    
    shipment_ids = fields.Many2many(
        'courier.shipment',
        string='Envíos a Procesar'
    )

    def action_verify(self):
        """Verifica stock y procesa envíos"""
        self._validate_stock()
        self._process_shipments()
        return self._show_success_notification()

    def _validate_stock(self):
        """Valida disponibilidad de stock"""
        for line in self.product_summary_ids:
            if line.quantity_to_ship > line.quantity_available:
                raise UserError(
                    f"Stock insuficiente para '{line.product_id.display_name}'\n"
                    f"Disponible: {line.quantity_available}, Requerido: {line.quantity_to_ship}"
                )

    def _process_shipments(self):
        """Procesa los envíos seleccionados"""
        for shipment in self.shipment_ids:
            new_state = 'in_transit' if shipment.carrier_id.auto_in_transit else 'despachado'
            
            # Actualizar envío y orden en una sola operación
            shipment.write({
                'state': new_state,
                'sale_order_id.x_initial_status': new_state
            })

            # Integración UChat
            if hasattr(self, 'assign_uchat_tag_and_carrier'):
                self.assign_uchat_tag_and_carrier(
                    shipment.partner_id,
                    shipment.carrier_id.name
                )

    def _show_success_notification(self):
        """Muestra notificación de éxito"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Verificación Exitosa",
                'message': "Proceso completado correctamente",
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def default_get(self, fields_list):
        """Obtiene valores por defecto optimizados"""
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        
        if not active_ids:
            return res

        shipments = self.env['courier.shipment'].browse(active_ids)
        
        # Asignar carrier y envíos
        res.update({
            'carrier_id': shipments.mapped('carrier_id')[:1].id,
            'shipment_ids': [(6, 0, shipments.ids)]
        })

        # Calcular resumen de productos
        products_dict = {}
        for line in shipments.mapped('deliverable_lines'):
            products_dict[line.product_id] = products_dict.get(
                line.product_id, 0
            ) + line.product_uom_qty

        # Crear líneas de resumen
        res['product_summary_ids'] = [
            (0, 0, {
                'product_id': product.id,
                'quantity_required': qty,
                'quantity_to_ship': qty,
            }) for product, qty in products_dict.items()
        ]

        return res


class ShipmentVerificationLine(models.TransientModel):
    _name = 'shipment.verification.line'
    _description = 'Línea de Verificación de Envío'

    wizard_id = fields.Many2one('shipment.verification.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    quantity_required = fields.Float('Cantidad Requerida', readonly=True)
    quantity_available = fields.Float(
        'Cantidad Disponible',
        related='product_id.qty_available',
        readonly=True
    )
    quantity_to_ship = fields.Float('Cantidad a Despachar')