import json
from openai import OpenAI
import pandas as pd

with open("storage/secrets.json", "r") as f:
    secrets = json.load(f)
oai = OpenAI(api_key=secrets["openai_key"])


def generate_weekly_commentary(client):
    payload = {
        "inputs": {
            "plans_90_day": client['plan_json'],
            "paid_data_mom": client['mom']['llm_data'],
            "overall_data_mom": client['mom']['overall_data'],
            "paid_data_yoy": client['yoy']['llm_data'],
            "overall_data_yoy": client['yoy']['overall_data'],
            "paid_data_90_day": client['timeseries'],
            "report_start_date": client['start_date_string'],
            "report_end_date": client['end_date_string'],
            "monthly_budget": client['budget'],
            "run_rate": client['run_rate'],
            "cost_to_date": client['paid_data']['Total']['Cost']['curr'],
            "reporting_period": client['comparison_dates'],
            "client_context": client['client_context'],
            "holistic_plans": client['holistic_plans'],
            "paid_plans": client['paid_plans'],
            "kpis": client['kpis'],
            "seasonality": client['seasonality'],
            "historical_context": client['historical_context']
        }
    }

    schema = {
        "name": "weekly_marketing_commentary",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "plan_overview": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "task": {"type": "string"},
                                    "description": {"type": "string"},
                                    "status": {"type": "string"},
                                    "start_date": {"type": "string"},
                                    "end_date": {"type": "string"},
                                    "summary": {"type": "string"},
                                },
                                "required": ["task", "description", "status", "start_date", "end_date", "summary"],
                            },
                        }
                    },
                    "required": ["tasks"],
                },
                "performance_overview": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                },
                "ninety_day_overview": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                },
                "performance_points": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 10,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["title", "summary"],
                    },
                },
            },
            "required": ["plan_overview", "performance_overview", "ninety_day_overview", "performance_points"],
        },
        "strict": True,
    }

    response = oai.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "You are a senior performance marketing manager writing weekly client-facing commentary.\n"
            "We want critical commentary, but when expanding, we don't want scathing commentary, we want productive commentary that will help us get on track with our KPIs\n"
            "Write in British English. Be direct, but human.\n"
            "The report must respect the provided report_start_date and report_end_date; comparisons can reference prior, especially if we can link performance to actions made previously, but the focus is the current reporting period.\n"

            "Attached is a json object called 'inputs' this has attached all the context that will be used for the commentary that has been provided to you, the definition of each variable can be found below"

            "Important classification rules for channels\n"
                "- Always use the channel labels exactly as they appear in the data."
                "- Do not reclassify channels based on platform assumptions."
                "- Do not merge Performance Max into Shopping unless explicitly instructed."
                "- Do not treat Paid Search as the same as Paid Media."
                "- Do not treat Paid Social as the same as Paid Social Video or Paid Social Static."
                "- If a point references a parent channel (e.g. Paid Media or Paid Social), make sure the commentary reflects aggregated performance rather than a single sub-channel."

            "DEFINITION OF CHANNELS"
                "- Paid Media: This is the total paid advertising performance across all paid channels combined (e.g. Paid Search, Shopping, Performance Max, Display, Video, Paid Social). Use this only when referring to the overall paid account performance, not a specific channel."
                "- Paid Search: This is exclusively Search Ads intent-led text search activity (e.g. Google Responsive Search Ads, Microsoft Search Ads). Do not confuse this with Paid Media (overall total), and do not include Shopping or Performance Max in Paid Search unless explicitly stated."
                "- Shopping: This is standard Shopping activity only (e.g. Google Shopping / Microsoft Shopping product-led ads). Treat this as separate from Paid Search and separate from Performance Max & Combined unless explicitly stated otherwise."
                "- Performance Max / Combined: This is Performance Max campaign activity only. Treat this as its own channel and do not merge it into Shopping, Paid Search, Display, or Video unless explicitly stated in the data or notes."
                "- Display: This is display advertising activity only (image/banner-led placements on display networks). Do not include Video activity here unless explicitly stated."
                "- Video: This is video advertising activity only (e.g. YouTube video campaigns or other video-led placements). Treat this as separate from Display unless explicitly stated."
                "- Paid Social: This is the total paid social advertising performance across paid social formats/platforms (e.g. Meta, LinkedIn, TikTok, etc. where applicable). This is a parent paid social grouping and may include Paid Social Video and Paid Social Static."
                "- Paid Social Video: This is paid social performance from video creative/placements only. Treat this as a sub-category of Paid Social, not the total Paid Social channel."
                "- Paid Social Static: This is paid social performance from static image creative/placements only. Treat this as a sub-category of Paid Social, not the total Paid Social channel."

            "DEFINITION OF VARIABLES:\n"
            "- plans_90_day: this is a json object that contains the plans for the current period as well as the plans from previous periods, giving you context on what we have done and what we are planning to do.\n"
            "- paid_data_mom: PPC data comparing the current period to the same period last month. Use as the primary dataset when reporting_period is 'MTD Monthly Comparison'.\n"
            "- overall_data_mom: GA4 site-wide data for the same month-on-month window.\n"
            "- paid_data_yoy: PPC data comparing the current period to the same period last year. Use as the primary dataset when reporting_period is 'MTD Yearly Comparison'.\n"
            "- overall_data_yoy: GA4 site-wide data for the same year-on-year window.\n"
            "- paid_data_90_day: this is the paid data broken down by week number to give a view of how the data has fluctuated over the past 90 days\n"
            "- report_start_date: This is the date where the reporting period begins\n"
            "- report_end_date: This is the date where the reporting period ends\n"
            "- monthly_budget: this is the monthly budget for the current reporting period\n"
            "- run_rate: this is the current run rate for the period\n"
            "- cost_to_date: this is the total media spend for the current month\n"
            "- reporting_period: this states the period of the report and states the data we are using as comparison. It can be one of three things:\n"
            "   - MTD Yearly Comparison: this means that the data period is month to date, and the comparison is the same date range last year\n"
            "   - MTD Monthly Comparison: this means that the data period is month to date, and the comparison is the same date range last month\n"
            "   - WTD Weekly Comparison: this means that the data period is week to date, is 7 day period prior to the last 7 day period\n"
            "- client_context: this is context on the client and what their offering is\n"
            "- holistic_plans: these are the goals for the entire website for the current year, we are striving to achieve these goals for our clients\n"
            "- paid_plans: these are the goals for the ppc channel for the current year, we are striving to achieve these goals for our clients within the context of ppc channels\n"
            "- kpis: these are the key performance indicators we are using to measure how effectively we are achieving the goals that we are trying to hit\n"
            "- seasonality: this is extra context for the account based on how it performs within the context of external factors\n"
            "- historical_context: this is an overview on the performance on the account over previous years, giving extra context as to why we have made these plans\n"

            "METRIC TIER HIERARCHY — apply this at all times when selecting evidence and framing points:\n"
            "- Tier 1 (Outcome) — always lead with these where available: ROAS (Ecommerce Clients), CPA (Lead Gen Clients   ), Transaction Revenue, Conversions, Revenue. These are the primary lens through which performance should be assessed and communicated.\n"
            "- Tier 2 (Efficiency) — use to explain or contextualise Tier 1 movements: Conversion Rate, AOV, CPC, Impression Share, Abs. Top Impression Share, CTR, Hook Rate, Hold Rate.\n"
            "- Tier 3 (Volume) — use only to contextualise Tier 1/2 findings, or when spend has materially changed: Cost, Clicks, Transactions. Never use as the sole basis for a point.\n"
            "- Tier 4 (Engagement) — use sparingly, and only when no Tier 1/2/3 story exists for a channel, or for channels that are exclusively awareness-led (Display, Video, Paid Social Video, Paid Social Static): , Impressions, Views, Thruplays, View Rate.\n"
            "- Impressions and Clicks must never be the primary evidence for a point unless the channel has no conversion data and is exclusively awareness-led.\n"
            "- If a point is anchored on a Tier 3 or Tier 4 metric, it must be explicitly framed in terms of a Tier 1 outcome (e.g. 'Click volume declined, contributing to a drop in conversions and a weaker ROAS for the period').\n"
            "- When multiple tiers are relevant, always lead with the highest tier and work downward — not the other way around.\n"

            "The reporting_period field tells you which comparison is primary. Use the primary dataset to lead all performance points. Reference the secondary dataset only where it adds meaningful seasonal or trend context — do not lead a point with the secondary comparison.\n"
            "It is essential that the context provided through the 'holistic_plans', 'paid_plans', 'kpis', 'seasonality' and 'historical_context' are used. We are comparing ourselves to ourselves and we want to stay aligned to our goals for the year\n"
            "When looking at volume metrics, make sure that we are comparing it to the amount we've spent, if conversions or transaction revenue is down, then we need to account for the cost as the interplay between volume metrics and cost are too important to just reference volume metrics on their own\n"
            "When referring to data in a point, make sure that we are identifying where that data has come from, is it from the paid dataset, or the overall dataset? Furthermore, if we are referencing data from a specific dimension, make sure that is stated in the commentary\n"
            "When using the comparisons, make sure that we are referring to the correct period, so if the comparison period is monthly, we are comparing to 'last month', if the comparison period is yearly, we are comparing to 'last year', etc.\n"

            "STYLE REQUIREMENTS:\n"
            "- Write paragraphs (human readable) for the summaries, not bullet lists.\n"
            "- Evidence must be specific numbers from the performance / ga4_context inputs (e.g., revenue, ROAS, CPA, CR, AOV, spend).\n"
            "- When comparing two data points from different time periods, ensure that the right comparison is used, the comparison can be found in 'comparison_period', if it is 'yoy' then we are comparing year on year, if it is 'mom' then we are comparing month on month\n"
            "- Avoid using dates when referring to periods, use 'current period' and if comparing to the previous period use 'previous month' or 'previous year' (depending on the 'comparison_period' field, if it is 'yoy' then we are comparing year on year, if it is 'mom' then we are comparing month on month)\n"
            "- Explicitly reference the 90-day plan where relevant: if an initiative from plans_90_day plausibly links to a performance movement, call it out and explain the linkage. If you can't find a relevant plan item, then don't reference it.\n"
            "- For each performance point, include a 2-3 sentence summary that combines all the points, this will be the part that gets sent to the client.\n"
            "- For acronyms (e.g. ROAS, TBD) style in all caps, make sure this is only for acronyms, not all metric names\n"
            "- When referencing dates, don't use ISO format, use British standard date format (dd/mm/yyyy)\n"
        ),
        input=[
            {
                "role": "user",
                "content": (
                    "Return JSON that matches the schema exactly.\n"
                    "Deliverables:\n"
                        "1) plan_overview\n"
                            "This is a direct reference to the 90 day plans which have been sent over through the plans_90_day json. Use this to create the following for EACH TASK that is attached in the JSON, irregardless of what category it falls under.:\n"
                                "- Task, description, status: These are all just the corresponding values that have been sent over in the JSON\n"
                                "- Start_date, end_date: convert these from ISO format into the British standard date format (dd/mm/yyyy)\n"
                                "- Summary: this is a more basic client friendly version of the description, make it a one sentence summary that is to the point and not wrapped in marketing fluff\n"
                                "- Ensure that the plans that are being used are 'current', not 'old' plans\n"
                        "2) performance_overview:\n"
                            "- A 2-4 sentence summary of paid_data and overall_data compared to the 'holistic_plans' and 'paid_plans' — how are we doing when it comes to achieving these goals. We want the focus to be on paid points, but frame it within the context of the holistic plans and the overall data we are seeing on the website\n"
                            "- When bringing in actual data from paid_data and overall_data, only use data that explicitly aligns with the kpis that have been given to you in the 'kpis' section.\n"
                            "- You are allowed to use data to back up the statements, but be sparing, this is a quick human readable paragraph for stakeholders\n"
                            "- Include a sentence on current spend to date. Use cost_to_date for the total spend this month, run_rate to see what the predicted cost at the end of the month, and budget to find the monthly budget for the client.\n"
                        "3) ninety day summary\n"
                            "- A 2-4 sentence summary of paid_data_90_day that just gives a top level overview of performance data over the past 90 days. We don't want specifics, we just want a view of the trends in the past 90 days\n"
                            "- Don't make it metric soup, just focus on the main KPI for the client (e.g. Transaction Revenue) and give an overview on how it has changed and what has driven the change\n"
                        "4) performance_points:\n"
                            "Goal: produce high-signal points that explain what's happening by ad channel (use paid_data at the ad channel level, not ad platform — do not use overall_data to create specific points), points must be centred around the metric groups below, we must absolutely not use specific metrics as the main theme of the point\n"
                            "- Use only these metric groups as the theme for a point (do not create points about single metrics):\n"
                                "- Volume: Impressions, Clicks, Cost, Views, Thruplays, Conversions, Transactions, Transaction Revenue\n"
                                "- Performance: CPA, ROAS, Conversion Rate, AOV\n"
                                "- Engagement: CTR, View Rate, Hook Rate, Hold Rate\n"
                                "- Efficiency: CPC, Impression Share, Abs. Top Impression Share\n"
                            "- Apply the METRIC TIER HIERARCHY when selecting which metric group to lead with for each point. Prioritise Performance and Outcome metrics (Tier 1) over Efficiency (Tier 2), Volume (Tier 3), and Engagement (Tier 4). Only lead with a lower tier if no meaningful Tier 1 or Tier 2 story exists for that channel.\n"
                            "Each point should have the following structure:\n"
                            "- title: <Ad Channel> <Metric Group> <Clear Direction/Outcome> (max ~8 words)\n"
                            "- summary: 2-4 sentences. Explain what changed and what it implies, anchoring on the highest available metric tier. Include 1-2 supporting metrics as evidence, working downward through tiers only where it adds explanatory value. You may reference data from the overall_data section to add extra context where relevant, but it is not essential.\n"
                            "- Point selection rules (prioritisation):\n"
                                "- Prioritise channels with the largest spend and/or largest outcome impact (Conversions, Revenue, CPA, ROAS).\n"
                                "- Prefer changes with clear narrative (e.g. Volume up + Performance stable; Performance down despite Volume up).\n"
                                "- Avoid 'metric soup': pick the minimum evidence needed to prove the point.\n"
                            "- Thresholds (to avoid noise):\n"
                                "- Only create a point if at least one Tier 1 or Tier 2 metric has ≥10% relative change, or the channel is ≥20% of total cost, or there is a clear multi-metric pattern within the same group.\n"
                                "- For low-spend channels (<10% of cost), require ≥20% change in a Tier 1 or Tier 2 metric to mention, unless it materially affects overall results.\n"
                                "- Do not create a point anchored solely on Impressions or Clicks — these may be referenced as supporting context only, and only when they help explain a Tier 1 or Tier 2 movement.\n"
                            "- Context:\n"
                                "- You may reference overall_data only when it strengthens the story (e.g. 'this channel drove the overall change').\n"
                                "- If paid_data[<channel>].total exists you may use it, but don't rely on it if it hides important opposing movements.\n"
                    "Input JSON:\n"
                    + json.dumps(payload, ensure_ascii=False)
                ),
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": schema["name"],
                "schema": schema["schema"],
                "strict": schema["strict"],
            }
        },
    )
    return json.loads(response.output_text)


