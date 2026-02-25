from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProgramIcon(models.Model):
    _name = 'program.icon'
    _description = 'Program Icon'
    _order = "priority, sequence, id"

    name = fields.Char(string="Program Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    image_url = fields.Char(string="Icon URL")
    filename = fields.Char(string="Filename")

    @api.model
    def _get_contract_fields(self):
        contract_model = self.env['consignment.contract']
        fields_list = contract_model.fields_get().items()
        return [(field, meta['string']) for field, meta in fields_list]

    field_name = fields.Selection(
        selection='_get_contract_fields',
        string="Field Name",
        help="Field in the contract model"
    )

    priority = fields.Integer(string="Priority", default=10)
    sequence = fields.Integer(string="Display Order", default=10)