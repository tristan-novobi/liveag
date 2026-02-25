from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ContractActivityLog(models.Model):
    _name = 'contract.activity.log'
    _description = 'Contract Activity Log'
    _order = 'timestamp desc'

    def _default_sequence(self):
        rec = self.search([], limit=1, order="sequence DESC")
        return rec.sequence and rec.sequence + 1 or 1


    contract_id = fields.Many2one(
      'consignment.contract',
      string="Contract",
      required=True,
      ondelete="cascade"
    )
    field_name = fields.Char(string="Field Changed", required=True)
    field_label = fields.Char(string="Field Label", compute='_compute_field_label', store=False)
    old_value = fields.Text(string="Original Value")
    new_value = fields.Text(string="New Value")
    message = fields.Text(string="Message")
    timestamp = fields.Datetime(string="Timestamp", required=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.partner', string="Changed By", required=True)

    @api.depends('field_name')
    def _compute_field_label(self):
        """Compute the human-readable label for the field."""
        for record in self:
            if record.field_name and record.contract_id:
                # Get the field label using _fields metadata
                field = record.contract_id._fields.get(record.field_name)
                record.field_label = field.string if field else record.field_name
            else:
                record.field_label = record.field_name