def generate_dimension_cut_commentary(data_mom, label, channel_filter, client):
    """
    Generates insight commentary for a single dimension cut.

    data_mom: dict — same shape as paid_data_mom, keyed by dimension value.
    label: human-readable dimension name (e.g. 'Campaign').
    channel_filter: dict {"type": "include"|"exclude", "channels": [...]} or None.
    client: full client dict (for account_type, kpis, start/end date strings, etc.)

    Returns:
        {
            "overview": "string paragraph",
            "insights": [
                {"title": "string", "summary": "string", "bullets": [{"point": "string"}]}
            ]
        }
    """
    channel_filter_desc = "No channel filter applied."
    if channel_filter:
        filter_type = channel_filter.get('type', 'include')
        channels = channel_filter.get('channels', [])
        if channels:
            channel_filter_desc = (
                f"Data filtered to include only: {', '.join(channels)}."
                if filter_type == 'include'
                else f"Data excludes: {', '.join(channels)}."
            )

    payload = {
        "inputs": {
            "dimension_label": label,
            "channel_filter":  channel_filter_desc,
            "data_mom":        data_mom,
            "report_start_date": client.get('start_date_string', ''),
            "report_end_date":   client.get('end_date_string', ''),
            "client_context":    client.get('client_context', ''),
            "kpis":              client.get('kpis', ''),
            "account_type":      client.get('account_type', 'Ecommerce'),
        }
    }

    schema = {
        "name": "dimension_cut_commentary",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "overview": {"type": "string"},
                "insights": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title":   {"type": "string"},
                            "summary": {"type": "string"},
                            "bullets": {
                                "type": "array",
                                "minItems": 2,
                                "maxItems": 5,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {"point": {"type": "string"}},
                                    "required": ["point"]
                                }
                            }
                        },
                        "required": ["title", "summary", "bullets"]
                    }
                }
            },
            "required": ["overview", "insights"]
        },
        "strict": True
    }

    response = oai.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "You are a senior performance marketing manager writing month-on-month insight "
            "commentary for a specific data dimension cut (e.g. by Campaign or by Asset). "
            "Write in British English. Be direct and evidence-led. "
            "The comparison is the current month vs. the previous month only. "
            "Use 'previous month' rather than specific dates.\n\n"

            "METRIC TIER HIERARCHY:\n"
            "- Tier 1 (Outcome): ROAS (Ecommerce), CPA (Lead Gen), Transaction Revenue, "
            "Conversions. Lead all points with these where available.\n"
            "- Tier 2 (Efficiency): Conversion Rate, AOV, CPC, CTR.\n"
            "- Tier 3 (Volume): Cost, Clicks, Transactions.\n"
            "- Only reference lower tiers to contextualise Tier 1/2 movements.\n\n"

            "STYLE:\n"
            "- No em dashes (—) anywhere — not in overviews, titles, summaries, or bullets. Use a comma, a conjunction, or split into two sentences instead.\n"
            "- overview: 2-3 sentences giving a top-level summary of the dimension's "
            "month-on-month performance, naming the strongest and weakest performers.\n"
            "- insights: 1-5 entries. Each insight covers a notable pattern or standout "
            "performer within the dimension (e.g. a specific campaign, asset, or group). "
            "title: snappy narrative headline (max 8 words, title-case) — capture the main insight, not just the topic (e.g. 'Brand Campaigns Lead Recovery' not 'Brand Campaign Performance'). summary: one sentence, no em dashes. "
            "bullets: 2-5 evidence-backed supporting points with specific numbers from data_mom. No em dashes.\n"
            "- Acronyms (ROAS, CPA, CTR, AOV, CPC) in all caps.\n"
            "- Do not create an insight for every single dimension value — focus on the "
            "most significant movements.\n"
        ),
        input=[
            {
                "role": "user",
                "content": (
                    "Return JSON exactly matching the schema.\n\n"
                    "dimension_label: the dimension being analysed (e.g. Campaign).\n"
                    "channel_filter: any Ad Channel scoping applied to the data.\n"
                    "data_mom: month-on-month comparison data keyed by dimension value, "
                    "each with curr/prev/delta/pct sub-keys per metric.\n"
                    "account_type: Ecommerce or Lead Gen — use the appropriate primary KPI "
                    "(ROAS for Ecommerce, CPA for Lead Gen).\n\n"
                    "Input JSON:\n"
                    + json.dumps(payload, ensure_ascii=False)
                )
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": schema["name"],
                "schema": schema["schema"],
                "strict": schema["strict"],
            }
        },
    )

    return json.loads(response.output_text)


