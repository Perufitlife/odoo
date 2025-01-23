{
    'name': 'Delivery Agencies Integration',
    'version': '1.0',
    'category': 'Inventory/Delivery',
    'sequence': 1,
    'summary': 'Integración con agencias de envío (Shalom, Olva)',
    'description': """
        Módulo para integrar diferentes agencias de envío
    """,
    'depends': [
        'base',
        'sale',
        'delivery',
        'l10n_pe',
        'base_setup',  # Agregar esta línea

    ],
    'data': [
        'security/ir.model.access.csv',
        'views/agency_address_views.xml',
        'views/choose_agency_wizard_views.xml',
        'views/choose_address_wizard_views.xml',
        'views/sale_order_inherit_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}