# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re
import csv
from io import StringIO
import base64
from datetime import datetime
import logging
from ..tools import round_half_up

_logger = logging.getLogger(__name__)

DIRECTION_LIST = [
    ('N', "N"),
    ('W', "W"),
    ('E', "E"),
    ('S', "S"),
    ('NE', "NE"),
    ('NW', "NW"),
    ('SE', "SE"),
    ('SW', "SW"),
    ('Radius', "Radius"),
]

CONTRACT_STATE = [

    ('draft', "Draft"),
    ('submitted', "Submitted"),
    ('changed', "Changed"),
    ('approved', "Approved"),
    ('rejected',"Rejected"),
    ('ready_for_sale', "Ready for Sale"),
    ('no_sale',"No Sale"),
    ('scratched',"Scratched"),
    ('merged', "Merged"),
    ('sold', "Sold"),
    ('delivery_ready', "Ready for Delivery"),
    ('delivered', "Delivered"),
    ('canceled',"Canceled"),
]

IGNORED_FIELDS = [
                    'catalog_changes_ids', 
                    'has_catalog_changes', 
                    'catalog_deadline_passed',
                    'addendum_ids',
                    'addendum_warning',
                    'show_addendum_warning',
                    'seller_part_payment',
                    'rep_ids',
                    'lot_number',
                    'sale_order',
                    'auction_id',
                    'asking_price',
                    'merged_contract_id',
                    'is_merged_contract',
                    'is_split_contract',
                    'source_contract_id',
                    'source_contract_ids',
                    'contract_id',
                    'has_master_agreement',
                    'lotted',
                    'state',
                    'sale_type',
                    'is_special_sale_type',
                    'payment_info_domain',
                    'seller_id',
                    'payment_info',
                    'buyer_id',
                    'buyer_number_domain',
                    'buyer_number',
                    'video_link',
                    'is_supplemental',
                    'asking_price',
                    'sold_price',
                    'sold_date',
                    'lien_holder_id',
                    'lien_holder_id_domain',
                    'sell_by_head',
                    'latitude',
                    'longitude',
                    'seller_need_part_payment',
                    'defer_part_payment',
                    'option_on_contract',
                    'load_option',
                    'created_loads',
                    'available_loads',
                    'oversize_load_weight',
                    'full_comments',
                    'office_notes',
                    'full_vaccination_desc',
                    'final_head_count',
                    'total_gross_weight',
                    'weight_uom',
                    'immediate_delivery',
                    'buyer_part_payment',
                    'shrink_deduct',
                    'total_net_weight',
                    'slide_active',
                    'company_id',
                    'currency_id',
                    'draft_ids',
                    'scale_head_count',
                    'scale_weight',
                    'sorted_off_head_count',
                    'sorted_off_weight',
                    'total_head_count',
                    'total_weight',
                    'average_weight',
                    'total_net_weight',
                    'slide_adjustment',
                    'slide_adjustment_cwt',
                    'total_before_deductions',
                    'price_per_pound',
                    'final_price',
                    'deductions_ids',
                    'total_deductions',
                    'net_price',
                    'delivery_city',
                    'delivery_state',
                    'activity_log_ids',
                    'primary_rep'
                    'has_past_auction_date',
                    
                ]

header_fields_to_validate = [
    'sale_type',
    'seller_id',
    'buyer_id',
    'lien_holder_id',
    'auction_id',
    'kind1',
    'kind2',

]

head_breed_info_fields_to_validate = [
    'kind1',
    'kind2'
]

fields_to_validate_for_submission = [
    'sale_type',
    'seller_id',
    'auction_id',
    'head1',
    'kind1',
    'weight1',
    'contract_type',
    'frame_size',
    'flesh_type',
    'weight_variance',
    'horns',
    'origin',
    'current_fob',
    'nearest_town',
    'state_of_nearest_town',
    'buyer_receives_fob',
    'delivery_date_start',
    'whose_option',
    'rep_ids',
]

fields_to_validate_for_approval = [
    'sale_type',
    'seller_id',
    'auction_id',
    'head1',
    'kind1',
    'weight1',
    'contract_type',
    'frame_size',
    'flesh_type',
    'weight_variance',
    'horns',
    'origin',
    'current_fob',
    'nearest_town',
    'state_of_nearest_town',
    'buyer_receives_fob',
    'delivery_date_start',
    'whose_option',
    'rep_ids',
]

fields_to_validate_for_ready_for_sale = [
    'sale_type',
    'seller_id',
    'auction_id',
    'head1',
    'kind1',
    'weight1',
    'contract_type',
    'frame_size',
    'flesh_type',
    'weight_variance',
    'horns',
    'origin',
    'current_fob',
    'nearest_town',
    'state_of_nearest_town',
    'buyer_receives_fob',
    'delivery_date_start',
    'whose_option',
    'rep_ids',
    'breed_type',
    'feeding_program',
    # Additional fields for ready for sale
    'lot_number',
]

fields_to_validate_for_sold = [
    'sale_type',
    'seller_id',
    'auction_id',
    'head1',
    'kind1',
    'weight1',
    'contract_type',
    'frame_size',
    'flesh_type',
    'weight_variance',
    'horns',
    'origin',
    'current_fob',
    'nearest_town',
    'state_of_nearest_town',
    'buyer_receives_fob',
    'delivery_date_start',
    'whose_option',
    'rep_ids',
    'breed_type',
    'feeding_program',
    # Additional fields for ready for sale
    'lot_number',
    # Additional fields for sold
    'buyer_id',
    'buyer_number',
    'sold_price',
]

