{
    'name': 'Courier Management',
    'version': '1.0',
    'category': 'Services/Courier',
    'summary': 'Sistema de gestión de courier',
    'depends': ['base', 'stock', 'sale', 'contacts', 'l10n_pe', 'delivery', 'sale_stock', 'web', 'shopify'],
    'data': [
        # 1) secuencias, seguridad, etc.
        'data/sequence.xml',
        'security/courier_management_security.xml',
        'security/ir.model.access.csv',

        'views/wizard_view.xml',  # <--- subirlo antes de 'shipment_views.xml'

        # 2) Vista HIJA (modelo hijo) antes de la del wizard que la referencia
        'views/shipment_verification_line_views.xml',

        # 3) Ahora sí, la vista del wizard padre
        'views/verification_wizard_views.xml',

        # 4) El resto de vistas (shipment_views, pricing_rule_views, etc.)
        'views/shipment_views.xml',
        'views/pricing_rule_views.xml',
        'views/sale_order_views.xml',
        'views/partner_views.xml',
        'report/shipment_reports.xml',
        'views/report_labels.xml',
        'views/carrier_views.xml',
        'views/sale_order_inherit_views.xml',
        'views/partner_address_views.xml',
        'views/sale_order_hide_buttons.xml',
        'views/dispatch_board_view.xml',
        'views/courier_kanban_view.xml',
        'data/no_delivery_reason_data.xml',
        'views/no_entregado_wizard_views.xml',
        'views/reprogramar_wizard_views.xml',

    ],

    'assets': {
        'web.assets_backend': [
            '/courier_management/static/src/css/style.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}