def generate_mtd_slide_content(client):
    """Generate overview summary + bullets for the current-month TD section (YoY comparison)."""
    payload = {
        "inputs": {
            "paid_data_mtd": client.get('llm_data_mtd', {}),
            "overall_data_mtd": client.get('overall_data_mtd', {}),
            "mtd_start_date": client.get('mtd_start_date_string', ''),
            "mtd_end_date": client.get('mtd_end_date_string', ''),
            "client_context": client.get('client_context', ''),
            "kpis": client.get('kpis', ''),
            "seasonality": client.get('seasonality', ''),
            "client_type": client.get('account_type', 'Ecommerce'),
        }
    }

    schema = {
        "name": "mtd_slide_content",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "mtd_overview": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "summary": {"type": "string"},
                        "bullets": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 6,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {"point": {"type": "string"}},
                                "required": ["point"]
                            }
                        },
                        "bullets_presentation": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {"point": {"type": "string"}},
                                "required": ["point"]
                            }
                        }
                    },
                    "required": ["summary", "bullets", "bullets_presentation"]
                }
            },
            "required": ["mtd_overview"]
        },
        "strict": True,
    }

    response = oai.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "You are a senior performance marketing manager writing a month-to-date performance overview slide.\n"
            "The data covers from the 1st of the current month to two days ago, compared to the same date range last year.\n"
            "Write in British English. Be direct but human. Commentary should be productive, not scathing.\n"
            "Use 'same period last year' for period references — never specific dates.\n\n"

            "METRIC TIER HIERARCHY:\n"
            "- Tier 1 (Outcome): ROAS (Ecommerce), CPA (Lead Gen), Transaction Revenue, Conversions. Lead all points here.\n"
            "- Tier 2 (Efficiency): Conversion Rate, AOV, CPC, CTR, Impression Share.\n"
            "- Tier 3 (Volume): Cost, Clicks, Transactions. Use only to contextualise Tier 1/2.\n\n"

            "STYLE REQUIREMENTS:\n"
            "- summary: 15 words maximum. Hard limit — count the words. Lead with direction, one data point only if it adds something a direction word cannot.\n"
            "- bullets: 3–6 points. Each bullet carries one idea. Include a data point only if it genuinely strengthens the bullet. Max one data point per bullet.\n"
            "- bullets_presentation: 2–3 narrative talking points for the in-room presentation copy. No data points, percentages, figures, or currency values. Direction and narrative only. Each bullet is a complete sentence a presenter can speak aloud.\n"
            "- Acronyms (ROAS, CPA, CTR, AOV) in all caps. Do not capitalise non-acronym metric names.\n"
            "- Note this is a partial month — frame commentary accordingly (e.g. 'month to date').\n"
        ),
        input=[{
            "role": "user",
            "content": (
                "Generate mtd_overview summary, bullets, and bullets_presentation for the month-to-date performance slide.\n"
                "Use paid_data_mtd as the primary source. Comparison is YoY (same days last year).\n"
                "bullets_presentation: 2–3 narrative-only talking points — no data points, no figures. For the presenter to speak aloud in the room.\n"
                "Input JSON:\n"
                + json.dumps(payload, ensure_ascii=False)
            )
        }],
        text={
            "format": {
                "type": "json_schema",
                "name": schema["name"],
                "schema": schema["schema"],
                "strict": schema["strict"],
            }
        },
    )
    return json.loads(response.output_text)


