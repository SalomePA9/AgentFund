# AgentFund: Phased Development Plan

## Overview

This document breaks down the AgentFund AI Trading Platform into manageable development phases. Each phase builds on the previous one and delivers a functional increment of the product.

**Total Timeline:** 24 weeks (6 months)
- **MVP Launch:** Phase 1-4 (12 weeks)
- **Post-Launch Enhancements:** Phase 5-7 (12 weeks)

---

## Phase Summary

| Phase | Name | Duration | Goal |
|-------|------|----------|------|
| 1 | Foundation | 4 weeks | Core infrastructure and data pipeline |
| 2 | Intelligence | 3 weeks | Sentiment analysis and LLM integration |
| 3 | Frontend | 3 weeks | Complete user interface |
| 4 | Launch | 2 weeks | Testing, hardening, and MVP launch |
| 5 | Live Trading | 4 weeks | Real money trading capability |
| 6 | Advanced Features | 4 weeks | Power user features |
| 7 | Scale | 4 weeks | Monetization and mobile |

---

## UI/UX Design Benchmark

**Reference Template:** [Superior by Dream Studio](https://superior-template.framer.website/)

All frontend development must follow the design guidelines documented in [`docs/UI_UX_GUIDELINES.md`](./docs/UI_UX_GUIDELINES.md).

**Key Design Principles:**
- Dark mode-first aesthetic
- Clean, minimal interface with premium feel
- Financial data clarity with monospace numbers
- Subtle, purposeful animations
- Mobile-responsive layouts

**Color Palette:** Dark backgrounds (#0A0A0B), electric blue accent (#3B82F6), green for gains, red for losses.

**Typography:** Inter for UI, JetBrains Mono for numbers.

---

## Phase 1: Foundation (Weeks 1-4)

### Goal
Establish the core infrastructure: database, API, market data pipeline, broker integration, and basic agent execution engine.

### Week 1.1: Project Setup & Infrastructure

**Objectives:**
- Initialize project structure for frontend and backend
- Set up database with complete schema
- Configure CI/CD pipelines
- Establish development environment

**Tasks:**
```
[ ] Initialize Next.js 14 project with TypeScript and Tailwind
[ ] Create FastAPI backend scaffold with proper project structure
[ ] Set up Supabase project
[ ] Execute database schema (all tables from spec)
[ ] Configure environment variables template
[ ] Set up Docker Compose for local development
[ ] Create GitHub Actions workflow for CI/CD
[ ] Deploy initial backend to Railway (empty endpoints)
[ ] Deploy initial frontend to Vercel (placeholder page)
```

**Deliverables:**
- Working local development environment
- Database schema deployed to Supabase
- CI/CD pipeline functional
- Both services deployed (placeholder state)

**Success Criteria:**
- `docker-compose up` starts all services locally
- Database tables exist and are accessible
- GitHub Actions runs on push
- Deployed URLs respond with 200

---

### Week 1.2: Market Data Pipeline

**Objectives:**
- Build data fetching infrastructure using yfinance
- Create stock universe (S&P 500 + Russell 1000)
- Calculate and store moving averages
- Implement nightly batch job

**Tasks:**
```
[ ] Create market_data.py module for yfinance integration
[ ] Define stock universe (~1,500 tickers)
[ ] Implement price fetching with rate limiting
[ ] Calculate 30/100/200-day moving averages
[ ] Fetch basic fundamentals (P/E, P/B, market cap)
[ ] Build batch processing for full universe
[ ] Create GitHub Actions scheduled job (runs 6 AM ET)
[ ] Implement error handling and retry logic
[ ] Add data validation and sanity checks
[ ] Create /api/market/stocks endpoint
```

**Deliverables:**
- `stocks` table populated with ~1,500 stocks
- Nightly job updating prices and MAs
- API endpoint returning stock data

**Success Criteria:**
- All stocks have current prices (< 24 hours old)
- Moving averages calculated correctly
- Nightly job completes without errors
- API returns paginated stock list

---

### Week 1.3: Factor Calculations & Strategy Screening

**Objectives:**
- Implement quantitative factor scoring
- Build all four strategy screening functions
- Create screening API endpoint

**Tasks:**
```
[ ] Implement momentum score calculation
    - 6-month price momentum
    - MA alignment scoring
    - Relative strength ranking
[ ] Implement value score calculation
    - P/E percentile within sector
    - P/B percentile within sector
    - Combined value rank
[ ] Implement quality score calculation
    - ROE scoring
    - Profit margin scoring
    - Debt/equity scoring
    - Combined quality rank
[ ] Add factor scores to nightly job
[ ] Build MomentumStrategy class
[ ] Build QualityValueStrategy class
[ ] Build QualityMomentumStrategy class
[ ] Build DividendGrowthStrategy class
[ ] Create /api/market/screen endpoint with filters
[ ] Add ATR calculation for position sizing
```

**Deliverables:**
- All stocks scored on momentum, value, quality (0-100)
- Four strategy classes returning ranked candidates
- Screening API with customizable parameters

**Success Criteria:**
- Factor scores update nightly
- Each strategy returns top 20 candidates
- Screening API supports all strategy types
- Results match manual calculation verification

---

### Week 1.4: Alpaca Integration & Agent Core

**Objectives:**
- Complete Alpaca broker integration
- Build agent CRUD operations
- Implement basic position tracking

**Tasks:**
```
[ ] Create AlpacaBroker class
    - Account info retrieval
    - Market/limit order placement
    - Order cancellation
    - Position retrieval
    - Quote/bar data access
[ ] Implement paper/live mode switching
[ ] Build agent database models
[ ] Create agent CRUD API endpoints
    - POST /api/agents (create)
    - GET /api/agents (list)
    - GET /api/agents/:id (detail)
    - PUT /api/agents/:id (update)
    - DELETE /api/agents/:id (delete)
[ ] Implement agent status management (active/paused/stopped)
[ ] Create position tracking logic
[ ] Build /api/broker/connect endpoint
[ ] Add /api/broker/status endpoint
[ ] Implement API key encryption for storage
```

**Deliverables:**
- Users can connect Alpaca account (paper mode)
- Complete agent CRUD functionality
- Position records created on trades

**Success Criteria:**
- Alpaca connection validates successfully
- Agents persist to database correctly
- Position tracking works end-to-end
- API keys stored encrypted

---

### Week 1.5: Agent Execution Engine (spans into Week 5)

**Objectives:**
- Build the core agent processing loop
- Implement stop loss and target monitoring
- Enable automated trade execution

**Tasks:**
```
[ ] Create AgentEngine class structure
[ ] Implement daily processing loop
[ ] Build stop loss checking logic
    - MA-based stops
    - Percentage-based stops
    - Trailing stop support
[ ] Build target price checking
[ ] Implement new opportunity scanning
[ ] Create signal generation pipeline
[ ] Connect strategy screens to execution
[ ] Build position sizing calculator
[ ] Implement order execution flow
[ ] Create activity logging system
[ ] Build performance metric calculations
    - Total return
    - Daily return
    - Sharpe ratio
    - Max drawdown
    - Win rate
[ ] Schedule agent processing job (market open)
```

**Deliverables:**
- Agents execute trades automatically
- Stops and targets enforced
- Activity logged to database
- Performance metrics calculated

**Success Criteria:**
- Agent processes daily without manual intervention
- Stop losses trigger correctly
- Targets trigger correctly
- Performance metrics match manual calculation

---

### Phase 1 Milestone Checklist

```
[ ] Database fully populated with market data
[ ] Factor scores calculated and updating nightly
[ ] All four strategies screening correctly
[ ] Alpaca integration working (paper mode)
[ ] Agents can be created and configured
[ ] Agent engine executing trades automatically
[ ] Activity and performance tracking working
```

---

## Phase 2: Intelligence (Weeks 5-7)

### Goal
Add sentiment analysis pipeline and LLM-powered features (reports, chat, personas).

### Week 2.1: Sentiment Pipeline

**Objectives:**
- Implement news sentiment analysis using FinBERT
- Build social sentiment from StockTwits and Reddit
- Create combined sentiment scoring with velocity tracking

**Tasks:**
```
[ ] Set up FinBERT model (local inference)
[ ] Create NewsSentimentAnalyzer class
    - Google News RSS fetching
    - Headline sentiment scoring
    - Batch processing for all tickers
[ ] Create SocialSentimentAnalyzer class
    - StockTwits API integration
    - Reddit PRAW integration
    - Engagement-weighted scoring
[ ] Build combined sentiment calculation
    - News weight: 40%
    - Social weight: 30%
    - Velocity weight: 30%
[ ] Add sentiment to stocks table
[ ] Create sentiment_history table population
[ ] Add sentiment to nightly job
[ ] Build sentiment velocity (7-day change) tracking
[ ] Create /api/market/sentiment/:ticker endpoint
[ ] Implement sentiment filter in strategy screens
```

**Deliverables:**
- Every stock has news + social sentiment scores
- Sentiment velocity tracked over time
- Triangulation filter working in strategies

**Success Criteria:**
- Sentiment scores range -100 to +100
- Velocity accurately reflects 7-day change
- Sentiment filter improves candidate quality
- Job completes within time budget

---

### Week 2.2: LLM Integration

**Objectives:**
- Set up Claude API client
- Implement daily report generation
- Build chat handler with persona support

**Tasks:**
```
[ ] Create Claude API client wrapper
[ ] Implement response caching layer
[ ] Build ReportGenerator class
    - Daily agent report template
    - Team summary template
    - Performance context building
[ ] Create persona prompt templates
    - Analytical persona
    - Aggressive persona
    - Conservative persona
    - Teacher persona
    - Concise persona
[ ] Implement AgentChatHandler class
    - Context building (positions, activity, performance)
    - Conversation history management
    - Persona voice enforcement
[ ] Create /api/agents/:id/reports endpoints
[ ] Create /api/agents/:id/chat endpoints
[ ] Build report storage and retrieval
[ ] Implement chat history persistence
[ ] Add LLM cost tracking/monitoring
```

**Deliverables:**
- Agents generate personalized daily reports
- Users can chat with agents in character
- Five distinct persona voices working

**Success Criteria:**
- Reports are contextually accurate
- Persona voices are distinguishable
- Chat responses use real portfolio data
- LLM costs within budget (~$50-100/mo)

---

### Week 2.3: Notifications & Delivery

**Objectives:**
- Set up email delivery system
- Implement notification preferences
- Schedule report delivery by timezone

**Tasks:**
```
[ ] Set up Resend for email delivery
[ ] Create email templates
    - Daily report email (HTML)
    - Team summary email (HTML)
    - Alert email (stop hit, target hit)
    - Welcome email
[ ] Build notification preference system
[ ] Implement user timezone handling
[ ] Create scheduled report delivery job
[ ] Build in-app notification system
[ ] Add notification API endpoints
[ ] Implement notification history
[ ] Create unsubscribe handling
[ ] Add email template previews (dev tool)
```

**Deliverables:**
- Daily reports delivered via email at user's preferred time
- Alerts sent for important trading events
- Users can configure all notification preferences

**Success Criteria:**
- Emails deliver successfully (>95% delivery rate)
- Reports arrive at configured time
- Alerts trigger within 5 minutes of event
- Unsubscribe works correctly

---

### Phase 2 Milestone Checklist

```
[ ] Sentiment scores populated for all stocks
[ ] Sentiment velocity tracking working
[ ] Daily reports generating with persona voice
[ ] Chat functionality working with context
[ ] Email delivery system operational
[ ] Notifications configurable per user
[ ] Alert emails triggering on events
```

---

## Phase 3: Frontend (Weeks 8-10)

### Goal
Build the complete user interface with dashboard, agent management, chat, and reports.

### Week 3.1: Dashboard & Agent Views

**Objectives:**
- Build team overview dashboard
- Create individual agent dashboard
- Implement agent list and cards

**Tasks:**
```
[ ] Create dashboard layout with navigation
[ ] Build TeamOverview component
    - Summary stat cards
    - Agent card list
    - Total portfolio value
[ ] Create AgentCard component
    - Status indicator
    - Performance summary
    - Today's summary quote
    - Quick actions
[ ] Build individual agent dashboard
    - Performance chart (line chart)
    - Key metrics cards
    - Positions table
    - Activity feed
[ ] Create AgentPositions component
    - Open positions list
    - Entry/current/target/stop columns
    - P&L display
    - Position actions
[ ] Build AgentActivity component
    - Activity timeline
    - Filter by type
    - Pagination
[ ] Implement AgentPerformance component
    - Return charts
    - Benchmark comparison
    - Drawdown visualization
[ ] Create responsive layouts for mobile
```

**Deliverables:**
- Full dashboard experience
- Complete agent detail views
- Performance visualization

**Success Criteria:**
- Dashboard loads in < 2 seconds
- All data displays correctly
- Charts render properly
- Mobile responsive

---

### Week 3.2: Agent Creation Wizard

**Objectives:**
- Build multi-step agent creation flow
- Implement all configuration options
- Create agent approval/introduction flow

**Tasks:**
```
[ ] Create CreateAgentWizard component
[ ] Build Step 1: Strategy Selection
    - Strategy cards with descriptions
    - Strategy comparison helper
[ ] Build Step 2: Capital Allocation
    - Amount input with validation
    - Available capital display
    - Time horizon selector
[ ] Build Step 3: Risk Configuration
    - Risk tolerance presets (low/medium/high)
    - Advanced options toggle
    - Stop loss configuration
    - Position sizing limits
[ ] Build Step 4: Persona Selection
    - Persona cards with examples
    - Preview sample response
[ ] Build Step 5: Name & Review
    - Custom name input
    - Configuration summary
    - Edit buttons for each section
[ ] Implement agent introduction flow
    - LLM generates initial strategy presentation
    - User approves or adjusts
[ ] Add form validation throughout
[ ] Create confirmation modal
[ ] Build success/redirect flow
```

**Deliverables:**
- Smooth multi-step creation experience
- All parameters customizable
- Agent introduces itself before trading

**Success Criteria:**
- Wizard completes without errors
- Validation prevents bad inputs
- Agent creation < 5 seconds
- Introduction generates correctly

---

### Week 3.3: Chat, Reports & Settings

**Objectives:**
- Build chat interface
- Create report viewing UI
- Implement settings pages

**Tasks:**
```
[ ] Create ChatWindow component
    - Message list with scroll
    - Input with send button
    - Loading state
    - Error handling
[ ] Build ChatMessage component
    - User/agent message styling
    - Timestamp display
    - Copy message action
[ ] Implement chat history loading
[ ] Create DailyReport component
    - Formatted report display
    - Performance snapshot
    - Actions taken section
[ ] Build report archive browser
    - Date picker/calendar
    - Report list by date
[ ] Create TeamSummary component
    - Combined team metrics
    - Agent-by-agent breakdown
[ ] Build Settings page
    - Broker connection management
    - Notification preferences
    - Timezone selection
    - Account settings
[ ] Create broker connection flow
    - API key input
    - Paper/live toggle
    - Connection test
[ ] Implement agent edit page
    - All parameters editable
    - Strategy change warnings
[ ] Add agent delete confirmation
    - Position handling options
```

**Deliverables:**
- Full chat functionality
- Report archive accessible
- Complete settings management

**Success Criteria:**
- Chat messages appear in < 1 second
- Reports display correctly
- Settings save without refresh
- Broker connects successfully

---

### Phase 3 Milestone Checklist

```
[ ] Dashboard displays all agent data
[ ] Individual agent pages fully functional
[ ] Agent creation wizard complete
[ ] Chat interface working smoothly
[ ] Report viewing and archive working
[ ] Settings page complete
[ ] Broker connection flow working
[ ] All pages mobile responsive
```

---

## Phase 4: Launch (Weeks 11-12)

### Goal
Test thoroughly, harden security, and launch MVP to beta users.

### Week 4.1: Testing & Edge Cases

**Objectives:**
- Write comprehensive tests
- Handle all edge cases
- Implement robust error handling

**Tasks:**
```
[ ] Write unit tests for strategies
[ ] Write unit tests for factor calculations
[ ] Write integration tests for agent engine
[ ] Write API endpoint tests
[ ] Test edge cases:
    - Market closed handling
    - Partial order fills
    - API failures and timeouts
    - Rate limit handling
    - Invalid data handling
    - Concurrent operations
[ ] Implement retry logic with exponential backoff
[ ] Add circuit breakers for external APIs
[ ] Create error notification system
[ ] Build admin error dashboard
[ ] Security audit:
    - API key encryption verification
    - Input validation review
    - SQL injection prevention
    - XSS prevention
    - Rate limiting implementation
    - Authentication token security
[ ] Load testing (simulate 100 users)
[ ] Fix all identified issues
```

**Deliverables:**
- Test coverage > 70%
- All edge cases handled gracefully
- Security vulnerabilities resolved

**Success Criteria:**
- All tests pass
- No critical security issues
- Error handling works correctly
- System handles load

---

### Week 4.2: Launch Preparation

**Objectives:**
- Optimize performance
- Create documentation
- Launch to beta users

**Tasks:**
```
[ ] Performance optimization
    - Database query optimization
    - API response caching
    - Frontend bundle optimization
    - Image optimization
[ ] Create user documentation
    - Getting started guide
    - Strategy explanations
    - FAQ section
[ ] Create legal pages
    - Terms of service
    - Privacy policy
    - Risk disclaimers
[ ] Set up monitoring
    - Sentry for error tracking
    - Log aggregation
    - Uptime monitoring
    - Performance metrics
[ ] Create onboarding flow
    - Welcome screen
    - Feature tour
    - First agent guidance
[ ] Beta user recruitment (10-20 users)
[ ] Beta testing period (1 week)
[ ] Collect and triage feedback
[ ] Fix critical bugs from beta
[ ] Final deployment checks
[ ] Launch MVP
```

**Deliverables:**
- Production-ready application
- Documentation complete
- Monitoring in place
- Beta feedback incorporated

**Success Criteria:**
- Page load < 3 seconds
- API response < 500ms (p95)
- No critical bugs in beta
- Documentation covers all features

---

### Phase 4 Milestone Checklist (MVP LAUNCH)

```
[ ] All tests passing
[ ] Security audit complete
[ ] Performance optimized
[ ] Documentation published
[ ] Monitoring operational
[ ] Beta testing complete
[ ] Critical bugs fixed
[ ] MVP launched to public
```

---

## Phase 5: Live Trading (Weeks 13-16)

### Goal
Enable real money trading with enhanced safety features.

### Objectives
- Alpaca live trading integration
- Enhanced risk controls for real money
- Regulatory compliance measures
- Position sizing refinements

### Tasks
```
[ ] Implement live trading mode activation
[ ] Add live trading confirmation requirements
[ ] Create enhanced risk controls
    - Daily loss limits
    - Position concentration limits
    - Unusual activity alerts
[ ] Build real-time order status tracking
[ ] Implement trade reconciliation
[ ] Add comprehensive audit logging
[ ] Create live trading dashboard
[ ] Update legal disclaimers
[ ] Implement gradual rollout system
[ ] Add live trading user verification
```

### Deliverables
- Live trading capability
- Enhanced safety measures
- Complete audit trail

---

## Phase 6: Advanced Features (Weeks 17-20)

### Goal
Add power user features for advanced customization.

### Objectives
- Custom strategy builder
- Backtesting visualization
- Portfolio-level features
- Agent comparison tools

### Tasks
```
[ ] Build custom strategy builder UI
    - Factor weight configuration
    - Custom screening rules
    - Save/load strategies
[ ] Create backtesting engine
    - Historical data simulation
    - Performance visualization
    - Strategy comparison
[ ] Implement portfolio-level rebalancing
[ ] Build agent performance comparisons
[ ] Add strategy leaderboard
[ ] Create export functionality (CSV, PDF)
[ ] Implement API key access for automation
[ ] Add webhook integrations
```

### Deliverables
- Custom strategy creation
- Backtesting tools
- Portfolio management features

---

## Phase 7: Scale & Monetization (Weeks 21-24)

### Goal
Implement premium features and expand platform.

### Objectives
- Premium subscription tier
- Mobile application
- Additional broker integrations
- Scale infrastructure

### Tasks
```
[ ] Design premium tier features
    - More agents per account
    - Advanced strategies
    - Priority support
    - API access
[ ] Implement Stripe subscription billing
[ ] Build React Native mobile app
[ ] Add additional broker integrations
    - TD Ameritrade
    - Interactive Brokers
[ ] Scale infrastructure
    - Database optimization
    - Caching layer
    - CDN setup
[ ] Implement referral system
[ ] Create affiliate program
[ ] Build admin dashboard
```

### Deliverables
- Premium subscription ($29/mo)
- Mobile app (iOS/Android)
- Multiple broker support

---

## Dependencies Map

```
Phase 1.1 (Setup) ─────────────────────────────────────────────────┐
    │                                                               │
    ▼                                                               │
Phase 1.2 (Market Data) ───────────────────────────────────────────┤
    │                                                               │
    ▼                                                               │
Phase 1.3 (Strategies) ────────────────────────────────────────────┤
    │                                                               │
    ├───────────────┬───────────────────────────────────────────────┤
    ▼               ▼                                               │
Phase 1.4       Phase 2.1                                          │
(Alpaca)        (Sentiment)                                        │
    │               │                                               │
    ▼               │                                               │
Phase 1.5           │                                               │
(Agent Engine) ◄────┘                                              │
    │                                                               │
    ├───────────────────────────────────────────────────────────────┤
    ▼                                                               │
Phase 2.2 (LLM) ───────────────────────────────────────────────────┤
    │                                                               │
    ▼                                                               │
Phase 2.3 (Notifications) ─────────────────────────────────────────┤
    │                                                               │
    └───────────────────────────────────────────────────────────────┤
                                                                    │
Phase 3.1 (Dashboard) ◄─────────────────────────────────────────────┤
    │                                                               │
    ▼                                                               │
Phase 3.2 (Wizard) ────────────────────────────────────────────────┤
    │                                                               │
    ▼                                                               │
Phase 3.3 (Chat/Reports) ──────────────────────────────────────────┤
    │                                                               │
    ▼                                                               │
Phase 4 (Launch) ◄──────────────────────────────────────────────────┘
    │
    ▼
Phase 5 (Live Trading)
    │
    ▼
Phase 6 (Advanced)
    │
    ▼
Phase 7 (Scale)
```

---

## Risk Register

| Phase | Risk | Impact | Mitigation |
|-------|------|--------|------------|
| 1.2 | yfinance rate limiting | Data gaps | Implement request throttling, caching |
| 1.4 | Alpaca API changes | Integration breaks | Abstract behind interface, version pin |
| 2.1 | FinBERT performance | Slow processing | Batch process, cache results |
| 2.2 | LLM costs exceed budget | Budget overrun | Cache aggressively, use Haiku |
| 3.2 | Complex wizard UX | User drop-off | User testing, simplify steps |
| 4.1 | Security vulnerabilities | Data breach | External audit, penetration testing |
| 5 | Live trading bugs | User financial loss | Extensive testing, gradual rollout |

---

## Success Metrics by Phase

### Phase 1-4 (MVP)
- Database: 1,500+ stocks tracked
- Agents: Create, configure, execute trades
- Strategies: 4 working strategies
- Users: 100 beta signups

### Phase 5-7 (Growth)
- Users: 500 registered
- Agents: 1,000 created
- Premium: 5% conversion
- Retention: 60% at 30 days

---

## Resource Requirements

### Development Team
- 1 Full-stack developer (primary)
- 1 Part-time designer (Phase 3)
- 1 Part-time QA (Phase 4)

### Infrastructure Costs (Monthly)
| Service | Free Tier | Paid Tier |
|---------|-----------|-----------|
| Supabase | $0 | $25 |
| Vercel | $0 | $20 |
| Railway | $0 | $20 |
| Claude API | - | $50-100 |
| Resend | $0 | $0 |
| **Total** | **$50-100** | **$115-165** |

---

## Getting Started

To begin Phase 1.1, run:

```bash
# Clone repository
git clone <repo-url>
cd AgentFund

# Create project structure
mkdir -p backend/{api,core/strategies,data/sentiment,llm/prompts,jobs,models}
mkdir -p frontend/src/{app,components,lib,types}
mkdir -p scripts docs

# Initialize backend
cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn supabase python-jose

# Initialize frontend
cd ../frontend
npx create-next-app@latest . --typescript --tailwind --app

# Set up environment
cp .env.example .env
# Edit .env with your credentials
```

---

*Last Updated: February 2026*
*Version: 1.0*