class ConsignmentContract(models.Model):
    _name = 'consignment.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Consignment Contract'
    _order = 'auction_id, sale_order'
    _rec_names_search = ['lot_number']

    @api.depends('lot_number', 'seller_id.name', 'seller_id.parent_name', 'seller_id.seller_name_display_preference')
    def _compute_display_name(self):
        """Compute display name based on lot_number or contract_id"""
        for record in self:
            if not isinstance(record.id, int):
                record.display_name = "New Contract"
                continue
            try:
                seller_name = record.seller_id.seller_name if record.seller_id.seller_name else record.seller_id.name
                if record.lot_number:
                    record.display_name = f"Lot {record.lot_number} - {seller_name}"
                else:
                    record.display_name = f"CN {record.id:05d} - {seller_name}"
            except Exception:
                record.display_name = f"CN {record.id:05d}"

    active = fields.Boolean('active',default=True)

    merged_contract_count = fields.Integer(
        string='Number of Merged Contracts',
        compute='_compute_merged_contract_count',
        help='Number of contracts that were merged to create this contract',
        copy=False)
    
    
    sold_date = fields.Date(
        string='Date Sold',
        help='Date when the contract was marked as sold',
        required=False,
        copy=False)

    is_merged_contract = fields.Boolean('Consolidated Contract',default=False,copy=False,help='True if this contract is the consolidation of other contracts')
    is_split_contract = fields.Boolean('Split Contract',default=False,copy=False,help='True if this contract was split')

    merged_contract_id = fields.Many2one(comodel_name='consignment.contract',
        copy=False,
        string='Merged contract')

    source_contract_ids = fields.One2many('consignment.contract',
        'merged_contract_id',
        context={'active_test': False},
        help='Source contracts that were merge to create this contract')

    source_contract_id = fields.Many2one(comodel_name='consignment.contract',
        copy=False,
        context={'active_test': False},
        string='Source contract',
        help='Contract that got split to create this and other contracts')

    split_contract_ids = fields.One2many('consignment.contract',
        'source_contract_id',
        string='List of split contracts',
        context={'active_test': False},
        help='Contracts that result of split this contract')
    
    copied_contract_id = fields.Many2one(
        comodel_name='consignment.contract',
        string='Copied Contract',
        help='Contract that was copied to create this contract')
    
    copied_contract_display = fields.Char(
        string='Copied Contract Display',
        compute='_compute_copied_contract_display')
    
    def _compute_copied_contract_display(self):
        for record in self:
            try:
                # Check if the field exists in the database
                if hasattr(record, 'copied_contract_id') and record.copied_contract_id:
                    record.copied_contract_display = f"Lot {record.copied_contract_id.lot_number} | {record.copied_contract_id.auction_id.name}"
                else:
                    record.copied_contract_display = ""
            except Exception as e:
                # If there's any error accessing the field, set empty display
                _logger.warning("Error accessing copied_contract_id for record %s: %s", record.id, str(e))
                record.copied_contract_display = ""
            
    def action_open_copied_contract(self):
        """Open the copied contract record"""
        self.ensure_one()
        try:
            # Check if the field exists in the database
            if not hasattr(self, 'copied_contract_id') or not self.copied_contract_id:
                return
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'Contract',
                'res_model': 'consignment.contract',
                'res_id': self.copied_contract_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        except Exception as e:
            _logger.warning("Error accessing copied_contract_id for record %s: %s", self.id, str(e))
            return

    contract_id = fields.Char(string='Contract Id',
        required=True, copy=False, readonly=False,
        default=lambda self: _('New'))

    consignment_id = fields.Char(string='Consignment #',
        copy=False)
    has_master_agreement = fields.Boolean(related="seller_id.has_master_agreement")

    lot_number = fields.Char(string="Lot Number",
        copy=False)
    sale_order = fields.Integer(string="Sale Order", copy=False)
    lotted = fields.Boolean(string='Lotted', default=False)

    state = fields.Selection(
        selection=CONTRACT_STATE,
        string="Status",
        copy=False,
        tracking=True,
        default='draft')

    sale_type = fields.Many2one(
        comodel_name='sale.type',
        string="Sale Type")
    
    is_special_sale_type = fields.Boolean(
        string='Is Special Sale Type',
        compute='_compute_is_special_sale_type',
        store=True,
        help='True if sale type is LiveagXchange or Private Treaty')

    @api.depends('sale_type', 'sale_type.name')
    def _compute_is_special_sale_type(self):
        special_types = ['liveagxchange', 'private treaty', 'liveag xchange']
        for record in self:
            try:
                # Use safe navigation pattern to avoid errors with None values
                sale_type_name = record.sale_type.name.lower() if record.sale_type and record.sale_type.name else None
                record.is_special_sale_type = sale_type_name in special_types
            except Exception as e:
                _logger.error("Error computing is_special_sale_type for record %s: %s", record.id, str(e))
                record.is_special_sale_type = False

    @api.onchange('sale_type')
    def _onchange_sale_type(self):
        if self.sale_type:
            if self.sale_type.name.lower() in ['liveagxchange', 'private treaty', 'liveag xchange']:
                auctions = self.env['sale.auction'].search([
                    ('sale_type', '=', self.sale_type.id)
                ], order='sale_date_begin desc', limit=1)
                if auctions:
                    self.auction_id = auctions

    auction_id = fields.Many2one(
        comodel_name='sale.auction',
        string="Auction")
    auction_name = fields.Char(related="auction_id.name", store=True, index=True)
    contract_type = fields.Many2one(
        comodel_name='contract.type',
        string="Contract Type",
        default=lambda self: self.env['contract.type'].search([('name', '=', "Non-Breeding")], limit=1).id)

    #Seller Section
    seller_id = fields.Many2one(
        comodel_name='res.partner',
        domain=[("contact_type_ids", "ilike", "Seller")],
        string="Seller", required=True)
    seller_name = fields.Char(related="seller_id.name", store=True, index=True)
    #Rep Section
    rep_ids = fields.One2many('res.rep',
        'contract_id',
        string="Reps", 
        copy=True,
        help='Representatives associated with this contract')
    payment_info_domain = fields.One2many(
        'res.partner',
        compute='_compute_payment_info_domain'
        ) 
    payment_info = fields.Many2one(
        comodel_name='res.partner',
        string='Payment info',
        compute='_compute_payment_info',
        store=True,
        readonly=False, 
        precompute=True,
        check_company=True)
    
    buyer_id = fields.Many2one(
        comodel_name='res.partner',
        domain=[("contact_type_ids", "ilike", "Buyer")],
        string='Buyer',
        context={'buyer_search': True},
        copy=False)
    buyer_name = fields.Char(related="buyer_id.name", store=True, index=True)
    buyer_number_domain = fields.One2many(related='buyer_id.buyer_number_ids') 

    buyer_number = fields.Many2one(
        comodel_name='buyer.number',
        domain="[('id', 'in', buyer_number_domain)]",
        string='Buyer Number',
        copy=False)
    
    video_link = fields.Char('Video Link', copy=False)

    is_supplemental = fields.Boolean('Supplemental', copy=False)

    asking_price = fields.Monetary(string="Asking Price", copy=False)
    
    delivery_date = fields.Date(
        string='Delivery Date',
        related='delivery_id.delivery_date'
        )

    sold_price = fields.Monetary(string="Sold Price", copy=False)
    
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
        check_company=True)

    #Head/Breed Section
    head1 = fields.Integer(string="Head 1")
    kind1 = fields.Many2one(
        comodel_name='kind.list',
        string="Kind 1")
    kind1_name = fields.Char(related="kind1.name", store=True, index=True)
    weight1 = fields.Integer(string="Weight 1")
    loads1 = fields.Float(string="Loads 1")
    head2 = fields.Integer(string="Head 2")
    kind2 = fields.Many2one(
        comodel_name='kind.list',
        string="Kind 2")
    kind2_name = fields.Char(related="kind2.name", store=True, index=True)
    weight2 = fields.Integer(string="Weight 2")
    loads2 = fields.Float(string="Loads 2")
    price_back = fields.Integer(string="Price Back")
    sell_by_head = fields.Boolean(string="Sell By Head")
    slide_under = fields.Integer(string="Slide (Under)", help="Cent Amount")
    slide_over = fields.Integer(string="Slide (Over)", help="Cent Amount")
    slide_both = fields.Integer(string="Slide (Both)", help="Cent Amount")
    slide_type = fields.Many2one(
        comodel_name='slide.type',
        string="Slide Type")
    short_slide_description = fields.Char(
        string="Short Slide Description", compute="_compute_short_slide_description", store=False)
    slide_description = fields.Char(
        string="Slide Description", compute="_compute_slide_description", store=False)
    


    display_slide_under = fields.Boolean(related='slide_type.under')
    display_slide_over = fields.Boolean(related='slide_type.above')
    display_slide_both = fields.Boolean(related='slide_type.both')
    
    short_location_description = fields.Char(
        string="Short Location Description",
        compute="_compute_short_location_description",
        store=False)
    location_description = fields.Char(
        string="Location Description",
        compute="_compute_location_description",
        store=False)

    weight_stop = fields.Many2one(
        comodel_name='weight.stop',
        string="Weight Stop")
    breed_type = fields.Text(string="Breed Type", tracking=True)
    all_black_hided = fields.Boolean(string="100% Black Hided")
    origin = fields.Many2one(
        comodel_name='origin.list',
        string="Origin")
    origin_description = fields.Char(string="Origin Description", tracking=True)
    state_of_origin = fields.Many2many(
        comodel_name='res.country.state',
        string="State Of Origin",
        domain="[('country_id', '=', country_id)]")
    origin_full_description = fields.Char(
        string="Full Origin Description",
        compute="_compute_origin_full_description",
        store=False)
    country_id = fields.Many2one(
        comodel_name='res.country',
        string="Country of Origin",
        default=lambda self: self.env.ref('base.us'),
        domain="[('code', 'in', ['US', 'CA', 'MX'])]")
    frame_size = fields.Many2one(
        comodel_name='frame.size',
        string="Frame Size")
    flesh_type = fields.Many2one(
        comodel_name='flesh.type',
        string="Flesh Type")
    weight_variance = fields.Many2one(
        comodel_name='weight.variance',
        string="Est. Weight Variance")
    horns = fields.Many2one(
        comodel_name='horns.list',
        string="Horns")
    feeding_program = fields.Text(string="Feeding Program", tracking=True)

    #Programs Section
    vac_program = fields.Many2one(
        comodel_name='vac.program',
        string="VAC Program")
    bangs_vaccinated = fields.Many2one(
        comodel_name='bangs.vaccinated',
        string="Bangs Vaccinated")
    special_section = fields.Many2one(
        comodel_name='special.section',
        string="Special Section")
    genetic_merit_program = fields.Many2one(
        comodel_name='genetic.merit',
        string="Genetic Merit Program")
    premium_genetics_program = fields.Many2many(
        comodel_name='premium.genetics.program',
        string="Premium Genetics Program")
    pi_free = fields.Boolean(string="PI Free")
    tag_840 = fields.Boolean(string="840 Tag")
    value_added_nutrition = fields.Many2one(
        comodel_name='van.program',
        string="Value Added Nutrition Program")
    source_age_program = fields.Many2one(
        comodel_name='third.party.age',
        string="Source/Age Program")
    natural = fields.Boolean(string="Natural")
    natural_plus = fields.Boolean(string="Natural Plus")
    nhtc = fields.Boolean(string="NHTC")
    verified_natural = fields.Boolean(string="Verified Natural")
    gap_program = fields.Many2one(
        comodel_name='gap.program',
        string="GAP Program")
    bqa_certified = fields.Boolean(string="BQA Certified")
    beef_care = fields.Boolean(string="Beef CARE", help='Program offered by IMI Global')
    cfp = fields.Boolean(string="Cattle Feeders Preferred (CFP)")
    verified_grassfed = fields.Boolean(string="Verified Grassfed")
    organic = fields.Boolean(string="Organic")
    non_gmo = fields.Boolean(string="Non-GMO")
    imi_raise_well = fields.Boolean(string="Raise Well", help='Program offered by IMI Global')
    imi_pasture_raised = fields.Boolean(string="Pasture Raised", help='Program offered by IMI Global')
    
    program_icon_ids = fields.Many2many('program.icon', string='Program Icons', compute='_compute_program_icons', store=False)
    @api.depends(
    'vac_program', 'bangs_vaccinated', 'special_section', 'genetic_merit_program',
    'premium_genetics_program', 'pi_free', 'tag_840', 'value_added_nutrition',
    'source_age_program', 'natural', 'nhtc', 'verified_natural',
    'gap_program', 'bqa_certified', 'beef_care', 'cfp', 'verified_grassfed',
    'organic', 'non_gmo', 'weight_stop', 'imi_raise_well', 'imi_pasture_raised')
    def _compute_program_icons(self):
        for contract in self:
            icon_records = self.env['program.icon']

            icon_reference_fields = [
                'vac_program', 'bangs_vaccinated', 'special_section', 'genetic_merit_program',
                'value_added_nutrition', 'source_age_program', 'gap_program', 'weight_stop', 'premium_genetics_program'
            ]

            for field_name in icon_reference_fields:
                related_record = getattr(contract, field_name)
                if related_record and related_record.icon:
                    icon_records |= related_record.icon

            boolean_fields = [
                'pi_free',
                'tag_840',
                'natural',
                'nhtc',
                'verified_natural',
                'bqa_certified',
                'beef_care',
                'cfp',
                'verified_grassfed',
                'organic',
                'non_gmo',
                'imi_raise_well',
                'imi_pasture_raised',
                'option_on_contract',
            ]

            for field_name in boolean_fields:
                if getattr(contract, field_name):
                    icon_record = self.env['program.icon'].search([('field_name', '=', field_name)], limit=1)
                    if icon_record:
                        icon_records |= icon_record

            icon_records = icon_records.sorted(key=lambda x: x.priority)
            contract.program_icon_ids = icon_records

    #Current Location
    current_fob = fields.Many2one(
        comodel_name='location.type',
        string="Current FOB")
    distance_to_nearest_town = fields.Integer(string="Distance to Nearest Town", help="Round number of miles")
    direction_to_nearest_town = fields.Selection(
        selection=DIRECTION_LIST,
        string="Direction to Nearest Town")
    nearest_town = fields.Char(string='Nearest Town')
    state_of_nearest_town = fields.Many2one(
        comodel_name='res.country.state',
        string="State Of Nearest Town",
        domain="[('country_id.code', 'in', ['US', 'CA'])]")
    distance_to_nearest_city = fields.Integer(string="Distance to Nearest City", help="Round number of miles")
    direction_to_nearest_city = fields.Selection(
        selection=DIRECTION_LIST,
        string="Direction to Nearest City")
    nearest_city = fields.Char(string='Nearest City')
    state_of_nearest_city = fields.Many2one(
        comodel_name='res.country.state',
        string="State of Nearest City",
        domain="[('country_id.code', 'in', ['US', 'CA'])]")
    region_id = fields.Many2one(
        comodel_name='res.region',
        string="Region",
        related='state_of_nearest_town.region_id',
        store=True,
        readonly=False,
        help="Region determined from the nearest town's state.")
    latitude = fields.Float(string="Latitude", help="Latitude from Google Maps")
    longitude = fields.Float(string="Longitude", help="Longitude from Google Maps")

    #Delivery Info
    buyer_receives_fob = fields.Many2one(
        comodel_name='location.type',
        string="Buyer Receives FOB")
    whose_option = fields.Many2one(
        comodel_name='whose.option',
        string="Whose Option",
        default=lambda self: self.env['whose.option'].search([('name', '=', "Rep's Option")], limit=1).id)
    delivery_date_start = fields.Date(string='Delivery Date Start')
    delivery_date_end = fields.Date(string='Delivery Date End')
    delivery_date_range = fields.Char(
        string="Delivery Date Range",
        compute="_compute_delivery_date_range",
        store=False)
    seller_need_part_payment = fields.Boolean(string='Seller Needs Part Payment')
    defer_part_payment = fields.Boolean(string='Defer Part Payment')
    option_on_contract = fields.Boolean(string="Option on Contract")
    option_description = fields.Text(string="Option Description", store=False, compute="_compute_option_description")
    display_chatter = fields.Boolean(string="Hide Chatter", default=False)
    can_merge_option_contracts = fields.Boolean(string="Able to merge option contracts",
                                                tracking=True,
                                                )
    to_be_merged = fields.Boolean(string="Merge",default=False)
    option_contract_ids = fields.Many2many(
        comodel_name='consignment.contract',
        relation='consignment_contract_options_rel',
        column1='contract_id',
        column2='option_id',
        string='Option Contracts',
        help="Select other contracts as options for this contract.")
    load_option = fields.Integer(string="Load Option", 
        help="Whole number of truck loads")
    created_loads = fields.Integer(string="Created Loads", 
        default=0,
        copy=False,
        help="Loads allocated on split contracts")
    available_loads = fields.Integer(string="Available Loads",
        compute='_compute_available_loads',
        help="Loads available to create new contracts \n (Load Option - Created Loads)")

    @api.depends('origin', 'origin_description')
    def _compute_origin_full_description(self):
        for contract in self:
            contract.origin_full_description = f"{contract.origin.name} {contract.origin_description}" if contract.origin_description else f"{contract.origin.name}" if contract.origin else ''

    @api.depends('option_on_contract', 'option_contract_ids', 'load_option')
    def _compute_option_description(self):
        for contract in self:
            contract.option_description = None  # Always assign a default value first
            
            if contract.option_contract_ids:
                try:
                    # Helper function to safely convert lot_number to float
                    def safe_float_lot(lot_number):
                        if not lot_number:
                            return None
                        try:
                            return float(lot_number)
                        except (ValueError, TypeError):
                            return None
                    
                    # First try by lot_number
                    current_lot_float = safe_float_lot(contract.lot_number)
                    greater_options = None

                    if current_lot_float is not None:
                        greater_options = contract.option_contract_ids.filtered(
                            lambda c: safe_float_lot(c.lot_number) is not None
                            and safe_float_lot(c.lot_number) > current_lot_float
                        )

                    # Fallback by id when lot_number doesn't work (no lot, non-numeric, or empty)
                    if not greater_options:
                        greater_options = contract.option_contract_ids.filtered(
                            lambda c: c.id > contract.id
                        )

                    # Final fallback: treat all options as "greater" if still empty
                    if not greater_options:
                        greater_options = contract.option_contract_ids

                    if len(greater_options) > 1:
                        contract.option_description = f"Option on next {len(greater_options)} lots"
                    elif len(greater_options) == 1:
                        contract.option_description = "Option on next lot"
                except Exception as e:
                    _logger.warning("Error computing option_description for contract %s: %s", contract.id, str(e))
                    contract.option_description = None
                    
            elif contract.load_option and contract.load_option > 1:
                contract.option_description = f"Option on {contract.load_option} Loads"
    
    shrink_percentage = fields.Float(string="Shrink %", digits=(5, 1))
    weighing_conditions = fields.Text(string="Weighing Conditions & Shrink", tracking=True)
    weighing_cond_w_freight = fields.Text(string="Weighing Conditions & Shrink w/ Freight Adjustment", compute="_compute_weighing_cond_w_freight", store=False)
    oversize_load = fields.Boolean(string='Oversize Load', help='Whether the lot is an oversized truck load')
    oversize_load_weight = fields.Integer(string='Oversize Load Weight')
    implanted_type = fields.Many2one(
        comodel_name='implanted.list',
        string="Implanted Type")
    implanted_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'), 
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Month')
    # This should be a dropdown of the last 10 years, starting from the current year
    implanted_year = fields.Selection(
        selection=lambda self: [(str(year), str(year)) for year in range(datetime.now().year, datetime.now().year - 11, -1)],
        string='Year'
    )
    implanted_date = fields.Date(string='Implanted Date')
    castration = fields.Many2one(
        comodel_name='castration.list',
        string="Castration")
    comments = fields.Text(string="Comments", tracking=True)
    full_comments = fields.Text(
        string="Full Comments", 
        compute="_compute_comments_with_castration", 
        store=True, 
        tracking=True
    )
    office_notes = fields.Text(string="Notes to office", tracking=True)
    vaccination_desc = fields.Text(string="Vaccination Description", tracking=True)
    full_vaccination_desc = fields.Text(
        string="Full Vaccination Description", 
        compute="_compute_vacc_description",
        tracking=True,
        store=True)
    final_head_count = fields.Integer(string="Final Head Count")
    total_gross_weight = fields.Float(string='Total Gross Weight')
    weight_uom = fields.Many2one("uom.uom", "Unit Of Measure",
        default=lambda self: self.env.ref('uom.product_uom_lb'))

    @api.depends('weighing_conditions', 'freight_adjustment_amount')
    def _compute_weighing_cond_w_freight(self):
        for contract in self:
            contract.weighing_cond_w_freight = contract.weighing_conditions or ''
            if contract.freight_adjustment_amount and contract.freight_adjustment_amount > 0:
                amount = f"${contract.freight_adjustment_amount:.0f}" if contract.freight_adjustment_amount % 1 == 0 else f"${contract.freight_adjustment_amount:.2f}"
                # Check if weighing_conditions ends with a period
                if contract.weighing_conditions and contract.weighing_conditions.rstrip().endswith('.'):
                    contract.weighing_cond_w_freight += f" Freight Adjustment: {amount}"
                else:
                    contract.weighing_cond_w_freight += f". Freight Adjustment: {amount}"

    # Delivery
    immediate_delivery = fields.Boolean(string="Immediate Delivery", compute="_compute_immediate_delivery")
    
    @api.depends('delivery_date_start', 'auction_id.sale_date_begin')
    def _compute_immediate_delivery(self):
        for contract in self:
            if not contract.auction_id:
                contract.immediate_delivery = False
                continue
                
            if not contract.auction_id.sale_date_begin:
                contract.immediate_delivery = False
                continue
                
            if not contract.delivery_date_start:
                contract.immediate_delivery = False
                continue

            sale_date = contract.auction_id.sale_date_begin.date()
            date_diff = (contract.delivery_date_start - sale_date).days
            contract.immediate_delivery = date_diff <= 14

    buyer_part_payment = fields.Monetary(string="Buyer Part Payment", compute="_compute_buyer_part_payment")
    
    @api.depends('head1', 'head2', 'seller_need_part_payment', 'defer_part_payment')
    def _compute_buyer_part_payment(self):
        for contract in self:
            if contract.seller_need_part_payment or contract.defer_part_payment:
                contract.buyer_part_payment = (contract.head1 or 0) * 40 + (contract.head2 or 0) * 40
            else:
                contract.buyer_part_payment = 0

    shrink_deduct = fields.Float(string="Shrink Deduct (lb)",
        compute='_compute_shrink_deduct',
        help="Total weight shrink deduct")
    total_net_weight = fields.Float(string="Total Net Weight")
    slide_active = fields.Boolean(string="Slide Active")
    freight_adjustment = fields.Boolean(string="Freight Adjustment")
    freight_adjustment_amount = fields.Monetary(string="Freight Adjustment $")
    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        store=True)
    
    draft_ids = fields.One2many('draft',
        'contract_id',
        string='Drafts',
        copy=True)

    scale_head_count = fields.Integer(string="Scale Head",
        compute='_compute_scale_head_count_weight',
        help="Total head count from all drafts")
    scale_weight = fields.Float(string="Scale Weight",
        compute='_compute_scale_head_count_weight',
        help="Total weight from all drafts")
    sorted_off_head_count = fields.Integer(string="Sorted Off Head",
        help="Total head count sorted off")
    sorted_off_weight = fields.Float(string="Sorted Off Weight",
        help="Total weight sorted off")
    total_head_count = fields.Integer(string="Total Head",
        compute='_compute_total_head_count_weight',
        help="Total head count after sorted off")
    total_weight = fields.Float(string="Gross Weight",
        compute='_compute_total_head_count_weight',
        help="Total weight after sorted off")
    
    average_weight = fields.Float(string="Average Weight",
        compute='_compute_average_weight',
        help="Average weight per head")
    
    total_net_weight = fields.Float(string="Total Net Weight",
        compute='_compute_total_net_weight',
        help="Total net weight after shrink deduct")
    
    slide_adjustment = fields.Monetary(string="Slide Adjustment",
        help="Slide adjustment amount")
    slide_adjustment_cwt = fields.Monetary(string="Slide Adj $ CWT",
        help="Price per 100lb (Slide adjustment amount per CWT)")
    
    total_before_deductions = fields.Monetary(string="Total Before Deductions",
    help="Total before discount deductions")

    price_per_pound = fields.Monetary(string="Price Per Pound",
        compute='_compute_price_per_pound',
        help="Price per pound")
    
    final_price = fields.Float(string="Final / Adjusted per head Wt",
        help="Final price per head weight")
    
    deductions_ids = fields.One2many('contract.deduction',
        'contract_id',
        string='Deductions',
        help="List of deductions")
    
    total_deductions = fields.Monetary(string="Total Deductions",
        compute='_compute_total_deductions',
        help="Total deductions amount")
    
    net_price = fields.Monetary(string="Net Price",
        compute='_compute_net_price',
        help="Net price after deductions")

    delivery_city = fields.Char(string='Delivery City',
        compute='_compute_delivery_location',
        store=True,
        readonly=False)

    delivery_state = fields.Many2one(
        comodel_name='res.country.state',
        string="Delivery State",
        compute='_compute_delivery_location',
        store=True,
        readonly=False,
        domain="[('country_id.code', '=', 'US')]")

    # Contract Addendum
    addendum_ids = fields.One2many('contract.addendum',
        'contract_id',
        string='Addendum',
        copy=True,
        help="List of addendum for this contract")

    seller_part_payment = fields.Monetary(
        string="Total Seller Part Payment",
        compute='_compute_total_part_payment',
        store=True)

    # Activity Log
    activity_log_ids = fields.One2many('contract.activity.log',
        'contract_id',
        string='Activity',
        help="List of actions performed on this contract",
        copy=False)

    def _compute_option_text(self, contract=None):
        if contract.option_contract_ids:
            greater_lots = contract.option_contract_ids.filtered(
                lambda c: c.lot_number and contract.lot_number and 
                float(c.lot_number) > float(contract.lot_number)
            )
            
            if len(greater_lots) > 1:
                greatest_lot = max(greater_lots, key=lambda c: float(c.lot_number))
                # return f"Option thru Lot {greatest_lot.lot_number}", f"Option thru<br>Lot {greatest_lot.lot_number}"
                return f"lot_option.png", f"thru Lot {greatest_lot.lot_number}"
            elif len(greater_lots) == 1:
                return "lot_option.png", "on Next Lot"
        return "", ""

    @api.depends('addendum_ids.part_payment')
    def _compute_total_part_payment(self):
        for contract in self:
            contract.seller_part_payment = sum(contract.addendum_ids.mapped('part_payment'))

    @api.depends('buyer_id')
    def _compute_delivery_location(self):
        for contract in self:
            contract.delivery_city = contract.buyer_id.city
            contract.delivery_state = contract.buyer_id.state_id.id

    delivery_city = fields.Char(string='Delivery City')

    delivery_state = fields.Many2one(
        comodel_name='res.country.state',
        string="Delivery State",
        domain="[('country_id.code', '=', 'US')]")

    
    activity_log_ids = fields.One2many('contract.activity.log',
                                     'contract_id',
                                     string='Activity',
                                     help="List of actions performed on this contract")
    
    @api.depends('seller_id')
    def _compute_lien_holder_id(self):
        for contract in self:
            contract.lien_holder_id = contract.seller_id.default_lien_holder_id.id 
            # if contract.seller_id else False

    @api.depends('seller_id')
    def _compute_payment_info(self):
        for contract in self:
            contract.payment_info = contract.seller_id.default_payment_info_id.id 
            # if contract.seller_id else False

    @api.depends('load_option','created_loads')
    def _compute_available_loads(self):
        for contract in self:
            contract.available_loads = contract.load_option - contract.created_loads 

    @api.depends('total_before_deductions','total_deductions')
    def _compute_net_price(self):
        for contract in self:
            contract.net_price = contract.total_before_deductions - contract.total_deductions
            
    @api.depends('deductions_ids')
    def _compute_total_deductions(self):
        for contract in self:
            contract.total_deductions = sum(contract.deductions_ids.mapped('debit')) - sum(contract.deductions_ids.mapped('credit'))

    @api.depends('slide_adjustment_cwt')
    def _compute_price_per_pound(self):
        for contract in self:
            contract.price_per_pound = contract.slide_adjustment_cwt / 100

    @api.depends('total_weight','shrink_deduct')
    def _compute_total_net_weight(self):
        for contract in self:
            contract.total_net_weight = contract.total_weight - contract.shrink_deduct    

    @api.depends('total_weight','shrink_percentage')
    def _compute_shrink_deduct(self):
        for contract in self:
            contract.shrink_deduct = contract.total_weight * contract.shrink_percentage / 100

    @api.depends('total_weight','total_head_count')
    def _compute_average_weight(self):
        for contract in self:
            contract.average_weight = contract.total_weight / contract.total_head_count if contract.total_head_count else 0


    @api.depends('scale_head_count','sorted_off_head_count','scale_weight','sorted_off_weight')
    def _compute_total_head_count_weight(self):
        for contract in self:
            contract.total_head_count = contract.scale_head_count - contract.sorted_off_head_count
            contract.total_weight = contract.scale_weight - contract.sorted_off_weight

    @api.depends('draft_ids')
    def _compute_scale_head_count_weight(self):
        for contract in self:
            contract.scale_head_count = sum(contract.draft_ids.mapped('head_count'))
            contract.scale_weight = sum(contract.draft_ids.mapped('weight'))    

    @api.onchange('contract_type')
    def _onchange_contract_type(self):
        if self.contract_type and self.contract_type.name == 'Breeding':
            self.sell_by_head = True
        else:
            self.sell_by_head = False

    def _compute_slide_description(self, contract=None):
        """Compute slide description for a given contract or self"""
        record = contract or self
        if not record.slide_type or not record.slide_type.name:
            record.slide_description = ""
            
        if record.slide_type.name == 'none':
            record.slide_description = ""
        
        description_parts = []
        
        def format_slide_value(value):
            if not value:
                return '0'
            if value < 100:
                return f"{value:.0f}\u00A2"
            return f"${value/100:.2f}"
        
        replacements = {
            '{{over}}': format_slide_value(record.slide_over) if record.slide_over else '0',
            '{{under}}': format_slide_value(record.slide_under) if record.slide_under else '0',
            '{{both}}': format_slide_value(record.slide_both) if record.slide_both else '0',
        }
        description = record.slide_type.description or ""
        for placeholder, value in replacements.items():
            description = description.replace(placeholder, value)
        
        description_parts.append(description)

        if record.weight_stop and record.weight_stop.name.lower() != 'none':
            try:
                weight_stop_num = int(record.weight_stop.name)
                description_parts.append(
                    _(", up to a %(weight_stop).0f lb weight stop.")
                    % {'weight_stop': weight_stop_num}
                )
            except ValueError:
                description_parts.append(
                    _(", up to a weight stop of %(weight_stop)s.")
                    % {'weight_stop': record.weight_stop.name}
                )

        record.slide_description = "".join(description_parts) if description_parts else _("Invalid slide configuration.")
            
    @api.depends('slide_type', 'slide_over', 'slide_under', 'slide_both')
    def _compute_short_slide_description(self, contract=None):
        """Compute slide description for a given contract or self"""
        records = contract or self
        if not isinstance(records, models.Model):
            records = self.browse(records)
            
        def format_slide_value(value):
            if not value:
                return '0'
            if value < 100:
                return f"{value:.0f}\u00A2"
            return f"${value/100:.2f}"
            
        for record in records:
            if not record.slide_type:
                record.short_slide_description = ""
                continue
                
            if record.slide_type.name == 'none':
                record.short_slide_description = ""
                continue

            description_parts = []

            # Determine slide type and build description
            if record.slide_type:
                if record.slide_type.both and record.slide_both:
                    description_parts.append(
                        _("%(name)s %(value)s")
                        % {'name': record.slide_type.label, 'value': format_slide_value(record.slide_both)}
                    )
                elif record.slide_over and record.slide_under:
                    # Handle 2-way slide case
                    description_parts.append(
                        _("%(name)s %(over)s over & %(under)s under")
                        % {
                            'name': record.slide_type.label,
                            'over': format_slide_value(record.slide_over),
                            'under': format_slide_value(record.slide_under)
                        }
                    )
                elif record.slide_over:
                    description_parts.append(
                        _("%(name)s %(value)s")
                        % {'name': record.slide_type.label, 'value': format_slide_value(record.slide_over)}
                    )
                elif record.slide_under:
                    description_parts.append(
                        _("%(name)s %(value)s")
                        % {'name': record.slide_type.label, 'value': format_slide_value(record.slide_under)}
                    )
                    
            record.short_slide_description = " ".join(description_parts) if description_parts else ""
    
    # def write(self,vals):
    #     if not self.env.user.has_group('liveag_consignment.group_consignment_manager'):
    #         if not vals.get('state'):
    #             vals['state'] = 'submitted' 
    #     res = super(ConsignmentContract,self).write(vals)

    #     return res

    def _format_implanted_date(self, date_str):
        """Format implanted date to first day of month."""
        from datetime import datetime
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.replace(day=1).strftime('%Y-%m-%d')

    def _handle_special_fields(self, vals):
        """Handle special field cases before write."""
        if implanted_date := vals.get('implanted_date'):
            vals['implanted_date'] = self._format_implanted_date(implanted_date)

        if vals.get('state') == 'submitted':
            self.action_submit()
            vals.pop('state', None)

        if vals.get('state') == 'sold' and not vals.get('sold_date') and not self.sold_date:
            vals['sold_date'] = fields.Date.today()

    def _should_track_field(self, field_name):
        """Determine if field changes should be tracked."""
        return field_name not in {
            '__last_update', 'write_date', 'write_uid',
            'activity_ids', 'message_ids', 'activity_log_ids'
        }

    def _format_create_rep(self, data, _):
        """Format a create rep command."""
        rep_record = self.env['res.partner'].browse(data.get('rep_id'))
        commission = data.get('percentage_commission', 0)
        return f"{rep_record.name} ({commission}%)"

    def _format_update_rep(self, data, record_id):
        """Format an update rep command."""
        record = self.env['res.rep'].browse(record_id)
        commission = data.get('percentage_commission', record.percentage_commission)
        return f"{record.rep_id.name} ({commission}%)"

    def _format_delete_rep(self, _, record_id):
        """Format a delete rep command."""
        record = self.env['res.rep'].browse(record_id)
        return f"{record.rep_id.name} (Removed)"

    def _format_command_rep(self, command, data, record_id=None):
        """Format a single rep command into a string."""
        handlers = {
            0: self._format_create_rep,
            1: self._format_update_rep,
            2: self._format_delete_rep,
        }
        handler = handlers.get(command)
        return handler(data, record_id) if handler else ''

    def _format_rep_value(self, reps):
        """Format rep records into readable string."""
        if not reps:
            return ''
        
        rep_strings = []
        for rep in reps:
            if isinstance(rep, (list, tuple)):
                # Convert list to tuple if needed
                rep_tuple = tuple(rep) if isinstance(rep, list) else rep
                command, record_id, data = (rep_tuple + (None, {}))[:3]
                formatted = self._format_command_rep(command, data, record_id)
            else:
                formatted = f"{rep.rep_id.name} ({rep.percentage_commission}%)"
            
            if formatted:
                rep_strings.append(formatted)
        
        return ', '.join(rep_strings)

    def _format_create_addendum(self, data, _):
        """Format a create addendum command."""
        seller = self.env['res.partner'].browse(data.get('seller_id'))
        percentage = data.get('percentage', 0)
        head_count = data.get('head_count', 0)
        return f"{seller.name} ({percentage}% - {head_count} head)"

    def _format_update_addendum(self, data, record_id):
        """Format an update addendum command."""
        record = self.env['contract.addendum'].browse(record_id)
        percentage = data.get('percentage', record.percentage)
        head_count = data.get('head_count', record.head_count)
        return f"{record.seller_id.name} ({percentage}% - {head_count} head)"

    def _format_delete_addendum(self, _, record_id):
        """Format a delete addendum command."""
        record = self.env['contract.addendum'].browse(record_id)
        return f"{record.seller_id.name} (Removed)"

    def _format_command_addendum(self, command, data, record_id=None):
        """Format a single addendum command into a string."""
        handlers = {
            0: self._format_create_addendum,
            1: self._format_update_addendum,
            2: self._format_delete_addendum,
        }
        handler = handlers.get(command)
        return handler(data, record_id) if handler else ''

    def _format_addendum_value(self, addendums):
        """Format addendum records into readable string."""
        if not addendums:
            return ''
        
        addendum_strings = []
        for addendum in addendums:
            if isinstance(addendum, (list, tuple)):
                command, record_id, data = (addendum + [None, {}])[:3]
                formatted = self._format_command_addendum(command, data, record_id)
            else:
                formatted = f"{addendum.seller_id.name} ({addendum.percentage}% - {addendum.head_count} head)"
            
            if formatted:
                addendum_strings.append(formatted)
        
        return ', '.join(addendum_strings)

    def _format_field_value(self, field, value):
        """Format a field value based on its type."""
        if not value:
            return ''

        if field.name == 'rep_ids':
            return self._format_rep_value(value)
        
        if field.name == 'addendum_ids':
            return self._format_addendum_value(value)
            
        if field.type == 'many2one':
            if isinstance(value, models.BaseModel):
                return value.display_name or ''
            if isinstance(value, int):
                record = self.env[field.comodel_name].browse(value)
                return record.display_name or ''
            return ''

        return str(value) if value not in (False, None) else ''

    def _get_field_values(self, field, old_value, new_value):
        """Get formatted old and new values for field."""
        return (
            self._format_field_value(field, old_value),
            self._format_field_value(field, new_value)
        )

    def _create_activity_log(self, contract_id, field_name, field_string, old_value, new_value):
        """Create activity log entry with error handling."""
        try:
            log_vals = {
                'contract_id': contract_id,
                'field_name': field_name,
                'old_value': old_value,
                'new_value': new_value,
                'message': f"Field '{field_string}' changed from '{old_value}' to '{new_value}'",
                'user_id': self.env.user.partner_id.id,
                'timestamp': fields.Datetime.now(),
            }
            self.env['contract.activity.log'].sudo().create(log_vals)
            _logger.info(f"Activity log created for {field_name}: {old_value} -> {new_value}")
        except Exception as e:
            _logger.error(f"Failed to create activity log for {field_name}: {str(e)}")

    def _get_field_change_values(self, record, field_name, new_value):
        """Get formatted old and new values for field change tracking."""
        field = record._fields[field_name]
        old_value = record[field_name]
        return self._get_field_values(field, old_value, new_value)

    def _should_log_change(self, old_value, new_value, field_name):
        """Determine if a field change should be logged."""
        return (
            self._should_track_field(field_name) and
            old_value != new_value
        )

    def _track_field_changes(self, record, field_name, new_value):
        """Track changes for a single field."""
        old_formatted, new_formatted = self._get_field_change_values(record, field_name, new_value)
        
        if self._should_log_change(old_formatted, new_formatted, field_name):
            self._create_activity_log(
                record.id,
                field_name,
                record._fields[field_name].string,
                old_formatted,
                new_formatted
            )

    def write(self, vals):
        """Override write method to handle special cases and track changes."""
        # Handle state validation before any changes are made
        if 'state' in vals:
            for record in self:
                new_state = vals['state']
                current_state = record.state
                
                # Only validate if state is actually changing
                if new_state != current_state:
                    # Create a temporary record with the new state for validation
                    temp_record = record.with_context(skip_validation=True)
                    temp_vals = dict(vals)
                    temp_vals['state'] = new_state
                    
                    # Validate the new state
                    validation_methods = {
                        'submitted': record._validate_for_submission,
                        'approved': record._validate_for_approval,
                        'ready_for_sale': record._validate_for_ready_for_sale,
                        'sold': record._validate_for_sold,
                    }
                    
                    if new_state in validation_methods:
                        errors = validation_methods[new_state]()
                        if errors:
                            error_message = f"Cannot change state to {new_state.replace('_', ' ').title()}:\n\n" + \
                                          "\n".join(f"• {error}" for error in errors)
                            raise ValidationError(error_message)
        
        self._handle_special_fields(vals)

        for record in self:
            valid_fields = {
                field_name: new_value
                for field_name, new_value in vals.items()
                if field_name in record._fields
            }
            for field_name, new_value in valid_fields.items():
                self._track_field_changes(record, field_name, new_value)

        return super().write(vals)
    
    def is_html_field_empty(self,html_content):
        # Remove HTML tags
        text = re.sub(r'<[^>]*>', '', html_content)
        # Strip any remaining whitespaces
        text = text.strip()
        # Check if the remaining text is empty
        return len(text) == 0
    
    def _validate_fields_for_state(self, field_list, state_name):
        """
        Validate required fields for a specific state transition.
        
        :param field_list: List of field names to validate
        :param state_name: Name of the state for error messages
        :return: List of error messages
        """
        errors = []
        
        for field_name in field_list:
            if field_name not in self._fields:
                continue
                
            field = self._fields[field_name]
            value = self[field_name]
            
            # Check if field is empty based on field type
            is_empty = False
            if field.type in ('char', 'text'):
                is_empty = not value or (isinstance(value, str) and not value.strip())
            elif field.type in ('many2one', 'integer', 'float', 'monetary'):
                is_empty = not value
            elif field.type == 'one2many':
                is_empty = not value or len(value) == 0
            elif field.type == 'many2many':
                is_empty = not value or len(value) == 0
            elif field.type == 'date':
                is_empty = not value
            elif field.type == 'boolean':
                # Boolean fields are never considered empty for validation
                is_empty = False
            else:
                is_empty = not value
            
            if is_empty:
                field_label = field.string or field_name.replace('_', ' ').title()
                errors.append(f"{field_label} is required to move to {state_name}")
        
        return errors
    
    def _validate_rep_commissions(self):
        """Validate that rep commissions don't exceed 100%"""
        active_reps = self.rep_ids.filtered(lambda r: r.active)
        total_percentage = round_half_up(sum(active_reps.mapped('percentage_commission')), 2)
        if total_percentage > 100:
            return ["Total commission percentage cannot exceed 100%"]
        return []
    
    def _validate_delivery_dates(self):
        """Validate delivery date logic"""
        errors = []
        if self.delivery_date_start and self.delivery_date_end:
            if self.delivery_date_start > self.delivery_date_end:
                errors.append("Delivery start date cannot be after delivery end date")
        return errors
    
    def _validate_addendum_head_counts(self):
        """Validate addendum head counts match contract totals"""
        errors = []
        if self.addendum_ids:
            total_contract_heads = (self.head1 or 0) + (self.head2 or 0)
            total_addendum_heads = sum(addendum.head_count or 0 for addendum in self.addendum_ids)
            
            if total_contract_heads != total_addendum_heads:
                errors.append(
                    f"The total head count in addendums ({total_addendum_heads}) "
                    f"does not match the contract's total head count ({total_contract_heads})"
                )
        return errors
    
    def _validate_for_submission(self):
        """Validate contract for submission state"""
        errors = []
        errors.extend(self._validate_fields_for_state(fields_to_validate_for_submission, 'Submitted'))
        errors.extend(self._validate_rep_commissions())
        errors.extend(self._validate_delivery_dates())
        errors.extend(self._validate_addendum_head_counts())
        return errors
    
    def _validate_for_approval(self):
        """Validate contract for approval state"""
        errors = []
        errors.extend(self._validate_fields_for_state(fields_to_validate_for_approval, 'Approved'))
        errors.extend(self._validate_rep_commissions())
        errors.extend(self._validate_delivery_dates())
        errors.extend(self._validate_addendum_head_counts())
        return errors
    
    def _validate_for_ready_for_sale(self):
        """Validate contract for ready for sale state"""
        errors = []
        errors.extend(self._validate_fields_for_state(fields_to_validate_for_ready_for_sale, 'Ready for Sale'))
        errors.extend(self._validate_rep_commissions())
        errors.extend(self._validate_delivery_dates())
        errors.extend(self._validate_addendum_head_counts())
        
        # Special validation for video sales
        # if self.sale_type and self.sale_type.name == 'Video Sale':
        #     if not self.video_link or self.is_html_field_empty(self.video_link):
        #         errors.append('Video link is required for Video Sale contracts to be ready for sale')
        
        return errors
    
    def _validate_for_sold(self):
        """Validate contract for sold state"""
        errors = []
        errors.extend(self._validate_fields_for_state(fields_to_validate_for_sold, 'Sold'))
        return errors
    
    def can_transition_to_state(self, target_state):
        """
        Check if contract can transition to target state without raising errors.
        
        :param target_state: Target state to validate for
        :return: Dictionary with 'can_transition' boolean and 'errors' list
        """
        validation_methods = {
            'submitted': self._validate_for_submission,
            'approved': self._validate_for_approval,
            'ready_for_sale': self._validate_for_ready_for_sale,
            'sold': self._validate_for_sold,
        }
        
        if target_state not in validation_methods:
            return {'can_transition': True, 'errors': []}
        
        errors = validation_methods[target_state]()
        return {
            'can_transition': len(errors) == 0,
            'errors': errors
        }
    
    def get_validation_errors_for_state(self, target_state):
        """
        Get validation errors for a specific state without raising exceptions.
        Useful for displaying validation messages in the UI.
        
        :param target_state: Target state to validate for
        :return: List of error messages
        """
        result = self.can_transition_to_state(target_state)
        return result['errors']
    
    @api.onchange('state')
    def _onchange_state(self):
        """Provide immediate feedback when state field is changed directly"""
        if not self.state:
            return
            
        # Get the original state from the database (if record exists)
        if self.id:
            original_record = self.browse(self.id)
            original_state = original_record.state
            
            # Only validate if state is actually changing
            if self.state != original_state:
                result = self.can_transition_to_state(self.state)
                if not result['can_transition']:
                    new_state_name = self.state.replace('_', ' ').title()
                    
                    # Reset to original state
                    self.state = original_state
                    
                    # Show validation errors
                    error_message = f"Cannot change state to {new_state_name}:\n\n" + \
                                  "\n".join(f"• {error}" for error in result['errors'])
                    
                    return {
                        'warning': {
                            'title': 'Validation Error',
                            'message': error_message
                        }
                    }
    
    # Computed fields for UI validation indicators
    can_submit = fields.Boolean(
        string='Can Submit',
        compute='_compute_state_validation_flags',
        help='Indicates if contract can be submitted')
    
    can_approve = fields.Boolean(
        string='Can Approve', 
        compute='_compute_state_validation_flags',
        help='Indicates if contract can be approved')
    
    can_ready_for_sale = fields.Boolean(
        string='Can Ready for Sale',
        compute='_compute_state_validation_flags', 
        help='Indicates if contract can be set to ready for sale')
    
    can_mark_sold = fields.Boolean(
        string='Can Mark Sold',
        compute='_compute_state_validation_flags',
        help='Indicates if contract can be marked as sold')
    
    submission_errors = fields.Text(
        string='Submission Validation Errors',
        compute='_compute_state_validation_flags',
        help='List of errors preventing submission')
    
    approval_errors = fields.Text(
        string='Approval Validation Errors', 
        compute='_compute_state_validation_flags',
        help='List of errors preventing approval')
    
    ready_for_sale_errors = fields.Text(
        string='Ready for Sale Validation Errors',
        compute='_compute_state_validation_flags',
        help='List of errors preventing ready for sale')
    
    sold_errors = fields.Text(
        string='Sold Validation Errors',
        compute='_compute_state_validation_flags',
        help='List of errors preventing sold status')

    delivery_id = fields.Many2one(
        comodel_name='consignment.delivery',
        string='Delivery',
        copy=False,
        help='Associated delivery record')
    

    @api.depends('sale_type', 'seller_id', 'auction_id', 'head1', 'kind1', 'weight1',
                'contract_type', 'frame_size', 'flesh_type', 'weight_variance', 'horns',
                'origin', 'current_fob', 'nearest_town', 'state_of_nearest_town',
                'buyer_receives_fob', 'delivery_date_start', 'whose_option', 'rep_ids',
                'breed_type', 'feeding_program', 'lot_number', 'buyer_id', 'sold_price',
                'sold_date', 'video_link', 'delivery_date_end', 'addendum_ids')
    def _compute_state_validation_flags(self):
        """Compute validation flags and error messages for different states"""
        for contract in self:
            # Check submission
            submission_result = contract.can_transition_to_state('submitted')
            contract.can_submit = submission_result['can_transition']
            contract.submission_errors = '\n'.join(submission_result['errors']) if submission_result['errors'] else ''
            
            # Check approval
            approval_result = contract.can_transition_to_state('approved')
            contract.can_approve = approval_result['can_transition']
            contract.approval_errors = '\n'.join(approval_result['errors']) if approval_result['errors'] else ''
            
            # Check ready for sale
            ready_result = contract.can_transition_to_state('ready_for_sale')
            contract.can_ready_for_sale = ready_result['can_transition']
            contract.ready_for_sale_errors = '\n'.join(ready_result['errors']) if ready_result['errors'] else ''
            
            # Check sold
            sold_result = contract.can_transition_to_state('sold')
            contract.can_mark_sold = sold_result['can_transition']
            contract.sold_errors = '\n'.join(sold_result['errors']) if sold_result['errors'] else ''
    def _set_delivery(self):
        for contract in self:
            vals = {
                'contract_id': contract.id,
                'seller_id': contract.seller_id.id,
                'sell_by_head': contract.sell_by_head,
                'buyer_id': contract.buyer_id.id,
                'lot_number': contract.lot_number,
                'contract_weight': contract.weight1,
                'contract_weight2': contract.weight2,
                'base_price': contract.sold_price,
                'slide_over': contract.slide_over,
                'slide_under': contract.slide_under,
                'slide_both': contract.slide_both,
                'slide_type': contract.slide_type.id,
                'price_back': contract.price_back,
                'contract_head1': contract.head1,
                'contract_head2': contract.head2,
                'seller_discount': contract.seller_id.discount,
                'rep_id': contract.primary_rep.id,
                'weight_stop_id': contract.weight_stop.id,
            }
            delivery = self.env['consignment.delivery'].create(vals)
            delivery.get_default_flow()
            contract.delivery_id = delivery

    def action_ready_for_delivery(self):
        self.write({'state':'delivery_ready'})
        for contract in self:
            if not contract.delivery_id:
                contract._set_delivery()
                


    def action_ready_to_sale(self):
        for contract in self:
            errors = contract._validate_for_ready_for_sale()
            if errors:
                error_message = "Cannot move contract to Ready for Sale:\n\n" + "\n".join(f"• {error}" for error in errors)
                raise ValidationError(error_message)
            # Use write with skip_validation context since we already validated
            contract.with_context(skip_validation=True).write({'state': 'ready_for_sale'})
            


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'company_id' in vals:
                self = self.with_company(vals['company_id'])
            if vals.get('contract_id', _("New")) == _("New"):
                vals['contract_id'] = self.env['ir.sequence'].next_by_code('consignment.contract') or _("New")
        res = super().create(vals_list)
        for contract in res:
            contract.set_is_supplemental()
        return res

    @api.constrains('rep_ids')
    def _check_duplicate_reps(self):
        for contract in self:
            rep_ids = contract.rep_ids.mapped('rep_id')
            if len(rep_ids) != len(set(rep_ids)):
                raise ValidationError(_("A rep cannot be added more than once to the same contract."))

    @api.constrains('state', 'sale_type', 'seller_id', 'auction_id', 'head1', 'kind1', 'weight1',
                   'contract_type', 'frame_size', 'flesh_type', 'weight_variance', 'horns',
                   'origin', 'current_fob', 'nearest_town', 'state_of_nearest_town',
                   'buyer_receives_fob', 'delivery_date_start', 'whose_option', 'rep_ids',
                   'breed_type', 'feeding_program', 'lot_number', 'buyer_id', 'sold_price',
                   'sold_date', 'video_link')
    def _check_state_validations(self):
        """Ensure contracts meet requirements for their current state"""
        # Skip validation if we're in a context that already validated
        if self.env.context.get('skip_validation'):
            return
            
        for contract in self:
            if contract.state == 'submitted':
                errors = contract._validate_for_submission()
                if errors:
                    raise ValidationError(f"Contract validation failed for submitted state:\n\n" + 
                                        "\n".join(f"• {error}" for error in errors))
            
            elif contract.state == 'approved':
                errors = contract._validate_for_approval()
                if errors:
                    raise ValidationError(f"Contract validation failed for approved state:\n\n" + 
                                        "\n".join(f"• {error}" for error in errors))
            
            elif contract.state == 'ready_for_sale':
                errors = contract._validate_for_ready_for_sale()
                if errors:
                    raise ValidationError(f"Contract validation failed for ready for sale state:\n\n" + 
                                        "\n".join(f"• {error}" for error in errors))
            
            elif contract.state == 'sold':
                errors = contract._validate_for_sold()
                if errors:
                    raise ValidationError(f"Contract validation failed for sold state:\n\n" + 
                                        "\n".join(f"• {error}" for error in errors))

    def action_cancel(self):
        for contract in self:
            contract.state = 'canceled'
            
    def action_scratch(self):
        for contract in self:
            contract.state = 'scratched'

    def action_no_sale(self):
        for contract in self:
            contract.state = 'no_sale'

    def action_sold(self):
        """Handler for the Sold button"""
        for record in self:
            errors = record._validate_for_sold()
            if errors:
                error_message = "Cannot mark contract as sold:\n\n" + "\n".join(f"• {error}" for error in errors)
                raise ValidationError(error_message)
            
            vals = {'state': 'sold'}
            # Only set sold_date if it's not already set
            if not record.sold_date:
                vals['sold_date'] = fields.Date.today()
            # Use write with skip_validation context since we already validated
            record.with_context(skip_validation=True).write(vals)
        return True
    
    def action_set_to_draft(self):
        self.write({'state':'draft'})

    def action_submit(self):
        for contract in self:
            errors = contract._validate_for_submission()
            if errors:
                error_message = "Cannot submit contract:\n\n" + "\n".join(f"• {error}" for error in errors)
                raise ValidationError(error_message)
            # Use write with skip_validation context since we already validated
            contract.with_context(skip_validation=True).write({'state': 'submitted'})

    def action_approve(self):
        for contract in self:
            errors = contract._validate_for_approval()
            if errors:
                error_message = "Cannot approve contract:\n\n" + "\n".join(f"• {error}" for error in errors)
                raise ValidationError(error_message)
            # Use write with skip_validation context since we already validated
            contract.with_context(skip_validation=True).write({'state': 'approved'})

    def action_reject(self):
        for contract in self:
            # No validation needed for rejection
            contract.write({'state': 'rejected'})

    # Merge feature
    def validate_status(self,action='Merged'):
        draft_contracts = self.filtered(lambda c: c.state == 'draft')
        if draft_contracts:
            error = f"Draft contracts cannot be {action}, please submit them first \n Contracts: {', '.join(f'CN {c.id:05d}' for c in draft_contracts)}"
            return error

        return ''
    
    def validate_merged_contracts(self,base_contract=None):
        merged_contracts = (self-base_contract).filtered(lambda c : c.merged_contract_id )
        if merged_contracts:
            error = f"Contracts: {', '.join(f'CN {c.id:05d}' for c in merged_contracts)} \n were already merged"
            return error

        return ''
    
            
    def _compute_merged_contract_count(self):
        """Compute the count of merged contracts."""
        for contract in self:
            contract.merged_contract_count = self.search_count([('merged_contract_id', '=', contract.id)]) 

    def validate_header_info(self):
        error = ''
        for field in  header_fields_to_validate:
            items = set(self.mapped(field))
            if len(items) > 1:
                error += f"Contracts are not consistent on field: {field} \n"
                return error
        if error:
            error += "Please fix the above errors before merging contracts."
            return error

        return ''
        

    def validate_head_bread_info(self):
        errors = []
        for field in  head_breed_info_fields_to_validate:
            items = set(self.mapped(field))
            if len(items) > 1:

                errors.append(f"Contracts have different {field}, It cannot be merged.")
        return errors
    
    def validate_reps(self):
        pass

    def action_toggle_chatter(self):
        """Toggle the visibility of the chatter."""
        for contract in self:
            contract.display_chatter = not contract.display_chatter

    def create_error_list(self,errors):
        # Start the unordered list
        msg = ""
        # Loop through each error and add it as a list item
        for error in errors:
            if error:
                msg += f"- {error}\n"
                msg += "---------------------------------------- \n"
        
        return msg
    
    def action_merged_contracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contracts',
            'view_mode': 'tree',
            'res_model': 'consignment.contract',
            'domain': [('merged_contract_id', '=', self.id)],
            'context': "{'create': False}"
        }
    def can_be_merged(self,base_contract=None):
        # Determine base_contract if not provided
        if not base_contract:
            # Get the lowest ID contract        
            base_contract = self.sorted(key=lambda c: c.id)[0]
        
        errors_to_fix = [
            self.validate_merged_contracts(base_contract=base_contract),
            self.validate_status(),
            self.validate_header_info(),
            *self.validate_head_bread_info()  # Unpack the list if there are multiple errors
            ]
        return all(elem == '' for elem in errors_to_fix)
            

                
    def action_merge_option_contracts(self):
        ''' Open the 'merge.option.contracts.wizard' to select the contracts to merge with the original 
            :return: An action opening 'merge.option.contracts.wizard'.
        '''
        return {
            'name': _('Merge option Contracts'),
            'res_model': 'merge.option.contracts.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {
                'default_base_contract': self.id,
                'default_option_contract_ids': self.option_contract_ids.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }      

    def merge(self,base_contract=None):
        """Merge contracts into the contract with lowest ID."""
        'When this function is called, contracts have passed all the validations'
        
        if not base_contract:
            #Get the lowest ID contract        
            base_contract = self.sorted(key=lambda c: c.id)[0]
        
        # Merge addendums by matching seller_id and lien_holder_id, summing head_count
        merged_addendums = {}
        for contract in self:
            for addendum in contract.addendum_ids:
                key = (addendum.seller_id.id, addendum.lien_holder_id.id if addendum.lien_holder_id else False)
                if key not in merged_addendums:
                    merged_addendums[key] = {
                        'seller_id': addendum.seller_id.id,
                        'lien_holder_id': addendum.lien_holder_id.id if addendum.lien_holder_id else False,
                        'percentage': addendum.percentage,
                        'head_count': 0,
                        'active': addendum.active,
                        'sequence': addendum.sequence,
                    }
                merged_addendums[key]['head_count'] += addendum.head_count or 0
        
        # Calculate merged contract head count
        merged_head_count = sum(self.mapped('head1')) + sum(self.mapped('head2'))
        
        # Scale the merged addendum head_counts to match the merged contract head count
        total_summed_addendum_heads = sum(data['head_count'] for data in merged_addendums.values())
        if total_summed_addendum_heads > 0:
            scale_factor = merged_head_count / total_summed_addendum_heads
            # Identify the addendum with the largest original head_count for later adjustment
            largest_key = max(merged_addendums, key=lambda k: merged_addendums[k]['head_count'])
            for data in merged_addendums.values():
                data['head_count'] = round_half_up(data['head_count'] * scale_factor)
            # After rounding, adjust the largest addendum so that totals match exactly
            current_total = sum(data['head_count'] for data in merged_addendums.values())
            difference = merged_head_count - current_total
            if difference:
                merged_addendums[largest_key]['head_count'] += difference
        
        # Prepare addendum commands
        addendum_commands = [(5, 0, 0)]  # Clear existing addendums
        for addendum_data in merged_addendums.values():
            addendum_commands.append((0, 0, addendum_data))
        
        vals_to_update = {
            'head1': merged_head_count,  # Since head2 is 0 in this case, but keeping general
            'head2': 0,  # Assuming head2 is summed to 0, but actually sum all head2
            'addendum_ids': addendum_commands,
        }
        # Actually sum head2 as well
        vals_to_update['head2'] = sum(self.mapped('head2'))
        vals_to_update['head1'] = sum(self.mapped('head1'))
        
        # Update the lowest ID contract with the total head counts and merged addendums
        base_contract.write(vals_to_update)

        # Zero out the head counts in the merged contracts
        for contract in self:
            if contract != base_contract:
                contract.write({
                    'head1': 0,
                    'head2': 0,
                    'addendum_ids': [(5, 0, 0)],  # Remove all addendums from merged contracts
                    'state':'merged',
                    'merged_contract_id': base_contract.id,
                    'office_notes': f'Merged into contract CN {base_contract.id:05d}',
                })
        

    def merge_contracts(self,base_contract=None):
        # Determine base_contract if not provided
        if not base_contract:
            # Get the lowest ID contract        
            base_contract = self.sorted(key=lambda c: c.id)[0]
        
        # Collect errors from various validation functions
        errors_to_fix = [
            self.validate_merged_contracts(base_contract=base_contract),
            self.validate_status(),
            self.validate_header_info(),
            *self.validate_head_bread_info()  # Unpack the list if there are multiple errors
        ]
        # Filter out any empty (falsy) errors
        errors_to_fix = [error for error in errors_to_fix if error]

        # Raise an error if there are any issues to fix
        if errors_to_fix:
            error_message = self.create_error_list(errors_to_fix)
            raise ValidationError(error_message)
        
        # Proceed to create the new contract if no errors
        self.merge(base_contract=base_contract)
    

    # Split Feature

    def split_contract(self):
        self.ensure_one()
        if self.created_loads == self.load_option:
            raise ValidationError('This contract was already split in full')
        if not self.lot_number:
            raise ValidationError(_('Please enter a valid lot number'))
        errors_to_fix = [
            self.validate_status(action='Split'),
            *self.validate_head_bread_info()  # Unpack the list if there are multiple errors
        ]
        # Filter out any empty (falsy) errors
        errors_to_fix = [error for error in errors_to_fix if error]

        # Raise an error if there are any issues to fix
        if errors_to_fix:
            error_message = self.create_error_list(errors_to_fix)
            raise ValidationError(error_message)
        
        # Open wizard to get amount of contracts to create
        if self.load_option == 0:
            raise ValidationError('Please set Load Option before splitting contract')
        return {
            'name': _('Split Contract'),
            'res_model': 'split.contract.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {
                'active_model': 'consignment.contract',
                'active_ids': self.ids,
                'load_option': self.load_option,
                'created_loads': self.created_loads,
                'available_loads': self.available_loads,
                'batch_size': self.head1 // self.load_option,
                'head1': self.head1,
                
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }     

    
    def format_phone(self, phone):
            """Format phone numbers for US and MX without external packages."""
            if not phone:
                return ''

            sanitized_phone = re.sub(r'[^\d+]', '', phone)

            if sanitized_phone.startswith('+1') or (len(sanitized_phone) == 10 and not sanitized_phone.startswith('+')):
                digits = sanitized_phone.lstrip('+1')
                if len(digits) == 10:
                    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
                return phone

            if sanitized_phone.startswith('+52') or sanitized_phone.startswith('52'):
                digits = sanitized_phone.lstrip('+52')
                if len(digits) in (10, 11):
                    return f"+52 {digits[:2]} {digits[2:6]} {digits[6:]}" if len(digits) == 10 else f"+52 {digits[:3]} {digits[3:7]} {digits[7:]}"
                return phone

            return phone

    def get_location_description(self, contract=None):
        """Construct the location description string."""
        record = contract or self
        description = ""

        if record.current_fob:
            description = record.current_fob.name

        if record.nearest_town and record.state_of_nearest_town:
            town_state = f"{record.nearest_town}, {record.state_of_nearest_town.code}"

            if record.distance_to_nearest_town and record.direction_to_nearest_town:
                town_desc = f"{record.distance_to_nearest_town} miles {record.direction_to_nearest_town} of {town_state}"
            else:
                town_desc = town_state

            description = f"{description}, {town_desc}" if description else town_desc

            if record.distance_to_nearest_city and record.direction_to_nearest_city and record.nearest_city and record.state_of_nearest_city:
                city_state = f"{record.nearest_city}, {record.state_of_nearest_city.code}"
                description += f" which is {record.distance_to_nearest_city} miles {record.direction_to_nearest_city} of {city_state}"

        return description

    def get_short_location_description(self, contract=None):
        """Construct the location description string."""
        record = contract or self
        description = ""

        if record.nearest_town and record.state_of_nearest_town:
            town_state = f"{record.nearest_town}, {record.state_of_nearest_town.code}"

            if record.distance_to_nearest_town and record.direction_to_nearest_town:
                description = f"{record.distance_to_nearest_town} {record.distance_to_nearest_town > 1 and 'miles' or 'mile'} {record.direction_to_nearest_town} of {town_state}"
            else:
                description = town_state

        return description
    
    @api.depends('distance_to_nearest_town', 'direction_to_nearest_town', 'nearest_town', 
                'state_of_nearest_town', 'distance_to_nearest_city', 'direction_to_nearest_city', 
                'nearest_city', 'state_of_nearest_city')
    def _compute_location_description(self):
        for record in self:
            record.location_description = record.get_location_description()

    @api.depends('distance_to_nearest_town', 'direction_to_nearest_town', 'nearest_town', 
                'state_of_nearest_town')
    def _compute_short_location_description(self):
        for record in self:
            record.short_location_description = record.get_short_location_description()

    @api.depends('seller_id')
    def _compute_lien_holder_id_domain(self):
        for rec in self:
            rec.lien_holder_id_domain = False
            if rec.seller_id and len(rec.seller_id.lien_holder_ids) > 1:
                rec.lien_holder_id_domain = [(6, 0, rec.seller_id.lien_holder_ids.ids)]

    @api.depends('castration', 'comments')
    def _compute_comments_with_castration(self):
        for record in self:
            castration_text = f"{record.castration.name}. " if record.castration else ""
            record.full_comments = f"{castration_text}{record.comments or ''}"
            
    @api.depends('vaccination_desc', 'vac_program')
    def _compute_vacc_description(self):
        for record in self:
            vacc_program_text = f"{record.vac_program.name}. " if record.vac_program else ""
            record.full_vaccination_desc = f"{vacc_program_text}{record.vaccination_desc or ''}"

    @api.onchange('weight_uom')
    def _update_total_gross_weight(self):
        self.total_gross_weight = self._origin.weight_uom._compute_quantity(self.total_gross_weight,self.weight_uom)

    @api.depends('seller_id')
    def _compute_payment_info_domain(self):
        for contract in self:
            if contract.seller_id:
                contract.payment_info_domain = contract.seller_id.child_ids.filtered(lambda address : address.type == 'payment')
            else:
                contract.payment_info_domain = False

    @api.onchange('seller_id')
    def _onchange_seller_id(self):
        # Skip default rep creation if copying
        if self.env.context.get('skip_default_reps'):
            return
        
        # Clear all existing reps when seller changes
        self.rep_ids = [(5, 0, 0)]
        
        # Create new default reps if seller exists
        if self.seller_id:
            for rep in self.seller_id.rep_ids:
                self.rep_ids = [(0, 0, {
                    'seller_id': self.seller_id.id,
                    'rep_id': rep.rep_id.id,
                    'percentage_commission': rep.percentage_commission,
                    'consigning_rep': len(self.seller_id.rep_ids) == 1,  # Set as consigning if it's the only rep
                    'active': True,
                })]

    @api.onchange('rep_ids')
    def _onchange_rep_ids(self):
        active_reps = self.rep_ids.filtered(lambda r: r.active)
        if len(active_reps) == 1:
            # If there's only one active rep, make it consigning
            active_reps.consigning_rep = True

    @api.onchange('rep_ids.consigning_rep')
    def _onchange_rep_consigning(self):
        active_reps = self.rep_ids.filtered(lambda r: r.active)
        if len(active_reps) > 1:
            # Find the rep that was just marked as consigning
            new_consigning = active_reps.filtered(lambda r: r.consigning_rep and r._origin.consigning_rep != r.consigning_rep)
            if new_consigning:
                # Uncheck all other reps
                for rep in active_reps - new_consigning:
                    rep.consigning_rep = False

    @api.onchange('state_of_nearest_town')
    def _onchange_state_of_nearest_town(self):
        for record in self:
            if record.state_of_nearest_town:
                record.region_id = record.state_of_nearest_town.region_id

    @api.onchange('state')
    def _onchange_state(self):
        for record in self:
            if record.state == 'sold':
                record.sold_date = fields.Date.today()


    def set_is_supplemental(self):
        for contract in self:
            if contract.auction_id and contract.create_date:
                contract.is_supplemental = contract.auction_id.is_public

    @api.depends('delivery_date_start', 'delivery_date_end')
    def _compute_delivery_date_range(self):
        for record in self:
            start = record.delivery_date_start
            end = record.delivery_date_end

            if start and end:
                if start.year == end.year and start.month == end.month:
                    record.delivery_date_range = f"{start.strftime('%B')} {start.day} - {end.day}, {start.year}"
                elif start.year == end.year:
                    record.delivery_date_range = f"{start.strftime('%B %-d')} - {end.strftime('%B %-d, %Y')}"
                else:
                    record.delivery_date_range = f"{start.strftime('%B %-d, %Y')} - {end.strftime('%B %-d, %Y')}"
            elif start:
                record.delivery_date_range = start.strftime('%B %-d, %Y')
            else:
                record.delivery_date_range = "Date not specified"

    @api.onchange('auction_id')
    def _onchange_auction_id(self):
        self.set_is_supplemental()

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.browse(docids)
        return {
            "doc_ids": docids,
            "doc_model": "consignment.contract",
            "docs": docs,
            "data": data,
        }

    def _compute_title(self, contract=None):
        """Compute title for a given contract or self"""
        record = contract or self
        base_title = f"{record.seller_id.name or ''} | {record.head1 or ''} {record.kind1.name if record.kind1 else ''} {f'{record.weight1}#' if record.weight1 else ''}"
        has_second_group = bool(record.head2 or record.kind2)
        if has_second_group:
            base_title += " &"
        if record.head2:
            base_title += f" {record.head2}"
        if record.kind2:
            base_title += f" {record.kind2.name}"
        if record.weight2:
            base_title += f" {record.weight2}#"
        
        return base_title

    #! Auctic Export
    def action_export_auctic_csv(self):
        """Export selected contracts to CSV file"""
        if not self:
            raise ValidationError(_("Please select at least one contract to export."))

        output = StringIO()
        writer = csv.writer(output)

        headers = [
            'Contract ID',
            'Lot Number',
            'Sale Order',
            'Title',
            # 'Title 2',
            # 'Title 3',
            'Description',
            'Seller',
            'Price Back',
            'Location',
            'City',
            'State',
            'Delivery',
            'Origin',
            'Slide',
            'Reps',
            'Breed Type',
            'Implanted',
            'Weighing Conditions',
            'Comments',
            'Vaccinations',
            'Frame Size',
            'Flesh Type',
            'Horns',
            'Weight Variance',
            'Feeding Program',
            'Icons',
            'Video',
        ]
        
        # Check if any contract is LiveAgXchange to determine headers
        is_liveagxchange = any(contract.auction_id and contract.auction_id.sale_type.name == 'LiveAgXchange' for contract in self)
        
        if is_liveagxchange:
            headers.append('Asking Price')
            headers.append('seller_user_email')
            headers.append('sale method')
            headers.append('status')
        else:
            headers.append('Starting Bid Amount')

        writer.writerow(headers)

        # Sort contracts based on state and dates
        def sort_key(c):
            # Universal sorting for all contracts
            is_sold = c.state in ['sold', 'delivered', 'delivery_ready']
            if is_sold:
                # Sold contracts: sort by sold_date (oldest first)
                sold_date = c.sold_date or c.create_date.date()
                return (1, sold_date.toordinal(), c.lot_number or '')
            else:
                # Active contracts: sort by create_date (newest first)
                return (0, -(c.create_date.date()).toordinal(), c.lot_number or '')
        
        sorted_contracts = self.sorted(key=sort_key)
        
        
        # Assign sale order numbers for LiveAgXchange contracts
        liveagxchange_contracts = [c for c in sorted_contracts if c.auction_id and c.auction_id.sale_type.name == 'LiveAgXchange']
        if liveagxchange_contracts:
            for i, contract in enumerate(liveagxchange_contracts, 1):
                contract.sale_order = i

        for contract in sorted_contracts:
            is_liveagxchange = contract.auction_id and contract.auction_id.sale_type.name == 'LiveAgXchange'
            lot_number = ''
            if contract.lot_number:
                cleaned = ''.join(char for char in contract.lot_number if char.isdigit() or char == '.')
                if '.' in cleaned:
                    parts = cleaned.split('.')
                    lot_number = f"{parts[0]}.{''.join(parts[1:])}"
                else:
                    lot_number = cleaned

            # title = self._compute_title(contract)
            title = ''
            if is_liveagxchange:
                title = f"{contract.head1} {contract.kind1.name} {f'{contract.weight1}#' if contract.weight1 else '' }"
                if contract.kind2 and contract.weight2:
                    title += f" &{f' {contract.head2}' if contract.head2 else '' } {contract.kind2.name} {f'{contract.weight2}#' if contract.weight2 else ''}"
            else:
                title = self._compute_title(contract)
            title2 = ''
            if contract.head1 and contract.kind1:
                title2 = f"{contract.head1} {contract.kind1.name} {f'{contract.weight1}#' if contract.weight1 else ''}"
            title3 = ''
            if contract.kind2 and contract.weight2:
                title3 = f"{f'#{contract.head2}' if contract.head2 else '&' } {contract.kind2.name} {f'{contract.weight2}#' if contract.weight2 else ''}"

            asking_price = contract.asking_price or ''
            if asking_price and isinstance(asking_price, (int, float)):
                asking_price = f"{asking_price:.0f}" if asking_price.is_integer() else f"{asking_price:.2f}"

            slide_description = contract.short_slide_description or ''
            location_description = self.get_short_location_description(contract)
            
            sorted_icons = contract.program_icon_ids.sorted(key=lambda x: x.priority)
            icon_urls = [f'{icon.image_url},{icon.name}' for icon in sorted_icons if icon.image_url]
            icon_string = '|'.join(icon_urls) if icon_urls else ''

            delivery_range = f'="{contract.delivery_date_range}"' if contract.delivery_date_range else ''
            description = ''
            description_parts = []
            if contract.seller_id:
                description_parts.append(f"<strong>Seller: </strong>{contract.seller_id.name}")
            if contract.origin_full_description:
                description_parts.append(f"<strong>Origin: </strong>{contract.origin_full_description}")
            if delivery_range:
                description_parts.append(f"<strong>Delivery: </strong>{delivery_range}")
            primary_rep = contract.primary_rep
            if primary_rep:
                description_parts.append(f"<strong>Rep: </strong>{primary_rep.rep_name}, {self.format_phone(primary_rep.phone) if primary_rep.phone else ''}")
            description_parts.append("")
            if contract.breed_type:
                description_parts.append(f"<strong>Breed Type: </strong>{contract.breed_type}")
            if slide_description:
                description_parts.append(f"<strong>Slide: </strong>{slide_description}")
            description = "<br>".join(description_parts)
            if sorted_icons:
                icon_html = '<div style="display: flex; gap: 10px; margin-top: 10px;">'
                for icon in sorted_icons:
                    if icon.image_url:
                        icon_html += f'<img src="{icon.image_url}" alt="{icon.name}" style="height: 40px;">'
                icon_html += '</div>'
                description_parts.append(icon_html)
                description = "<br>".join(description_parts)


            implanted = ""
            if contract.implanted_type:
                if contract.implanted_month and contract.implanted_year:
                    month_name = datetime.strptime(str(contract.implanted_month), '%m').strftime('%b')
                    implanted = f"{contract.implanted_type.name} - {month_name} {contract.implanted_year}"
                else:
                    implanted = contract.implanted_type.name

            reps = ""
            for i, rep in enumerate(contract.rep_ids):
                if rep.rep_id.rep_name:
                    formatted_phone = self.format_phone(rep.rep_id.phone)
                    reps += f"{rep.rep_id.rep_name} {formatted_phone}"
                    if i < len(contract.rep_ids) - 1:
                        reps += ", "
                        

            row = [
                f'CN {contract.id:05d}',
                lot_number or '',
                contract.sale_order or '',
                title,
                # title2,
                # title3,
                description,
                contract.seller_id.name or '',
                contract.price_back or '',
                location_description or '',
                contract.nearest_town or '',
                contract.state_of_nearest_town.code or '',
                delivery_range or '',
                contract.origin_full_description or '',
                slide_description,
                reps,
                contract.breed_type or '',
                implanted,
                contract.weighing_cond_w_freight or '',
                contract.full_comments or '',
                contract.full_vaccination_desc or '',
                contract.frame_size.name if contract.frame_size else '',
                contract.flesh_type.name if contract.flesh_type else '',
                contract.horns.name if contract.horns else '',
                contract.weight_variance.name if contract.weight_variance else '',
                contract.feeding_program or '',
                icon_string,
                contract.video_link or '',
            ]
            if is_liveagxchange:
                row.append(asking_price)
                row.append('xchange@live-ag.com')
                row.append('buynow_makeoffer')
                row.append('active')
            else:
                row.append(asking_price or '')
                
            writer.writerow(row)

        auction = self[0].auction_id
        timestamp = fields.Datetime.now().strftime('%b-%d-%y_%H:%M')
        if auction and auction.sale_type.name == 'Video Sale':
            date_str = auction.sale_date_begin.strftime('%B %d')
            filename = f'LAVA_Auctic_{date_str}.csv'
        elif auction and auction.sale_type.name == 'Private Treaty':
            filename = f'PT_Auctic_{timestamp}.csv'
        elif auction and auction.sale_type.name == 'LiveAgXchange':
            filename = f'LAX_Auctic_{timestamp}.csv'
        else:
            filename = f'Auctic_Contracts_{timestamp}.csv'

        attachment_vals = {
            'name': filename,
            'datas': base64.b64encode(output.getvalue().encode()).decode(),
            'type': 'binary',
        }
        attachment = self.env['ir.attachment'].create(attachment_vals)

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
        
    #! Auctic Export v2
    def action_export_auctic_v2_csv(self):
        """Export selected contracts to CSV file"""
        if not self:
            raise ValidationError(_("Please select at least one contract to export."))

        output = StringIO()
        writer = csv.writer(output)

        headers = [
            'Contract ID',
            'Lot Number',
            'Sale Order',
            'Title',
            'Seller',
            'Head1',
            'Kind1',
            'Weight1',
            'Head2',
            'Kind2',
            'Weight2',
            'Price Back',
            'Description',
            'Location',
            'Delivery',
            'Slide',
            'Rep',
            'Origin',
            'Breed Type',
            'Bangs Vacc',
            'Frame Size',
            'Flesh',
            'Wt. Variance',
            'Horns',
            'Implanted',
            'Feeding Type',
            'Weigh Cond.',
            'Vaccinations',
            'Comments',
            'Option',
            'Represented By',
            'City',
            'State',
            'Icons',
            'Video',
        ]
        
        # Check if any contract is LiveAgXchange to determine headers
        is_liveagxchange = any(contract.auction_id and contract.auction_id.sale_type.name == 'LiveAgXchange' for contract in self)
        
        if is_liveagxchange:
            headers.append('Asking Price')
            headers.append('seller_user_email')
            headers.append('sale method')
            headers.append('status')
        else:
            headers.append('Starting Bid Amount')

        writer.writerow(headers)

        # Sort contracts based on state and dates
        def sort_key(c):
            # Universal sorting for all contracts
            is_sold = c.state in ['sold', 'delivered', 'delivery_ready']
            if is_sold:
                # Sold contracts: sort by sold_date (oldest first)
                sold_date = c.sold_date or c.create_date.date()
                return (1, sold_date.toordinal(), c.lot_number or '')
            else:
                # Active contracts: sort by create_date (newest first)
                return (0, -(c.sale_order or 0), c.lot_number or '')

        sorted_contracts = self.sorted(key=sort_key)
        
        
        # Assign sale order numbers for LiveAgXchange contracts
        liveagxchange_contracts = [c for c in sorted_contracts if c.auction_id and c.auction_id.sale_type.name == 'LiveAgXchange']
        if liveagxchange_contracts:
            for i, contract in enumerate(liveagxchange_contracts, 1):
                contract.sale_order = i

        for contract in sorted_contracts:
            is_liveagxchange = contract.auction_id and contract.auction_id.sale_type.name == 'LiveAgXchange'
            lot_number = ''
            if contract.lot_number:
                cleaned = ''.join(char for char in contract.lot_number if char.isdigit() or char == '.')
                if '.' in cleaned:
                    parts = cleaned.split('.')
                    lot_number = f"{parts[0]}.{''.join(parts[1:])}"
                else:
                    lot_number = cleaned

            title = ''
            if is_liveagxchange:
                title = f"{contract.head1} {contract.kind1.name} {f'{contract.weight1}#' if contract.weight1 else '' }"
                if contract.kind2 and contract.weight2:
                    title += f" &{f' {contract.head2}' if contract.head2 else '' } {contract.kind2.name} {f'{contract.weight2}#' if contract.weight2 else ''}"
            else:
                title = self._compute_title(contract)

            asking_price = contract.asking_price or ''
            if asking_price and isinstance(asking_price, (int, float)):
                asking_price = f"{asking_price:.0f}" if asking_price.is_integer() else f"{asking_price:.2f}"

            slide_description = contract.short_slide_description or ''
            sorted_icons = contract.program_icon_ids.sorted(key=lambda x: x.priority)
            icon_urls = [f'{icon.image_url}' for icon in sorted_icons if icon.image_url]
            icon_string = ','.join(icon_urls) if icon_urls else ''

            delivery_range = f"{contract.delivery_date_range}" if contract.delivery_date_range else ''
            description = ''
            description_parts = []
            if contract.seller_id:
                description_parts.append(f"<strong>Seller: </strong>{contract.seller_id.name}")
            if contract.origin_full_description:
                description_parts.append(f"<strong>Origin: </strong>{contract.origin_full_description}")
            if delivery_range:
                description_parts.append(f"<strong>Delivery: </strong>{delivery_range}")
            primary_rep = contract.primary_rep
            if primary_rep:
                description_parts.append(f"<strong>Rep: </strong>{primary_rep.rep_name}, {self.format_phone(primary_rep.phone) if primary_rep.phone else ''}")
            description_parts.append("")
            if contract.breed_type:
                description_parts.append(f"<strong>Breed Type: </strong>{contract.breed_type}")
            if slide_description:
                description_parts.append(f"<strong>Slide: </strong>{slide_description}")
            description = "<br>".join(description_parts)
            if sorted_icons:
                icon_html = '<div style="display: flex; gap: 10px; margin-top: 10px;">'
                for icon in sorted_icons:
                    if icon.image_url:
                        icon_html += f'<img src="{icon.image_url}" alt="{icon.name}" style="height: 40px;">'
                icon_html += '</div>'
                description_parts.append(icon_html)
                description = "<br>".join(description_parts)


            implanted = ""
            if contract.implanted_type:
                if contract.implanted_month and contract.implanted_year:
                    month_name = datetime.strptime(str(contract.implanted_month), '%m').strftime('%b')
                    implanted = f"{contract.implanted_type.name} - {month_name} {contract.implanted_year}"
                else:
                    implanted = contract.implanted_type.name

            primary_rep = f"{contract.primary_rep.rep_name} - {self.format_phone(contract.primary_rep.phone) if contract.primary_rep.phone else ''}"
            reps = ""
            for i, rep in enumerate(contract.rep_ids):
                if rep.rep_id.rep_name:
                    formatted_phone = self.format_phone(rep.rep_id.phone)
                    reps += f"{rep.rep_id.rep_name} - {formatted_phone}"
                    if i < len(contract.rep_ids) - 1:
                        reps += ", "
                        

            row = [
                contract.id or '',
                lot_number or '',
                contract.sale_order or '',
                title,
                contract.seller_id.seller_name or '',
                contract.head1 or '',
                contract.kind1.name if contract.kind1 else '',
                contract.weight1 or '',
                contract.head2 or '',
                contract.kind2.name if contract.kind2 else '',
                contract.weight2 or '',
                contract.price_back or '',
                description,
                contract.location_description or '',
                f"'{contract.delivery_date_range}" if contract.delivery_date_range else '',
                slide_description,
                primary_rep or '',
                contract.origin_full_description or '',
                contract.breed_type or '',
                contract.bangs_vaccinated.name if contract.bangs_vaccinated else '',
                contract.frame_size.name if contract.frame_size else '',
                contract.flesh_type.name if contract.flesh_type else '',
                contract.weight_variance.name if contract.weight_variance else '',
                contract.horns.name if contract.horns else '',
                implanted,
                contract.feeding_program or '',
                contract.weighing_cond_w_freight or '',
                contract.full_vaccination_desc or '',
                contract.full_comments or '',
                contract.option_description or '',
                reps,
                contract.nearest_town or '',
                contract.state_of_nearest_town.code or '',
                icon_string,
                contract.video_link or '',
            ]
            if is_liveagxchange:
                row.append(asking_price)
                row.append('xchange@live-ag.com')
                row.append('buynow_makeoffer')
                row.append('active')
            else:
                row.append(asking_price or '')
                
            writer.writerow(row)

        auction = self[0].auction_id
        timestamp = fields.Datetime.now().strftime('%b-%d-%y_%H:%M')
        if auction and auction.sale_type.name == 'Video Sale':
            date_str = auction.sale_date_begin.strftime('%B %d')
            filename = f'LAVA_Auctic_{date_str}.csv'
        elif auction and auction.sale_type.name == 'Private Treaty':
            filename = f'PT_Auctic_{timestamp}.csv'
        elif auction and auction.sale_type.name == 'LiveAgXchange':
            filename = f'LAX_Auctic_{timestamp}.csv'
        else:
            filename = f'Auctic_Contracts_{timestamp}.csv'

        attachment_vals = {
            'name': filename,
            'datas': base64.b64encode(output.getvalue().encode()).decode(),
            'type': 'binary',
        }
        attachment = self.env['ir.attachment'].create(attachment_vals)

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
        
    #! Catalog Export
    def action_export_catalog_csv(self):
        """Export selected contracts to CSV file"""
        if not self:
            raise ValidationError(_("Please select at least one contract to export."))

        output = StringIO()
        writer = csv.writer(output)
        output.write('\ufeff')

        headers = [
            'Code',
            'Contract ID',
            'Seller',
            'Head 1',
            'Kind 1',
            'Weight 1',
            'Head 2',
            'Kind 2',
            'Weight 2',
            'Price Back',
            'Delivery Date Range',
            'Location Description',
            'Weighing Conditions',
            'Breed Type',
            'Short Slide Description',
            'Origin',
            'Frame Size',
            'Flesh Type',
            'Est Weight Variance',
            'Horns',
            'Feeding Program',
            'VAC Program',
            'Bangs Vaccinated',
            'Vaccination Description',
            'Implanted',
            'Comments',
            'Rep 1',
            'Rep 2',
            'Rep 3',
            'Programs',
            'Icon 1',
            'Icon 2',
            'Icon 3',
            'Icon 4',
            'Icon 5',
            'Icon 6',
            'Icon 7',
            'Icon 8',
            'Icon 9',
            'Icon 10',
            'Option Lot'
        ]
        writer.writerow(headers)

        sorted_contracts = self.sorted(
            key=lambda c: (c.sale_order or float('inf'), c.lot_number or '')
        )

        for contract in sorted_contracts:
            location_description = self.get_location_description(contract)
            implanted = ""
            if contract.implanted_type:
                if contract.implanted_month and contract.implanted_year:
                    month_name = datetime.strptime(str(contract.implanted_month), '%m').strftime('%b')
                    implanted = f"{contract.implanted_type.name} - {month_name} {contract.implanted_year}"
                else:
                    implanted = contract.implanted_type.name
                    
            reps = []
            for i, rep in enumerate(contract.rep_ids):
                if rep.rep_id.name:
                    formatted_phone = self.format_phone(rep.rep_id.phone)
                    reps.append(f"{rep.rep_id.rep_name} - {formatted_phone}")

            program_names = ""
            for program in contract.program_icon_ids:
                program_names += f"{program.name}"
                if program.name != contract.program_icon_ids[-1].name:
                    program_names += ", "

            sorted_icons = contract.program_icon_ids.sorted(key=lambda x: x.priority)
            icon_urls = [icon.image_url for icon in sorted_icons[:10]]
            icon_urls.extend([''] * (10 - len(icon_urls)))
            
            row = [
                contract.lot_number or '',
                f'CN {contract.id:05d}',
                contract.seller_id.name or '',
                contract.head1 or '',
                contract.kind1.name if contract.kind1 else '',
                contract.weight1 or '',
                contract.head2 or '',
                contract.kind2.name if contract.kind2 else '',
                contract.weight2 or '',
                contract.price_back or '',
                contract.delivery_date_range if contract.delivery_date_range else '',
                location_description or '',
                contract.weighing_cond_w_freight or '',
                (contract.breed_type or '').replace('\n', ' ').replace('\r', ' ').strip(),
                contract.short_slide_description or '',
                contract.origin_full_description or '',
                contract.frame_size.name if contract.frame_size else '',
                contract.flesh_type.name if contract.flesh_type else '',
                contract.weight_variance.name if contract.weight_variance else '',
                contract.horns.name if contract.horns else '',
                contract.feeding_program or '',
                contract.vac_program.name if contract.vac_program else '',
                contract.bangs_vaccinated.name if contract.bangs_vaccinated else '',
                contract.full_vaccination_desc or '',
                implanted,
                contract.full_comments or '',
                reps[0] if reps else '',
                reps[1] if len(reps) > 1 else '',
                reps[2] if len(reps) > 2 else '',
                program_names,
                icon_urls[0],  # Icon 1
                icon_urls[1],  # Icon 2
                icon_urls[2],  # Icon 3
                icon_urls[3],  # Icon 4
                icon_urls[4],  # Icon 5
                icon_urls[5],  # Icon 6
                icon_urls[6],  # Icon 7
                icon_urls[7],  # Icon 8
                icon_urls[8],  # Icon 9
                icon_urls[9],  # Icon 10
                contract.option_description or '',
            ]
            writer.writerow(row)

        auction = self[0].auction_id
        timestamp = fields.Datetime.now().strftime('%b-%d-%y_%H:%M')
        if auction and auction.sale_type.name == 'Video Sale':
            date_str = auction.sale_date_begin.strftime('%B %d')
            filename = f'LAVA_Catalog_{date_str}.csv'
        elif auction and auction.sale_type.name == 'Private Treaty':
            filename = f'PT_Catalog_{timestamp}.csv'
        elif auction and auction.sale_type.name == 'LiveAgXchange':
            filename = f'LAX_Catalog_{timestamp}.csv'
        else:
            filename = f'Catalog_Contracts_{timestamp}.csv'

        attachment_vals = {
            'name': filename,
            'datas': base64.b64encode(output.getvalue().encode('utf-8-sig')).decode(),
            'type': 'binary',
        }
        attachment = self.env['ir.attachment'].create(attachment_vals)

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    def format_delivery_date_range(self, start_date, end_date):
        """Format delivery date range according to TV format rules"""
        if not start_date:
            return ""
            
        if not end_date:
            return start_date.strftime("%B %-d")
            
        if start_date == end_date:
            return start_date.strftime("%B %-d")
        elif start_date.month == end_date.month and start_date.year == end_date.year:
            return f"{start_date.strftime('%B %-d')} - {end_date.strftime('%-d')}"
        elif start_date.year == end_date.year:
            return f"{start_date.strftime('%B %-d')} - {end_date.strftime('%B %-d')}"
        else:
            return f"{start_date.strftime('%b %-d, %y')} - {end_date.strftime('%b %-d, %y')}"

    #! GFX Export
    def action_export_gfx_csv(self):
        """Export selected contracts to CSV file"""
        if not self:
            raise ValidationError(_("Please select at least one contract to export."))

        output = StringIO()
        writer = csv.writer(output)
        output.write('\ufeff')

        headers = [
            'Lot',
            'Consignor',
            'HeadKind',
            'Location',
            'Delivery',
            'Origin',
            'Slide',
            'Rep',
            'BreedType',
            'Notes',
            'Changes',
            'IconFiles',
            'gfxChanged',
        ]
        writer.writerow(headers)
        
        sorted_contracts = self.sorted(
            key=lambda c: (c.sale_order or float('inf'), c.lot_number or '')
        )

        for row_num, contract in enumerate(sorted_contracts, start=1):
            sorted_icons = contract.program_icon_ids.sorted(key=lambda x: x.priority)
            icon_filenames = [f'{icon.filename}' for icon in sorted_icons if icon.filename]
            icon_string = '|'.join(icon_filenames) if icon_filenames else ''
            
            total_changes = 0

            headKind = ""
            if contract.head1 and contract.kind1 and contract.weight1:
                head1_changed = bool(contract.catalog_changes_ids.filtered(
                    lambda c: c.field_name == 'head1' and c.state == 'approved'))
                kind1_changed = bool(contract.catalog_changes_ids.filtered(
                    lambda c: c.field_name == 'kind1' and c.state == 'approved'))
                weight1_changed = bool(contract.catalog_changes_ids.filtered(
                    lambda c: c.field_name == 'weight1' and c.state == 'approved'))
                price_back_changed = bool(contract.catalog_changes_ids.filtered(
                    lambda c: c.field_name == 'price_back' and c.state == 'approved'))

                total_changes += sum([head1_changed, kind1_changed, weight1_changed, price_back_changed])

                head1_str = f"**{contract.head1}**" if head1_changed else str(contract.head1)
                kind1_str = f"**{contract.kind1.name}**" if kind1_changed else contract.kind1.name
                weight1_str = f"**{contract.weight1}#**" if weight1_changed else f"{contract.weight1}#"
                
                headKind = f"{head1_str} {kind1_str} {weight1_str}"
                
                if contract.head2 and contract.kind2 and contract.weight2:
                    head2_changed = bool(contract.catalog_changes_ids.filtered(
                        lambda c: c.field_name == 'head2' and c.state == 'approved'))
                    kind2_changed = bool(contract.catalog_changes_ids.filtered(
                        lambda c: c.field_name == 'kind2' and c.state == 'approved'))
                    weight2_changed = bool(contract.catalog_changes_ids.filtered(
                        lambda c: c.field_name == 'weight2' and c.state == 'approved'))

                    total_changes += sum([head2_changed, kind2_changed, weight2_changed])

                    head2_str = f"**{contract.head2}**" if head2_changed else str(contract.head2)
                    kind2_str = f"**{contract.kind2.name}**" if kind2_changed else contract.kind2.name
                    weight2_str = f"**{contract.weight2}#**" if weight2_changed else f"{contract.weight2}#"
                    
                    headKind += f"<br>{head2_str} {kind2_str} {weight2_str}"
                    
                    if contract.price_back:
                        price_back_str = f"**${contract.price_back} back**" if price_back_changed else f"${contract.price_back} back"
                        headKind += f" - {price_back_str}"
                elif contract.price_back:
                    price_back_str = f"**${contract.price_back} back**" if price_back_changed else f"${contract.price_back} back"
                    headKind += f" - {price_back_str}"
            
            delivery_start_changed = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.field_name == 'delivery_date_start' and c.state == 'approved'))
            delivery_end_changed = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.field_name == 'delivery_date_end' and c.state == 'approved'))
            
            if delivery_start_changed or delivery_end_changed:
                total_changes += 1
            
            delivery_range = self.format_delivery_date_range(contract.delivery_date_start, contract.delivery_date_end)
            if delivery_start_changed or delivery_end_changed:
                delivery_range = f"**{delivery_range}**"
            
            location_description = self.get_short_location_description(contract)
            location_changed = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.field_name in ['nearest_town', 'state_of_nearest_town', 'distance_to_nearest_town', 'direction_to_nearest_town', 'nearest_city', 'state_of_nearest_city', 'distance_to_nearest_city', 'direction_to_nearest_city'] 
                and c.state == 'approved'))
            origin_changed = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.field_name == 'origin' and c.state == 'approved'))
            
            slide_description = contract.short_slide_description or ''
            
            slide_changed = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.field_name in ['slide_type', 'slide_over', 'slide_under', 'slide_both'] 
                and c.state == 'approved'))
            
            if slide_changed:
                slide_description = f"**{contract.short_slide_description}**"
            
            breed_type_changed = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.field_name == 'breed_type' and c.state == 'approved'))
            
            total_changes += sum([location_changed, origin_changed, slide_changed, breed_type_changed])
            
            location = f"**{location_description}**" if location_changed else location_description
            origin = f"**{contract.origin_full_description}**" if origin_changed else contract.origin_full_description or ''
            slide = f"**{slide_description}**" if slide_changed else slide_description
            breed_type = f"**{contract.breed_type}**" if breed_type_changed else contract.breed_type
            option_text, option_text_markdown = self._compute_option_text(contract)
            
            row_data = [
                contract.lot_number or '', #Lot Number
                contract.seller_id.name or '', #Seller
                headKind, #Head Kind
                location, #Location
                delivery_range, #Delivery Range
                origin, #Origin
                slide, #Slide
                contract.rep_ids[0].rep_id.name if contract.rep_ids else '', #Rep
                breed_type, #Breed Type
                option_text_markdown, # notes
                option_text, # changes
                icon_string,
                "2" if total_changes > 1 else "1" if total_changes == 1 else "", # gfxChanged 
            ]
            writer.writerow(row_data)
            
        auction = self[0].auction_id
        timestamp = fields.Datetime.now().strftime('%b-%d-%y_%H:%M')
        if auction and auction.sale_type.name == 'Video Sale':
            date_str = auction.sale_date_begin.strftime('%B %d')
            filename = f'LAVA_GFX_{date_str}.csv'
        elif auction and auction.sale_type.name == 'Private Treaty':
            filename = f'PT_GFX_{timestamp}.csv'
        elif auction and auction.sale_type.name == 'LiveAgXchange':
            filename = f'LAX_GFX_{timestamp}.csv'
        else:
            filename = f'GFX_Contracts_{timestamp}.csv'
            
        attachment_vals = {
            'name': filename,
            'datas': base64.b64encode(output.getvalue().encode('utf-8-sig')).decode(),
            'type': 'binary',
        }
        attachment = self.env['ir.attachment'].create(attachment_vals)

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    @api.onchange('seller_id')
    def _onchange_seller_id_addendum(self):
        if self.seller_id and not self.addendum_ids:
            # First addendum: default payment address (or main seller), and seller's default lien holder
            payment_partner = self.seller_id.default_payment_info_id or self.seller_id
            lien_holder_id = self.seller_id.default_lien_holder_id.id if self.seller_id.default_lien_holder_id else False
            self.addendum_ids = [(0, 0, {
                'seller_id': payment_partner.id,
                'lien_holder_id': lien_holder_id,
                'head_count': (self.head1 or 0) + (self.head2 or 0),
                'active': True,
            })]

    primary_rep = fields.Many2one('res.partner', string='Primary Rep', compute='_compute_primary_rep', store=True)

    @api.depends('rep_ids', 'rep_ids.active', 'rep_ids.consigning_rep')
    def _compute_primary_rep(self):
        for contract in self:
            active_reps = contract.rep_ids.filtered(lambda r: r.active)
            if not active_reps:
                contract.primary_rep = False
                continue
                
            # First try to find a rep marked as consigning
            consigning_rep = active_reps.filtered(lambda r: r.consigning_rep)
            if consigning_rep:
                contract.primary_rep = consigning_rep[0].rep_id.id
            else:
                # If no rep is marked as consigning, use the first active rep
                contract.primary_rep = active_reps[0].rep_id.id
                # Mark this rep as consigning for future reference
                active_reps[0].consigning_rep = True

    def fix_consigning_reps(self):
        """Method to fix consigning reps in existing contracts"""
        contracts = self.search([])
        for contract in contracts:
            active_reps = contract.rep_ids.filtered(lambda r: r.active)
            if not active_reps:
                continue
                
            # Check if any rep is marked as consigning
            consigning_rep = active_reps.filtered(lambda r: r.consigning_rep)
            if not consigning_rep:
                # If no rep is marked as consigning, mark the first active rep
                active_reps[0].consigning_rep = True

    @api.onchange('buyer_id')
    def _onchange_buyer_id(self):
        if self.buyer_id:
            self.buyer_number = self.buyer_id.buyer_number_ids[0] if self.buyer_id.buyer_number_ids else False

    @api.onchange('implanted_date')
    def _onchange_implanted_date(self):
        if self.implanted_date:
            self.implanted_date = self.implanted_date.replace(day=1)

    def write(self, vals):
        if vals.get('implanted_date'):
            from datetime import datetime
            date_obj = datetime.strptime(vals['implanted_date'], '%Y-%m-%d')
            vals['implanted_date'] = date_obj.replace(day=1).strftime('%Y-%m-%d')
        return super().write(vals)

    @api.depends('head1', 'head2', 'addendum_ids', 'addendum_ids.head_count')
    def _compute_addendum_warning(self):
        for contract in self:
            contract.addendum_warning = False
            contract.show_addendum_warning = False
            
            if contract.addendum_ids:
                total_contract_heads = (contract.head1 or 0) + (contract.head2 or 0)
                total_addendum_heads = sum(addendum.head_count or 0 for addendum in contract.addendum_ids)
                
                if total_contract_heads != total_addendum_heads:
                    contract.show_addendum_warning = True
                    contract.addendum_warning = _(
                        "Warning: The total head count in addendums (%s) does not match "
                        "the contract's total head count (%s)"
                    ) % (total_addendum_heads, total_contract_heads)


    # @api.constrains('head1', 'head2', 'addendum_ids', 'addendum_ids.head_count')
    # def _check_addendum_head_counts(self):
    #     for contract in self:
    #         if contract.addendum_ids:
    #             total_contract_heads = (contract.head1 or 0) + (contract.head2 or 0)
    #             total_addendum_heads = sum(addendum.head_count or 0 for addendum in contract.addendum_ids)
                
    #             if total_contract_heads != total_addendum_heads:
    #                 raise ValidationError(_(
    #                     "Cannot save contract: The total head count in addendums (%s) "
    #                     "does not match the contract's total head count (%s)"
    #                 ) % (total_addendum_heads, total_contract_heads))


    @api.constrains('delivery_date_start', 'delivery_date_end')
    def _check_delivery_date_range(self):
        for contract in self:
            if contract.delivery_date_start and contract.delivery_date_end:
                if contract.delivery_date_start > contract.delivery_date_end:
                    raise ValidationError(_("The start of the delivery cannot be after the end of the delivery"))

    addendum_warning = fields.Text(
        string='Addendum Warning',
        compute='_compute_addendum_warning',
        store=True,
        help="Warning message when addendum head counts don't match contract")
    
    show_addendum_warning = fields.Boolean(
        string='Show Addendum Warning',
        compute='_compute_addendum_warning',
        store=True,
        help="Technical field to control warning visibility")

    def copy(self, default=None):
        default = dict(default or {})
        if 'auction_id' not in default:
            default['auction_id'] = False
        default.update({
            'contract_id': _('New'),
            'state': 'draft',
            'addendum_ids': False,
            'option_contract_ids': False,
            'copied_contract_id': self.id,
        })
        
        new_record = super(ConsignmentContract, self.with_context(skip_default_reps=True)).copy(default)
        if new_record.seller_id:
            for addendum in self.addendum_ids:
                self.env['contract.addendum'].create({
                    'contract_id': new_record.id,
                    'seller_id': addendum.seller_id.id,
                    'lien_holder_id': addendum.lien_holder_id.id,
                    'percentage': addendum.percentage,
                    'head_count': addendum.head_count,
                    'active': addendum.active,
                })
        
        return new_record

    has_past_auction_date = fields.Boolean(
        string='Has Past Auction Date',
        compute='_compute_has_past_auction_date',
        store=False)

    @api.depends('auction_id', 'auction_id.sale_date_begin')
    def _compute_has_past_auction_date(self):
        today = fields.Date.today()
        for contract in self:
            contract.has_past_auction_date = (
                contract.auction_id and 
                contract.auction_id.sale_date_begin and 
                contract.auction_id.sale_date_begin.date() < today
            )

    def action_create_option_contract(self):
        """Duplicate the current contract and link it as an option"""
        self.ensure_one()
        
        default = {
            'contract_id': _('New'),
            'state': 'draft',
            'option_on_contract': True,
            'delivery_date_start': self.delivery_date_start,
            'delivery_date_end': self.delivery_date_end,
            'auction_id': self.auction_id.id if self.auction_id else False,
        }
        
        new_record = self.copy(default)
        
        all_options = self.option_contract_ids | self       
        all_option_ids = all_options.ids + [new_record.id]
        
        for option in all_options:
            option.option_contract_ids = [(6, 0, [id for id in all_option_ids if id != option.id])]
        
        new_record.option_contract_ids = [(6, 0, all_options.ids)]
        
        return True
    
    def go_to_contract(self):
        """Redirect to the newly created contract"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'consignment.contract',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    catalog_changes_ids = fields.One2many('catalog.change', 
                                          'contract_id', 
                                          string='Catalog Changes',
                                          domain=[('catalog_change', '=', 'True')])
    changes_ids = fields.One2many('catalog.change', 
                                          'contract_id', 
                                          string='Changes',
                                          domain=[('catalog_change', '!=', 'True')])
    
    has_catalog_changes = fields.Boolean(compute='_compute_has_catalog_changes', store=False)
    catalog_deadline_passed = fields.Boolean(compute='_compute_catalog_deadline_passed', store=False)
    catalog_change = fields.Boolean(compute='_compute_catalog_change', store=False, help='True if contract has any catalog changes')

    @api.depends('catalog_changes_ids', 'catalog_changes_ids.state')
    def _compute_catalog_change(self):
        """Compute if contract has any catalog changes"""
        for contract in self:
            contract.catalog_change = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.state in ['pending', 'approved']
            ))

    def has_field_catalog_change(self, field_names):
        """Check if specific field(s) have catalog changes
        
        Args:
            field_names: String or list of field names to check
            
        Returns:
            bool: True if any of the specified fields have catalog changes
        """
        if isinstance(field_names, str):
            field_names = [field_names]
        
        return bool(self.catalog_changes_ids.filtered(
            lambda c: c.field_name in field_names and c.state in ['pending', 'approved']
        ))

    @api.depends('auction_id', 'auction_id.catalog_deadline', 'auction_id.is_public')
    def _compute_catalog_deadline_passed(self):
        for contract in self:
            contract.catalog_deadline_passed = (
                contract.auction_id and 
                contract.auction_id.catalog_deadline and 
                contract.auction_id.catalog_deadline < fields.Date.today() and
                contract.auction_id.is_public
            )

    @api.depends('catalog_changes_ids', 'catalog_changes_ids.state')
    def _compute_has_catalog_changes(self):
        for contract in self:
            contract.has_catalog_changes = bool(contract.catalog_changes_ids.filtered(
                lambda c: c.state in ['draft', 'pending', 'approved']
            ))


    def write(self, vals):
        user_partner = self.env.user.partner_id
        is_admin = 'Admin' in user_partner.contact_type_ids.mapped('name')

        def _create_change_log(catalog_change=True, vals=None, record=None):
            to_remove = []
            for field_name, new_value in vals.items():
                if field_name in record._fields and field_name not in IGNORED_FIELDS:
                    old_value = record[field_name]
                    if old_value != new_value:
                        change = self.env['catalog.change'].create({
                            'contract_id': record.id,
                            'field_name': field_name,
                            'old_value': str(old_value),
                            'new_value': str(new_value),
                            'state': 'approved' if is_admin else 'pending',
                            'catalog_change': catalog_change,
                        })
                        if is_admin:
                            change.write({
                                'approved_by': self.env.user.id,
                                'approved_date': fields.Datetime.now()
                            })
                        else:
                            to_remove.append(field_name)
            
            return to_remove

        for record in self:
            to_remove = []
            if record.catalog_deadline_passed:
                if self.env.context.get('from_catalog_change'):
                    return super().write(vals)
                    
                to_remove = _create_change_log(catalog_change=True, vals=vals, record=record)
                
            if not record.catalog_deadline_passed and record.state in ['approved', 'ready_for_sale','changed']:
                if self.env.context.get('from_catalog_change'):
                    return super().write(vals)
                    
                to_remove = _create_change_log(catalog_change=False, vals=vals, record=record)
                
                
            for field in to_remove:
                vals.pop(field, None)
            
            if not vals:
                return True
                
        return super().write(vals)

    @api.constrains('slide_type')
    def _check_slide_type(self):
        for record in self:
            if record.slide_type and len(record.slide_type) > 1:
                raise ValidationError(_("A contract can only have one slide type."))

