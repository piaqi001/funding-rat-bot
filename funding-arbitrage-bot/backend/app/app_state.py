
"""
应用状态管理模块
"""

# 全局状态字典
app_state = {}


def get_app_state():
    """获取应用状态"""
    return app_state


def set_app_state(key, value):
    """设置应用状态"""
    app_state[key] = value
