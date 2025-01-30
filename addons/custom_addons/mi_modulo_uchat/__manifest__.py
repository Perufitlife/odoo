{
    'name': 'Integración UChat con Ventas',
    'version': '1.0',
    'license': 'LGPL-3',
    'category': 'Sales',
    'summary': 'Abrir conversación de UChat desde Odoo',
    'author': 'Tu Nombre / Empresa',
    'depends': [
        'base',
        'sale',
        'courier_management',
        'shopify',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/delivery_date_wizard_views.xml',  # Agregamos el nuevo wizard
        'views/pending_reason_views.xml',
        'views/res_config_settings_view.xml',
        'views/sale_order_chat_button.xml',
        'views/sale_order_status_buttons.xml',
        'views/sale_order_list_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}