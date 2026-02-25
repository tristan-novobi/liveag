# -*- coding: utf-8 -*-
# Helper serializers and utilities ported from muk_rest.tools.liveag

from urllib.parse import urlencode
from urllib.parse import urlparse, urlunparse, parse_qs

def serialize_address(address):
	return {
		'street': address.street or None,
		'street2': address.street2 or None,
		'city': address.city or None,
		'state': address.state_id.code if address.state_id else None,
		'zip': address.zip or None,
		'country': address.country_id.code if address.country_id else None,
	}

def serialize_reps_for_contract(contract):
	reps = list(contract.rep_ids)
	reps.sort(key=lambda x: x.consigning_rep or x.percentage_commission, reverse=True)
	rep_info = []
	for rep in reps:
		rep_info.append({
			'name': rep.rep_id.name,
			'phone': contract.format_phone(rep.rep_id.phone) or None,
		})
	return rep_info

def basic_reps_for_contract(contract):
	reps = list(contract.rep_ids)
	reps.sort(key=lambda x: x.consigning_rep or x.percentage_commission, reverse=True)
	rep_names = []
	for rep in reps:
		rep_names.append(rep.rep_id.name)
	return rep_names

def serialize_contract_preview(contract):
	delivery_range = contract.format_delivery_date_range(contract.delivery_date_start, contract.delivery_date_end)
	auction = {
		'id': contract.auction_id.id,
		'name': contract.auction_id.name,
		'sale_date_begin': contract.auction_id.sale_date_begin or None,
		'sale_date_est_end': contract.auction_id.sale_date_est_end or None,
	} if contract.auction_id else None
	return {
		'id': contract.id,
		'created_on': contract.create_date,
		'contract_id': contract.id,
		'lot_number': contract.lot_number or None,
		'video_link': contract.video_link or None,
		'has_catalog_change': contract.has_catalog_changes,
		'sale_type': contract.contract_type.name if contract.contract_type else None,
		'status': dict(contract._fields['state'].selection).get(contract.state, 'Unknown').lower(),
		'auction': auction,
		'contract_type': {
			'value': contract.contract_type.name,
			'catalog_change': contract.has_field_catalog_change('contract_type'),
		} if contract.contract_type else None,
		'seller': {'id': contract.seller_id.id, 'name': contract.seller_id.name} if contract.seller_id else None,
		'slide': {
			'value': {
				'type': contract.slide_type.label,
				'over': contract.slide_over or None,
				'under': contract.slide_under or None,
				'both': contract.slide_both or None,
				'description': contract.short_slide_description or None
			},
			'catalog_change': contract.has_field_catalog_change(['slide_type', 'slide_over', 'slide_under', 'slide_both']),
		} if contract.slide_type else None,
		'location': {
			'value': contract.location_description or None,
			'catalog_change': contract.has_field_catalog_change(['nearest_town', 'state_of_nearest_town', 'direction_to_nearest_town', 'distance_to_nearest_town', 'buyer_fob']),
		} if contract.nearest_town and contract.state_of_nearest_town else None,
		'primary_rep': {'name':contract.primary_rep.name, 'phone':contract.format_phone(contract.primary_rep.phone) or None} if contract.primary_rep else None,
		'delivery_range': {'value': delivery_range, 'catalog_change': contract.has_field_catalog_change(['delivery_date_start', 'delivery_date_end'])},
		'delivery_dates': {
			'value': {
				'start': contract.delivery_date_start,
				'end': contract.delivery_date_end,
			},
			'catalog_change': contract.has_field_catalog_change(['delivery_date_start', 'delivery_date_end']),
		},
		'program_icons': [{'url':program.image_url, 'name':program.name} for program in contract.program_icon_ids] if contract.program_icon_ids else None,
		'head1': {
			'value': contract.head1,
			'catalog_change': contract.has_field_catalog_change('head1'),
		} if contract.head1 else None,
		'kind1': {
			'value': contract.kind1.name,
			'catalog_change': contract.has_field_catalog_change('kind1'),
		} if contract.kind1 else None,
		'weight1': {
			'value': contract.weight1,
			'catalog_change': contract.has_field_catalog_change('weight1'),
		} if contract.weight1 else None,
		'head2': {
			'value': contract.head2,
			'catalog_change': contract.has_field_catalog_change('head2'),
		} if contract.head2 else None,
		'kind2': {
			'value': contract.kind2.name,
			'catalog_change': contract.has_field_catalog_change('kind2'),
		} if contract.kind2 else None,
		'weight2': {
			'value': contract.weight2,
			'catalog_change': contract.has_field_catalog_change('weight2'),
		} if contract.weight2 else None,
		'sell_by_head': {
			'value': contract.sell_by_head,
			'catalog_change': contract.has_field_catalog_change('sell_by_head'),
		},
		'price_back': {
			'value': contract.price_back,
			'catalog_change': contract.has_field_catalog_change('price_back'),
		} if contract.price_back else None,
		'breed_type': {
			'value': contract.breed_type,
			'catalog_change': contract.has_field_catalog_change('breed_type'),
		} if contract.breed_type else None,
	}

