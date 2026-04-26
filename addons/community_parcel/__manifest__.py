{
    'name': '社區包裹管理',
    'version': '18.0.1.0.0',
    'category': 'Services',
    'summary': '社區管理室包裹收發與寄放物品管理',
    'description': """
        Community Parcel Management System
        ===================================
        - 包裹收件登記與通知
        - 寄放物品管理
        - 管理室工作台
        - 快速條碼登記精靈
    """,
    'author': 'Woow Tech',
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
