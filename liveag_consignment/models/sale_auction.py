# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
import logging

AUCTION_STATE = [
    ('pending', "Pending"),
    ('scheduled', "Scheduled"),
    ('live', "Live"),
    ('finished', "Finished"),
    ('closed', "Closed"),
    ('cancel', "Cancelled"),
]

class SaleAuction(models.Model):
    _name = 'sale.auction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Auction'

    name = fields.Char(string='Name', required=True)
    location = fields.Char(string='Location')
    catalog_deadline = fields.Date(string='Catalog Deadline')
    is_public = fields.Boolean(string="Is Public", default=False)
    state = fields.Selection(
        selection=AUCTION_STATE,
        string="Status",
        copy=False,
        tracking=True,
        default='pending')
    head_offered = fields.Integer(
        string="Head Offered",
        compute="_compute_head_offered",
        store=False,
        help="Sum of head1 and head2 fields from related contracts."
    )
    head_sold = fields.Integer(string="Head Sold", store=False, compute="_compute_head_sold")
    number_sale_days = fields.Integer(string="Number of Sale Days")
    sale_date_begin = fields.Datetime(string="Sale Date Begin")
    sale_date_est_end = fields.Datetime(string="Sale Date Est. End")

    percentage_pending = fields.Float(string="Pending", compute="_compute_percentages", store=False)
    percentage_sold = fields.Float(string="Sold", compute="_compute_percentages", store=False)
    percentage_scratched = fields.Float(string="Scratched", compute="_compute_percentages", store=False)
    percentage_no_sale = fields.Float(string="No Sale", compute="_compute_percentages", store=False)

    sale_type = fields.Many2one(
        comodel_name='sale.type',
        string="Sale Type")
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company)
    contracts_ids = fields.One2many(
                            'consignment.contract',
                            'auction_id',
                            string="Contracts", 
                            help="")

    filtered_contracts_ids = fields.One2many(
                            'consignment.contract',
                            compute="_compute_contracts",
                            string="Contracts (Filtered)")

    pending_contracts_ids = fields.One2many(
                            'consignment.contract',
                            compute="_compute_contracts",
                            string="Contracts (Pending)")
                            
    sold_contracts_ids = fields.One2many(
                            'consignment.contract',
                            compute="_compute_contracts",
                            string="Contracts (Sold)")

    scratched_contracts_ids = fields.One2many(
                            'consignment.contract',
                            compute="_compute_contracts",
                            string="Contracts (Scratched)")
                            
    no_sale_contracts_ids = fields.One2many(
                            'consignment.contract',
                            compute="_compute_contracts",
                            string="Contracts (No Sale)")

    canceled_contracts_ids = fields.One2many(
                            'consignment.contract',
                            compute="_compute_contracts",
                            string="Contracts (Canceled)")

    draft_contracts_ids = fields.One2many(
                            'consignment.contract',
                            compute="_compute_contracts",
                            string="Contracts (Draft)")
    
    def write(self,vals):
        res = super(SaleAuction,self).write(vals)
        for auction in self:
            if auction.contracts_ids:
                # raise ValidationError(self._origin.contracts_ids)
                auction.contracts_ids.set_is_supplemental()

    def set_sale_order_in_contracts(self):
        sale_order = 1
        for contract in self.filtered_contracts_ids:
                contract.sale_order = sale_order
                contract.lotted = True
                sale_order += 1

    def _get_sorted_contracts(self, states):
        return sorted(
            self.contracts_ids.filtered(lambda c: c.state in states),
            key=lambda c: (c.sale_order == 0, c.sale_order))

    @api.depends('contracts_ids.state')
    def _compute_contracts(self):
        for auction in self:
            auction.filtered_contracts_ids = [(6, 0, [c.id for c in auction._get_sorted_contracts(['approved', 'ready_for_sale'])])]
            auction.pending_contracts_ids = [(6, 0, [c.id for c in auction._get_sorted_contracts(['submitted', 'changed'])])]
            auction.sold_contracts_ids = [(6, 0, [c.id for c in auction._get_sorted_contracts(['sold', 'delivery_ready', 'delivered'])])]
            auction.scratched_contracts_ids = [(6, 0, [c.id for c in auction._get_sorted_contracts(['scratched'])])]
            auction.no_sale_contracts_ids = [(6, 0, [c.id for c in auction._get_sorted_contracts(['no_sale'])])]
            auction.canceled_contracts_ids = [(6, 0, [c.id for c in auction._get_sorted_contracts(['canceled'])])]
            auction.draft_contracts_ids = [(6, 0, [c.id for c in auction._get_sorted_contracts(['draft'])])]

    @api.depends('contracts_ids', 'contracts_ids.head1', 'contracts_ids.head2')
    def _compute_head_offered(self):
        for auction in self:
            auction.head_offered = 0
            valid_contracts = auction.contracts_ids.filtered(
                lambda c: c.state not in ['draft', 'canceled', 'submitted', 'changed', 'rejected']
            )
            for contract in valid_contracts:
                auction.head_offered += (contract.head1 or 0) + (contract.head2 or 0)

    @api.depends('contracts_ids', 'contracts_ids.state', 'contracts_ids.head1', 'contracts_ids.head2')
    def _compute_head_sold(self):
        for auction in self:
            auction.head_sold = 0
            valid_contracts = auction.contracts_ids.filtered(
                lambda c: c.state in ['sold', 'delivery_ready', 'delivered']
            )
            for contract in valid_contracts:
                auction.head_sold += (contract.head1 or 0) + (contract.head2 or 0)

    def action_export_filtered_contracts(self):
        self.ensure_one()
        if self.filtered_contracts_ids:
            return self.filtered_contracts_ids.action_export_auctic_csv()
        
    def _get_buyers_final_data(self, buyer_id=None):
        """Organize sold contracts by buyer for the buyer's final report."""
        self.ensure_one()
        date_from = self.env.context.get('date_from')
        date_to = self.env.context.get('date_to')
        # Get all sold contracts, filtered by buyer if specified
        sold_contracts = self.sold_contracts_ids
        if buyer_id:
            sold_contracts = sold_contracts.filtered(lambda c: c.buyer_id.id == buyer_id)
        
        # Filter by date if specified
        if date_from:
            # Convert string date to datetime.date if it's a string
            if isinstance(date_from, str):
                date_from = fields.Date.from_string(date_from)
            sold_contracts = sold_contracts.filtered(lambda c: c.sold_date and c.sold_date >= date_from)

        if date_to:
            if isinstance(date_to, str):
                date_to = fields.Date.from_string(date_to)
            sold_contracts = sold_contracts.filtered(lambda c: c.sold_date and c.sold_date <= date_to)

        sold_contracts = sold_contracts.sorted(lambda c: (c.buyer_id.name or '', c.lot_number or 0))
        
        buyers_data = []
        
        for buyer in sold_contracts.mapped('buyer_id'):
            contracts = sold_contracts.filtered(lambda c: c.buyer_id == buyer)
            buyer_numbers = contracts.mapped('buyer_number')
            for buyer_number in buyer_numbers:
                contract_by_buyer_number = contracts.filtered(lambda c: c.buyer_number == buyer_number)
                contracts_data = []
                for contract in contract_by_buyer_number:
                    contracts_data.append({
                        'lot_number': str(contract.lot_number or ''),
                        'state': contract.state_of_nearest_town.code,
                        'head1': int(contract.head1 or 0),
                        'kind1': str(contract.kind1.name if contract.kind1 else ''),
                        'weight1': float(contract.weight1 or 0.0),
                        'price1': float(contract.sold_price or 0.0),
                        'head2': int(contract.head2 or 0),
                        'kind2': str(contract.kind2.name if contract.kind2 else ''),
                        'weight2': float(contract.weight2 or 0.0),
                        'price2': float((contract.sold_price - contract.price_back) if contract.price_back else 0.0),
                        'delivery_date_range': contract.delivery_date_range or '',
                        'delivery_date_start': contract.delivery_date_start,
                        'delivery_date_end': contract.delivery_date_end,
                        'part_payment': float(contract.buyer_part_payment or 0.0)
                    })
                
                total_head = sum((c.get('head1', 0) or 0) + (c.get('head2', 0) or 0) for c in contracts_data)
                total_part_payment = sum(c.get('part_payment', 0.0) or 0.0 for c in contracts_data)
                
                buyers_data.append({
                    'buyer': buyer,
                    'buyer_number': buyer_number,
                    'contracts': contracts_data,
                    'total_head': total_head,
                    'total_part_payment': total_part_payment
                })
        
        return sorted(buyers_data, key=lambda x: x['buyer'].name or '')

    def _get_sellers_recap_data(self, seller_id=None):
        """Organize sold contracts by seller and lien holder for the seller's final report."""
        self.ensure_one()
        date_from = self.env.context.get('date_from')
        date_to = self.env.context.get('date_to')
        
        # Get all sold contracts
        sold_contracts = self.sold_contracts_ids
        
        # Filter by date if specified
        if date_from:
            if isinstance(date_from, str):
                date_from = fields.Date.from_string(date_from)
            sold_contracts = sold_contracts.filtered(lambda c: c.sold_date and c.sold_date >= date_from)

        if date_to:
            if isinstance(date_to, str):
                date_to = fields.Date.from_string(date_to)
            sold_contracts = sold_contracts.filtered(lambda c: c.sold_date and c.sold_date <= date_to)

        sellers_data = []
        sold_contracts = sold_contracts.sorted(lambda c: (c.lot_number or 0))
        
        # Helper function to get seller data from contract or addendum
        def get_contract_seller_data(contract, addendum=None):
            if addendum:
                return {
                    'seller_id': addendum.seller_id,
                    'lien_holder_id': addendum.lien_holder_id,
                    'head1': int(addendum.head_count) if addendum.head_count else 0,
                    'head2': 0,
                    'part_payment': float(addendum.part_payment or 0.0)
                }
            return {
                'seller_id': contract.seller_id,
                'lien_holder_id': contract.lien_holder_id,
                'head1': int(contract.head1) if contract.head1 else 0,
                'head2': int(contract.head2) if contract.head2 else 0,
                'part_payment': float(contract.seller_part_payment or 0.0)
            }

        # Build a list of all seller entries (from contracts and addendums)
        seller_entries = []
        for contract in sold_contracts:
            if contract.addendum_ids:
                # Add an entry for each addendum
                for addendum in contract.addendum_ids:
                    seller_data = get_contract_seller_data(contract, addendum)
                    seller_entries.append((contract, seller_data))
            else:
                # Add an entry for the contract
                seller_data = get_contract_seller_data(contract)
                seller_entries.append((contract, seller_data))

        # Filter by seller_id if specified
        if seller_id:
            seller_entries = [
                entry for entry in seller_entries 
                if entry[1]['seller_id'].id == seller_id
            ]

        # Group by seller and lien holder
        seller_groups = {}
        for contract, seller_data in seller_entries:
            seller = seller_data['seller_id']
            lien_holder = seller_data['lien_holder_id']
            
            if seller not in seller_groups:
                seller_groups[seller] = {}
            if lien_holder not in seller_groups[seller]:
                seller_groups[seller][lien_holder] = []
            
            contract_data = {
                'lot_number': str(contract.lot_number or ''),
                'state': contract.state_of_nearest_town.code,
                'head1': seller_data['head1'],
                'kind1': str(contract.kind1.name if contract.kind1 else ''),
                'weight1': float(contract.weight1 or 0.0),
                'price1': float(contract.sold_price or 0.0),
                'head2': seller_data['head2'],
                'kind2': str(contract.kind2.name if contract.kind2 else ''),
                'weight2': float(contract.weight2 or 0.0),
                'price2': float((contract.sold_price - contract.price_back) if contract.price_back else 0.0),
                'delivery_date_range': contract.delivery_date_range or '',
                'delivery_date_start': contract.delivery_date_start,
                'delivery_date_end': contract.delivery_date_end,
                'part_payment': seller_data['part_payment']
            }
            seller_groups[seller][lien_holder].append(contract_data)

        # Build final sellers_data structure
        for seller, lien_holder_groups in seller_groups.items():
            lien_holder_data = []
            seller_total_head = 0
            seller_total_part_payment = 0.0
            
            for lien_holder, contracts in lien_holder_groups.items():
                total_head = sum((c['head1'] or 0) + (c['head2'] or 0) for c in contracts)
                total_part_payment = sum(c['part_payment'] or 0.0 for c in contracts)
                
                seller_total_head += total_head
                seller_total_part_payment += total_part_payment
                
                lien_holder_data.append({
                    'lien_holder': lien_holder,
                    'contracts': sorted(contracts, key=lambda x: x['lot_number']),
                    'total_head': total_head,
                    'total_part_payment': total_part_payment
                })
            
            sellers_data.append({
                'seller': seller,
                'lien_holder_groups': sorted(
                    lien_holder_data,
                    # Put None/False lien holders first, then sort by name
                    key=lambda x: (x['lien_holder'] is not None, x['lien_holder'].name if x['lien_holder'] else '')
                ),
                'total_head': seller_total_head,
                'total_part_payment': seller_total_part_payment
            })

        return sorted(sellers_data, key=lambda x: x['seller'].name or '')
    
    def get_all_reps_recap_final_data(self):
        _logger = logging.getLogger(__name__)
        # Get all unique rep IDs from all contracts
        rep_ids = self.sold_contracts_ids.mapped('rep_ids.rep_id').ids
        # Get the rep partner record directly
        rep_partners = self.env['res.partner'].browse(rep_ids)
        reps_data = []
        for rep_partner in rep_partners:
            _logger.info(f"Processing rep: {rep_partner.name}")
            
            # Find all rep records for this rep_id
            rep_records = self.env['res.rep'].search([
                ('rep_id', '=', rep_partner.id),
                ('contract_id', 'in', self.sold_contracts_ids.ids),
                ('active', '=', True)
            ])
            _logger.info(f"Found {len(rep_records)} rep records")
            
            # Get the contracts through the rep records
            sold_contracts = rep_records.mapped('contract_id')
            
            sold_contracts = sold_contracts.sorted(lambda c: c.lot_number or 0)
            _logger.info(f"Found {len(sold_contracts)} contracts for rep")
            
            contracts_data = []
            for contract in sold_contracts:
                contract_data = {
                    'lot_number': contract.lot_number,
                    'seller': contract.seller_id.name,
                    'state': dict(contract._fields['state'].selection).get(contract.state),
                    'buyer': contract.buyer_id.name,
                    'head1': contract.head1 or 0,
                    'price': contract.sold_price,
                    'head2': contract.head2 or 0,
                    'price2': float((contract.sold_price - contract.price_back) if contract.price_back else 0.0),
                    'delivery_date_range': contract.delivery_date_range,
                    'delivery_date_start': contract.delivery_date_start,
                    'delivery_date_end': contract.delivery_date_end,
                }
                _logger.info(f"Added contract data: {contract_data}")
                contracts_data.append(contract_data)
            
            # Calculate total head count
            total_head = sum(c['head1'] + c['head2'] for c in contracts_data)
            
            # Always return a list with a single rep's data
            reps_data.append({
                'rep': rep_partner,
                'contracts': contracts_data,
                'total_head': total_head,
            })
        
        return reps_data


    def _get_rep_recap_data(self, rep_id=None):
        """Organize sold contracts by rep for the rep's final report."""
        self.ensure_one()
        _logger = logging.getLogger(__name__)
        date_from = self.env.context.get('date_from')
        date_to = self.env.context.get('date_to')

        if not rep_id:
            return self.get_all_reps_recap_final_data()
            # return []
        
        # Get the rep partner record directly
        rep_partner = self.env['res.partner'].browse(rep_id)
        if not rep_partner.exists():
            return []
        
        _logger.info(f"Processing rep: {rep_partner.name}")
        
        # Find all rep records for this rep_id
        rep_records = self.env['res.rep'].search([
            ('rep_id', '=', rep_id),
            ('contract_id', 'in', self.sold_contracts_ids.ids),
            ('active', '=', True)
        ])
        _logger.info(f"Found {len(rep_records)} rep records")
        
        # Get the contracts through the rep records
        sold_contracts = rep_records.mapped('contract_id')
        
        # Filter by date if specified
        if date_from:
            if isinstance(date_from, str):
                date_from = fields.Date.from_string(date_from)
            sold_contracts = sold_contracts.filtered(lambda c: c.sold_date and c.sold_date >= date_from)

        if date_to:
            if isinstance(date_to, str):
                date_to = fields.Date.from_string(date_to)
            sold_contracts = sold_contracts.filtered(lambda c: c.sold_date and c.sold_date <= date_to)

        sold_contracts = sold_contracts.sorted(lambda c: c.lot_number or 0)
        _logger.info(f"Found {len(sold_contracts)} contracts for rep")
        
        contracts_data = []
        for contract in sold_contracts:
            contract_data = {
                'lot_number': contract.lot_number,
                'seller': contract.seller_id.name,
                'state': dict(contract._fields['state'].selection).get(contract.state),
                'buyer': contract.buyer_id.name,
                'head1': contract.head1 or 0,
                'price': contract.sold_price,
                'head2': contract.head2 or 0,
                'price2': float((contract.sold_price - contract.price_back) if contract.price_back else 0.0),
                'delivery_date_range': contract.delivery_date_range,
                'delivery_date_start': contract.delivery_date_start,
                'delivery_date_end': contract.delivery_date_end,
            }
            _logger.info(f"Added contract data: {contract_data}")
            contracts_data.append(contract_data)
        
        # Calculate total head count
        total_head = sum(c['head1'] + c['head2'] for c in contracts_data)
        
        # Always return a list with a single rep's data
        return [{
            'rep': rep_partner,
            'contracts': contracts_data,
            'total_head': total_head,
        }]

    def action_export_buyers_final(self):
        self.ensure_one()
        if not self.exists():
            raise ValidationError('The auction record no longer exists.')
        if not self.sold_contracts_ids:
            raise ValidationError('No sold contracts found for this auction')
        
        return self.env.ref('liveag_consignment.buyers_final_report').with_context(
            active_model=self._name,
            active_id=self.id
        ).report_action(self)
    
    def action_export_sellers_final(self):
        self.ensure_one()
        if not self.exists():
            raise ValidationError('The auction record no longer exists.')
        if not self.sold_contracts_ids:
            raise ValidationError('No sold contracts found for this auction')
        
        return self.env.ref('liveag_consignment.seller_final_report').with_context(
            active_model=self._name,
            active_id=self.id
        ).report_action(self)

    def action_print_buyer_report(self):
        self.ensure_one()
        if not self.sold_contracts_ids:
            raise ValidationError('No sold contracts found for this auction')
        
        buyer_ids = self.sold_contracts_ids.mapped('buyer_id').ids
        return {
            'name': 'Select Buyer',
            'type': 'ir.actions.act_window',
            'res_model': 'buyer.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_auction_id': self.id,
                'buyer_ids': buyer_ids,
            }
        }
        
    def action_print_seller_report(self):
        self.ensure_one()
        if not self.sold_contracts_ids:
            raise ValidationError('No sold contracts found for this auction')
        
        # Get sellers from both contracts and addendums
        contract_seller_ids = self.sold_contracts_ids.mapped('seller_id').ids
        addendum_seller_ids = self.sold_contracts_ids.mapped('addendum_ids.seller_id').ids
        
        # Combine and remove duplicates
        seller_ids = list(set(contract_seller_ids + addendum_seller_ids))
        
        return {
            'name': 'Select Seller',
            'type': 'ir.actions.act_window',
            'res_model': 'seller.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_auction_id': self.id,
                'seller_ids': seller_ids,
            }
        }
        
    def action_print_rep_report(self):
        self.ensure_one()
        if not self.sold_contracts_ids:
            raise ValidationError('No sold contracts found for this auction')
        
        # Get all unique rep IDs from all contracts
        rep_ids = self.sold_contracts_ids.mapped('rep_ids').ids
        
        return {
            'name': 'Select Rep',
            'type': 'ir.actions.act_window',
            'res_model': 'rep.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_auction_id': self.id,
                'rep_ids': rep_ids,
            }
        }
    def action_print_rep_report_final(self):
        self.ensure_one()
        if not self.exists():
            raise ValidationError('The auction record no longer exists.')
        if not self.sold_contracts_ids:
            raise ValidationError('No sold contracts found for this auction')
        
        return self.env.ref('liveag_consignment.action_report_rep_final').with_context(
            active_model=self._name,
            active_id=self.id
        ).report_action(self)


    @api.depends('contracts_ids.state')
    def _compute_percentages(self):
        for auction in self:
            if not auction.contracts_ids:
                auction.percentage_pending = 0
                auction.percentage_sold = 0
                auction.percentage_scratched = 0
                auction.percentage_no_sale = 0
                continue

            # Calculate total head count
            total_head = sum(
                contract.head1 + (contract.head2 or 0)
                for contract in auction.contracts_ids
            )

            if total_head == 0:
                auction.percentage_pending = 0
                auction.percentage_sold = 0
                auction.percentage_scratched = 0
                auction.percentage_no_sale = 0
                continue

            # Calculate head counts for each state
            state_counts = {
                'ready_for_sale': 0,  # pending
                'sold': 0,
                'delivery_ready': 0,  # sold
                'delivered': 0,       # sold
                'scratched': 0,
                'no_sale': 0
            }

            for contract in auction.contracts_ids:
                head_count = contract.head1 + (contract.head2 or 0)
                if contract.state in state_counts:
                    state_counts[contract.state] += head_count

            # Calculate percentages
            auction.percentage_pending = (state_counts['ready_for_sale'] / total_head) * 100
            auction.percentage_sold = ((state_counts['sold'] + state_counts['delivery_ready'] + state_counts['delivered']) / total_head) * 100
            auction.percentage_scratched = (state_counts['scratched'] / total_head) * 100
            auction.percentage_no_sale = (state_counts['no_sale'] / total_head) * 100

    def dummy(self):
        """Empty method for dropdown toggle button"""
        pass

    # ============================== EMAIL SENDING (BATCH) ==============================
    def _get_partners_for_report_type(self, report_type):
        self.ensure_one()
        if report_type == 'buyer_report':
            return self.sold_contracts_ids.mapped('buyer_id')
        if report_type == 'seller_report':
            contract_seller_ids = self.sold_contracts_ids.mapped('seller_id').ids
            addendum_seller_ids = self.sold_contracts_ids.mapped('addendum_ids.seller_id').ids
            partner_ids = list(set([pid for pid in (contract_seller_ids + addendum_seller_ids) if pid]))
            return self.env['res.partner'].browse(partner_ids)
        if report_type == 'rep_recap':
            # reps are stored on res.rep with field rep_id (partner)
            return self.sold_contracts_ids.mapped('rep_ids.rep_id')
        raise ValidationError(_('Unsupported report type: %s') % report_type)

    def _action_send_reports(self, report_type):
        self.ensure_one()
        Email = self.env['auction.report.email']
        partners = self._get_partners_for_report_type(report_type)

        for partner in partners:
            email = Email.search([
                ('auction_id', '=', self.id),
                ('partner_id', '=', partner.id),
                ('report_type', '=', report_type),
            ], limit=1)
            if not email:
                email = Email.create({
                    'auction_id': self.id,
                    'partner_id': partner.id,
                    'report_type': report_type,
                    'state': 'draft',
                    'email_to': (partner.email or '').strip() or False,
                })
            else:
                if not email.email_to and partner.email:
                    email.email_to = partner.email

            if email.state == 'sent':
                continue

            email_to = (email.email_to or '').strip() or (partner.email or '').strip()
            if not email_to:
                email.write({'state': 'no_email', 'error_message': _('Missing partner email')})
                email.env.cr.commit()
                continue
            email.action_send_single()

        action = self.env.ref('liveag_consignment.action_auction_report_email').read()[0]
        action['domain'] = [('auction_id', '=', self.id)]
        action.setdefault('context', {})
        return action

    def action_send_buyer_reports(self):
        self.ensure_one()
        return {
            'name': 'Send Buyer Reports',
            'type': 'ir.actions.act_window',
            'res_model': 'buyer.email.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }

    def action_send_seller_reports(self):
        self.ensure_one()
        return {
            'name': 'Send Seller Reports',
            'type': 'ir.actions.act_window',
            'res_model': 'seller.email.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }

    def action_send_rep_reports(self):
        self.ensure_one()
        return {
            'name': 'Send Rep Recap',
            'type': 'ir.actions.act_window',
            'res_model': 'rep.email.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }

    def action_open_auction_emails(self):
        self.ensure_one()
        action = self.env.ref('liveag_consignment.action_auction_report_email').read()[0]
        action['domain'] = [('auction_id', '=', self.id)]
        action.setdefault('context', {})
        return action
