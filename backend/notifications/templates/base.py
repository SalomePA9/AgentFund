"""
Base email template with shared styles.

Provides the foundational HTML structure and styling used by all
email templates, following AgentFund's dark mode aesthetic.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BaseTemplate:
    """Base template with shared email styles and structure."""

    # Color palette (matching AgentFund UI)
    COLORS = {
        "background": "#0A0A0B",
        "card_bg": "#111113",
        "border": "#1F1F23",
        "text_primary": "#FFFFFF",
        "text_secondary": "#A1A1AA",
        "text_muted": "#71717A",
        "accent": "#3B82F6",
        "success": "#22C55E",
        "danger": "#EF4444",
        "warning": "#F59E0B",
    }

    # Font stacks
    FONTS = {
        "sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "mono": "'JetBrains Mono', 'SF Mono', Monaco, Consolas, monospace",
    }

    @classmethod
    def get_styles(cls) -> str:
        """Get shared CSS styles."""
        return f"""
        <style>
            /* Reset */
            body, table, td, div, p, a {{
                margin: 0;
                padding: 0;
                border: 0;
                font-size: 100%;
                font: inherit;
                vertical-align: baseline;
            }}

            /* Base */
            body {{
                font-family: {cls.FONTS['sans']};
                background-color: {cls.COLORS['background']};
                color: {cls.COLORS['text_primary']};
                line-height: 1.6;
                -webkit-font-smoothing: antialiased;
            }}

            /* Container */
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 32px 16px;
            }}

            /* Card */
            .card {{
                background-color: {cls.COLORS['card_bg']};
                border: 1px solid {cls.COLORS['border']};
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 16px;
            }}

            /* Typography */
            h1 {{
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 8px;
            }}
            h2 {{
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 8px;
            }}
            h3 {{
                font-size: 14px;
                font-weight: 600;
                color: {cls.COLORS['text_secondary']};
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 12px;
            }}
            p {{
                color: {cls.COLORS['text_secondary']};
                margin-bottom: 16px;
            }}

            /* Numbers (monospace) */
            .mono {{
                font-family: {cls.FONTS['mono']};
            }}
            .number {{
                font-family: {cls.FONTS['mono']};
                font-weight: 500;
            }}
            .positive {{
                color: {cls.COLORS['success']};
            }}
            .negative {{
                color: {cls.COLORS['danger']};
            }}

            /* Metric card */
            .metric {{
                display: inline-block;
                padding: 12px 16px;
                background-color: {cls.COLORS['background']};
                border-radius: 8px;
                margin: 4px;
            }}
            .metric-label {{
                font-size: 12px;
                color: {cls.COLORS['text_muted']};
                margin-bottom: 4px;
            }}
            .metric-value {{
                font-size: 20px;
                font-weight: 600;
            }}

            /* Button */
            .button {{
                display: inline-block;
                background-color: {cls.COLORS['accent']};
                color: white !important;
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 500;
            }}
            .button:hover {{
                background-color: #2563EB;
            }}

            /* Status badge */
            .badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 9999px;
                font-size: 12px;
                font-weight: 500;
            }}
            .badge-success {{
                background-color: rgba(34, 197, 94, 0.1);
                color: {cls.COLORS['success']};
            }}
            .badge-danger {{
                background-color: rgba(239, 68, 68, 0.1);
                color: {cls.COLORS['danger']};
            }}
            .badge-warning {{
                background-color: rgba(245, 158, 11, 0.1);
                color: {cls.COLORS['warning']};
            }}

            /* Divider */
            .divider {{
                border-top: 1px solid {cls.COLORS['border']};
                margin: 16px 0;
            }}

            /* Footer */
            .footer {{
                text-align: center;
                padding-top: 24px;
                color: {cls.COLORS['text_muted']};
                font-size: 12px;
            }}
            .footer a {{
                color: {cls.COLORS['text_secondary']};
            }}

            /* Table */
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th {{
                text-align: left;
                font-size: 12px;
                color: {cls.COLORS['text_muted']};
                text-transform: uppercase;
                padding: 8px 0;
                border-bottom: 1px solid {cls.COLORS['border']};
            }}
            td {{
                padding: 12px 0;
                border-bottom: 1px solid {cls.COLORS['border']};
            }}

            /* Responsive */
            @media (max-width: 600px) {{
                .container {{
                    padding: 16px 8px;
                }}
                .card {{
                    padding: 16px;
                }}
                .metric {{
                    display: block;
                    margin: 8px 0;
                }}
            }}
        </style>
        """

    @classmethod
    def wrap_html(cls, title: str, body: str, preheader: str = "") -> str:
        """Wrap content in full HTML document structure."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{title}</title>
    {cls.get_styles()}
</head>
<body style="background-color: {cls.COLORS['background']};">
    <!-- Preheader (hidden text for email preview) -->
    <div style="display:none;max-height:0;overflow:hidden;">
        {preheader}
    </div>
    <div class="container">
        {body}
        {cls.get_footer()}
    </div>
</body>
</html>
        """.strip()

    @classmethod
    def get_footer(cls) -> str:
        """Get standard email footer."""
        year = datetime.utcnow().year
        return f"""
        <div class="footer">
            <p>AgentFund - AI-Powered Trading Agents</p>
            <p style="margin-top: 8px;">
                <a href="{{{{unsubscribe_url}}}}">Unsubscribe</a> |
                <a href="{{{{preferences_url}}}}">Email Preferences</a>
            </p>
            <p style="margin-top: 16px; color: {cls.COLORS['text_muted']};">
                &copy; {year} AgentFund. All rights reserved.
            </p>
        </div>
        """

    @classmethod
    def format_currency(cls, value: float, include_sign: bool = False) -> str:
        """Format currency value with styling class."""
        sign = "+" if include_sign and value > 0 else ""
        css_class = "positive" if value >= 0 else "negative"
        return f'<span class="number {css_class}">{sign}${abs(value):,.2f}</span>'

    @classmethod
    def format_percent(cls, value: float, include_sign: bool = True) -> str:
        """Format percentage value with styling class."""
        sign = "+" if include_sign and value > 0 else ""
        css_class = "positive" if value >= 0 else "negative"
        return f'<span class="number {css_class}">{sign}{value:.2f}%</span>'

    @classmethod
    def format_number(cls, value: float | int, decimals: int = 0) -> str:
        """Format number with monospace styling."""
        if decimals > 0:
            return f'<span class="number">{value:,.{decimals}f}</span>'
        return f'<span class="number">{value:,}</span>'
