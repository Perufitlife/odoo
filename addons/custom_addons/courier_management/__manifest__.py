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
        'web',
        # Removemos 'shopify' ya que debería estar en un módulo puente separado
    ],
    'data': [
        # 1. Datos de seguridad (primero siempre)
        'security/courier_management_security.xml',
        'security/ir.model.access.csv',

        # 2. Datos y secuencias
        'data/sequence.xml',
        'data/no_delivery_reason_data.xml',

        # 3. Wizards (agrupados juntos)
        'wizard/shipment_verification_wizard_views.xml',  # Renombrado y reubicado
        'wizard/no_entregado_wizard_views.xml',          # Movido a carpeta wizard
        'wizard/reprogramar_wizard_views.xml',           # Movido a carpeta wizard

        # 4. Vistas principales
        'views/courier_shipment_views.xml',              # Renombrado para claridad
        'views/courier_carrier_views.xml',               # Renombrado para claridad
        'views/courier_pricing_rule_views.xml',          # Renombrado para claridad
        
        # 5. Vistas heredadas
        'views/sale_order_views.xml',
        'views/partner_views.xml',
        'views/partner_address_views.xml',
        
        # 6. Vistas de tablero y reportes
        'views/courier_dispatch_board_view.xml',         # Renombrado para claridad
        'views/courier_kanban_view.xml',
        'report/shipment_reports.xml',
        'report/shipment_labels.xml',                    # Movido a carpeta report
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