import json
import logging
from typing import Dict, List, Optional, Set, Any

from odoo import http
from odoo.http import request
from odoo.models import Model

from odoo.addons.liveag_muk_rest.tools.http import build_route
from odoo.addons.liveag_muk_rest import core
from odoo.addons.liveag_api.controllers.liveag import LiveAgController

_logger = logging.getLogger(__name__)

class LiveAgContractsController(LiveAgController):
    """Controller for managing LiveAg contract-related endpoints."""
    
    CONSIGNMENT_GROUPS = {
        'Sales / Consignment / Buyer', 'Consignment / Buyer',
        'Sales / Consignment / Seller', 'Consignment / Seller',
        'Sales / Consignment / Rep', 'Consignment / Rep',
        'Consignment / Administrator'
    }
    
    REP_GROUPS = {'Sales / Consignment / Rep', 'Consignment / Rep'}
    
    def _get_user_group_names(self, groups: Model) -> Set[str]:
        """Extract all group names including full names.
        
        Args:
            groups: Record set of groups
            
        Returns:
            Set of group names
        """
        group_names = set()
        for group in groups:
            group_names.add(group.name)
            if group.full_name:
                group_names.add(group.full_name)
        return group_names

    def _get_user_and_partner(self, clerk_user_id: str) -> tuple[Optional[Model], Optional[Model]]:
        """Get user and partner records from clerk_user_id.
        
        Args:
            clerk_user_id: Unique Clerk user identifier
            
        Returns:
            Tuple of (partner, user) records
        """
        if not clerk_user_id:
            return None, None
            
        partner = request.env['res.partner'].sudo().search(
            [('clerk_user_id', '=', clerk_user_id)], 
            limit=1
        )
        user = partner.user_ids[0] if partner and partner.user_ids else None
        return partner, user

    def _make_error_response(self, error: str, status: bool = False) -> Dict:
        """Create consistent error response format.
        
        Args:
            error: Error message
            status: Success status
            
        Returns:
            Error response dictionary
        """
        return request.make_json_response({
            'success': status,
            'error': error
        })

    @core.http.rest_route(
        routes=build_route('/users/assigned-sellers'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='Get Rep Assigned Sellers',
            description='Get list of sellers assigned to a rep based on their Clerk ID.',
        ),
    )
    def get_assigned_sellers(self, **kw) -> Dict:
        """Get list of sellers assigned to a rep based on their Clerk ID."""
        try:
            vals = request.params.get('vals')
            if not vals:
                return self._make_error_response('Missing required parameter: vals')

            try:
                data = json.loads(vals)
                clerk_user_id = data.get('clerk_user_id')
                
                partner, user = self._get_user_and_partner(clerk_user_id)
                if not user:
                    return self._make_error_response('User not found')
                
                group_names = self._get_user_group_names(user.group_ids)
                if not self.REP_GROUPS.intersection(group_names):
                    return self._make_error_response('User does not have Rep role')
                
                sellers = self._get_rep_assigned_sellers(partner, user)
                return request.make_json_response({
                    'success': True,
                    'sellers': list(sellers.values())
                })
                
            except json.JSONDecodeError:
                return self._make_error_response('Invalid JSON format')
                
        except Exception as e:
            _logger.error("Error getting assigned sellers: %s", str(e))
            return self._make_error_response(str(e))

    def _get_rep_assigned_sellers(self, partner: Model, user: Model) -> Dict[int, Dict]:
        """Get sellers assigned to a rep from contracts.
        
        Args:
            partner: Rep partner record
            user: Rep user record
            
        Returns:
            Dictionary of seller details
        """
        Contract = request.env['consignment.contract'].with_user(user)
        contracts = Contract.search([
            '|',
            ('rep_ids.rep_id', '=', partner.id),
            '|',
            ('create_uid', '=', user.id),
            ('create_uid.partner_id', '=', partner.id)
        ])
        
        sellers = {}
        for contract in contracts:
            for rep in contract.rep_ids:
                if rep.rep_id.id == partner.id and contract.seller_id:
                    seller = contract.sudo().seller_id
                    if seller.id not in sellers:
                        sellers[seller.id] = self._prepare_seller_data(seller, rep)
                        
        return sellers

    def _prepare_seller_data(self, seller: Model, rep: Model) -> Dict:
        """Prepare seller data for response.
        
        Args:
            seller: Seller partner record
            rep: Rep record with commission data
            
        Returns:
            Seller data dictionary matching TypeScript Contact interface
        """
        address = None
        if any([seller.street, seller.city, seller.state_id, seller.zip, seller.country_id]):
            address = {
                'street': seller.street or '',
                'city': seller.city or '',
                'state': seller.state_id.code if seller.state_id else '',
                'zip': seller.zip or '',
                'country': seller.country_id.code if seller.country_id else ''
            }
            
        return {
            'id': seller.id,
            'name': seller.name,
            'company_type': seller.company_type or 'person',
            'contact_name': seller.child_ids[0].name if seller.child_ids else None,
            'email': seller.email,
            'phone': seller.phone or None,
            'address': address,
            'types': [cat.name for cat in seller.category_id] if seller.category_id else []
        }

    @core.http.rest_route(
        routes=build_route('/users/contracts'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='Get User Contracts',
            description='Get contracts for a user based on their Clerk ID and role permissions.',
        ),
    )
    def get_user_contracts(self, **kw) -> Dict:
        """Get contracts for a user based on their Clerk ID and role permissions."""
        try:
            vals = request.params.get('vals')
            if not vals:
                return self._make_error_response('Missing required parameter: vals')

            page = int(request.params.get('page', 1))
            per_page = int(request.params.get('per_page', 25))
            if page < 1:
                return self._make_error_response('Page must be >= 1')
            if per_page < 1 or per_page > 100:
                return self._make_error_response('Per page must be between 1 and 100')

            try:
                data = json.loads(vals)
                clerk_user_id = data.get('clerk_user_id')
                
                partner, user = self._get_user_and_partner(clerk_user_id)
                if not user:
                    return self._make_error_response('User not found')
                
                result = self._get_user_accessible_contracts(partner, user, page, per_page)
                return request.make_json_response({
                    'success': True,
                    'contracts': result['contracts'],
                    'pagination': result['pagination']
                })
                
            except json.JSONDecodeError:
                return self._make_error_response('Invalid JSON format')
            except ValueError:
                return self._make_error_response('Invalid page or per_page parameter')
                
        except Exception as e:
            _logger.error("Error getting user contracts: %s", str(e))
            return self._make_error_response(str(e))

    def _get_user_accessible_contracts(self, partner: Model, user: Model, page: int = 1, per_page: int = 25) -> Dict:
        """Get paginated contracts accessible to the user based on their roles.
        
        Args:
            partner: User partner record
            user: User record
            page: Page number (1-based)
            per_page: Number of contracts per page
            
        Returns:
            Dictionary containing contracts and pagination metadata
        """
        group_names = self._get_user_group_names(user.group_ids)
        if not group_names.intersection(self.CONSIGNMENT_GROUPS):
            return {
                'contracts': [],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': 0,
                    'total_pages': 0
                }
            }
            
        # Use sudo() to check rules to avoid access rights issues
        rules = request.env['ir.rule'].sudo().search([('model_id.model', '=', 'consignment.contract')])
        
        user_groups = set(user.group_ids.ids)
        rule_groups = {group.id for rule in rules for group in rule.groups}
        
        if not user_groups.intersection(rule_groups):
            _logger.info("User does not have any required groups from record rules")
            return {
                'contracts': [],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': 0,
                    'total_pages': 0
                }
            }
        
        Contract = request.env['consignment.contract'].with_user(user)
        domain = self._get_contract_domain(partner, user.group_ids, user)
        
        total_count = Contract.search_count(domain)
        offset = (page - 1) * per_page
        contracts = Contract.search(domain, limit=per_page, offset=offset)
        total_pages = (total_count + per_page - 1) // per_page
        
        _logger.info("Contracts user can access: %d (page %d of %d)", len(contracts), page, total_pages)
        
        return {
            'contracts': [self._prepare_contract_data(c) for c in contracts],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages
            }
        }

    def _get_contract_domain(self, partner: Model, groups: Model, user: Model = None) -> List:
        """Determine contract domain based on user groups.
        
        Args:
            partner: User partner record
            groups: User groups recordset
            user: User record
            
        Returns:
            Domain list for contract search
        """
        group_names = self._get_user_group_names(groups)
        _logger.info("User groups: %s", list(group_names))
        
        if not group_names.intersection(self.CONSIGNMENT_GROUPS):
            return [('id', '=', False)]
            
        domain = []
        if {'Sales / Consignment / Buyer', 'Consignment / Buyer'}.intersection(group_names):
            domain.append(('buyer_id', '=', partner.id))
        if {'Sales / Consignment / Seller', 'Consignment / Seller'}.intersection(group_names):
            domain.append(('seller_id', '=', partner.id))
        if self.REP_GROUPS.intersection(group_names):
            _logger.info("Building Rep domain for partner_id: %d", partner.id)
            rep_domain = [
                '|',
                ('rep_ids.rep_id', '=', partner.id),
                '|',
                ('create_uid', '=', user.id),
                ('create_uid.partner_id', '=', partner.id)
            ]
            _logger.info("Rep domain: %s", rep_domain)
            domain.extend(rep_domain)
            
        return domain if domain else [('id', '=', False)]
        
    def _prepare_contract_data(self, contract: Model) -> Dict[str, Any]:
        """Prepare contract data for response.
        
        Args:
            contract: Contract record
            
        Returns:
            Contract data dictionary
        """
        try:
            contract_sudo = contract.sudo()
            return {
                'id': contract.id,
                'contract_id': contract.contract_id,
                'lot_number': contract.lot_number,
                'sale_type': contract_sudo.sale_type.name if contract_sudo.sale_type else None,
                'video_link': contract.video_link,
                'status': contract.state,
                'auction': self._prepare_auction_data(contract_sudo),
                'delivery_dates': {
                    'start': str(contract.delivery_date_start) if contract.delivery_date_start else None,
                    'end': str(contract.delivery_date_end) if contract.delivery_date_end else None
                },
                'contract_type': contract_sudo.contract_type.name if contract_sudo.contract_type else None,
                'seller': {
                    'id': contract_sudo.seller_id.id,
                    'name': contract_sudo.seller_id.name
                },
                'location': self._format_contract_location(contract_sudo),
                'reps': self._prepare_reps_data(contract_sudo),
                'head1': contract.head1 or 0,
                'kind1': contract_sudo.kind1.name if contract_sudo.kind1 else None,
                'weight1': contract.weight1 or 0,
                'head2': contract.head2 or 0,
                'kind2': contract_sudo.kind2.name if contract_sudo.kind2 else None,
                'weight2': contract.weight2 or 0,
                'sell_by_head': contract.sell_by_head,
                'price_back': contract.price_back or 0,
                'breed_type': contract.breed_type or ''
            }
        except Exception as e:
            _logger.error("Error preparing contract data: %s", str(e))
            return {
                'id': contract.id,
                'contract_id': contract.contract_id,
                'status': contract.state
            }

    def _prepare_auction_data(self, contract: Model) -> Dict:
        """Prepare auction data for contract response.
        
        Args:
            contract: Contract record
            
        Returns:
            Auction data dictionary
        """
        return {
            'id': contract.auction_id.id,
            'name': contract.auction_id.name,
            'sale_date_begin': str(contract.auction_id.sale_date_begin),
            'sale_date_est_end': str(contract.auction_id.sale_date_begin)
        }

    def _format_contract_location(self, contract: Model) -> str:
        """Format contract location string.
        
        Args:
            contract: Contract record
            
        Returns:
            Formatted location string
        """
        if not contract.nearest_town:
            return ""
        state_code = contract.state_of_nearest_town.code if contract.state_of_nearest_town else ''
        return f"{contract.nearest_town}, {state_code}"

    def _prepare_reps_data(self, contract: Model) -> Optional[List[Dict]]:
        """Prepare representatives data for contract response.
        
        Args:
            contract: Contract record
            
        Returns:
            List of rep data dictionaries or None
        """
        if not contract.rep_ids:
            return None
        return [{
            'name': rep.rep_id.name,
            'percentage_commission': rep.percentage_commission
        } for rep in contract.rep_ids]

    @core.http.rest_route(
        routes=build_route(['/contracts/<int:contract_id>/duplicate']),
        methods=['PUT'],
        protected=True,
        docs=dict(
            tags=['Contracts'],
            summary='Duplicate Contract',
            description='''Create a duplicate copy of an existing contract.
            
            The duplicated contract will:
            - Get a new contract ID
            - Be set to draft state
            - Have empty reps list
            - Have new addendums with 0 head count
            
            Fields that are NOT copied (set to empty/default):
            - contract_id (new ID generated)
            - state (set to draft)
            - consignment_id
            - lot_number
            - sale_order
            - video_link
            - is_supplemental
            - asking_price
            - sold_price
            - sold_date
            - is_merged_contract
            - is_split_contract
            - merged_contract_id
            - source_contract_id
            - activity_log_ids
            - created_loads
            
            All other fields (including but not limited to):
            - sale_type
            - auction_id
            - seller_id
            - buyer_id
            - head/breed information
            - location information
            - delivery information
            - program information
            Are copied with their original values.
            
            For addendums:
            - Original addendum structure is preserved
            - seller_id, lien_holder_id, percentage, and active status are copied
            - head_count is set to 0
            ''',
        ),
    )
    def duplicate_contract(self, contract_id: int, **kw) -> Dict:
        """Create a duplicate copy of an existing contract."""
        try:
            Contract = request.env['consignment.contract']
            contract = Contract.browse(contract_id)
            if not contract.exists():
                return self._make_error_response('Contract not found')

            new_contract = contract.copy()
            
            return request.make_json_response({
                'success': True,
                'contract': self._prepare_contract_data(new_contract)
            })

        except Exception as e:
            _logger.error("Error duplicating contract: %s", str(e))
            return self._make_error_response(str(e))