def serialize_contract_detailed(contract):
	return {
		**serialize_contract_preview(contract),
		'reps': serialize_reps_for_contract(contract),
		'weight_stop': {
			'value': contract.weight_stop.name,
			'catalog_change': contract.has_field_catalog_change('weight_stop'),
		} if contract.weight_stop else None,
		'all_black_hided': {
			'value': contract.all_black_hided,
			'catalog_change': contract.has_field_catalog_change('all_black_hided'),
		},
		'frame_size': {
			'value': contract.frame_size.name,
			'catalog_change': contract.has_field_catalog_change('frame_size'),
		} if contract.frame_size else None,
		'flesh_type': {
			'value': contract.flesh_type.name,
			'catalog_change': contract.has_field_catalog_change('flesh_type'),
		} if contract.flesh_type else None,
		'weight_variance': {
			'value': contract.weight_variance.name,
			'catalog_change': contract.has_field_catalog_change('weight_variance'),
		} if contract.weight_variance else None,
		'horns': {
			'value': contract.horns.name,
			'catalog_change': contract.has_field_catalog_change('horns'),
		} if contract.horns else None,
		'feeding_program': {
			'value': contract.feeding_program,
			'catalog_change': contract.has_field_catalog_change('feeding_program'),
		} if contract.feeding_program else None,
		'implanted_type': {
			'value': contract.implanted_type.name,
			'catalog_change': contract.has_field_catalog_change('implanted_type'),
		} if contract.implanted_type else None,
		'implanted_date': {
			'value': {
				'month': contract.implanted_month,
				'year': contract.implanted_year,
			},
			'catalog_change': contract.has_field_catalog_change(['implanted_month', 'implanted_year', 'implanted_date']),
		} if contract.implanted_date else None,
		'castration': {
			'value': contract.castration.name,
			'catalog_change': contract.has_field_catalog_change('castration'),
		} if contract.castration else None,
		'bangs_vacc': {
			'value': contract.bangs_vaccinated.name,
			'catalog_change': contract.has_field_catalog_change('bangs_vaccinated'),
		} if contract.bangs_vaccinated else None,
		'origin': {
			'value': f"{contract.origin.name} {contract.origin_description}" if contract.origin_description else f"{contract.origin.name}",
			'catalog_change': contract.has_field_catalog_change('origin'),
		} if contract.origin else None,
		'origin_description': {
			'value': contract.origin_description,
			'catalog_change': contract.has_field_catalog_change('origin_description'),
		} if contract.origin_description else None,
		'states_of_origin': {
			'value': [state.code for state in contract.state_of_origin],
			'catalog_change': contract.has_field_catalog_change('state_of_origin'),
		} if contract.state_of_origin else None,
		'country': {
			'value': contract.country_id.code,
			'catalog_change': contract.has_field_catalog_change('country_id'),
		} if contract.country_id else None,
		'comments': {
			'value': contract.full_comments,
			'catalog_change': contract.has_field_catalog_change('full_comments'),
		} if contract.full_comments else None,
	}

