from odoo import api, fields, models
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class MergeOptionContractsWizard(models.TransientModel):
    _name = 'merge.option.contracts.wizard'
    _description = 'Merge option contracts Wizard'

    base_contract = fields.Many2one(comodel_name='consignment.contract',
        string='Base Contract')

    option_contract_ids = fields.Many2many('consignment.contract',string='Option Contracts')


    def action_merge(self):
        contracts = self.option_contract_ids.filtered(lambda contract: contract.to_be_merged) + self.base_contract

        contracts.merge_contracts(base_contract=self.base_contract)

        self.option_contract_ids.write({'to_be_merged':False})