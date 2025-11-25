# Second Brain Database - Pre-Seed Fundraising Documentation

## 📋 Master Index

This directory contains comprehensive pre-seed fundraising documentation for the **Second Brain Database ecosystem**, including the main FastAPI backend and all 14 micro-frontend submodules.

---

## 🏗️ Ecosystem Overview

**Second Brain Database** is a platform-agnostic personal knowledge management (PKM) system with a modular micro-frontend architecture. The ecosystem consists of:

### Main Repository: FastAPI Backend
- **Tech Stack:** FastAPI (Python), MongoDB, Redis, Prometheus, Loki
- **API Surface:** 25+ routers, 200+ endpoints
- **Core Features:**
  - Authentication & Security (JWT, 2FA, permanent API tokens)
  - Family Management (budgets, chores, goals, virtual currency)
  - IPAM (hierarchical IP address management)
  - Shop & Subscriptions (digital assets marketplace)
  - RAG & AI Chat (LangGraph, Qdrant, MCP tools)
  - Blog Platform (multi-tenant, SEO, analytics)
  - MemEx (spaced repetition learning)
  - Cluster Management (distributed deployments)
  - Multi-Tenancy (RBAC, tenant isolation)

### 14 Micro-Frontend Submodules

| # | Submodule | Tech | Purpose | Key Features |
|---|-----------|------|---------|--------------|
| 1 | **sbd-nextjs-myaccount** | Next.js 16 | Account management | 21 routes, 2FA, profile, family, tenants, tokens |
| 2 | **sbd-nextjs-family-hub** | Next.js 16 | Family collaboration | Budgets, chores, goals, allowances |
| 3 | **sbd-nextjs-digital-shop** | Next.js 16 | Digital asset marketplace | Avatars, banners, themes, subscriptions |
| 4 | **sbd-nextjs-blog-platform** | Next.js 16 | Blogging platform | SEO, RSS, analytics, multi-tenant |
| 5 | **sbd-nextjs-university-clubs** | Next.js 16 | Club management | Events, members, WebRTC meetings |
| 6 | **sbd-flutter-emotion_tracker** | Flutter | Mobile emotion tracking | Daily mood logging, analytics |
| 7 | **sbd-nextjs-chat** | Next.js 16 | Real-time chat | WebSocket, message history |
| 8 | **sbd-nextjs-ipam** | Next.js 16 | IP address management | Hierarchical allocation, quotas |
| 9 | **sbd-nextjs-landing-page** | Next.js 16 | Marketing site | Product showcase, pricing |
| 10 | **sbd-nextjs-memex** | Next.js 16 | Spaced repetition | SuperMemo-2 algorithm, flashcards |
| 11 | **sbd-nextjs-raunak-ai** | Next.js 16 | AI chat interface | RAG, MCP tools, document upload |
| 12 | **sbd-nextjs-cluster-dashboard** | Next.js 16 | Cluster monitoring | Node health, replication, failover |
| 13 | **n8n-nodes-sbd** | TypeScript | n8n integration | Workflow automation nodes |
| 14 | **sbd-mkdocs** | MkDocs | Documentation site | API docs, guides, tutorials |

---

## 📂 Documentation Structure

```
docs/fundraising/
├── README.md (this file)
├── main_repo/
│   ├── 1_pitch_fundraising.md ✅
│   ├── 2_product_tech.md
│   ├── 3_market_strategy.md
│   ├── 4_traction_metrics.md
│   ├── 5_team_operations.md
│   ├── 6_financial_docs.md
│   ├── 7_legal_compliance.md
│   ├── 8_operational_process.md
│   ├── 9_data_room.md
│   └── 10_bonus_docs.md
└── submodules/
    ├── sbd-nextjs-myaccount/
    │   └── [1-10 sections]
    ├── sbd-nextjs-family-hub/
    │   └── [1-10 sections]
    └── ... (12 more submodules)
```

---

## 🎯 Quick Reference: Key Metrics

### Market Opportunity
- **TAM:** $15B global productivity software market
- **SAM:** $3B PKM & note-taking tools
- **SOM:** $150M (5% of SAM in 3-5 years)

### Competitive Landscape
- **Notion:** $10B valuation, 30M users
- **Obsidian:** 1M+ users, $50/yr pricing
- **Logseq:** Open-source, 100K+ users

