import json
from openai import OpenAI

with open("storage/secrets.json", "r") as f:
    secrets = json.load(f)
oai = OpenAI(api_key=secrets["openai_key"])


def generate_commentary(client):
    payload = {
        "inputs": {
            "plans_90_day": client['plan_json'],
            "paid_data": client['llm_data'],
            "overall_data": client['overall_data'],
            "paid_data_90_day": client['timeseries_data'],
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
            "DEFINITION OF VAIRABLES:"
            "- plans_90_day: this is a json object that contains the plans for the current period as well as the plans from previous periods, giving you context on what we have done and what we are planning to do.\n"
            "- paid_data: this is a json object that has all of the ppc data (e.g. Google ads) from the current period, compared to our comparison period. This has the data that we need to translate into insights, so it is the most importnat variable that you should factor in"
            "- overall_data: this is a json object that has the overall site data, taken from GA4, from the current period, compared to our comparison period. This should be used for extra context for paid data so that we can compare it to other channels, like Organic, and lets us review how holistic plans are performing\n"
            "- paid_data_90_day: this is the paid data broken down by week number to give a view of how the data has fluctuated over the past 90 days"
            "- report_start_date: This is the date where the reporting period begins/\n"
            "- report_end_date: This is the date where the reporting period ends\n"
            "- monthly_budget: this is the monthly budget for the current reporting period\n"
            "- run_rate: this is the current run rate for the period"
            "- cost_to_date: this is the total media spend for the current month"
            "- reporting_period: this states the period of the report and states the data we are using as comparison. It can be one of three things:\n" \
            "   - MTD Yearly Comparison: this means that the data period is month to date, and the comparison is the same date range last year\n"
            "   - MTD Monthly Comparison: this means that the data period is month to date, and the comparison is the same date range last month\n"
            "   - WTD Weekly Comparison: this means that the data period is week to date, is 7 day period prior to the last 7 day period\n"
            "- client_context: this is context on the client and what their offering is"
            "- holistic_plans: these are the goals for the entire website for the current year, we are striving to achieve these goals for our clients"
            "- paid_plans: these are the goals for the ppc channel for the current year, we are striving to achieve these goals for our clients within the context of ppc channels"
            "- kpis: these are the key performance indicators we are using to measure how the effectively we are achieving the goals that we are trying to hit"
            "- seasonality: this is extra context for the account based on how it performs within the context of external factors"
            "- historical_context: this is an overview on the performance on the account over previous years, giving extra context as to why we have made these plans"
            
            "It is essential that the context provided through the 'holistic_plans', 'paid_plans', 'kpis', 'seasonality' and 'historical_context' are used. We are comparing ourselves to ourselves and we want to stay algined to or goals for the year\n"
            "When looking at volume metrics, make sure that we are comparing it to the amount we've spent, if conversions or transaction revenue is down, then we need to account for the cost as the interplay between volume metrics and cost are too important to just reference volume metrics on their own\n"
            "When referring to data in a point, make sure that we are identfying where that data has come from, is it from the paid dataset, or the overall dataset? Furthermore, if we are referencing data from a specific dimension, make sure that is stated in the commentary\n"
            "When using the comparisons, make sure that we are referring to the correct period, so if the comparison period is monthly, we are comparing to 'last month', if the compariosn period is yearly, we are comparing to 'last year', etc.\n"

            "STYLE REQUIREMENTS:\n"
            "- Write paragraphs (human readable) for the summaries, not bullet lists.\n"
            "- Evidence must be specific numbers from the performance / ga4_context inputs (e.g., revenue, ROAS, CPA, CR, AOV, spend).\n"
            "- When comparing two data points from different time periods, ensure that the right comparison is used, the comparison can be found in 'comparison_period', if it is 'yoy' then we are comparing year on year, if it is 'mom' then we are comparing month on month\n"
            "- Avoid using dates when referring to periods, use 'current period' and if comparing to the previous period use 'previous month' or 'previous year' (depending on the 'comparison_period' field,if it is 'yoy' then we are comparing year on year, if it is 'mom' then we are comparing month on month) \n"
            "- Explicitly reference the 90-day plan where relevant: if an initiative from plans_90_day plausibly links to a performance movement, call it out and explain the linkage. If you can’t find a relevant plan item, then don't reference it.\n"
            "- For each performance point, include a 2-3 sentence summary that combines all the points, this will be the part that gets sent to the client.\n"
            "- For acronyms (e.g. ROAS, TBD) style in all caps, make sure this is only for acronyms, not all metric names\n"
            "- when referencing dates, don't use iso format, use brtish standard date format (dd/mm/yyyy)\n"
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
                                "- Start_date, end_date: convert these from iso format into the british standard date format (dd/mm/yyyy)\n"
                                "- Summary: this is a more basic client friendly version of the description, make it a one sentence summary that is to the point and not wrapped in marketing fluff\n"
                                "- Ensure that the plans that are being used are 'current', not 'old' plans"
                        "2) performance_overview:\n"
                            "- A 2-4 sentence summary of paid_data and overall_data compared to the the 'holistic_plans' and 'paid_plans' how are we doing when it comes to achieving these goals. We want the focus to be on paid points, but frame it within the context of the holistic plans and the overall data we are seeing on the webstie\n"
                            "- When bringing in actual data from paid_data and overall_data, only use data that explicitly aligns with the kpis that have been given to you is the 'kpis' secion.\n"
                            "- You are allowed to use data to back up the statements, but be sparing, this is a quick human readable paaragraph for stakeholders\n"
                            "- Include a sentence on current spend to date. Use cost_to_date for the total spend this month, run_rate to see what the predicted cost at the end of the month, and budget to find the monthly budget for the client.\n"
                        "3) ninety day summary\n"
                            "- A 2-4 sentence summary of paid_data_90_day that just gives a top level overview of performance data over the past 90 days. We don't want specifics, we just want a view of the trends in the past 90 days"
                            "- Don't make it metric soup, just focus on the main KPI for the client (e.g. Transaction Revneue) and give an overview on how it has changed and what has driven the change"
                        "4) performance_points: \n"
                            "Goal: produce high-signal points that explain what’s happening by ad channel (use paid_data at the ad channel level, not ad platform - do not use overall_data to create specific points), points must be centred around the metric groups below, we must absolutely not use specific metrics as the main theme of the point\n"
                            "- Use only these metric groups as the theme for a point (do not create points about single metrics) "
                                "- Volume: Impressions, Clicks, Cost, Views, Thruplays, Conversions, Transactions, Transaction Revenue"
                                "- Performance: CPA, ROAS, Conversion Rate, AOV"
                                "- Engagement: CTR, View Rate, Hook Rate, Hold Rate"
                                "- Efficiency: CPC, Impression Share, Abs. Top Impression Share"
                            "Each point should have the following structure:\n"
                            "- title: <Ad Channel> <Metric Group> <Clear Direction/Outcome> (max ~8 words)\n"
                            "- summary: 2–4 sentences. Explain what changed and what it implies, include evidence 1-2 supporting specific metrics, you can also reference data from the overall_data section to add extra context, it isn't essential to use overall_data, just use it where necessary.\n"
                            "- Point selection rules (prioritisation):\n"
                                "- Prioritise channels with the largest spend and/or largest outcome impact (Conversions, Revenue, CPA, ROAS).\n"
                                "- Prefer changes with clear narrative (e.g. Volume up + Performance stable; Performance down despite Volume up).\n"
                                "- Avoid “metric soup”: pick the minimum evidence needed to prove the point.\n"
                            "- Thresholds (to avoid noise):\n"
                                "- Only create a point if at least one supporting metric has ≥10% relative change, or the channel is ≥20% of total cost, or there is a clear multi-metric pattern within the same group.\n"
                                "- For low-spend channels (<10% of cost), require ≥20% change to mention unless it materially affects overall results.\n"
                            "- Context: \n"
                                "- You may reference overall_data only when it strengthens the story (e.g. “this channel drove the overall change”).\n"
                                "- If paid_data[<channel>].total exists you may use it, but don’t rely on it if it hides important opposing movements.\n"
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