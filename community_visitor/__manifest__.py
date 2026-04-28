{
    'name': '社區訪客管理',
    'version': '18.0.1.1.0',
    'category': 'Community',
    'summary': '訪客登記、住戶確認、預約通行管理',
    'description': """
        社區訪客管理模組，提供：
        - 臨時訪客登記與住戶確認放行
        - 預約訪客通行（QR Code + 驗證碼）
        - 常態授權訪客管理
        - 黑名單管理
        - 訪客證借還管理
        - 來訪目的分類管理
        - 住戶 Portal 管理介面
    """,
    'author': 'WoowTech',
    'depends': ['community_base', 'mail', 'portal'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/sequences.xml',
        'data/mail_templates.xml',
        'data/ir_cron.xml',
        'views/community_visit_purpose_views.xml',
        'views/community_visitor_badge_views.xml',
        'views/community_visitor_views.xml',
        'views/community_visit_views.xml',
        'views/community_appointment_views.xml',
        'views/portal_visitor_templates.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'community_visitor/static/src/js/visitor_bus.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
