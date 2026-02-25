# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ContractAddendum(models.Model):
    _name = 'contract.addendum'
    _description = 'Contract Addendum'
    _order = "sequence, id"

    def _default_sequence(self):
        rec = self.search([], limit=1, order="sequence DESC")
        return rec.sequence and rec.sequence + 1 or 1

    seller_id_domain = fields.Many2many(
        comodel_name='res.partner',
        relation='seller_domain_rel',
        compute='_compute_seller_id_domain')    

    seller_id = fields.Many2one(
        comodel_name='res.partner',
        # domain=[('id', 'in', seller_id_domain.ids)],
        string="Addendum Seller", 
        required=True,
        help='''Select the seller for this addendum.
        if you don't see the seller you want, please add them as a child contact
        of the main seller on the contract with type "Payment Address".''',)

    lien_holder_id_domain = fields.Many2many(
        comodel_name='res.partner',
        relation='lien_domain_rel',
        compute='_compute_lien_holder_id_domain')
    
    lien_holder_id = fields.Many2one(
        comodel_name='res.partner',
        string="Lien Holder", 
        compute='_compute_lien_holder_id',
        store=True, 
        readonly=False, 
        precompute=True,
        )

    seller_address = fields.Char(
        string='Address',
        compute='_compute_seller_address',
        store=False,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        store=True)

    percentage = fields.Integer('%')

    contract_id = fields.Many2one(
        comodel_name='consignment.contract',
        string='Contract'
    )

    @api.depends('contract_id')
    def _compute_seller_id_domain(self):
        ''' Domain: contract seller + contract seller's payment-address children. '''
        for addendum in self:
            seller = addendum.contract_id.seller_id
            if not seller:
                addendum.seller_id_domain = [(5, 0, 0)]
                continue
            payment_children = seller.child_ids.filtered(lambda p: p.type == 'payment')
            ids = [seller.id] + payment_children.ids
            addendum.seller_id_domain = [(6, 0, ids)]

    @api.depends('contract_id', 'contract_id.head1', 'contract_id.head2', 'contract_id.addendum_ids')
    @api.onchange('contract_id', 'contract_id.head1', 'contract_id.head2')
    def _compute_head_count(self):
        for addendum in self:
            if addendum.contract_id and len(addendum.contract_id.addendum_ids) == 1:
                addendum.head_count = (addendum.contract_id.head1 or 0) + (addendum.contract_id.head2 or 0)

    head_count = fields.Integer(
        'Head Count',
        compute='_compute_head_count',
        store=True,
        readonly=False,
        precompute=True
    )

    @api.depends('head_count', 'contract_id.seller_need_part_payment', 'contract_id')
    @api.onchange('head_count', 'contract_id', 'contract_id.seller_need_part_payment')
    def _compute_part_payment(self):
        for addendum in self:
            if addendum.contract_id and addendum.contract_id.seller_need_part_payment:
                addendum.part_payment = addendum.head_count * 30
            else:
                addendum.part_payment = 0

    part_payment = fields.Monetary(
        'Part Payment',
        currency_field='currency_id',
        compute='_compute_part_payment',
        store=True,
        readonly=False,
        precompute=True
    )

    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer("Sequence", default=_default_sequence)

    @api.depends('seller_id')
    def _compute_lien_holder_id_domain(self):
        for rec in self:
            rec.lien_holder_id_domain = False
            if rec.seller_id and len(rec.seller_id.lien_holder_ids) > 1:
                rec.lien_holder_id_domain = [(6, 0, rec.seller_id.lien_holder_ids.ids)]

    @api.depends('seller_id')
    def _compute_lien_holder_id(self):
        for addendum in self:
            addendum.lien_holder_id = addendum.seller_id.default_lien_holder_id.id 

    @api.depends('seller_id', 'contract_id', 'contract_id.seller_id')
    def _compute_lien_holder_id(self):
        for addendum in self:
            # Prefer contract seller's default lien holder when addendum belongs to a contract
            seller = addendum.contract_id.seller_id if addendum.contract_id else addendum.seller_id
            addendum.lien_holder_id = seller.default_lien_holder_id.id if (seller and seller.default_lien_holder_id) else False 

    @api.depends('seller_id')
    def _compute_seller_address(self):
        for addendum in self:
            addendum.seller_address = addendum.seller_id.contact_address_inline_clean 