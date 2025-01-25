class ProductAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    def write(self, vals):
        vals['active'] = True
        vals['visibility'] = 'visible'  # Hace visible el atributo en líneas de venta
        return super().write(vals)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _create_variant_ids(self):
        """Sobrescribe para asegurar que las variantes sean visibles en ventas"""
        variants = super()._create_variant_ids()
        for variant in self.product_variant_ids:
            variant.sale_ok = True
            variant.active = True
        return variants