"""
Centralized Chart Configuration - v2.0
Same colors and specs used by HTML and PDF exports
Must match frontend/src/config/chartConfig.ts
"""

CHART_COLORS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
    '#14b8a6', '#e11d48', '#7c3aed', '#0ea5e9', '#d946ef',
]

HTTP_CODE_COLORS = {
    '200': '#10b981', '201': '#34d399', '204': '#6ee7b7',
    '301': '#60a5fa', '302': '#93c5fd',
    '400': '#f59e0b', '401': '#fb923c', '403': '#fdba74',
    '404': '#ef4444', '405': '#dc2626',
    '500': '#dc2626', '502': '#b91c1c', '503': '#991b1b',
}

# Chart.js specific configs for HTML/PDF exports
CHARTJS_DEFAULTS = {
    'responsive': True,
    'maintainAspectRatio': False,
    'plugins': {
        'legend': {
            'position': 'bottom',
            'labels': {
                'font': {'size': 11},
                'boxWidth': 12,
                'padding': 12,
            },
        },
        'tooltip': {
            'enabled': True,
            'mode': 'index',
            'intersect': False,
        },
    },
    'scales': {
        'x': {
            'type': 'time',
            'time': {
                'unit': 'second',
                'displayFormats': {'second': 'HH:mm:ss'},
            },
            'title': {'display': True, 'text': 'Tiempo'},
            'ticks': {'maxTicksLimit': 20, 'font': {'size': 10}},
        },
        'y': {
            'beginAtZero': True,
            'ticks': {'font': {'size': 10}},
        },
    },
    'elements': {
        'line': {'tension': 0.3, 'borderWidth': 2},
        'point': {'radius': 0, 'hoverRadius': 4},
    },
}

TEST_TYPE_LABELS = {
    'load': {'label': 'Load Test', 'color': '#3b82f6', 'bg': '#1e3a5f'},
    'stress': {'label': 'Stress Test', 'color': '#ef4444', 'bg': '#5f1e1e'},
    'endurance': {'label': 'Endurance Test', 'color': '#10b981', 'bg': '#1e5f3a'},
    'scalability': {'label': 'Scalability Test', 'color': '#8b5cf6', 'bg': '#3a1e5f'},
    'spike': {'label': 'Spike Test', 'color': '#f97316', 'bg': '#5f3a1e'},
    'smoke': {'label': 'Smoke Test', 'color': '#94a3b8', 'bg': '#3a3f47'},
}


def get_color_for_index(index: int) -> str:
    return CHART_COLORS[index % len(CHART_COLORS)]


def get_code_color(code: str) -> str:
    return HTTP_CODE_COLORS.get(str(code), '#94a3b8')
