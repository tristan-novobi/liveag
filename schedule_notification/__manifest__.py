# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'LiveAg: Schedule Notification',
    'summary': 'Send scheduled notifications to users based on predefined criteria.',
    'author': 'Novobi',
    'website': 'https://www.novobi.com/',
    'category': 'Consignment/Consignment',
    'version': '1.0.0',
    'license': 'OPL-1',
    'depends': [
        'base_setup', 
        'mail', 
        'contacts',
        'uom',
        'liveag_consignment',
    ],
    'data': [
        # ============================== DATA =================================
        'data/server_actions.xml',
        # ============================== SECURITY =============================
        # ============================== REPORT ===============================
        # ============================== VIEWS ================================
        'views/sale_auction_views.xml',
        # ============================== WIZARDS ==============================
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
