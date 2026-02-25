# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RepCommision(models.Model):
    _name = 'res.rep'
    _description = 'Representatives and commissions'
    _order = "id"

    seller_id = fields.Many2one(
        comodel_name='res.partner',
        default=lambda self: self.env['res.partner'].search([('id','=',self.env.context.get('seller',False))]) ,
        string="Seller", required=True)
    
    rep_id = fields.Many2one(
        comodel_name='res.partner',
        string="Rep.", required=True)
    
    percentage_commission = fields.Float('% Commission')
    
    consigning_rep = fields.Boolean('Consigning Rep', default=False)

    contract_id = fields.Many2one(
        comodel_name='consignment.contract',
        string='Contract'
    )
    
    delivery_id = fields.Many2one(
        comodel_name='consignment.delivery',
        string='Delivery',
        related='contract_id.delivery_id',
    )

    rep_sold_head_count = fields.Float(
        string='Sold Head Count',
        compute='_compute_rep_head_count',
        store=False,
        help='Calculated head count for this rep based on commission percentage and contract head count'
    )

    rep_delivered_head_count = fields.Float(
        string='Delivered Head Count',
        compute='_compute_rep_head_count',
        store=False,
        help='Calculated head count for this rep based on commission percentage and delivery head count'
    )

    active = fields.Boolean('active',default=True)
    
    @api.depends('percentage_commission', 'delivery_id.head_count', 'contract_id.head1', 'contract_id.head2')
    def _compute_rep_head_count(self):
        """Calculate the head count for this rep based on commission percentage"""
        for record in self:
            # Handle sold head count (contract)
            if record.contract_id:
                record.rep_sold_head_count = self._distribute_head_count_for_contract(record.contract_id, record)
            else:
                record.rep_sold_head_count = 0.0
                
            # Handle delivered head count (delivery)
            if record.delivery_id:
                record.rep_delivered_head_count = self._distribute_head_count_for_delivery(record.delivery_id, record)
            else:
                record.rep_delivered_head_count = 0.0

    def _distribute_head_count_for_contract(self, contract, current_rep):
        """Distribute contract head count among reps, ensuring whole numbers and proper total"""
        if not contract or not current_rep.percentage_commission:
            return 0.0
            
        # Get all reps for this contract
        all_reps = self.search([('contract_id', '=', contract.id), ('active', '=', True)])
        total_heads = (contract.head1 or 0) + (contract.head2 or 0)
        
        return self._calculate_distributed_head_count(all_reps, current_rep, total_heads)

    def _distribute_head_count_for_delivery(self, delivery, current_rep):
        """Distribute delivery head count among reps, ensuring whole numbers and proper total"""
        if not delivery or not current_rep.percentage_commission:
            return 0.0
            
        # Get all reps for this delivery (through contract)
        all_reps = self.search([('delivery_id', '=', delivery.id), ('active', '=', True)])
        total_heads = delivery.head_count or 0
        
        return self._calculate_distributed_head_count(all_reps, current_rep, total_heads)

    def _calculate_distributed_head_count(self, all_reps, current_rep, total_heads):
        """Calculate distributed head count ensuring whole numbers and consigning rep gets remainder"""
        if not total_heads or not all_reps:
            return 0.0
            
        # Calculate raw distributions
        distributions = []
        total_percentage = 0
        consigning_rep = None
        
        for rep in all_reps:
            if rep.percentage_commission:
                raw_count = (rep.percentage_commission / 100.0) * total_heads
                distributions.append({
                    'rep': rep,
                    'raw_count': raw_count,
                    'floor_count': int(raw_count)
                })
                total_percentage += rep.percentage_commission
                if rep.consigning_rep:
                    consigning_rep = rep
        
        if not distributions:
            return 0.0
            
        # Calculate floor sum and remainder
        floor_sum = sum(d['floor_count'] for d in distributions)
        remainder = int(total_heads) - floor_sum
        
        # If there's no consigning rep, find the rep with the highest fractional part
        if not consigning_rep and remainder > 0:
            max_fractional = 0
            for d in distributions:
                fractional_part = d['raw_count'] - d['floor_count']
                if fractional_part > max_fractional:
                    max_fractional = fractional_part
                    consigning_rep = d['rep']
        
        # Distribute the remainder
        final_distributions = {}
        for d in distributions:
            rep = d['rep']
            final_count = d['floor_count']
            
            # Give remainder to consigning rep
            if rep == consigning_rep and remainder > 0:
                final_count += remainder
                
            final_distributions[rep.id] = final_count
        
        # Return the count for the current rep
        return final_distributions.get(current_rep.id, 0.0)

    @api.constrains('consigning_rep', 'contract_id')
    def _check_consigning_rep(self):
        for record in self:
            if record.consigning_rep and record.contract_id:
                # Find other reps in the same contract that are marked as consigning
                other_consigning_reps = self.search([
                    ('contract_id', '=', record.contract_id.id),
                    ('consigning_rep', '=', True),
                    ('id', '!=', record.id)
                ])
                if other_consigning_reps:
                    # Instead of raising an error, uncheck the other reps
                    other_consigning_reps.write({'consigning_rep': False})

    def unlink(self):
        for rep in self:
            if rep.contract_id:
                rep.contract_id.message_unsubscribe(rep.rep_id.mapped('id'))
        return super(RepCommision, self).unlink()
    
    def create(self,vals):
        res = super(RepCommision, self).create(vals)
        for rep in res:
            if rep.contract_id:
                rep.contract_id.message_subscribe(rep.rep_id.mapped('id'))
        return res
    