# custom_addons/shopify/models/shopify_webhook_log.py

import unicodedata
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import json

_logger = logging.getLogger(__name__)

# Mantener los patrones existentes ya que funcionan bien
DEPARTMENT_PATTERNS = ['departamento', 'department']
PROVINCE_PATTERNS = ['provincia', 'province']
DISTRICT_PATTERNS = ['distrito', 'district']
ADDRESS_PATTERNS = ['dirección', 'direccion', 'address', 'dirección (incluir']
REFERENCE_PATTERNS = ['referencia', 'reference']
DNI_PATTERNS = ['dni']

# Mantener el mapeo existente
PAYLOAD_TO_DB_CODES = {
    'LAL': '13', 'LIM': '15', 'CUS': '08', 'PIU': '20', 'LAM': '14',
    'CAJ': '06', 'ARE': '04', 'TAC': '23', 'MDD': '17', 'AMA': '01',
    'ANC': '02', 'APU': '03', 'AYA': '05', 'CAL': '07', 'HUV': '09',
    'HUC': '10', 'ICA': '11', 'JUN': '12', 'LOR': '16', 'MOQ': '18',
    'PAS': '19', 'PUN': '21', 'SAM': '22', 'TUM': '24', 'UCA': '25'
}

class ShopifyWebhookLog(models.Model):
    _name = 'shopify.webhook.log'
    _description = 'Shopify Webhook Log'
    _order = 'received_at desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, tracking=True)
    payload = fields.Text(string='Payload', tracking=True)
    event_type = fields.Char(string='Event Type', tracking=True)
    received_at = fields.Datetime(
        string='Received At', 
        default=fields.Datetime.now,
        tracking=True
    )
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('processed', 'Procesado'),
        ('failed', 'Error')
    ], string='Estado', default='pending', tracking=True)
    error_message = fields.Text(string='Mensaje de Error', tracking=True)
    
    # Nuevos campos para mejor seguimiento
    shopify_order_id = fields.Char(string='Shopify Order ID', tracking=True)
    sale_order_id = fields.Many2one('sale.order', string='Orden de Venta', tracking=True)
    customer_name = fields.Char(string='Nombre del Cliente')

    @api.model
    def create(self, vals):
        """Genera un nombre secuencial para el registro del webhook
           y extrae el nombre del cliente si se encuentra en el payload."""
        # Asignar un nombre secuencial si no existe
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code('shopify.webhook.log') or 'SHOP/WH/000'

        # Intentar parsear el payload para extraer el nombre del cliente
        payload_str = vals.get('payload')
        if payload_str:
            try:
                data = json.loads(payload_str)
                # Intentar obtener el nombre del cliente de diferentes fuentes
                customer_name = ""
                
                # 1. Intentar desde shipping_address
                shipping_address = data.get('shipping_address', {})
                if shipping_address:
                    first_name = shipping_address.get('first_name', '').strip()
                    last_name = shipping_address.get('last_name', '').strip()
                    customer_name = f"{first_name} {last_name}".strip()
                
                # 2. Si no hay nombre en shipping_address, intentar desde customer
                if not customer_name:
                    customer = data.get('customer', {})
                    first_name = customer.get('first_name', '').strip()
                    last_name = customer.get('last_name', '').strip()
                    customer_name = (first_name + ' ' + last_name).strip()
                
                # 3. Si aún no hay nombre, intentar desde note_attributes
                if not customer_name:
                    note_attributes = data.get('note_attributes', [])
                    for attr in note_attributes:
                        if attr.get('name', '').lower() == 'nombre y apellido':
                            customer_name = attr.get('value', '').strip()
                            break
                
                if customer_name:
                    vals['customer_name'] = customer_name
            except Exception as e:
                _logger.warning("No se pudo parsear el payload para obtener el nombre del cliente: %s", e)

        return super(ShopifyWebhookLog, self).create(vals)

    @staticmethod
    def normalize_text(text):
        """
        Normaliza un texto eliminando acentos y caracteres especiales
        """
        if not text:
            return ""
        normalized = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        return ''.join(c.lower() for c in normalized if c.isalnum() or c.isspace()).strip()

    def get_location_from_note_attributes(self, note_attributes):
        """
        Obtiene la información de ubicación desde note_attributes
        """
        location_data = {
            'department': '',
            'province': '',
            'district': '',
            'street': '',
            'reference': ''
        }

        ignore_attributes = ['ip address', 'country code', 'correo electronico', 
                           'numero celular', 'nombre y apellido']

        for attr in note_attributes:
            attr_name = self.normalize_text(attr.get('name', ''))
            attr_value = attr.get('value', '').strip()

            if attr_name in ignore_attributes or not attr_value:
                continue

            if any(pattern in attr_name for pattern in DEPARTMENT_PATTERNS):
                location_data['department'] = attr_value
            elif any(pattern in attr_name for pattern in PROVINCE_PATTERNS):
                location_data['province'] = attr_value
            elif any(pattern in attr_name for pattern in DISTRICT_PATTERNS):
                location_data['district'] = attr_value
            elif any(pattern in attr_name for pattern in ADDRESS_PATTERNS):
                location_data['street'] = attr_value
            elif any(pattern in attr_name for pattern in REFERENCE_PATTERNS):
                location_data['reference'] = attr_value

        return location_data

    def process_customer(self, customer_data, order_data):
        """Procesa datos del cliente, priorizando shipping_address para draft orders"""
        # Inicializar variables básicas
        shipping_address = order_data.get('shipping_address') or order_data.get('billing_address', {})
        timestamp = fields.Datetime.now().strftime('%Y%m%d%H%M%S')

        # Obtener información del cliente (ya sea de customer_data o shipping_address)
        if customer_data and customer_data.get('first_name'):
            first_name = (customer_data.get('first_name') or '').strip()
            last_name = (customer_data.get('last_name') or '').strip()
            email = customer_data.get('email', '')
            phone = customer_data.get('phone') or customer_data.get('default_address', {}).get('phone', '')
        else:
            first_name = shipping_address.get('first_name', '').strip()
            last_name = shipping_address.get('last_name', '').strip()
            email = order_data.get('email', '')  # En draft orders, el email está en la raíz
            phone = shipping_address.get('phone', '')

        # Construir nombre completo
        full_name = f"{first_name} {last_name}".strip() or f"Cliente Anónimo {timestamp}"

        # === Procesamiento de la ubicación ===
        location_data = {
            'department': '',
            'province': '',
            'district': '',
            'street': '',
            'reference': '',
        }

        # Procesar note_attributes primero
        if order_data.get('note_attributes'):
            location_data.update(self.get_location_from_note_attributes(order_data['note_attributes']))
            _logger.info(f"Datos obtenidos de note_attributes: {location_data}")

        # Complementar con datos de shipping_address
        if shipping_address:
            if not location_data['department']:
                location_data['department'] = shipping_address.get('province_code')
            if not location_data['province']:
                location_data['province'] = shipping_address.get('province', shipping_address.get('city'))
            if not location_data['district']:
                location_data['district'] = shipping_address.get('address2')
            if not location_data['street']:
                location_data['street'] = shipping_address.get('address1')
            if not location_data['reference']:
                location_data['reference'] = shipping_address.get('company')

        # Buscar país
        country = self.env['res.country'].sudo().search([('code', '=', 'PE')], limit=1)
        if not country:
            raise ValueError("No se encontró el país Perú en la base de datos")

        # Procesar departamento/estado
        state = False
        state_name = location_data['department']
        if state_name:
            if state_name.startswith('PE-'):
                state_code = state_name[3:]
                state_code = PAYLOAD_TO_DB_CODES.get(state_code, state_code)
            else:
                state_code = PAYLOAD_TO_DB_CODES.get(state_name, state_name)

            state = self.env['res.country.state'].sudo().search([
                ('code', '=', state_code),
                ('country_id', '=', country.id)
            ], limit=1)

        # Buscar Provincia/Ciudad
        city = False
        if state and location_data['province']:
            normalized_province = self.normalize_text(location_data['province'])
            normalized_province_no_spaces = normalized_province.replace(' ', '')

            cities = self.env['res.city'].sudo().search([
                ('state_id', '=', state.id)
            ])

            for possible_city in cities:
                possible_name = self.normalize_text(possible_city.name)
                possible_name_no_spaces = possible_name.replace(' ', '')

                if possible_name_no_spaces == normalized_province_no_spaces:
                    city = possible_city
                    break

        # Buscar Distrito
        district = False
        if city and location_data['district']:
            normalized_district = self.normalize_text(location_data['district'])
            normalized_district_no_spaces = normalized_district.replace(' ', '')

            districts = self.env['l10n_pe.res.city.district'].sudo().search([
                ('city_id', '=', city.id)
            ])

            for possible_district in districts:
                possible_district_name = self.normalize_text(possible_district.name)
                possible_district_name_no_spaces = possible_district_name.replace(' ', '')

                if possible_district_name_no_spaces == normalized_district_no_spaces:
                    district = possible_district
                    break

        # Construir valores del partner
        partner_vals = {
            'name': full_name,
            'email': email,
            'phone': phone,
            'street': location_data['street'],
            'street2': location_data['reference'],
            'country_id': country.id,
            'state_id': state.id if state else False,
            'city_id': city.id if city else False,
            'l10n_pe_district': district.id if district else False,
        }

        # Detectar DNI
        dni = None
        if order_data.get('note_attributes'):
            for attr in order_data['note_attributes']:
                if any(pattern in (attr.get('name') or '').lower() for pattern in DNI_PATTERNS):
                    dni_value = (attr.get('value') or '').strip()
                    if dni_value and dni_value.isdigit():
                        dni = dni_value
                        break

        if dni:
            dni_type = self.env['l10n_latam.identification.type'].sudo().search([
                ('name', 'ilike', 'DNI')
            ], limit=1)
            if dni_type:
                partner_vals.update({
                    'vat': dni,
                    'l10n_latam_identification_type_id': dni_type.id
                })

        # Buscar o crear partner
        domain = []
        if email:
            domain.append(('email', '=', email))
        if phone:
            domain.append(('phone', '=', phone))

        if domain:
            domain = ['|'] * (len(domain) - 1) + domain
            partner = self.env['res.partner'].sudo().search(domain, limit=1)
        else:
            partner = False

        if partner:
            partner.sudo().write(partner_vals)
            _logger.info(f"Cliente actualizado con ID: {partner.id}")
        else:
            partner = self.env['res.partner'].sudo().create(partner_vals)
            _logger.info(f"Cliente creado con ID: {partner.id}")

        return partner

    def find_or_create_product(self, item_data):
        """
        Busca o crea un producto basado en los datos de Shopify
        """
        Product = self.env['product.product'].sudo()
        
        # Primero intentamos encontrar el producto por SKU
        sku = item_data.get('sku')
        product = False
        if sku:
            product = Product.search([('default_code', '=', sku)], limit=1)
            if product:
                _logger.info(f"Producto encontrado por SKU: {sku}")
                return product

        # Si no encontramos por SKU, buscamos por ID de Shopify
        shopify_product_id = str(item_data.get('product_id'))
        if shopify_product_id:
            product = Product.search([('default_code', '=', shopify_product_id)], limit=1)
            if product:
                _logger.info(f"Producto encontrado por Shopify ID: {shopify_product_id}")
                return product

        # Si no encontramos el producto, lo creamos
        product_title = item_data.get('title') or item_data.get('name', 'Producto sin nombre')
        variant_title = item_data.get('variant_title')
        price = float(item_data.get('price', 0.0))

        # Crear el producto
        product_vals = {
            'name': product_title,
            'default_code': sku or shopify_product_id,
            'type': 'consu',  # Cambiado de 'product' a 'consu'
            'sale_ok': True,
            'purchase_ok': True,
            'list_price': price,
            'standard_price': price,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
            'invoice_policy': 'order',
            'description_sale': variant_title if variant_title else '',
            'categ_id': self.env.ref('product.product_category_all').id,
        }

        try:
            product = Product.create(product_vals)
            _logger.info(f"Producto creado: {product.name} [{product.default_code}]")
            return product
        except Exception as e:
            _logger.error(f"Error creando producto: {str(e)}")
            raise ValidationError(f"Error creando producto {product_title}: {str(e)}")

    def process_order_line(self, order, item_data, igv_tax):
        """
        Procesa una línea de pedido individual sin IGV
        """
        product = self.find_or_create_product(item_data)
        quantity = float(item_data.get('quantity', 1.0))
        price_unit = float(item_data.get('price', 0.0))

        # Calcular descuentos
        discount_allocations = item_data.get('discount_allocations', [])
        total_discount = sum(float(allocation.get('amount', 0)) for allocation in discount_allocations)

        line_total = price_unit * quantity
        discount_percentage = (total_discount / line_total) * 100 if line_total > 0 else 0.0

        line_name = product.name
        variant_title = item_data.get('variant_title')
        if variant_title:
            line_name += f" ({variant_title})"

        vals = {
            'order_id': order.id,
            'product_id': product.id,
            'name': line_name,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'price_unit': price_unit,
            'discount': discount_percentage,
            'tax_id': [(6, 0, [])]  # Empty tax assignment
        }

        return self.env['sale.order.line'].sudo().create(vals)

    def process_order(self, order_data, store):
        """
        Procesa una orden completa de Shopify
        """
        # Validar datos básicos
        if not order_data:
            raise ValidationError("No se recibieron datos de la orden")

        line_items = order_data.get('line_items', [])
        if not line_items:
            raise ValidationError("La orden no contiene líneas de productos")

        # Procesar cliente (ya no validamos si existe customer_data)
        partner = self.process_customer(order_data.get('customer'), order_data)

        # Obtener nombre/ID de orden
        order_name = order_data.get('name', '')
        shopify_order_id = str(order_data.get('id', ''))

        # Determinar estado inicial según el tipo de evento
        if self.event_type == 'orders/create':
            initial_status = 'order_completed'
        elif self.event_type == 'draft_orders/create':
            initial_status = 'abandoned_cart'
        else:
            initial_status = 'whatsapp'

        # Crear orden de venta
        order_vals = {
            'partner_id': partner.id,
            'client_order_ref': f"Shopify-{order_name}",
            'date_order': fields.Datetime.now(),
            'company_id': self.env.company.id,
            'shopify_store_id': store.id,
            'x_initial_status': initial_status,
        }

        order = self.env['sale.order'].sudo().create(order_vals)
        _logger.info(f"Orden de venta creada: {order.name}")

        # Obtener impuesto IGV
        igv_tax = self._get_or_create_igv_tax()

        # Procesar líneas de orden
        shopify_total = float(order_data.get('total_price', 0))
        for item in line_items:
            try:
                self.process_order_line(order, item, igv_tax)
            except Exception as e:
                _logger.error(f"Error procesando línea de orden: {str(e)}")
                raise ValidationError(f"Error procesando línea de producto {item.get('title')}: {str(e)}")

        # Validar totales
        if abs(order.amount_total - shopify_total) > 0.01:
            message = (
                f"⚠️ Diferencia en totales detectada:\n"
                f"Shopify: {shopify_total}\n"
                f"Odoo: {order.amount_total}"
            )
            _logger.warning(message)

        return order

    def _get_or_create_igv_tax(self):
        """
        Obtiene o crea el impuesto IGV
        """
        igv_tax = self.env['account.tax'].sudo().search([
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 18),
            ('price_include', '=', False),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not igv_tax:
            igv_tax = self.env['account.tax'].sudo().create({
                'name': 'IGV 18%',
                'type_tax_use': 'sale',
                'amount_type': 'percent',
                'amount': 18,
                'price_include': False,
                'include_base_amount': False,
                'company_id': self.env.company.id,
                'l10n_pe_edi_tax_code': '1000',
                'l10n_pe_edi_unece_category': 'S',
            })

        return igv_tax