### Business Model
- **Free Tier:** Self-hosted (Docker), 1 family, 5 users
- **Pro Tier:** $9/mo - Cloud-hosted, 3 families, 50 users, 100GB
- **Enterprise:** Custom pricing - Unlimited users, SSO, SLA

### Fundraising Goal
- **Amount:** $500K Pre-Seed
- **Instrument:** YC SAFE
- **Valuation Cap:** $5M
- **Discount:** 20%

### Use of Funds (18 months)
- **Product & Engineering (50%):** $250K - 3 engineers, infrastructure
- **Growth & Marketing (30%):** $150K - Content, community, paid ads
- **Operations (20%):** $100K - Legal, accounting, office

### Milestones (18 months)
- 10,000 self-hosted users (Docker pulls)
- $50K MRR (500 paying customers)
- 5 enterprise pilot customers
- Series A readiness ($3M @ $20M valuation)

---

## 🚀 Traction Highlights

### Production-Ready Applications
- ✅ **sbd-nextjs-myaccount:** 100% feature coverage, 21 routes, zero errors
- ✅ **Main Backend:** 200+ endpoints, multi-tenancy, cluster mode
- ✅ **Docker Hub:** Public image available (`rohanbatra/second_brain_database:latest`)
- ✅ **GitHub:** Open-source backend + 14 submodules

### Technical Achievements
- **Authentication:** JWT, 2FA (TOTP), permanent API tokens, session management
- **Family System:** Virtual currency (SBD tokens), budgets, chores, purchase requests
- **AI/RAG:** LangGraph integration, Qdrant vector DB, MCP tools
- **Scalability:** Cluster mode with replication, failover, split-brain detection
- **Observability:** Prometheus metrics, Loki logging, performance tracking

---

## 🏢 Target Customers

### Primary Segments

#### 1. Individual Knowledge Workers
- **Profile:** Developers, researchers, writers, students
- **Pain Point:** Vendor lock-in in Notion/Obsidian, no data portability
- **Value Prop:** Self-hosted, API-first, full data ownership
- **Acquisition:** GitHub, Docker Hub, Dev.to, Hacker News

#### 2. Families
- **Profile:** Tech-savvy families (3-7 members)
- **Pain Point:** Fragmented tools for budgets, chores, calendars
- **Value Prop:** Unified platform with virtual currency, shared budgets
- **Acquisition:** Family tech blogs, Reddit (r/productivity), YouTube

#### 3. Enterprises & Universities
- **Profile:** IT departments, university clubs, small businesses
- **Pain Point:** SaaS costs, compliance requirements, customization needs
- **Value Prop:** Self-hosted, RBAC, multi-tenancy, unlimited customization
- **Acquisition:** Direct sales, university partnerships, enterprise trials

---

## 💡 Unique Value Propositions

### 1. Platform Independence
- **Data Layer:** MongoDB (flexible schema, easy export)
- **Presentation Layer:** 14 micro-frontends (Next.js, Flutter)
- **Integration Layer:** REST API, n8n nodes, MCP tools
- **Result:** Switch frontends without losing data

### 2. Vertical Integration (Family Features)
- **Virtual Currency:** SBD tokens for allowances, rewards
- **Budgets:** Shared family budgets with approval workflows
- **Chores:** Task assignment with token rewards
- **Purchase Requests:** Kids request, parents approve
- **Result:** No competitor has this depth in family collaboration

### 3. AI-Native Architecture
- **RAG:** Document-based retrieval with Qdrant vector DB
- **MCP Tools:** Model Context Protocol for AI agent integration
- **LangGraph:** Agent orchestration for complex workflows
- **Result:** Your notes become an intelligent knowledge base

### 4. Self-Hosted + Cloud Hybrid
- **Self-Hosted:** Docker one-click deploy, Kubernetes-ready
- **Managed Cloud:** Pro tier for convenience
- **Enterprise:** On-premise or VPC deployment
- **Result:** Flexibility for all customer segments

---

## 📊 Financial Projections (3-Year)

| Metric | Year 1 | Year 2 | Year 3 |
|--------|--------|--------|--------|
| **Self-Hosted Users** | 10,000 | 50,000 | 200,000 |
| **Paying Customers** | 500 | 2,500 | 10,000 |
| **MRR** | $50K | $250K | $1M |
| **ARR** | $600K | $3M | $12M |
| **Gross Margin** | 85% | 88% | 90% |
| **CAC** | $50 | $40 | $30 |
| **LTV** | $500 | $750 | $1,000 |
| **LTV:CAC** | 10:1 | 19:1 | 33:1 |
| **Burn Rate** | $35K/mo | $75K/mo | $150K/mo |
| **Headcount** | 5 | 15 | 35 |

