# Deferred hosted-service cost envelope

- Prepared: 2026-08-20
- Currency: USD/month, list price before tax, credits, negotiated discounts, support labor, and payment processing
- Purpose: archived planning estimate for a future hosted phase, not the approved local-first topology or a vendor quote

Human Gate 0 approved a single-user local prototype. MAU projections and hosted web/API/auth/database costs are therefore deferred. During the local phase, expected external variable cost is limited primarily to OpenAI API usage; local hardware, electricity, and developer time are not modeled below. Reopen this estimate before deployment or shared use.

The recommended beta topology is Vercel Pro (web), Google Cloud Run request-based billing (API), Neon Launch (PostgreSQL), Clerk Pro (identity), OpenAI GPT-5.6 Terra standard processing (interviewer/evaluator), and E2B (sandbox). Final vendors remain a Human Gate 0 decision.

## Official rates used

- [Vercel pricing](https://vercel.com/pricing): Pro starts at $20/month with $20 included usage credit.
- [Google Cloud Run pricing](https://cloud.google.com/run/pricing): request/instance usage pricing with a free tier; us-central1 instance-based reference rates are $0.000018/vCPU-second and $0.000002/GiB-second. Actual request-based billing and region can differ.
- [Neon pricing](https://neon.com/pricing): Launch typical spend is $15/month; $0.106/CU-hour and $0.35/GB-month plus history storage.
- [Clerk pricing](https://clerk.com/pricing): Pro starts at $25/month; pricing is based on monthly retained users. Current free/overage details must be confirmed in checkout.
- [OpenAI API pricing](https://openai.com/api/pricing/): GPT-5.6 Terra standard processing is $2/million input tokens, $0.20/million cached input tokens, and $12/million output tokens for contexts under 270K.
- [E2B pricing](https://e2b.dev/pricing): Hobby has usage billing and up to 20 concurrent sandboxes; Pro is $150/month plus usage. One vCPU is $0.000014/second and 1 GiB memory is $0.0000045/second.

Prices change. Recheck all official pages when Human Gate 0 is reviewed and before each launch decision.

## Workload assumptions

| Scenario | MAU | Interviews/user/month | Runs/interview | Drill attempts/user/month |
| --- | ---: | ---: | ---: | ---: |
| Alpha | 100 | 4 | 10 | 30 |
| Private beta | 1,000 | 4 | 10 | 30 |
| Early scale | 10,000 | 4 | 10 | 30 |

Base LLM assumptions per completed interview are 30,000 uncached input tokens and 6,000 output tokens across all interviewer and evaluation calls, or about **$0.132/interview** at the listed Terra rates. Base drill assumptions are 2,000 input and 500 output tokens, or about **$0.010/attempt**. The estimate conservatively ignores cached-input discounts.

Low/base/high LLM usage per active user per month:

| Case | Interview assumption | Drill assumption | LLM cost/user/month |
| --- | --- | --- | ---: |
| Low | 10K input + 2K output | 1K input + no generated output/templated feedback | $0.24 |
| Base | 30K input + 6K output | 2K input + 0.5K output | $0.83 |
| High | 60K input + 15K output | 5K input + 1K output | $1.86 |

Sandbox base assumes one vCPU and 1 GiB for five seconds per code run: 50 billable seconds/interview, approximately $0.000925/interview before fixed plan fees. This must be replaced with measured p50/p95 runtime and creation overhead during Milestone 3. Early scale includes E2B Pro because 20 Hobby concurrent sandboxes may be insufficient.

## Estimated monthly total

| Cost area | Alpha (100) | Private beta (1,000) | Early scale (10,000) |
| --- | ---: | ---: | ---: |
| Web | $20 | $20 | $20 |
| API | $0–5 | $0–15 | $15–60 |
| PostgreSQL + restore history | $15 | $20–35 | $75–200 |
| Authentication | $25 | $25 | $25 |
| LLM — low/base/high | $24 / $83 / $186 | $240 / $830 / $1,860 | $2,400 / $8,300 / $18,600 |
| Sandbox | $0–5 | $5–25 | $165–350 |
| Logs/metrics/backups beyond database | $0–10 | $10–40 | $50–250 |
| **Estimated total — low/base/high** | **$84 / $143 / $246** | **$325 / $915 / $1,945** | **$2,750 / $8,650 / $19,250** |

Ranges intentionally round up usage uncertainty. They exclude engineering/support labor, enterprise compliance plans, custom domains, email delivery, analytics vendors, taxes, and incident-driven usage.

## Unit economics and budget controls

- Base variable AI cost is about **$0.21 per completed interview** when allocating four interviews and 30 drill attempts per user: $0.132 direct interview LLM + about $0.075 of monthly drill LLM usage + less than one cent of sandbox usage.
- High-case AI usage is about **$0.47 per completed interview equivalent** after allocating drills. Model output is the dominant variable cost.
- Enforce per-session token ceilings, bounded event context, maximum turns, model timeouts, sandbox runtime/output limits, daily user quotas, account/global spend alerts, and feature kill switches before beta.
- Measure actual tokens, cached tokens, sandbox seconds, queue time, and retries by feature and prompt/model version. Replace these estimates after the first 100 completed interviews.
- Do not select a cheaper model solely on price; Milestone 5 calibration thresholds govern model choice.

## Gate 0 decisions required

1. Approve a beta operating budget and a hard monthly spend cap.
2. Approve Vercel + Cloud Run + Neon or choose a different regional topology.
3. Approve Clerk or switch ADR 0002 to a self-hosted identity solution.
4. Approve E2B for the Milestone 3 security evaluation or choose Modal/self-managed microVMs.
5. Approve OpenAI as the initial provider boundary; exact model selection remains evaluation-driven.
