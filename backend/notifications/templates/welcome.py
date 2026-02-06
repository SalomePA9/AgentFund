"""
Welcome email template.

Generates onboarding emails for new users.
"""

from dataclasses import dataclass

from notifications.templates.base import BaseTemplate


@dataclass
class WelcomeData:
    """Data for welcome email."""

    user_name: str
    user_email: str


class WelcomeTemplate(BaseTemplate):
    """Template for welcome emails."""

    @classmethod
    def render(cls, data: WelcomeData) -> str:
        """
        Render the welcome email.

        Args:
            data: Welcome data

        Returns:
            Complete HTML email string
        """
        # Build the email body
        body = f"""
        <!-- Header -->
        <div class="card" style="text-align: center; padding: 40px 24px;">
            <div style="font-size: 48px; margin-bottom: 16px;">🚀</div>
            <h1 style="font-size: 28px;">Welcome to AgentFund!</h1>
            <p style="font-size: 16px; margin-bottom: 0;">
                Hi {data.user_name}, you're ready to start building your AI trading team.
            </p>
        </div>

        <!-- Getting Started -->
        <div class="card">
            <h3>Get Started in 3 Steps</h3>

            <div style="display: flex; align-items: flex-start; margin-bottom: 20px;">
                <div style="width: 32px; height: 32px; background-color: {cls.COLORS['accent']}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; margin-right: 16px; flex-shrink: 0;">
                    1
                </div>
                <div>
                    <div style="font-weight: 600; margin-bottom: 4px;">Connect Your Broker</div>
                    <p style="margin-bottom: 0; font-size: 14px;">
                        Link your Alpaca account to enable paper trading. Start risk-free to test strategies before going live.
                    </p>
                </div>
            </div>

            <div style="display: flex; align-items: flex-start; margin-bottom: 20px;">
                <div style="width: 32px; height: 32px; background-color: {cls.COLORS['accent']}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; margin-right: 16px; flex-shrink: 0;">
                    2
                </div>
                <div>
                    <div style="font-weight: 600; margin-bottom: 4px;">Create Your First Agent</div>
                    <p style="margin-bottom: 0; font-size: 14px;">
                        Choose a strategy, set your risk parameters, and give your agent a personality. It takes less than 2 minutes.
                    </p>
                </div>
            </div>

            <div style="display: flex; align-items: flex-start;">
                <div style="width: 32px; height: 32px; background-color: {cls.COLORS['accent']}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; margin-right: 16px; flex-shrink: 0;">
                    3
                </div>
                <div>
                    <div style="font-weight: 600; margin-bottom: 4px;">Watch & Chat</div>
                    <p style="margin-bottom: 0; font-size: 14px;">
                        Monitor your agent's performance, read daily reports, and chat to understand their decisions.
                    </p>
                </div>
            </div>
        </div>

        <!-- Strategy Overview -->
        <div class="card">
            <h3>Available Strategies</h3>

            <div style="margin-bottom: 16px; padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px;">
                <div style="font-weight: 600; margin-bottom: 4px; color: {cls.COLORS['text_primary']};">📈 Momentum</div>
                <p style="margin-bottom: 0; font-size: 14px;">
                    Rides trending stocks with strong price momentum and moving average alignment.
                </p>
            </div>

            <div style="margin-bottom: 16px; padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px;">
                <div style="font-weight: 600; margin-bottom: 4px; color: {cls.COLORS['text_primary']};">💎 Quality Value</div>
                <p style="margin-bottom: 0; font-size: 14px;">
                    Finds undervalued companies with strong fundamentals and quality metrics.
                </p>
            </div>

            <div style="margin-bottom: 16px; padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px;">
                <div style="font-weight: 600; margin-bottom: 4px; color: {cls.COLORS['text_primary']};">⚡ Quality Momentum</div>
                <p style="margin-bottom: 0; font-size: 14px;">
                    Combines momentum with quality filters for high-conviction opportunities.
                </p>
            </div>

            <div style="padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px;">
                <div style="font-weight: 600; margin-bottom: 4px; color: {cls.COLORS['text_primary']};">💰 Dividend Growth</div>
                <p style="margin-bottom: 0; font-size: 14px;">
                    Invests in companies with consistent dividend growth and income potential.
                </p>
            </div>
        </div>

        <!-- Features -->
        <div class="card">
            <h3>What You Get</h3>

            <div style="display: flex; flex-wrap: wrap; margin: -8px;">
                <div style="flex: 1; min-width: 200px; padding: 8px;">
                    <div style="padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px; height: 100%;">
                        <div style="color: {cls.COLORS['accent']}; margin-bottom: 8px;">🤖</div>
                        <div style="font-weight: 500; margin-bottom: 4px;">AI Trading Agents</div>
                        <div style="font-size: 12px; color: {cls.COLORS['text_muted']};">Autonomous execution</div>
                    </div>
                </div>
                <div style="flex: 1; min-width: 200px; padding: 8px;">
                    <div style="padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px; height: 100%;">
                        <div style="color: {cls.COLORS['accent']}; margin-bottom: 8px;">📊</div>
                        <div style="font-weight: 500; margin-bottom: 4px;">Daily Reports</div>
                        <div style="font-size: 12px; color: {cls.COLORS['text_muted']};">Personalized insights</div>
                    </div>
                </div>
                <div style="flex: 1; min-width: 200px; padding: 8px;">
                    <div style="padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px; height: 100%;">
                        <div style="color: {cls.COLORS['accent']}; margin-bottom: 8px;">💬</div>
                        <div style="font-weight: 500; margin-bottom: 4px;">Chat Interface</div>
                        <div style="font-size: 12px; color: {cls.COLORS['text_muted']};">Ask questions anytime</div>
                    </div>
                </div>
                <div style="flex: 1; min-width: 200px; padding: 8px;">
                    <div style="padding: 16px; background-color: {cls.COLORS['background']}; border-radius: 8px; height: 100%;">
                        <div style="color: {cls.COLORS['accent']}; margin-bottom: 8px;">🎯</div>
                        <div style="font-weight: 500; margin-bottom: 4px;">Risk Management</div>
                        <div style="font-size: 12px; color: {cls.COLORS['text_muted']};">Built-in stop losses</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- CTA -->
        <div class="card" style="text-align: center;">
            <p style="margin-bottom: 16px;">Ready to build your trading team?</p>
            <a href="{{{{dashboard_url}}}}" class="button" style="font-size: 16px; padding: 16px 32px;">
                Go to Dashboard
            </a>
        </div>

        <!-- Help -->
        <div class="card" style="text-align: center;">
            <h3>Need Help?</h3>
            <p style="margin-bottom: 0;">
                Check out our <a href="{{{{docs_url}}}}" style="color: {cls.COLORS['accent']};">documentation</a>
                or reply to this email if you have questions.
            </p>
        </div>
        """

        preheader = f"Welcome {data.user_name}! Your AI trading team awaits."

        return cls.wrap_html(
            title="Welcome to AgentFund!",
            body=body,
            preheader=preheader,
        )

    @classmethod
    def render_plain_text(cls, data: WelcomeData) -> str:
        """Render plain text version of the welcome email."""
        return f"""
WELCOME TO AGENTFUND!
=====================

Hi {data.user_name},

You're ready to start building your AI trading team!

GET STARTED IN 3 STEPS
----------------------

1. CONNECT YOUR BROKER
   Link your Alpaca account to enable paper trading.
   Start risk-free to test strategies before going live.

2. CREATE YOUR FIRST AGENT
   Choose a strategy, set your risk parameters, and
   give your agent a personality. Takes less than 2 minutes.

3. WATCH & CHAT
   Monitor your agent's performance, read daily reports,
   and chat to understand their decisions.


AVAILABLE STRATEGIES
--------------------

- MOMENTUM: Rides trending stocks with strong price momentum
- QUALITY VALUE: Finds undervalued companies with strong fundamentals
- QUALITY MOMENTUM: Combines momentum with quality filters
- DIVIDEND GROWTH: Invests in consistent dividend growers


WHAT YOU GET
------------

- AI Trading Agents: Autonomous execution
- Daily Reports: Personalized insights
- Chat Interface: Ask questions anytime
- Risk Management: Built-in stop losses


Ready to build your trading team?
Visit: {{{{dashboard_url}}}}

Need help? Check our docs at {{{{docs_url}}}}
or reply to this email.

---
To unsubscribe, visit {{{{unsubscribe_url}}}}
""".strip()
