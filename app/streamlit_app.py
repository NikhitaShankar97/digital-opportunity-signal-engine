from pathlib import Path
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st


# ---------------------------------------------------------
# Project setup
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import run


st.set_page_config(
    page_title="Digital Signal Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------
# Visual styling
# ---------------------------------------------------------

st.markdown(
    """
    <style>
        .stApp {
            background-color: #F6F8FC;
        }

        .block-container {
            max-width: 1240px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }

        [data-testid="stSidebar"] {
            background-color: #0B1830;
        }

        [data-testid="stSidebar"] * {
            color: #FFFFFF;
        }

        [data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E4EAF2;
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 4px 14px rgba(16, 42, 67, 0.05);
        }

        .hero {
            padding: 26px 30px;
            border-radius: 18px;
            background: linear-gradient(120deg, #102A43 0%, #175CD3 100%);
            color: white;
            margin-bottom: 22px;
        }

        .hero h1 {
            color: white;
            margin: 0;
            font-size: 2.1rem;
        }

        .hero p {
            color: #DCE9FF;
            margin: 8px 0 0;
            font-size: 1rem;
        }

        .insight-card {
            background: #FFFFFF;
            border: 1px solid #E4EAF2;
            border-left: 5px solid #FF6B5E;
            border-radius: 12px;
            padding: 18px 20px;
            margin: 8px 0 20px;
        }

        .section-label {
            color: #52677D;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }

        .small-note {
            color: #627D98;
            font-size: 0.85rem;
        }

        h1, h2, h3 {
            color: #102A43;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid #E4EAF2;
            border-radius: 12px;
            overflow: hidden;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Load validated project data
# ---------------------------------------------------------

signals, issues = run(ROOT)

complete = signals[
    signals["record_status"].eq("complete")
].copy()

countries = pd.read_csv(
    ROOT / "data/raw/country_traffic.csv"
)

audience = pd.read_csv(
    ROOT / "data/raw/audience_demographics.csv"
)

company_colors = {
    "Rare Beauty": "#7C3AED",
    "Rhode": "#175CD3",
    "Glossier": "#FF6B5E",
}


# ---------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------

def percentile_score(series, higher_is_better=True):
    """Convert a metric into a peer-relative score."""

    rank = series.rank(
        method="average",
        pct=True,
    )

    if higher_is_better:
        return rank * 100

    return (
        1
        - rank
        + (1 / len(series))
    ) * 100


def calculate_scores(
    data,
    momentum_weight,
    engagement_weight,
    scale_weight,
):
    """Recalculate scores using the selected weights."""

    result = data.copy()

    result["momentum_score"] = percentile_score(
        result["mom_change_pct"]
    )

    pages_score = percentile_score(
        result["pages_per_visit"]
    )

    duration_score = percentile_score(
        result["avg_visit_duration_seconds"]
    )

    bounce_score = percentile_score(
        result["bounce_rate_pct"],
        higher_is_better=False,
    )

    result["engagement_depth_score"] = (
        pages_score
        + duration_score
        + bounce_score
    ) / 3

    result["traffic_scale_score"] = percentile_score(
        result["monthly_visits"]
    )

    result["opportunity_score"] = (
        result["momentum_score"] * momentum_weight
        + result["engagement_depth_score"] * engagement_weight
        + result["traffic_scale_score"] * scale_weight
    ).round(2)

    result["classification"] = pd.cut(
        result["opportunity_score"],
        bins=[-1, 45, 70, 101],
        labels=["Watch", "Investigate", "Priority"],
        right=False,
    )

    return result


def format_visits(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"

    if value >= 1_000:
        return f"{value / 1_000:.1f}K"

    return f"{value:,.0f}"


def format_duration(seconds):
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    return f"{minutes}:{remaining_seconds:02d}"


def style_figure(figure, height=380):
    figure.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=55, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Arial",
            color="#334E68",
        ),
        legend_title_text="",
    )

    figure.update_xaxes(
        showgrid=True,
        gridcolor="#E8EDF4",
        zeroline=False,
    )

    figure.update_yaxes(
        showgrid=False,
        zeroline=False,
    )

    return figure


def build_leader_explanation(leader):
    strongest_component = max(
        {
            "traffic momentum": leader["momentum_score"],
            "visitor engagement": leader["engagement_depth_score"],
            "traffic scale": leader["traffic_scale_score"],
        },
        key=lambda item: {
            "traffic momentum": leader["momentum_score"],
            "visitor engagement": leader["engagement_depth_score"],
            "traffic scale": leader["traffic_scale_score"],
        }[item],
    )

    return (
        f"{leader['company']} currently ranks first with an "
        f"opportunity score of {leader['opportunity_score']:.2f}. "
        f"Its strongest relative signal is {strongest_component}. "
        f"Traffic changed {leader['mom_change_pct']:+.1f}% during the "
        f"latest observed month. This result prioritizes further "
        f"research and is not an investment recommendation."
    )


default_scores = calculate_scores(
    complete,
    momentum_weight=0.40,
    engagement_weight=0.35,
    scale_weight=0.25,
)


def build_ai_context(selected_company):
    """Prepare a small, validated data package for the research copilot."""

    score_columns = [
        "company", "monthly_visits", "mom_change_pct", "bounce_rate_pct",
        "pages_per_visit", "avg_visit_duration_seconds", "global_rank",
        "country_rank", "category_rank", "leading_channel",
        "leading_channel_share_pct", "organic_search_within_search_pct",
        "paid_search_within_search_pct", "momentum_score",
        "engagement_depth_score", "traffic_scale_score",
        "opportunity_score", "confidence_score", "classification",
    ]
    company_scores = default_scores[score_columns].copy()
    selected_domain = default_scores.loc[
        default_scores["company"].eq(selected_company), "domain"
    ].iloc[0]
    selected_countries = countries[countries["domain"].eq(selected_domain)]
    selected_audience = audience[audience["domain"].eq(selected_domain)]

    return {
        "observation_month": "July 2026",
        "collection_date": "August 16, 2026",
        "selected_company": selected_company,
        "company_scores": company_scores.where(
            pd.notna(company_scores), None
        ).to_dict(orient="records"),
        "selected_company_countries": selected_countries.where(
            pd.notna(selected_countries), None
        ).to_dict(orient="records"),
        "selected_company_audience": selected_audience.where(
            pd.notna(selected_audience), None
        ).to_dict(orient="records"),
        "scoring_weights": {
            "momentum": 0.40,
            "engagement_depth": 0.35,
            "traffic_scale": 0.25,
        },
    }


def call_deepseek(system_prompt, user_prompt):
    """Call DeepSeek only after a deliberate user action."""

    api_key = st.secrets.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DeepSeek API key is not configured.")

    request_body = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # These are short analyst summaries, so use the lower-cost
        # non-thinking mode and reserve the token budget for the final answer.
        "thinking": {"type": "disabled"},
        "temperature": 0.2,
        "max_tokens": 800,
        "stream": False,
    }
    request = Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"DeepSeek returned HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            "The DeepSeek service could not be reached. Please try again."
        ) from error

    choice = result["choices"][0]
    content = (choice["message"].get("content") or "").strip()

    if not content:
        finish_reason = choice.get("finish_reason", "unknown")
        raise RuntimeError(
            "DeepSeek returned no final answer "
            f"(finish reason: {finish_reason}). Please try again."
        )

    return content


# ---------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------

with st.sidebar:
    st.markdown("## Signal Engine")

    st.caption(
        "Digital intelligence for research prioritization"
    )

    page = st.radio(
        "Navigate",
        [
            "Executive Overview",
            "Company Explorer",
            "Scenario Simulator",
            "AI Research Copilot",
            "Data Trust",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    st.markdown("### Observation")

    st.write("July 2026")

    st.caption(
        "Public Similarweb estimates collected "
        "August 16, 2026"
    )

    with st.expander("Quick glossary"):
        st.markdown(
            """
            **Momentum:** Recent website traffic growth or decline.

            **Engagement:** How deeply visitors interact with the website.

            **Scale:** The relative size of the website audience.

            **Peer-relative:** Compared only with the other companies in this analysis.

            **Opportunity score:** A research-priority score, not an investment rating.

            **Confidence:** Strength of the available evidence, not estimate accuracy.
            """
        )

    st.markdown("---")

    st.caption(
        "Proof of concept. Not investment advice."
    )


# ---------------------------------------------------------
# Shared page header
# ---------------------------------------------------------

st.markdown(
    """
    <div class="hero">
        <h1>Digital Opportunity Signal Engine</h1>
        <p>
            Turn digital behavior into a transparent and reusable
            company-research priority.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Executive Overview
# ---------------------------------------------------------

if page == "Executive Overview":
    ranked = default_scores.sort_values(
        "opportunity_score",
        ascending=False,
    )

    leader = ranked.iloc[0]

    st.markdown(
        '<div class="section-label">Current decision</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        f"Research priority: {leader['company']}"
    )

    st.markdown(
        f"""
        <div class="insight-card">
            {build_leader_explanation(leader)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)

    metric_1.metric(
        "Leading company",
        leader["company"],
    )

    metric_2.metric(
        "Opportunity score",
        f"{leader['opportunity_score']:.2f}",
        help=(
            "A peer-relative score used to prioritize companies for further "
            "research. It combines traffic momentum, visitor engagement and "
            "traffic scale."
        ),
    )

    metric_3.metric(
        "Observed visits",
        format_visits(leader["monthly_visits"]),
        delta=f"{leader['mom_change_pct']:+.1f}% vs previous month",
        help="Estimated website visits during the latest observed month.",
    )

    metric_4.metric(
        "Confidence",
        f"{leader['confidence_score']:.0f}%",
        help=(
            "Describes data completeness, peer coverage, source type and "
            "available history. It does not measure the accuracy of Similarweb estimates."
        ),
    )

    left, right = st.columns(
        [1.25, 1],
        gap="large",
    )

    with left:
        score_chart = px.bar(
            ranked.sort_values(
                "opportunity_score"
            ),
            x="opportunity_score",
            y="company",
            orientation="h",
            color="company",
            color_discrete_map=company_colors,
            text="opportunity_score",
            title="Current research-priority ranking",
            labels={
                "opportunity_score": "Opportunity score",
                "company": "",
            },
            range_x=[0, 100],
        )

        score_chart.update_traces(
            texttemplate="%{text:.2f}",
            textposition="outside",
        )

        score_chart.update_layout(
            showlegend=False,
        )

        st.plotly_chart(
            style_figure(score_chart),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with right:
        component_data = ranked[
            [
                "company",
                "momentum_score",
                "engagement_depth_score",
                "traffic_scale_score",
            ]
        ].melt(
            id_vars="company",
            var_name="Signal",
            value_name="Score",
        )

        component_data["Signal"] = component_data[
            "Signal"
        ].replace(
            {
                "momentum_score": "Momentum",
                "engagement_depth_score": "Engagement",
                "traffic_scale_score": "Scale",
            }
        )

        component_chart = px.bar(
            component_data,
            x="company",
            y="Score",
            color="Signal",
            barmode="group",
            title="What drives each company’s score",
            labels={"company": ""},
            color_discrete_map={
                "Momentum": "#7C3AED",
                "Engagement": "#175CD3",
                "Scale": "#FF6B5E",
            },
        )

        st.plotly_chart(
            style_figure(component_chart),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    display_table = ranked[
        [
            "company",
            "opportunity_score",
            "confidence_score",
            "classification",
            "monthly_visits",
            "mom_change_pct",
        ]
    ].copy()

    display_table.columns = [
        "Company",
        "Opportunity Score",
        "Confidence",
        "Classification",
        "Monthly Visits",
        "Monthly Change %",
    ]

    st.dataframe(
        display_table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Opportunity Score": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.2f",
            ),
            "Monthly Visits": st.column_config.NumberColumn(
                format="compact",
            ),
            "Monthly Change %": st.column_config.NumberColumn(
                format="%.2f%%",
                help="Change in estimated visits compared with the previous month.",
            ),
        },
    )


# ---------------------------------------------------------
# Company Explorer
# ---------------------------------------------------------

elif page == "Company Explorer":
    selected_company = st.selectbox(
        "Select a company",
        default_scores["company"].tolist(),
    )

    company_row = default_scores[
        default_scores["company"].eq(selected_company)
    ].iloc[0]

    domain = company_row["domain"]

    st.markdown(
        '<div class="section-label">Company profile</div>',
        unsafe_allow_html=True,
    )

    st.subheader(selected_company)

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)

    metric_1.metric(
        "Monthly visits",
        format_visits(company_row["monthly_visits"]),
        delta=f"{company_row['mom_change_pct']:+.1f}% vs previous month",
        help="Estimated website visits during the latest observed month.",
    )

    metric_2.metric(
        "Pages per visit",
        f"{company_row['pages_per_visit']:.2f}",
    )

    metric_3.metric(
        "Average visit duration",
        format_duration(
            company_row["avg_visit_duration_seconds"]
        ),
    )

    metric_4.metric(
        "Bounce rate",
        f"{company_row['bounce_rate_pct']:.2f}%",
        help=(
            "The percentage of visits that ended without the visitor continuing "
            "to another page. A lower rate generally indicates stronger engagement."
        ),
    )

    left, right = st.columns(2, gap="large")

    with left:
        company_countries = countries[
            countries["domain"].eq(domain)
        ].sort_values(
            "desktop_traffic_share_pct",
            ascending=True,
        )

        geography_chart = px.bar(
            company_countries,
            x="desktop_traffic_share_pct",
            y="country",
            orientation="h",
            title="Desktop traffic by country",
            labels={
                "desktop_traffic_share_pct": "Traffic share %",
                "country": "",
            },
            color_discrete_sequence=[
                company_colors[selected_company]
            ],
            text="desktop_traffic_share_pct",
        )

        geography_chart.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
        )

        st.plotly_chart(
            style_figure(geography_chart),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with right:
        peer_comparison = default_scores[
            [
                "company",
                "momentum_score",
                "engagement_depth_score",
                "traffic_scale_score",
            ]
        ].copy()

        peer_comparison = peer_comparison.melt(
            id_vars="company",
            var_name="Signal",
            value_name="Score",
        )

        peer_comparison["Signal"] = peer_comparison[
            "Signal"
        ].replace(
            {
                "momentum_score": "Momentum",
                "engagement_depth_score": "Engagement",
                "traffic_scale_score": "Scale",
            }
        )

        peer_chart = px.line(
            peer_comparison,
            x="Signal",
            y="Score",
            color="company",
            markers=True,
            title="Signal profile against peers",
            color_discrete_map=company_colors,
        )

        peer_chart.update_traces(
            line=dict(width=3),
            marker=dict(size=9),
        )

        st.plotly_chart(
            style_figure(peer_chart),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    st.subheader("Audience and acquisition")

    audience_row = audience[
        audience["domain"].eq(domain)
    ].iloc[0]

    audience_1, audience_2, audience_3 = st.columns(3)

    audience_1.metric(
        "Female audience",
        f"{audience_row['female_pct']:.2f}%",
    )

    audience_2.metric(
        "Male audience",
        f"{audience_row['male_pct']:.2f}%",
    )

    audience_3.metric(
        "Largest age group",
        audience_row["largest_age_group"],
    )

    acquisition_1, acquisition_2, acquisition_3 = st.columns(3)

    acquisition_1.metric(
        "Leading channel",
        company_row["leading_channel"],
    )

    acquisition_2.metric(
        "Leading channel share",
        f"{company_row['leading_channel_share_pct']:.2f}%",
    )

    acquisition_3.metric(
        "Organic share of search",
        f"{company_row['organic_search_within_search_pct']:.2f}%",
        help=(
            "The percentage of search-driven visits that came from unpaid search "
            "results rather than paid search advertisements."
        ),
    )

    st.caption(
        "Country and acquisition metrics represent desktop traffic. "
        "The organic-versus-paid figures describe search traffic only."
    )


# ---------------------------------------------------------
# Scenario Simulator
# ---------------------------------------------------------

elif page == "Scenario Simulator":
    st.markdown(
        '<div class="section-label">Interactive assumptions</div>',
        unsafe_allow_html=True,
    )

    st.subheader("Test a different research strategy")

    st.write(
        "Adjust how much importance the research team places on "
        "traffic momentum, visitor engagement and audience scale."
    )

    if "momentum_weight" not in st.session_state:
        st.session_state["momentum_weight"] = 40

    if "engagement_weight" not in st.session_state:
        st.session_state["engagement_weight"] = 35

    if "scale_weight" not in st.session_state:
        st.session_state["scale_weight"] = 25

    slider_1, slider_2, slider_3 = st.columns(3)

    with slider_1:
        momentum_input = st.slider(
            "Momentum importance",
            min_value=0,
            max_value=100,
            key="momentum_weight",
            help="How much traffic growth or decline should influence the final score?",
        )

    with slider_2:
        engagement_input = st.slider(
            "Engagement importance",
            min_value=0,
            max_value=100,
            key="engagement_weight",
            help=(
                "How much pages per visit, visit duration and bounce rate should "
                "influence the final score?"
            ),
        )

    with slider_3:
        scale_input = st.slider(
            "Traffic scale importance",
            min_value=0,
            max_value=100,
            key="scale_weight",
            help="How much audience size should influence the final score?",
        )

    total_input = (
        momentum_input
        + engagement_input
        + scale_input
    )

    if total_input == 0:
        st.error(
            "At least one weight must be greater than zero."
        )

        st.stop()

    momentum_weight = momentum_input / total_input
    engagement_weight = engagement_input / total_input
    scale_weight = scale_input / total_input

    effective_1, effective_2, effective_3 = st.columns(3)

    effective_1.metric(
        "Effective momentum weight",
        f"{momentum_weight:.0%}",
    )

    effective_2.metric(
        "Effective engagement weight",
        f"{engagement_weight:.0%}",
    )

    effective_3.metric(
        "Effective scale weight",
        f"{scale_weight:.0%}",
    )

    if st.button("Reset to default weights"):
        st.session_state["momentum_weight"] = 40
        st.session_state["engagement_weight"] = 35
        st.session_state["scale_weight"] = 25
        st.rerun()

    scenario_scores = calculate_scores(
        complete,
        momentum_weight,
        engagement_weight,
        scale_weight,
    ).sort_values(
        "opportunity_score",
        ascending=False,
    )

    default_lookup = default_scores[
        ["domain", "opportunity_score"]
    ].rename(
        columns={
            "opportunity_score": "default_score"
        }
    )

    scenario_scores = scenario_scores.merge(
        default_lookup,
        on="domain",
        how="left",
    )

    scenario_scores["score_change"] = (
        scenario_scores["opportunity_score"]
        - scenario_scores["default_score"]
    ).round(2)

    scenario_leader = scenario_scores.iloc[0]

    st.markdown(
        f"""
        <div class="insight-card">
            Under this scenario, <strong>{scenario_leader['company']}</strong>
            ranks first with a score of
            <strong>{scenario_leader['opportunity_score']:.2f}</strong>.
            The result changes automatically as the weights change.
        </div>
        """,
        unsafe_allow_html=True,
    )

    scenario_chart = px.bar(
        scenario_scores.sort_values(
            "opportunity_score"
        ),
        x="opportunity_score",
        y="company",
        orientation="h",
        color="company",
        color_discrete_map=company_colors,
        text="opportunity_score",
        title="Scenario ranking",
        labels={
            "opportunity_score": "Opportunity score",
            "company": "",
        },
        range_x=[0, 100],
    )

    scenario_chart.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
    )

    scenario_chart.update_layout(
        showlegend=False,
    )

    st.plotly_chart(
        style_figure(scenario_chart),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    scenario_table = scenario_scores[
        [
            "company",
            "opportunity_score",
            "default_score",
            "score_change",
            "classification",
        ]
    ].copy()

    scenario_table.columns = [
        "Company",
        "Scenario Score",
        "Default Score",
        "Score Change",
        "Classification",
    ]

    st.dataframe(
        scenario_table,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# AI Research Copilot
# ---------------------------------------------------------

elif page == "AI Research Copilot":
    st.markdown(
        '<div class="section-label">Grounded AI interpretation</div>',
        unsafe_allow_html=True,
    )
    st.subheader("Ask the validated data a business question")
    st.write(
        "The copilot explains results that were already calculated by the "
        "deterministic scoring pipeline. It does not calculate scores or make "
        "investment decisions."
    )

    ai_key_available = bool(st.secrets.get("DEEPSEEK_API_KEY"))
    if not ai_key_available:
        st.info(
            "The AI page is ready but disabled until a DeepSeek API key is added "
            "through Streamlit secrets. The key should never be placed in this file."
        )
        with st.expander("How to enable the copilot"):
            st.markdown(
                """
                1. Create a file named `.streamlit/secrets.toml` in the project folder.
                2. Add `DEEPSEEK_API_KEY = "your-key-here"`.
                3. Keep `.streamlit/secrets.toml` out of GitHub.
                4. For Streamlit Community Cloud, add the same value in the app's Secrets settings.
                """
            )

    ai_company = st.selectbox(
        "Company to focus on",
        default_scores["company"].tolist(),
        key="ai_company",
    )
    ai_task = st.selectbox(
        "Research task",
        [
            "Explain this company's score",
            "Compare all three companies",
            "Generate diligence questions",
            "Ask a custom question",
        ],
        help=(
            "The copilot receives only the validated metrics stored in this project. "
            "It does not browse the web or access private company information."
        ),
    )

    custom_question = ""
    if ai_task == "Ask a custom question":
        custom_question = st.text_area(
            "Question",
            placeholder=(
                "Example: Why does Rare Beauty rank above Rhode even though "
                "Rhode has more website visits?"
            ),
            max_chars=500,
        )

    if "ai_calls" not in st.session_state:
        st.session_state["ai_calls"] = 0

    remaining_calls = max(10 - st.session_state["ai_calls"], 0)
    usage_placeholder = st.empty()
    usage_placeholder.caption(
        f"Session usage limit: {remaining_calls} of 10 AI requests remaining."
    )

    run_ai = st.button(
        "Generate analyst briefing",
        type="primary",
        disabled=(not ai_key_available or remaining_calls == 0),
    )

    if run_ai:
        if ai_task == "Ask a custom question" and not custom_question.strip():
            st.warning("Enter a question before generating the briefing.")
        else:
            context = build_ai_context(ai_company)
            task_prompts = {
                "Explain this company's score": (
                    f"Explain why {ai_company} received its opportunity score. "
                    "Identify its strongest and weakest signals and state the next research step."
                ),
                "Compare all three companies": (
                    "Compare the three companies across momentum, engagement and scale. "
                    "Explain the trade-offs and why the current ranking is reasonable."
                ),
                "Generate diligence questions": (
                    f"Generate the three highest-priority diligence questions for {ai_company}. "
                    "For each one, use the headings Question, Why it matters, and "
                    "What to validate next. Tie the rationale to a specific observed "
                    "metric or stated data limitation."
                ),
                "Ask a custom question": custom_question.strip(),
            }
            system_prompt = (
                "You are a research copilot inside a digital-intelligence proof of concept. "
                "Use only the structured data supplied by the application. Do not invent facts, "
                "browse, or imply access to first-party analytics. Clearly distinguish observed "
                "metrics from hypotheses and recommended validation. Never present a possible cause "
                "as an established cause. The monthly_visits value is the current month's estimate, "
                "not the previous month's baseline. Do not combine separate audience measures into "
                "a joint segment: female_pct and largest_age_group are separate observations. Keep "
                "total traffic share separate from organic-versus-paid share within search. If the "
                "data cannot support a conclusion, say what additional data is required. Do not use "
                "words such as statistically significant or significant unless a statistical test "
                "was performed. Translate internal field names such as momentum_score into natural "
                "business labels such as momentum score. Describe percentile scores as relative to "
                "this three-company peer set, not as absolute strength or weakness. Keep the answer "
                "under 400 words, prioritize decision relevance over generic ideas, and never present "
                "the result as investment advice. If the user directly asks what to invest in, which "
                "company to buy, or for an investment recommendation, explicitly state that this tool "
                "cannot make that selection. You may identify the current digital research priority, "
                "but clearly distinguish it from an investment recommendation and list the financial, "
                "valuation, conversion, retention and multi-month evidence still required."
            )
            user_prompt = (
                f"Task: {task_prompts[ai_task]}\n\n"
                f"Validated project data:\n{json.dumps(context, default=str)}"
            )

            with st.spinner("Generating a grounded analyst briefing..."):
                try:
                    ai_response = call_deepseek(system_prompt, user_prompt)
                    st.session_state["ai_calls"] += 1
                    updated_remaining = max(
                        10 - st.session_state["ai_calls"], 0
                    )
                    usage_placeholder.caption(
                        "Session usage limit: "
                        f"{updated_remaining} of 10 AI requests remaining."
                    )
                    st.markdown("### Analyst briefing")
                    st.markdown(ai_response)
                    st.caption(
                        "Generated by DeepSeek from the validated project data shown above. "
                        "Review before using in research."
                    )
                except (ValueError, RuntimeError) as error:
                    st.error(str(error))


# ---------------------------------------------------------
# Data Trust
# ---------------------------------------------------------

elif page == "Data Trust":
    st.markdown(
        '<div class="section-label">Data governance</div>',
        unsafe_allow_html=True,
    )

    st.subheader("Why the results can be traced")

    error_count = len(
        [
            issue
            for issue in issues
            if issue["severity"] == "error"
        ]
    )

    trust_1, trust_2, trust_3, trust_4 = st.columns(4)

    trust_1.metric(
        "Company records",
        len(complete),
    )

    trust_2.metric(
        "Country records",
        len(countries),
    )

    trust_3.metric(
        "Validation errors",
        error_count,
    )

    trust_4.metric(
        "Observation months",
        complete["observation_month"].nunique(),
    )

    if error_count == 0:
        st.success(
            "All required observations passed the configured checks."
        )
    else:
        st.error(
            f"{error_count} validation errors require attention."
        )

    left, right = st.columns(2, gap="large")

    with left:
        st.subheader("Validation coverage")

        st.markdown(
            """
            - Duplicate company-month records
            - Missing required scoring metrics
            - Percentages outside the 0 to 100 range
            - Negative traffic and engagement measurements
            - Incomplete public observations
            """
        )

    with right:
        st.subheader("Known limitations")

        st.markdown(
            """
            - Only one observation month is available
            - The peer set contains three companies
            - Similarweb values are third-party estimates
            - Some public channel percentages are unavailable
            - Geography and channel metrics use desktop traffic
            """
        )

    st.subheader("Source register")

    source_table = complete[
        [
            "company",
            "observation_month",
            "collection_date",
            "geography",
            "device_scope",
            "source_url",
        ]
    ].copy()

    source_table.columns = [
        "Company",
        "Observation Month",
        "Collection Date",
        "Geography",
        "Device Scope",
        "Source",
    ]

    st.dataframe(
        source_table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Source": st.column_config.LinkColumn(
                display_text="Open Similarweb source"
            )
        },
    )

    st.subheader("Scoring methodology")

    st.write(
        "The default opportunity score combines 40% traffic momentum, "
        "35% engagement depth and 25% traffic scale. The score compares "
        "companies only within this peer set."
    )

    st.info(
        "The 84% confidence score describes data completeness, peer "
        "coverage, source type and available history. It does not mean "
        "that the Similarweb estimates are 84% accurate."
    )


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

st.markdown("---")

st.markdown(
    """
    <p class="small-note">
        Public Similarweb estimates collected on August 16, 2026.
        This proof of concept supports research prioritization and
        does not provide investment advice.
    </p>
    """,
    unsafe_allow_html=True,
)
