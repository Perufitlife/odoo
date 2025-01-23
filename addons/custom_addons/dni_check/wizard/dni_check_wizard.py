from odoo import models, fields, api
import requests
from bs4 import BeautifulSoup

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
        try:
            # URL de la página donde se hace la búsqueda
            url_form = "https://eldni.com/pe/buscar-datos-por-dni"
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/112.0.0.0"
            })

            # Obtener token
            resp_get = session.get(url_form)
            soup = BeautifulSoup(resp_get.text, "html.parser")
            token = soup.find("input", {"name": "_token"}).get("value")

            # Hacer la consulta
            payload = {"_token": token, "dni": dni}
            resp_post = session.post(url_form, data=payload)
            soup = BeautifulSoup(resp_post.text, "html.parser")
            
            tabla = soup.find("table", {"class": "table table-striped table-scroll"})
            if not tabla:
                return None
            
            celdas = tabla.find("tbody").find("tr").find_all("td")
            return {
                'nombres': celdas[1].get_text(strip=True),
                'apellido_paterno': celdas[2].get_text(strip=True),
                'apellido_materno': celdas[3].get_text(strip=True)
            }
        except Exception as e:
            return None