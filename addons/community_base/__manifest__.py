{
    'name': '社區基礎管理',
    'version': '18.0.2.0.0',
    'category': 'Community',
    'summary': '社區基礎資料：戶號、管理室、公布欄、意見反映',
    'description': """
        社區管理系統的基礎模組，提供：
        - 戶號（community.unit）管理
        - 管理室（community.office）管理
        - 住戶與戶號的多對多關聯
        - 社區公布欄（community.announcement）
        - 住戶意見反映（community.feedback）
    """,
    'author': 'WoowTech',
    'depends': ['base', 'mail', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/sequences.xml',
        'views/community_office_views.xml',
        'views/community_unit_views.xml',
        'views/res_partner_views.xml',
        'views/community_announcement_category_views.xml',
        'views/community_announcement_views.xml',
        'views/community_feedback_category_views.xml',
        'views/community_feedback_views.xml',
        'views/portal_templates.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
