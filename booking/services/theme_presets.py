"""7 built-in theme presets for StoreTheme.

Each preset defines color and font overrides.
Keys must match StoreTheme field names.
"""

THEME_PRESETS = {
    'default': {
        'primary_color': '#8c876c',
        'secondary_color': '#f1f0ec',
        'accent_color': '#b8860b',
        'text_color': '#333333',
        'header_bg_color': '#8c876c',
        'footer_bg_color': '#333333',
        'heading_font': 'Hiragino Kaku Gothic Pro',
        'body_font': 'Hiragino Kaku Gothic Pro',
    },
    'elegant': {
        'primary_color': '#2c3e50',
        'secondary_color': '#ecf0f1',
        'accent_color': '#c0392b',
        'text_color': '#2c3e50',
        'header_bg_color': '#2c3e50',
        'footer_bg_color': '#1a252f',
        'heading_font': 'Noto Serif JP',
        'body_font': 'Noto Sans JP',
    },
    'modern': {
        'primary_color': '#1a1a2e',
        'secondary_color': '#f5f5f5',
        'accent_color': '#e94560',
        'text_color': '#16213e',
        'header_bg_color': '#1a1a2e',
        'footer_bg_color': '#0f3460',
        'heading_font': 'M PLUS 1p',
        'body_font': 'Noto Sans JP',
    },
    'natural': {
        'primary_color': '#5c7a3b',
        'secondary_color': '#f5f0e8',
        'accent_color': '#d4a574',
        'text_color': '#3d3d3d',
        'header_bg_color': '#5c7a3b',
        'footer_bg_color': '#3d5a1e',
        'heading_font': 'Noto Serif JP',
        'body_font': 'Noto Sans JP',
    },
    'luxury': {
        'primary_color': '#1c1c1c',
        'secondary_color': '#f8f6f0',
        'accent_color': '#c9a96e',
        'text_color': '#1c1c1c',
        'header_bg_color': '#1c1c1c',
        'footer_bg_color': '#0d0d0d',
        'heading_font': 'Noto Serif JP',
        'body_font': 'Noto Sans JP',
    },
    'pop': {
        'primary_color': '#ff6b6b',
        'secondary_color': '#fff3e6',
        'accent_color': '#ffd93d',
        'text_color': '#333333',
        'header_bg_color': '#ff6b6b',
        'footer_bg_color': '#ee5a5a',
        'heading_font': 'M PLUS Rounded 1c',
        'body_font': 'M PLUS 1p',
    },
    'japanese': {
        'primary_color': '#5b3256',
        'secondary_color': '#f7f3f0',
        'accent_color': '#c1272d',
        'text_color': '#333333',
        'header_bg_color': '#5b3256',
        'footer_bg_color': '#3d1f39',
        'heading_font': 'Noto Serif JP',
        'body_font': 'Noto Sans JP',
    },
}


def get_preset_names():
    """プリセット名のリストを返す。"""
    return list(THEME_PRESETS.keys())


def get_preset(name):
    """指定プリセットの辞書を返す。存在しなければ None。"""
    return THEME_PRESETS.get(name)
