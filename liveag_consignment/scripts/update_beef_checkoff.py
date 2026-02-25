# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

def update_beef_checkoff_data(env):
    """
    Update existing states with beef checkoff data from the beef.checkoff model.
    This script can be run manually to update states after importing new beef checkoff data.
    """
    print("Starting beef checkoff data update...")
    
    # Get all US states
    us_country = env['res.country'].search([('code', '=', 'US')])
    if not us_country:
        print("Error: US country not found")
        return False
        
    states = env['res.country.state'].search([('country_id', '=', us_country.id)])
    if not states:
        print("Error: No US states found")
        return False
    
    # Get all beef checkoff records
    checkoff_records = env['beef.checkoff'].search([])
    if not checkoff_records:
        print("Error: No beef checkoff records found")
        return False
    
    # Create a mapping of state codes to checkoff records
    checkoff_map = {record.state_code: record for record in checkoff_records}
    
    # Update each state with its corresponding checkoff data
    updated_count = 0
    for state in states:
        if not state.code:
            continue
            
        checkoff = checkoff_map.get(state.code)
        if not checkoff:
            continue
            
        state.write({
            'national_beef_checkoff': checkoff.national_beef_checkoff,
            'state_beef_checkoff': checkoff.state_beef_checkoff,
            'other_state_fees': checkoff.other_state_fees,
            'fee_description': checkoff.description,
            'brand_inspector_national': checkoff.brand_inspector_national,
            'brand_inspector_state': checkoff.brand_inspector_state,
        })
        updated_count += 1
    
    print(f"Updated {updated_count} states with beef checkoff data")
    return True

def run_update(env):
    """Run the update script"""
    return update_beef_checkoff_data(env)