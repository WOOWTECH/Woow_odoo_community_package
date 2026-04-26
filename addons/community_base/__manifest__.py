{
    'name': '社區基礎管理',
    'version': '18.0.1.0.0',
    'category': 'Community',
    'summary': '社區基礎資料：戶號、管理室',
    'description': """
        社區管理系統的基礎模組，提供：
        - 戶號（community.unit）管理
        - 管理室（community.office）管理
        - 住戶與戶號的多對多關聯
    """,
    'author': 'WoowTech',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/community_office_views.xml',
        'views/community_unit_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
