# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import Command, models, fields, api, _
from odoo.tools import frozendict
from odoo.exceptions import ValidationError


class SplitContractW(models.TransientModel):
    _name = 'split.contract.wizard'
    _description = 'Split contract wizard'
    _check_company_auto = True

    number_of_lots = fields.Integer(string="Lots to use",
                                    help='Lots to allocate in new contract')
    load_option = fields.Integer('Load option',
                                 default=lambda self: self.env.context.get('load_option'),
                                 help="Whole number of truck load in the contract")
    created_loads = fields.Integer('Created loads',
                                   default=lambda self: self.env.context.get('created_loads'),
                                   help="Number of loads created from the contract")
    
    available_loads = fields.Integer('Available loads',
                                     default=lambda self: self.env.context.get('available_loads'),
                                     help="Number of loads available to create from the contract")
    
    batch_size = fields.Integer('Batch size',
                                default=lambda self: self.env.context.get('batch_size'),
                                help="Number of heads in each batch")
    split_message = fields.Html(compute='_compute_action_message')



    @api.depends('number_of_lots')
    def _compute_action_message(self):
        for record in self:
            source_contract_id = self.env.context.get('active_ids')
            source_contract = self.env['consignment.contract'].browse(source_contract_id)
            record.split_message = f'''You are about to create a contract with {self.batch_size * self.number_of_lots} heads \n
                                        from the source contract CN {source_contract.id:05d}'''


    # def action_create_contracts(self):
    #     if self.number_of_lots <= 0 or self.number_of_lots > self.available_loads:
    #         raise ValidationError(_('Please enter a valid number of contracts: 1 - %s') % self.available_loads)
    #     source_contract_id = self.env.context.get('active_ids')
    #     source_contract = self.env['consignment.contract'].browse(source_contract_id)
    #     vals_list = []
    #     contract = {'seller_id':source_contract.seller_id.id,
    #                 'sale_type': source_contract.sale_type.id,
    #                 'auction_id': source_contract.auction_id.id,
    #                 'kind1': source_contract.kind1.id,
    #                 'kind2': source_contract.kind2.id,
    #                 'head1': self.batch_size * self.number_of_lots, # calculated
    #                 'source_contract_id': source_contract.id,
    #                 'lot_number': source_contract.lot_number + chr(97) # char(97) = 'a', char(98)='b' and so on,
    #                 }    
    #     vals_list.append(contract)

    #     source_contract.created_loads += self.number_of_lots

    #     self.env['consignment.contract'].create(vals_list)

    def action_create_contracts(self):
        if self.number_of_lots <= 0 or self.number_of_lots > self.available_loads:
            raise ValidationError(_('Please enter a valid number of contracts: 1 - %s') % self.available_loads)
        source_contract_id = self.env.context.get('active_ids')
        source_contract = self.env['consignment.contract'].browse(source_contract_id)

        new_contract = source_contract.copy(default={
                    'head1': self.batch_size * self.number_of_lots, # calculated
                    'source_contract_id': source_contract.id,
                    'lot_number': source_contract.lot_number + chr(65), # char(97) = 'a', char(98)='b' and so on
                    'auction_id': source_contract.auction_id.id if source_contract.auction_id else False,
                    })

        source_contract.created_loads += self.number_of_lots

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'consignment.contract',
            'view_mode': 'form',
            'res_id': new_contract.id,
            'target': 'current',
        }