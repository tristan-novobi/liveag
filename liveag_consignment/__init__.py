# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard
from . import tools

from odoo.tools import convert_file


def import_csv_data(env):
    filenames = ['data/sale.type.csv',
                'data/contract.type.csv',
                'data/kind.list.csv',
                'data/slide.type.csv',
                'data/weight.stop.csv',
                'data/origin.list.csv',
                'data/frame.size.csv',
                'data/flesh.type.csv',
                'data/weight.variance.csv',
                'data/horns.list.csv',
                'data/bangs.vaccinated.csv',
                'data/special.section.csv',
                'data/genetic.merit.csv',
                'data/location.type.csv',
                'data/whose.option.csv',
                'data/implanted.list.csv',
                'data/castration.list.csv',
                'data/third.party.age.csv',
                'data/vac.program.csv',
                'data/res.contact.type.csv',
                'data/res.region.csv',
                'data/beef.checkoff.csv'
            ]
    for filename in filenames:
        convert_file(
            env, 'liveag_consignment',
            filename, None, mode='init', noupdate=True,
            kind='data'
        )

def update_states_with_beef_checkoff(env):
    """Update states with beef checkoff information"""
    # First make sure beef checkoff data is imported
    import_csv_data(env)
    
    # Then update states with the data
    env['res.country.state']._update_from_beef_checkoff()

def post_init(env):
    import_csv_data(env)
    update_states_with_beef_checkoff(env)