---

## 🛡️ Competitive Moat

### 1. Data Network Effects
- More users → More n8n integrations → More MCP tools → More community plugins
- GitHub stars, Docker pulls, community contributions create flywheel

### 2. Switching Costs
- Once a family/enterprise is on SBD:
  - Custom workflows built on REST API
  - n8n automations integrated
  - Data structured in MongoDB
  - **Migrating out = rebuilding everything**

### 3. Vertical Integration
- Family features (budgets, chores, virtual currency) are unique
- Notion can't copy without cannibalizing workspace revenue
- Obsidian can't copy without breaking single-user model

### 4. Open-Source Community
- Backend is open-source → Developer evangelists
- Micro-frontends are modular → Community can build new ones
- **Result:** Community becomes moat (like Linux, WordPress)

---

## 🎯 Go-To-Market Strategy

### Phase 1: Developer-First (Months 1-6)
- **Channels:**
  - GitHub (open-source backend)
  - Docker Hub (one-click deploy)
  - Dev.to, Hacker News, Reddit (r/selfhosted, r/PKMS)
- **Content:**
  - Technical blog posts (RAG, micro-frontends, FastAPI)
  - YouTube tutorials (self-hosting, n8n integration)
  - Documentation site (sbd-mkdocs)
- **Goal:** 10,000 Docker pulls, 1,000 GitHub stars

### Phase 2: Community Building (Months 7-12)
- **Channels:**
  - Discord community (power users, plugin developers)
  - n8n integration marketplace
  - PKM influencer partnerships (Tiago Forte, Ali Abdaal)
- **Content:**
  - Case studies (families, university clubs)
  - Webinars (RAG, self-hosting, family collaboration)
  - Community plugins showcase
- **Goal:** 500 paying customers, $50K MRR

### Phase 3: Enterprise Sales (Months 13-18)
- **Channels:**
  - Direct outreach to universities (student clubs platform)
  - Enterprise self-hosted trials
  - Partnerships with IT consultants
- **Content:**
  - Enterprise case studies
  - Compliance documentation (GDPR, SOC2)
  - White-glove onboarding
- **Goal:** 5 enterprise customers, $100K ARR from enterprise

---

## 📞 Contact & Next Steps

### Founder
- **Name:** Rohan Batrain
- **Email:** rohan@secondbraindatabase.com
- **GitHub:** github.com/rohanbatrain
- **LinkedIn:** [Add LinkedIn URL]

### Resources
- **Pitch Deck:** [Link to deck]
- **Product Demo:** [Link to demo video]
- **GitHub Repo:** github.com/rohanbatrain/second_brain_database
- **Docker Hub:** hub.docker.com/r/rohanbatra/second_brain_database

### Investor Meetings
To schedule a meeting or request access to the full data room, please email rohan@secondbraindatabase.com with:
- Your fund/angel network
- Areas of interest (product, market, team)
- Preferred meeting times

---

## 📝 Document Status

| Section | Main Repo | Submodules (14) | Status |
|---------|-----------|-----------------|--------|
| 1. Pitch & Fundraising | ✅ Complete | 🚧 In Progress | 1/15 |
| 2. Product & Technology | 🚧 In Progress | ⏳ Pending | 0/15 |
| 3. Market & Strategy | ⏳ Pending | ⏳ Pending | 0/15 |
| 4. Traction & Metrics | ⏳ Pending | ⏳ Pending | 0/15 |
| 5. Team & Operations | ⏳ Pending | ⏳ Pending | 0/15 |
| 6. Financial Documents | ⏳ Pending | ⏳ Pending | 0/15 |
| 7. Legal & Compliance | ⏳ Pending | ⏳ Pending | 0/15 |
| 8. Operational & Process | ⏳ Pending | ⏳ Pending | 0/15 |
| 9. Data Room Files | ⏳ Pending | ⏳ Pending | 0/15 |
| 10. Bonus / Rare Docs | ⏳ Pending | ⏳ Pending | 0/15 |

**Last Updated:** 2025-11-25

---

*This documentation is continuously updated as the product evolves. For the latest version, please check the GitHub repository.*