def serialize_contract_editable(contract):
	return {
		'id': contract.id,
		'contract_id': contract.id,
		'status': dict(contract._fields['state'].selection).get(contract.state, 'Unknown').lower(),
		'sale_type': contract.sale_type.id if contract.sale_type else None,
		'auction_id': contract.auction_id.id if contract.auction_id else None,
		'contract_type': contract.contract_type.id if contract.contract_type else None,
		'seller_id': contract.seller_id.id if contract.seller_id else None,
		'lien_holder_id': contract.lien_holder_id.id if contract.lien_holder_id else None,
		'payment_info': contract.payment_info.id if contract.payment_info else None,
		'rep_ids': [
			{
				'rep_id': rep['rep_id'][0],
				'percentage_commission': rep['percentage_commission']
			}
			for rep in contract.rep_ids.read(['rep_id', 'percentage_commission'])
		] if contract.rep_ids else None,
		'head1': contract.head1 if contract.head1 else None,
		'kind1': contract.kind1.id if contract.kind1 else None,
		'weight1': contract.weight1 if contract.weight1 else None,
		'head2': contract.head2 if contract.head2 else None,
		'kind2': contract.kind2.id if contract.kind2 else None,
		'weight2': contract.weight2 if contract.weight2 else None,
		'sell_by_head': contract.sell_by_head,
		'price_back': contract.price_back if contract.price_back else None,
		'slide_type': contract.slide_type.id if contract.slide_type else None,
		'slide_over': contract.slide_over if contract.slide_over else None,
		'slide_under': contract.slide_under if contract.slide_under else None,
		'weight_stop': contract.weight_stop.id if contract.weight_stop else None,
		'all_black_hided': contract.all_black_hided,
		'breed_type': contract.breed_type if contract.breed_type else None,
		'frame_size': contract.frame_size.id if contract.frame_size else None,
		'flesh_type': contract.flesh_type.id if contract.flesh_type else None,
		'weight_variance': contract.weight_variance.id if contract.weight_variance else None,
		'horns': contract.horns.id if contract.horns else None,
		'feeding_program': contract.feeding_program or None,
		'implanted_type': contract.implanted_type.id if contract.implanted_type else None,
		'implanted_month': contract.implanted_month or None,
		'implanted_year': contract.implanted_year or None,
		'implanted_date': contract.implanted_date or None,
		'castration': contract.castration.id if contract.castration else None,
		'bangs_vaccinated': contract.bangs_vaccinated.id if contract.bangs_vaccinated else None,
		'origin': contract.origin.id if contract.origin else None,
		'states_of_origin': contract.state_of_origin or None,
		'country_id': contract.country_id.id if contract.country_id else None,
		'asking_price': contract.asking_price or None,
		'comments': contract.comments or None,
		'vac_program': contract.vac_program.id if contract.vac_program else None,
		'special_section': contract.special_section.id if contract.special_section else None,
		'genetic_merit_program': contract.genetic_merit_program.id if contract.genetic_merit_program else None,
		'value_added_nutrition': contract.value_added_nutrition.id if contract.value_added_nutrition else None,
		'premium_genetics_program': contract.premium_genetics_program.id if contract.premium_genetics_program else None,
		'pi_free': contract.pi_free,
		'tag_840': contract.tag_840,
		'vaccination_desc': contract.vaccination_desc or None,
		'source_age_program': contract.source_age_program.id if contract.source_age_program else None,
		'gap_program': contract.gap_program.id if contract.gap_program else None,
		'natural': contract.natural,
		'nhtc': contract.nhtc,
		'verified_natural': contract.verified_natural,
		'bqa_certified': contract.bqa_certified,
		'beef_care': contract.beef_care,
		'cfp': contract.cfp,
		'verified_grassfed': contract.verified_grassfed,
		'organic': contract.organic,
		'non_gmo': contract.non_gmo,
		'current_fob': contract.current_fob.id if contract.current_fob else None,
		'distance_to_nearest_town': contract.distance_to_nearest_town or None,
		'direction_to_nearest_town': contract.direction_to_nearest_town or None,
		'nearest_town': contract.nearest_town or None,
		'state_of_nearest_town': contract.state_of_nearest_town.id if contract.state_of_nearest_town else None,
		'distance_to_nearest_city': contract.distance_to_nearest_city or None,
		'direction_to_nearest_city': contract.direction_to_nearest_city or None,
		'nearest_city': contract.nearest_city or None,
		'state_of_nearest_city': contract.state_of_nearest_city.id if contract.state_of_nearest_city else None,
		'region_id': contract.region_id.id if contract.region_id else None,
		'latitude': contract.latitude or None,
		'longitude': contract.longitude or None,
		'buyer_receives_fob': contract.buyer_receives_fob.id if contract.buyer_receives_fob else None,
		'whose_option': contract.whose_option.id if contract.whose_option else None,
		'delivery_date_start': contract.delivery_date_start or None,
		'delivery_date_end': contract.delivery_date_end or None,
		'shrink_percentage': contract.shrink_percentage or None,
		'freight_adjustment_amount': contract.freight_adjustment_amount or None,
		'oversize_load': contract.oversize_load,
		'seller_need_part_payment': contract.seller_need_part_payment,
		'weighing_conditions': contract.weighing_conditions or None,
		'load_option': contract.load_option or None,
		'option_contract_ids': [
				c.id for c in contract.option_contract_ids
			],
		'office_notes': contract.office_notes or None,
		'addendum_ids': [
			{
				'id': addendum.id,
				'seller_id': addendum.seller_id.id,
				'head_count': addendum.head_count,
				'percentage': addendum.percentage or 100,
				'lien_holder_id': addendum.lien_holder_id.id if addendum.lien_holder_id else None,
				'part_payment': addendum.part_payment or 0
			} for addendum in contract.addendum_ids
		] if contract.addendum_ids else None,
		'seller_part_payment': contract.seller_part_payment or 0,
	}

