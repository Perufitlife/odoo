from odoo import models, fields, api
import requests
from bs4 import BeautifulSoup
import logging

_logger = logging.getLogger(__name__)

class DniCheckWizard(models.TransientModel):
    _name = 'dni.check.wizard'
    _description = 'Wizard para consulta de DNI'

    dni = fields.Char('DNI', readonly=True)
    nombres = fields.Char('Nombres')
    apellido_paterno = fields.Char('Apellido Paterno')
    apellido_materno = fields.Char('Apellido Materno')
    sale_id = fields.Many2one('sale.order', 'Orden de Venta')
    mensaje = fields.Char('Mensaje', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'dni' in res:
            datos = self.consultar_dni(res['dni'])
            if datos:
                res.update(datos)
            else:
                res['mensaje'] = 'No se encontraron datos para este DNI'
        return res

    def consultar_dni(self, dni):
        """
        Consulta DNI en https://dniperu.com/querySelector
        Envía POST con 'dni4': <DNI> y parsea la respuesta JSON.
        """
        import requests
        import logging
        _logger = logging.getLogger(__name__)

        # URL donde se hace la búsqueda
        url_form = "https://dniperu.com/querySelector"

        # Iniciamos sesión (opcional, en caso de querer cookies persistentes)
        session = requests.Session()
        session.headers.update({
            # Ajusta tus cabeceras como desees, aquí un user-agent de ejemplo
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": "https://dniperu.com",
            "Referer": "https://dniperu.com/buscar-dni-nombres-apellidos/",
        })

        # data (o files) con el campo 'dni4' (que se ve en tu Network)
        payload = {"dni4": dni}

        try:
            resp_post = session.post(url_form, data=payload)
            _logger.info("POST status code: %s", resp_post.status_code)
            if resp_post.status_code != 200:
                return None

            # La respuesta es JSON (según tu Network). Ejemplo:
            # { "mensaje": "Número de DNI: 47856459\nNombres: RENZO ANTONIO\nApellido Paterno: MADUEÑO\nApellido Materno: CARCELEN\n..." }
            data_json = resp_post.json()
            # Extraer 'mensaje':
            mensaje_raw = data_json.get("mensaje", "")
            # 'mensaje_raw' contiene algo como:
            # "Número de DNI: 47856459\nNombres: RENZO ANTONIO\nApellido Paterno: MADUEÑO\nApellido Materno: CARCELEN\nCódigo de Verificación: 2"

            # Dividir por saltos de línea
            lineas = mensaje_raw.split("\n")
            # lineas[1] = "Nombres: RENZO ANTONIO"
            # lineas[2] = "Apellido Paterno: MADUEÑO"
            # lineas[3] = "Apellido Materno: CARCELEN"
            # Ajusta según la estructura real.

            # Extraer nombres y apellidos
            nombres = ""
            apellido_paterno = ""
            apellido_materno = ""

            for linea in lineas:
                linea = linea.strip()
                if linea.startswith("Nombres:"):
                    nombres = linea.replace("Nombres:", "").strip()
                elif linea.startswith("Apellido Paterno:"):
                    apellido_paterno = linea.replace("Apellido Paterno:", "").strip()
                elif linea.startswith("Apellido Materno:"):
                    apellido_materno = linea.replace("Apellido Materno:", "").strip()

            if not nombres:
                # Si no hallamos nada, asumimos que no se encontraron datos
                return None

            # Retornar diccionario con lo que deseas guardar en Odoo
            return {
                'nombres': nombres,
                'apellido_paterno': apellido_paterno,
                'apellido_materno': apellido_materno
            }

        except Exception as e:
            _logger.error("Error al consultar DNI en dniperu.com: %s", e)
            return None
