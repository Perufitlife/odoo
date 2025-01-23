{
    'name': 'Integración UChat con Ventas',
    'version': '1.0',
    'license': 'LGPL-3',
    'category': 'Sales',
    'summary': 'Abrir conversación de UChat desde Odoo',
    'author': 'Tu Nombre / Empresa',
    'depends': [
        'base',  # Importante añadir base
        'sale',
        'courier_management',
        'shopify',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/pending_reason_views.xml',  # Poner vista del wizard antes
        'views/res_config_settings_view.xml',
        'views/sale_order_chat_button.xml',
        'views/sale_order_status_buttons.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}