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
        url_form = "https://eldni.com/pe/buscar-datos-por-dni"
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        })

        # 1) GET
        resp_get = session.get(url_form)
        if resp_get.status_code != 200:
            _logger.info("GET status code: %s", resp_get.status_code)
            return None

        soup = BeautifulSoup(resp_get.text, "html.parser")
        token_elem = soup.find("input", {"name": "_token"})
        if not token_elem:
            _logger.info("No se encontró _token en el GET")
            _logger.info("HTML GET => %s", resp_get.text[:1000])  # Logea primeros 1000 chars
            return None

        token = token_elem.get("value")

        # 2) POST
        payload = {"_token": token, "dni": dni}
        resp_post = session.post(url_form, data=payload)
        _logger.info("POST status code: %s", resp_post.status_code)
        _logger.info("POST TEXT => %s", resp_post.text[:2000])  # Logea primeros 2000 chars

        if resp_post.status_code != 200:
            return None

        soup2 = BeautifulSoup(resp_post.text, "html.parser")
        tabla = soup2.find("table", {"class": "table table-striped table-scroll"})
        if not tabla:
            _logger.info("No se encontró la tabla en la respuesta POST. "
                        "Posible captcha o bloqueo.")
            return None

        fila = tabla.find("tbody").find("tr")
        celdas = fila.find_all("td")
        if len(celdas) < 4:
            return None

        return {
            'nombres': celdas[1].get_text(strip=True),
            'apellido_paterno': celdas[2].get_text(strip=True),
            'apellido_materno': celdas[3].get_text(strip=True)
        }