def serialize_contact_basic_info(contact):
	# portal_user = None
	# if contact.user_ids:
	# 	portal_user = contact.user_ids
	# 	if portal_user:
	# 		portal_user = portal_user[0].read()
	return {
		'id': contact.id,
		'company_type': contact.company_type,
		'company': contact.commercial_company_name or None,
		'contact_name': contact.contact_name,
		'email': contact.email,
		'phone': contact.phone or None,
		'address': serialize_address(contact),
		'roles': [contact_type.name.lower() for contact_type in contact.contact_type_ids],
		'name': contact.name or None,
		# 'portal_user': portal_user,
	}

def serialize_contact_buyer(contact):
	bank_info_options = []
	for bank_info in contact.child_ids:
		if bank_info.type == 'bank':
			bank_info_options.append({
				'name': bank_info.name,
				'contact_name': bank_info.contact_name,
				'phone': bank_info.phone,
				'email': bank_info.email,
				'address': serialize_address(bank_info),
			})
	return {
		'buyer_number': [buyer_number.name for buyer_number in contact.buyer_number_ids],
		'verified_buyer': contact.verified_buyer,
		'verified_date': contact.verified_date,
		'bank': bank_info_options,
	}

def serialize_contact_seller(contact):
	default_reps = None
	if contact.rep_ids:
		default_reps = []
		for rep in contact.rep_ids:
			default_reps.append({
				'percentage_commission': rep.percentage_commission,
				'id': rep.rep_id.id,
				'name': rep.rep_id.rep_name,
			})
	default_lien_holder = None
	if contact.default_lien_holder_id:
		lien_holder = contact.default_lien_holder_id
		default_lien_holder = {
			'id': lien_holder.id,
			'name': lien_holder.name,
			'city': lien_holder.city,
			'state': lien_holder.state_id.code if lien_holder.state_id else None,
			'zip': lien_holder.zip,
			'country': lien_holder.country_id.code if lien_holder.country_id else None,
		}
	default_payment_info = None
	if contact.default_payment_info_id:
		payment_info = contact.default_payment_info_id
		default_payment_info = {
			'id': payment_info.id,
			'name': payment_info.name,
			'street': payment_info.street,
			'street2': payment_info.street2 if payment_info.street2 else None,
			'city': payment_info.city,
			'state': payment_info.state_id.code if payment_info.state_id else None,
			'zip': payment_info.zip,
			'country': payment_info.country_id.code if payment_info.country_id else None,
		}
	return {
		'default_lien_holder': default_lien_holder or None,
		'affidavit_verified': contact.affidavit_verified or None,
		'has_master_agreement': contact.has_master_agreement or None,
		'default_payment_info': default_payment_info or None,
		'reps': default_reps
	}

def serialize_contact_rep(contact):
	return {
		'rep_number': 'test of rep serialization',
	}
