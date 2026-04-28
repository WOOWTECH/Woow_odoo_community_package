{
    'name': '社區包裹管理',
    'version': '18.0.1.0.0',
    'category': 'Community',
    'summary': '包裹收發登記與寄放物品管理',
    'description': """
        社區包裹管理模組，提供：
        - 包裹收件登記與住戶通知（到件通知、逾期提醒）
        - 寄放物品管理（登記、保管、取件）
        - 管理室工作台（今日到件、未取件、逾期一覽）
        - 快速條碼登記精靈
        - 自動逾期排程（7 天未取件自動標記）
    """,
    'author': 'WoowTech',
    'license': 'LGPL-3',
    'depends': ['community_base', 'mail'],
    'data': [
        # Security
        'security/community_parcel_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/sequence_data.xml',
        'data/mail_template_data.xml',
        # Views
        'views/community_parcel_type_views.xml',
        'views/community_storage_type_views.xml',
        'views/community_parcel_views.xml',
        'views/community_storage_views.xml',
        'views/parcel_quick_register_views.xml',
        'views/community_parcel_dashboard.xml',
        'views/menu_views.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
