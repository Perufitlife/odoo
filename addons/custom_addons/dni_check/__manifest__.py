{
    'name': 'DNI Check',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Consulta de DNI para órdenes de venta',
    'description': 'Módulo para consultar DNI y validar datos del cliente',
    'author': 'Tu Nombre',
    'depends': ['sale', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/dni_check_wizard_views.xml',  # Asegúrate de que esta línea esté aquí
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}