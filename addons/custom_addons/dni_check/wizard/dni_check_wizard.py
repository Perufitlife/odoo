import logging
import requests

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class DniCheckWizard(models.TransientModel):
    _name = 'dni.check.wizard'
    _description = 'Wizard para consulta de DNI (ApisPeru + dniperu fallback)'

    dni = fields.Char('DNI', readonly=True)
    nombres = fields.Char('Nombres')
    apellido_paterno = fields.Char('Apellido Paterno')
    apellido_materno = fields.Char('Apellido Materno')
    sale_id = fields.Many2one('sale.order', 'Orden de Venta')
    mensaje = fields.Char('Mensaje', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        dni_val = res.get('dni')
        if dni_val:
            datos = self.consultar_dni(dni_val)
            if datos:
                res.update(datos)
            else:
                res['mensaje'] = 'No se encontraron datos para este DNI'
        return res

    def consultar_dni(self, dni):
        """
        Primero consulta a ApisPeru:
          - Si encuentra datos, retorna esos.
          - Si no, intenta con dniperu.com.
          - Si tampoco funciona, retorna None.
        """
        datos_apis = self._consultar_dni_apisperu(dni)
        if datos_apis:
            return datos_apis

        # Si ApisPeru devolvió None / no data, 
        # probamos dniperu:
        datos_dniperu = self._consultar_dni_dniperu(dni)
        if datos_dniperu:
            return datos_dniperu

        # Ninguno devolvió datos
        return None

    def _consultar_dni_apisperu(self, dni):
        """
        Lógica para ApisPeru. Usa tokens rotativos si así lo deseas,
        o un token fijo. 
        GET https://dniruc.apisperu.com/api/v1/dni/{dni}?token=XYZ
        """
        token = self._get_next_token()  # si tienes método para tokens rotativos
        if not token:
            _logger.info("No hay token configurado o no hay param 'apis_peru.tokens'")
            return None

        url = f"https://dniruc.apisperu.com/api/v1/dni/{dni}?token={token}"
        _logger.info("Consultando DNI en ApisPeru: %s", url)

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data_json = resp.json()
            _logger.debug("Respuesta ApisPeru: %s", data_json)

            # caso OK => 'dni' en data_json
            if 'dni' in data_json:
                nombres = data_json.get('nombres', '')
                ap_pat = data_json.get('apellidoPaterno', '')
                ap_mat = data_json.get('apellidoMaterno', '')
                if nombres:
                    return {
                        'nombres': nombres,
                        'apellido_paterno': ap_pat,
                        'apellido_materno': ap_mat
                    }
            else:
                _logger.warning("ApisPeru: %s", data_json.get('message') or "No results")

            return None

        except Exception as e:
            _logger.error("Error consultando ApisPeru: %s", e, exc_info=True)
            return None

    def _consultar_dni_dniperu(self, dni):
        """
        Lógica vieja de dniperu.com, 
        POST a https://dniperu.com/querySelector con data={'dni4':dni}
        """
        url_form = "https://dniperu.com/querySelector"
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": "https://dniperu.com",
            "Referer": "https://dniperu.com/buscar-dni-nombres-apellidos/",
        })
        payload = {"dni4": dni}

        try:
            resp_post = session.post(url_form, data=payload, timeout=10)
            _logger.info("Dniperu POST status: %s", resp_post.status_code)
            if resp_post.status_code != 200:
                return None

            data_json = resp_post.json()
            mensaje_raw = data_json.get("mensaje", "")
            lineas = mensaje_raw.split("\n")

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
                return None

            return {
                'nombres': nombres,
                'apellido_paterno': apellido_paterno,
                'apellido_materno': apellido_materno
            }

        except Exception as e:
            _logger.error("Error consultando dniperu.com: %s", e, exc_info=True)
            return None

    def _get_next_token(self):
        """
        Opcional, si quieres usar la rotación de tokens para ApisPeru,
        mismo approach que te pasé antes.
        """
        icp = self.env['ir.config_parameter'].sudo()
        tokens_str = icp.get_param('apis_peru.tokens', '')
        if not tokens_str.strip():
            return None

        tokens_list = [t.strip() for t in tokens_str.split(',') if t.strip()]
        if not tokens_list:
            return None

        index_str = icp.get_param('apis_peru.token_index', '0')
        try:
            index = int(index_str)
        except ValueError:
            index = 0

        token = tokens_list[index % len(tokens_list)]
        icp.set_param('apis_peru.token_index', str(index+1))

        return token
