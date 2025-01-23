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
        import requests
        _logger.info("== Enviando POST EXACTO a eldni.com, con boundary y cookies ==")

        url_form = "https://eldni.com/pe/buscar-datos-por-dni"

        # Encabezados copiados (ajusta con EXACTAMENTE lo que tu DevTools muestre)
        # Ojo: El boundary debe coincidir con el body raw.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,es-419;q=0.8,es;q=0.7",
            "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundarypl6WiRpHkdmTbYjb",
            "Cookie": (
                "XSRF-TOKEN=eyJpdiI6IngwN1k5WGRsVjlINGdIUFR1YlkxK0E9PSIsInZhbHVlIjoiT0J0XC9XZEdcL1Vpa0RCTFBNcXNlbENmZzZvdDZ4NDNvSEJSUldTdVg1R2t6dzFcL0RXRWFNenVNUEppRjZkOGhLVSIsIm1hYyI6IjIzOGNhMGVjOTlhY2ZmNDYzMzBhNjU4NGQwYzViMTU4Nzc3NTgyYzUwYzQ1OTY0ZDM2MzllMjAwMzIzN2U1MjgifQ; "  # tu valor real
                "laravel_session=eyJpdiI6IjNCUkh1OG5rTU52SzNia1YybzVyOUE9PSIsInZhbHVlIjoiZG5nb2Q5XC9HUWpyZ2Zlc1U5V1wvd3VpNEkxR1hucGtiSFgrcklTbmRPaGMxTVNKQjcyV1kzWGd6T1VKTWcycVNMWE1QcTJlc2NNWFVGWUlpUU9XQ2lnUEZZR0RPNVg2anIrVmJQZUdSR29TQnhwYXFmd3lwdTZGRzVEU09EQXpUayIsIm1hYyI6ImFmNmM1MjRmOTUxMGU2M2E4MjQ0NDViNjY4Zjk0ZTY2MTA2NmFhN2ZjM2RlMWM5YThlY2MwYmVhNGQ1NzIxNTgifQ;"  # tu valor real
            ),
            "Origin": "https://eldni.com",
            "Referer": "https://eldni.com/pe/buscar-datos-por-dni",
            "Sec-Fetch-Site": "same-origin",
            # ... (copia cualquier otro header esencial)
        }

        # El cuerpo "raw" EXACTO (boundary + token + dni):
        #   Sustituye '40896485' por el DNI que quieras, o deja fijo para probar
        #   Y el token 'kTnM8izp2sv...' que viste en DevTools
        body = (
            b"------WebKitFormBoundarypl6WiRpHkdmTbYjb\r\n"
            b'Content-Disposition: form-data; name="_token"\r\n\r\n'
            b"kTnM8izp2svQe67bkrNVMhBJebF4lVIU1Kc3XdOJ\r\n"
            b"------WebKitFormBoundarypl6WiRpHkdmTbYjb\r\n"
            b'Content-Disposition: form-data; name="dni"\r\n\r\n'
            + dni.encode("utf-8") +  # Insertar el DNI proveniente del wizard
            b"\r\n"
            b"------WebKitFormBoundarypl6WiRpHkdmTbYjb--\r\n"
        )

        # Enviar el POST con ese body "raw"
        resp = requests.post(url_form, headers=headers, data=body)
        _logger.info("POST status code: %s", resp.status_code)
        _logger.info("POST TEXT => %s", resp.text[:2000])

        if resp.status_code != 200:
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        tabla = soup.find("table", {"class": "table table-striped table-scroll"})
        if not tabla:
            _logger.info("No se encontró tabla => %s", resp.text[:500])
            return None

        fila = tabla.find("tbody").find("tr")
        celdas = fila.find_all("td")
        if len(celdas) < 4:
            return None

        return {
            'nombres': celdas[1].get_text(strip=True),
            'apellido_paterno': celdas[2].get_text(strip=True),
            'apellido_materno': celdas[3].get_text(strip=True),
        }
