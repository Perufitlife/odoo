{
    'name': 'Courier Management',
    'version': '1.0',
    'category': 'Services/Courier',
    'summary': 'Sistema de gestión de courier',
    'description': """
        Sistema integrado de gestión de courier con:
        - Gestión de envíos
        - Reglas de precios
        - Verificación de stock
        - Panel de despacho
        - Integración con carriers
    """,
    'depends': [
        'base',
        'stock',
        'sale',
        'contacts',
        'l10n_pe',
        'delivery',
        'sale_stock',
        'mail',
        'web',
        # Removemos 'shopify' ya que debería estar en un módulo puente separado
    ],
    'data': [
        # 1. Seguridad
        'security/courier_management_security.xml',
        'security/ir.model.access.csv',

        # 2. Datos, secuencias
        'data/sequence.xml',
        'data/no_delivery_reason_data.xml',
        'data/address_format_pe.xml',
        # 3. Wizards
        'wizards/verification_wizard_views.xml',
        'wizards/no_entregado_wizard_views.xml',
        'wizards/reprogramar_wizard_views.xml',
        'wizards/quick_courier_wizard_views.xml',
        'wizards/delivery_method_wizard_views.xml',  # Nueva línea

        # 4. Vistas principales
        #    NOTA: Mueve "courier_shipment_views.xml" antes que "courier_carrier_views.xml"
        'views/courier_shipment_views.xml',    # define menu_courier_config
        'views/courier_carrier_views.xml',     # usa parent="menu_courier_config"
        'views/courier_pricing_rule_views.xml',
        'views/pickup_point_views.xml',        # Nueva vista para puntos de recojo
        'views/sale_order_inherit_views.xml',
        'views/sale_order_inherit_quotation_tree.xml',

        # 5. Otras vistas heredadas
        'views/sale_order_views.xml',
        'views/partner_views.xml',
        'views/partner_address_views.xml',
        'views/sale_order_inherit_contact_address.xml',

        # 6. Tableros y reportes
        'views/courier_dispatch_board_view.xml',
        'views/courier_kanban_view.xml',
        'report/shipment_reports.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            # CSS
            '/courier_management/static/src/css/style.css',
            # Nuevos assets JS para el tablero
            '/courier_management/static/src/js/dispatch_board.js',
            # Componentes
            '/courier_management/static/src/components/**/*.js',
            '/courier_management/static/src/components/**/*.xml',
        ],
    },

    # Metadatos adicionales recomendados
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'maintainer': 'Tu Empresa',
    'support': 'soporte@tuempresa.com',
    
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    
    # Nueva configuración recomendada
    'auto_install': False,
    'sequence': 1,
}