from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class ShipmentVerificationWizard(models.TransientModel):
    _name = 'shipment.verification.wizard'
    _description = 'Asistente de Verificación de Envíos'

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

    @api.constrains('shipment_ids')
    def _check_shipments(self):
        """Validar que haya envíos seleccionados"""
        for record in self:
            if not record.shipment_ids:
                raise ValidationError('Debe seleccionar al menos un envío para procesar.')

    def action_verify(self):
        """Verifica stock y procesa envíos"""
        self.ensure_one()
        self._validate_stock()
        self._process_shipments()
        return self._show_success_notification()

    def _validate_stock(self):
        """Valida disponibilidad de stock"""
        if not self.product_summary_ids:
            raise UserError('No hay productos para verificar.')
            
        for line in self.product_summary_ids:
            if not line.product_id:
                continue
                
            if line.quantity_to_ship > line.quantity_available:
                raise UserError(
                    f"Stock insuficiente para '{line.product_id.display_name}'\n"
                    f"Disponible: {line.quantity_available}, Requerido: {line.quantity_to_ship}"
                )

    def _process_shipments(self):
        """Procesa los envíos seleccionados"""
        self.ensure_one()
        processed_shipments = []
        
        for shipment in self.shipment_ids:
            try:
                self._process_single_shipment(shipment)
                processed_shipments.append(shipment.name)
            except Exception as e:
                # Si hay error, hacer rollback de los envíos procesados
                if processed_shipments:
                    _logger.error(
                        f'Error después de procesar los envíos {", ".join(processed_shipments)}. '
                        f'Se requiere intervención manual. Error: {str(e)}'
                    )
                raise UserError(
                    f'Error al procesar el envío {shipment.name}: {str(e)}'
                )

    def _process_single_shipment(self, shipment):
        """Procesa un único envío"""
        if not shipment:
            return
            
        new_state = 'in_transit' if shipment.carrier_id.auto_in_transit else 'despachado'
        
        # Actualizar envío
        shipment.write({
            'state': new_state
        })
        
        # Actualizar orden de venta
        if shipment.sale_order_id:
            shipment.sale_order_id.with_context(
                no_propagate_to_shipment=True
            ).write({
                'x_initial_status': new_state
            })
        
        # Registrar éxito
        _logger.info(
            f'Envío {shipment.name} procesado exitosamente. '
            f'Nuevo estado: {new_state}'
        )
        
        # Notificar en chatter
        shipment.message_post(
            body=f"Envío verificado y marcado como {new_state}"
        )

    def _show_success_notification(self):
        """Muestra notificación de éxito"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Verificación Exitosa",
                'message': f"Se procesaron {len(self.shipment_ids)} envíos correctamente",
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def default_get(self, fields_list):
        """Obtiene valores por defecto optimizados"""
        _logger.info("Iniciando default_get")
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        
        _logger.info(f"Active IDs encontrados: {active_ids}")
        
        if not active_ids:
            _logger.warning("No se encontraron active_ids")
            return res

        try:
            # Obtener envíos
            shipments = self.env['courier.shipment'].browse(active_ids)
            _logger.info(f"Envíos encontrados: {shipments.mapped('name')}")
            
            # Validar carrier único
            carriers = shipments.mapped('carrier_id')
            _logger.info(f"Carriers encontrados: {carriers.mapped('name')}")
            
            if len(carriers) > 1:
                raise ValidationError(
                    'Todos los envíos deben pertenecer al mismo courier.'
                )
            
            # Asignar carrier y envíos
            res.update({
                'carrier_id': carriers[:1].id,
                'shipment_ids': [(6, 0, shipments.ids)]
            })

            # Obtener líneas de venta
            sale_lines = shipments.mapped('deliverable_lines')
            _logger.info(f"Número de líneas de venta encontradas: {len(sale_lines)}")
            
            # Filtrar líneas válidas
            valid_lines = sale_lines.filtered(
                lambda l: l.product_id and not l.display_type
            )
            _logger.info(f"Número de líneas válidas: {len(valid_lines)}")
            
            if not valid_lines:
                _logger.warning("No se encontraron líneas válidas")
                return res

            # Crear diccionario de productos
            product_dict = {}
            for line in valid_lines:
                product = line.product_id
                if not product or not product.id:
                    _logger.warning(f"Línea con producto inválido: {line.id}")
                    continue
                    
                _logger.info(f"Procesando producto: {product.display_name}")
                
                if product.id not in product_dict:
                    product_dict[product.id] = {
                        'product': product,
                        'quantity': 0.0
                    }
                product_dict[product.id]['quantity'] += line.product_uom_qty

            # Crear líneas de resumen
            summary_lines = []
            for product_id, data in product_dict.items():
                if not data['product'].exists():
                    _logger.warning(f"Producto {product_id} no existe")
                    continue
                    
                line_vals = {
                    'product_id': product_id,
                    'quantity_required': data['quantity'],
                    'quantity_to_ship': data['quantity'],
                }
                _logger.info(f"Creando línea de resumen: {line_vals}")
                summary_lines.append((0, 0, line_vals))

            if summary_lines:
                res['product_summary_ids'] = summary_lines
                _logger.info(f"Número de líneas de resumen creadas: {len(summary_lines)}")
            else:
                _logger.warning("No se crearon líneas de resumen")

        except Exception as e:
            _logger.error(f"Error en default_get: {str(e)}", exc_info=True)
            raise UserError(f"Error al cargar los datos: {str(e)}")

        return res

    @api.model
    def create(self, values):
        """Override create para manejar mejor la creación de líneas"""
        if 'product_summary_ids' in values:
            for i, (command, _, line_vals) in enumerate(values['product_summary_ids']):
                if command == 0:  # Comando de creación
                    # Obtener los valores por defecto si no existen
                    default_values = self.default_get(['product_summary_ids'])
                    if 'product_summary_ids' in default_values and len(default_values['product_summary_ids']) > i:
                        # Combinar valores por defecto con los valores proporcionados
                        _, _, default_line = default_values['product_summary_ids'][i]
                        default_line.update(line_vals)
                        values['product_summary_ids'][i] = (0, 0, default_line)
                        
        return super(ShipmentVerificationWizard, self).create(values)




class ShipmentVerificationLine(models.TransientModel):
    _name = 'shipment.verification.line'
    _description = 'Línea de Verificación de Envío'

    wizard_id = fields.Many2one(
        'shipment.verification.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        ondelete='cascade',
        domain=[('type', '!=', 'service')]
    )
    
    quantity_required = fields.Float(
        string='Cantidad Requerida',
        required=True,
        default=0.0,
        digits='Product Unit of Measure'
    )
    
    quantity_available = fields.Float(
        string='Cantidad Disponible',
        related='product_id.qty_available',
        readonly=True,
        digits='Product Unit of Measure'
    )
    
    quantity_to_ship = fields.Float(
        string='Cantidad a Despachar',
        required=True,
        default=0.0,
        digits='Product Unit of Measure'
    )

    @api.model
    def create(self, values):
        """Override create para validar datos requeridos"""
        if not values.get('product_id'):
            wizard = self.env['shipment.verification.wizard'].browse(values.get('wizard_id'))
            if wizard and wizard.shipment_ids:
                # Intentar obtener el producto del envío
                shipment = wizard.shipment_ids[0]
                if shipment.deliverable_lines:
                    line = shipment.deliverable_lines[0]
                    values['product_id'] = line.product_id.id
                    
        if not values.get('product_id'):
            raise ValidationError('El campo Producto es obligatorio.')
            
        return super(ShipmentVerificationLine, self).create(values)