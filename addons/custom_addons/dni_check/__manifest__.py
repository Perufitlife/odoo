{
    'name': 'DNI Check',
    'version': '16.0.1.0.0',  # Convención recomendada
    'category': 'Sales',
    'summary': 'Consulta de DNI para órdenes de venta',
    'description': """
Módulo para consultar DNI y validar datos del cliente.
- Agrega un wizard para verificar el DNI del cliente en la orden de venta.
- Valida la información antes de confirmar la orden.
    """,
    'author': 'Renzo Madueño',
    'website': 'https://myecomsuite.com',
    'license': 'LGPL-3',
    'depends': ['sale', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/dni_check_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