def generate_monthly_slide_content(client):
    payload = {
        "inputs": {
            "plans_90_day": client['plan_json'],
            "paid_data_mom": client['llm_data_mom'],
            "overall_data_mom": client['overall_data_mom'],
            "paid_data_yoy": client['llm_data_yoy'],
            "overall_data_yoy": client['overall_data_yoy'],
            "paid_data_90_day": client['timeseries_data'],
            "report_start_date": client['start_date_string'],
            "report_end_date": client['end_date_string'],
            "run_rate": client['run_rate'],
            "cost_for_month": client['paid_data_mom']['Total']['Cost']['curr'],
            "client_context": client['client_context'],
            "holistic_plans": client['holistic_plans'],
            "paid_plans": client['paid_plans'],
            "kpis": client['kpis'],
            "seasonality": client['seasonality'],
            "historical_context": client['historical_context'],
            "client_type": client['account_type']
        }
    }

    GRAPH_SCHEMA = {
        "dimensions": {
            "x": ["Date", "Week number (ISO)", "Month", "Year"],
            "group_by": ["Ad Platform", "Ad Channel", "Channel", "Campaign"]
        },
        "metrics": {
            "Ecommerce": [
                "Sessions",
                "Impressions",
                "Clicks",
                "Cost",
                "Transactions",
                "Transaction Revenue",
                "CTR",
                "CPC",
                "Conversion Rate",
                "ROAS",
                "AOV",
                "Hook Rate",
                "Hold Rate",
                "Impression Share",
                "Abs. Top Impression Share"
            ],
            "Lead Gen": [
                "Sessions",
                "Impressions",
                "Clicks",
                "Cost",
                "Conversions",
                "CTR",
                "CPC",
                "Conversion Rate",
                "CPA",
                "Hook Rate",
                "Hold Rate",
                "Impression Share",
                "Abs. Top Impression Share"
            ]
        },
        "graph_types": ["line", "bar", "scatter", "stacked_bar", "pie", "line_bar_combo", "horizontal_bar"],
        "styles": ["trend", "comparison", "distribution"]
    }

    VALID_DIMENSIONS = ["Ad Platform", "Ad Channel", "Channel", "Campaign"]
    ts = client.get('timeseries_data', {})
    ts_rows = [
        {'Ad Channel': channel, 'Week number (ISO)': int(week_str)}
        for channel, weeks in ts.items()
        for week_str in weeks.keys()
    ]
    ts_df = pd.DataFrame(ts_rows) if ts_rows else pd.DataFrame()
    dimension_values = {
        col: sorted(ts_df[col].dropna().unique().tolist())
        for col in VALID_DIMENSIONS if col in ts_df.columns
    }

    schema = {
        "name": "monthly_slide_content",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "overview": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "summary": {"type": "string"},
                        "bullets": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 6,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "point": {"type": "string"}
                                },
                                "required": ["point"]
                            }
                        },
                        "bullets_presentation": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "point": {"type": "string"}
                                },
                                "required": ["point"]
                            }
                        }
                    },
                    "required": ["summary", "bullets", "bullets_presentation"]
                },
                "trends": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "bullets": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 4,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "point": {"type": "string"}
                                    },
                                    "required": ["point"]
                                }
                            },
                            "bullets_presentation": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 3,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "point": {"type": "string"}
                                    },
                                    "required": ["point"]
                                }
                            },
                            "graph": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "graph_type": {"type": "string"},
                                    "dimensions": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "x": {"type": "string"},
                                            "group_by": {"type": "string"}
                                        },
                                        "required": ["x", "group_by"]
                                    },
                                    "metrics": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    },
                                    "date_range": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "start": {"type": "string"},
                                            "end": {"type": "string"}
                                        },
                                        "required": ["start", "end"]
                                    },
                                    "filters": {"type": "string"},
                                    "title": {"type": "string"},
                                    "style": {"type": "string"}
                                },
                                "required": ["graph_type", "dimensions", "metrics", "date_range", "filters", "title", "style"]
                            }
                        },
                        "required": ["title", "summary", "bullets", "bullets_presentation", "graph"]
                    }
                },
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "task": {"type": "string"},
                            "summary": {"type": "string"},
                            "status": {"type": "string"},
                            "graph": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "graph_type": {"type": "string"},
                                            "dimensions": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "x": {"type": "string"},
                                                    "group_by": {"type": "string"}
                                                },
                                                "required": ["x", "group_by"]
                                            },
                                            "metrics": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                            },
                                            "date_range": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "start": {"type": "string"},
                                                    "end": {"type": "string"}
                                                },
                                                "required": ["start", "end"]
                                            },
                                            "filters": {"type": "string"},
                                            "title": {"type": "string"},
                                            "style": {"type": "string"}
                                        },
                                        "required": ["graph_type", "dimensions", "metrics", "date_range", "filters", "title", "style"]
                                    },
                                    {"type": "null"}
                                ]
                            }
                        },
                        "required": ["task", "summary", "status", "graph"]
                    }
                }
            },
            "required": ["overview", "trends", "actions"]
        },
        "strict": True
    }

    response = oai.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "You are a senior performance marketing manager producing monthly client-facing slide content.\n"
            "Write in British English. Be direct but human. Commentary should be productive, not scathing.\n"
            "The report must respect the provided report_start_date and report_end_date.\n"

            "IMPORTANT CHANNEL CLASSIFICATION RULES:\n"
            "- Always use channel labels exactly as they appear in the data.\n"
            "- Do not reclassify channels based on platform assumptions.\n"
            "- Do not merge Performance Max into Shopping unless explicitly instructed.\n"
            "- Paid Media refers to total paid performance across all paid channels combined — do not use it for a single sub-channel.\n"
            "- Paid Search is exclusively intent-led text search (RSAs, Microsoft Search). Do not include Shopping or PMax.\n"
            "- Shopping is standard Shopping activity only. Treat as separate from PMax.\n"
            "- Performance Max / Combined is its own channel. Do not merge into Shopping, Search, Display, or Video.\n"
            "- Display and Video are separate channels.\n"
            "- Paid Social is the parent grouping. Paid Social Video and Paid Social Static are sub-categories.\n"

            "DEFINITION OF VARIABLES:\n"
            "- plans_90_day: current and historical 90-day plans, giving context on what has been done and what is planned.\n"
            "- paid_data_mom: PPC performance data comparing the reported month to the previous calendar month (month-on-month). Use this to identify short-term trends and recent momentum.\n"
            "- overall_data_mom: GA4 site-wide data for the same month-on-month comparison window.\n"
            "- paid_data_yoy: PPC performance data comparing the reported month to the same month last year (year-on-year). Use this to identify seasonal patterns and longer-term progress.\n"
            "- overall_data_yoy: GA4 site-wide data for the same year-on-year comparison window.\n"
            "- paid_data_90_day: paid data broken down by week to show performance over the past 90 days.\n"
            "- report_start_date / report_end_date: the bounds of the reporting period (the full calendar month being reported).\n"
            "- run_rate: projected monthly spend. For a full completed month this will be '-' — ignore it in that case.\n"
            "- cost_for_month: total media spend for the reported month.\n"
            "- client_context: background on the client and their offering.\n"
            "- holistic_plans: site-wide goals for the year.\n"
            "- paid_plans: PPC-specific goals for the year.\n"
            "- kpis: the key metrics used to evaluate performance against goals.\n"
            "- seasonality: context on external factors affecting performance.\n"
            "- historical_context: overview of past performance to inform current plans.\n"
            "When choosing which comparison to reference (MoM vs YoY), pick whichever window tells the more insightful story for each individual trend or action. State clearly in the commentary which comparison you are using (e.g. 'vs. the previous month' or 'vs. the same month last year').\n"

            "STYLE REQUIREMENTS:\n"
            "- No em dashes (—) anywhere — not in summaries, bullets, titles, or any other field. This is a hard rule. Use a comma, a conjunction, or split into two sentences instead.\n"
            "- Summaries have a hard limit of 15 words. Count them. This is not a guideline — do not exceed it under any circumstances. Lead with direction, add one supporting data point only if it adds something a direction word cannot.\n"
            "- Bullets carry one idea each. If a point needs two clauses, write two bullets. Do not chain observations with 'while', 'however', 'but', or 'suggesting that'.\n"
            "- Data points in bullets are optional. Include one only if it genuinely makes the bullet stronger. Never add a number just to look thorough. Maximum one data point per bullet.\n"
            "- Use 'current period', 'previous month', or 'previous year' rather than specific dates.\n"
            "- Acronyms (ROAS, CPA, CTR, AOV) in all caps. Do not capitalise non-acronym metric names.\n"
            "- When referencing dates, use British standard format (dd/mm/yyyy).\n"
            "- When referencing volume metrics, account for spend — do not reference conversions or revenue movements in isolation.\n"

            "PRESENTATION BULLETS (bullets_presentation):\n"
            "- For every slide that has bullets, also produce bullets_presentation: narrative talking points for the in-room presentation copy.\n"
            "- No data points, percentages, figures, or currency values of any kind — direction and narrative only.\n"
            "- Each bullet is one idea a presenter can speak aloud confidently in a client meeting. Write it as a complete, natural sentence.\n"
            "- Do not strip numbers from the detailed bullets — write bullets_presentation independently so the narrative flows without data.\n"
            "- overview gets 2–3 presentation bullets. Each trend gets 1–3 presentation bullets.\n\n"

            "GRAPH SCHEMA — you must only use values from this schema when generating graph specs:\n"
            + json.dumps({
                "dimensions": GRAPH_SCHEMA["dimensions"],
                "metrics": GRAPH_SCHEMA["metrics"][client["account_type"]],
                "graph_types": GRAPH_SCHEMA["graph_types"],
                "styles": GRAPH_SCHEMA["styles"],
                "filter_values": dimension_values
            }, ensure_ascii=False) + "\n"
            "- dimensions.x must be one of the values in dimensions.x above.\n"
            "- dimensions.group_by must be one of the values in dimensions.group_by above.\n"
            "- metrics must only contain values from the metrics list above.\n"
            "- line charts must have a maximum of 2 metrics. Do not add a third metric to a line chart — use a different graph type instead.\n"
            "- graph_type must be one of the values in graph_types above.\n"
            "- style must be one of the values in styles above.\n"
            "- filter keys must exactly match a key in filter_values above.\n"
            "- every graph must have a filter, to ensure that only paid data is being used, there must never be a null filter"
            "- filter values must exactly match one of the corresponding values in filter_values above — do not reformat, snake_case, or lowercase them.\n"
            "- Website is a dimension filter value only — do not include it in metrics.\n"
        ),
        input=[
            {
                "role": "user",
                "content": (
                    "Return JSON that matches the schema exactly.\n\n"

                    "DELIVERABLES:\n\n"

                    "1) overview\n"
                    "- summary: the headline paid media story for the period in 15 words or fewer. Hard limit — count the words. Lead with direction, aligned to the client's primary KPI.\n"
                    "- bullets: 3–6 bullet points covering the most important performance movements across paid channels. "
                    "Each bullet carries one idea. Reference a specific channel. Include a data point only if it makes the bullet stronger — not by default. Max one data point per bullet.\n"
                    "- bullets_presentation: 2–3 narrative talking points for the in-room presentation copy. No data points — direction and story only. Each bullet is a complete sentence a presenter can speak aloud.\n\n"

                    "2) trends\n"
                    "Identify the most meaningful trends visible in paid_data_90_day. Each trend gets its own slide.\n"
                    "- title: a snappy, narrative headline for the slide (e.g. 'Paid Search ROAS Bounces Back', 'Social CPA Climbs Under Pressure'). 4–8 words, title-case. Capture the story, not just the topic. No dates.\n"
                    "- summary: 15 words maximum. Hard limit — count the words before submitting. Lead with direction, one supporting data point only if it adds something a direction word cannot. No em dashes.\n"
                    "- bullets: 1–4 supporting points. Each bullet carries one idea — if it needs two clauses, write two bullets. No em dashes anywhere. No chaining with 'while', 'however', or 'suggesting that'. Include a data point only if it genuinely strengthens the bullet. Max one data point per bullet.\n"
                    "- bullets_presentation: 1–3 narrative talking points for the in-room presentation copy. No data points — direction and story only. Each bullet is a complete sentence a presenter can speak aloud.\n"
                    "- graph: every trend must have a graph spec. Choose the graph that best visualises the trend over time using paid_data_90_day. "
                    "Use graph_type 'line' for trends over time, 'bar' for period comparisons. "
                    "Set date_range to cover the full 90-day window. Serialise filters as a JSON string using exact values from filter_values in the graph schema (e.g. '{\"Ad Channel\": \"Paid Search\"}').\n"
                    "Only surface trends with a clear narrative. Do not force trends where data is flat or noisy.\n\n"

                    "3) actions\n"
                    "One entry per task in the current plans_90_day (use only 'current' plans, not 'old').\n"
                    "- task: the task name exactly as it appears in plans_90_day.\n"
                    "- summary: one snappy client-friendly sentence (≤15 words) describing what the task is. No marketing fluff.\n"
                    "- status: the status exactly as it appears in plans_90_day.\n"
                    "- graph: if status is 'Complete', generate a graph spec that best illustrates the impact or context of this task. "
                    "If status is not 'Complete', set graph to null.\n"
                    "Serialise filters as a JSON string using exact values from filter_values in the graph schema (e.g. '{\"Ad Channel\": \"Paid Search\"}').\n"
                    "Choose graph_type, metrics, and style based on what would most clearly evidence the completed task's outcome.\n\n"

                    "Input JSON:\n"
                    + json.dumps(payload, ensure_ascii=False)
                )
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": schema["name"],
                "schema": schema["schema"],
                "strict": schema["strict"],
            }
        },
    )

    return json.loads(response.output_text)