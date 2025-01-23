{
    'name': 'Shopify Integration',
    'version': '1.0',
    'summary': 'Integración con Shopify para gestión de pedidos',
    'category': 'Sales',
    'author': 'TuNombre',
    'website': 'https://www.yourwebsite.com',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',  # Añadido para gestión de ventas completa
        'stock',           # Añadido para gestión de inventario
        'base',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/shopify_store_views.xml',
        'views/shopify_webhook_views.xml',
        'views/shopify_menus.xml',
        "views/sale_order_inherit_views.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}