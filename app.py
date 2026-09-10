"""
AgriScope-India — single consolidated dashboard.
Tabs: Fertilizer Optimizer | District Map & Yield | EDA | Live Feed
"""
import json
import os
from datetime import date
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

from src.fertilizer_reference import (
    get_dose_options, list_known_crops, PRICE_LAST_VERIFIED,
)
from src.cost_calculator import compute_fertilizer_plan
from src.yield_model import (
    list_crops, crop_history, predict_yield, load_odisha_data,
    load_recent_official_data,
)
from src.live_data import get_agmarknet_daily_prices, get_live_weather

DATA_DIR = Path(__file__).parent / "data"


def configured_value(name: str) -> str:
    """Read a setting from Streamlit secrets, then environment variables."""
    try:
        return st.secrets.get(name) or os.environ.get(name, "")
    except FileNotFoundError:
        return os.environ.get(name, "")


st.set_page_config(page_title="AgriScope-India", layout="wide", page_icon="🌾")
theme_base = st.get_option("theme.base") or "light"
px.defaults.template = "plotly_dark" if theme_base == "dark" else "plotly_white"

st.markdown("""
<style>
.stApp { color: inherit; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { right: 1rem; }
.block-container { max-width: 1440px; padding: 2rem 3rem 3rem; }
.hero { padding: 1.8rem 2rem; border-radius: 22px;
        background: linear-gradient(120deg, #0f3327 0%, #1c654b 62%, #d19a3f 140%);
        color: #fff; margin-bottom: 1.4rem; box-shadow: 0 12px 30px rgba(15,51,39,.16); }
.hero h1 { margin: 0; font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -.04em; }
.hero p { margin: .5rem 0 0; color: #e7f4ec; font-size: 1.02rem; }
.hero-meta { display: flex; gap: .55rem; flex-wrap: wrap; margin-top: 1rem; }
.hero-meta span { padding: .28rem .65rem; border: 1px solid rgba(255,255,255,.28);
                  border-radius: 999px; color: #f2faf4; font-size: .8rem; }
[data-baseweb="tab-list"] { gap: .45rem; background: rgba(128,128,128,.12); padding: .4rem;
                             border-radius: 14px; }
[data-baseweb="tab"] { border-radius: 10px; padding: .65rem 1rem; font-weight: 600; }
[aria-selected="true"][data-baseweb="tab"] { background: rgba(128,128,128,.18); color: inherit; box-shadow: 0 2px 8px rgba(15,51,39,.1); }
.section-kicker { color: #1c654b; font-size: .78rem; font-weight: 700;
                  letter-spacing: .12em; text-transform: uppercase; margin-top: .8rem; }
.section-note { color: inherit; opacity: .72; margin-top: -.5rem; margin-bottom: 1rem; }
.forecast-card { padding: 1.1rem 1.25rem; border: 1px solid rgba(128,128,128,.35);
                 border-radius: 16px; background: rgba(128,128,128,.10); min-height: 124px;
                 box-shadow: 0 5px 16px rgba(29,91,70,.06); }
.forecast-card h4 { margin: 0; color: #1d5b46; font-size: .95rem; }
.forecast-card .value { font-size: 1.65rem; font-weight: 750; color: inherit; margin: .45rem 0 .2rem; }
.source-note { color: inherit; opacity: .72; font-size: .82rem; }
.footer { border-top: 1px solid rgba(128,128,128,.35); margin-top: 2rem; padding-top: 1rem;
          color: inherit; opacity: .72; font-size: .8rem; }
</style>
<div class="hero">
  <h1>🌾 AgriScope-India</h1>
  <p>Agricultural Decision-Support Dashboard</p>
  <div class="hero-meta"><span>🧪 Nutrition planning</span><span>🌧️ Weather risk</span>
  <span>📈 Yield context</span><span>📡 Official mandi prices</span></div>
</div>
""", unsafe_allow_html=True)

tab_fert, tab_map, tab_eda, tab_yield, tab_live = st.tabs(
    ["🧪 Fertilizer Optimizer", "🗺️ District Map & Yield", "📊 EDA",
     "🌾 Yield Prediction", "📡 Live Feed"]
)

# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — FERTILIZER OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════
with tab_fert:
    st.markdown('<div class="section-kicker">Farm planning</div><h2>🧪 Fertilizer Optimizer</h2>'
                '<p class="section-note">Build a practical fertilizer plan from crop, growing condition and land area.</p>',
                unsafe_allow_html=True)
    with st.expander("ℹ️ Where every number here comes from"):
        st.markdown(f"""
- **Recommended N-P₂O₅-K₂O doses**: ICAR-CRRI (Cuttack) / OUAT package-of-practice
  publications for Odisha where available, general ICAR national RDF otherwise
  (labeled below) — not model output.
- **Historical yield trend**: real 1997–2019 Odisha rows from the Govt of India
  Crop Production Statistics dataset. The "Fertilizer" figure is state-level
  consumption apportioned by area, not a measured per-crop dose.
- **Recent anchor (2022–23)**: Odisha rice yield reached **29.09 quintal/ha**
  (up from 10.41 in 2000-01), state NPK consumption **66.17 kg/ha** — per the
  Odisha Dept. of Agriculture & Farmers' Empowerment "Significant Achievements"
  report (krushi-odisha.in), the latest official summary figures available.
- **Fertilizer prices**: current Govt of India statutory/NBS MRP, last verified
  {PRICE_LAST_VERIFIED}.
- **Mandi selling price**: live pull from the official Agmarknet 2.0 service.
""")

    crops_with_doses = list_known_crops()
    crop = st.selectbox("Crop", crops_with_doses,
                         index=crops_with_doses.index("Rice") if "Rice" in crops_with_doses else 0,
                         key="fert_crop")
    dose_opts = get_dose_options(crop)
    opt_labels = [f"{d.season} — {d.ecology}" for d in dose_opts]
    choice_idx = st.selectbox("Growing condition", range(len(opt_labels)),
                               format_func=lambda i: opt_labels[i], key="fert_cond")
    dose = dose_opts[choice_idx]

    c1, c2 = st.columns(2)
    with c1:
        area_value = st.number_input("Land area", min_value=0.1, value=1.0, step=0.5, key="fert_area")
    with c2:
        area_unit = st.radio("Unit", ["acre", "hectare"], horizontal=True, key="fert_unit")

    st.markdown(f'<div class="source-note">📚 Source: {dose.source}'
                + (f" — {dose.note}" if dose.note else "") + "</div>", unsafe_allow_html=True)
    st.write(f"**Recommended dose:** N = {dose.N} kg/ha, P₂O₅ = {dose.P2O5} kg/ha, K₂O = {dose.K2O} kg/ha")

    plan = compute_fertilizer_plan(dose.N, dose.P2O5, dose.K2O, area_value, area_unit)

    st.subheader("📦 Fertilizer bags needed & cost")
    rows = [{"Product": name, "Quantity (kg)": p["kg"], "Bags": p["bags"],
             "Bag size (kg)": p["bag_kg"], "Cost (₹)": p["cost_inr"]}
            for name, p in plan["products"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    m1, m2 = st.columns(2)
    m1.metric("Total cost", f"₹{plan['total_cost_inr']:,.0f}", help=f"for {plan['area_display']}")
    m2.metric("Cost per hectare", f"₹{plan['cost_per_ha_inr']:,.0f}")

    st.divider()
    st.subheader("📈 Yield-vs-fertilizer trend (Odisha)")
    recent_official = load_recent_official_data()
    recent_crop = recent_official[recent_official["Crop"] == crop]
    if not recent_crop.empty:
        latest = recent_crop.iloc[-1]
        st.metric(
            "Latest verified official yield",
            f"{latest['Yield']:.3f} t/ha",
            help=f"{latest['Season']} state-level anchor from {latest['Source']}",
        )
        st.caption(
            f"This {latest['Season']} official state-level yield anchor is shown "
            "alongside the model data; it is not used as a fabricated fertilizer observation."
        )
    hist_crops = list_crops()
    if crop in hist_crops:
        hist_all = crop_history(crop)
        hist_years = st.slider(
            "Historical crop-year range",
            min_value=int(hist_all["Crop_Year"].min()),
            max_value=max(2023, int(hist_all["Crop_Year"].max())),
            value=(int(hist_all["Crop_Year"].min()), 2023),
            key="fert_hist_years",
        )
        hist = hist_all[hist_all["Crop_Year"].between(*hist_years)]
        if hist.empty:
            st.info(f"No {crop} records are available in crop years {hist_years[0]}–{hist_years[1]}.")
        else:
            fig = px.scatter(hist, x="fert_per_ha", y="Yield", color="Season",
                              hover_data=["Crop_Year", "Annual_Rainfall"],
                              labels={"fert_per_ha": "Fertilizer intensity (kg/ha, state avg)",
                                      "Yield": "Yield (t/ha)"},
                              title=f"{crop}: real Odisha data, {hist_years[0]}–{hist_years[1]} ({len(hist)} records)")
            st.plotly_chart(fig, use_container_width=True)

        result = predict_yield(crop, dose.N + dose.P2O5 + dose.K2O,
                                rainfall_mm=float(hist_all["Annual_Rainfall"].median()),
                                pest_per_ha=float(hist_all["pest_per_ha"].median()))
        if result:
            st.subheader("📊 Historical yield estimate")
            st.caption(
                "A Random Forest model trained on historical Odisha records. "
                "This is an estimate for comparison, not a guaranteed forecast."
            )
            model_col1, model_col2, model_col3 = st.columns(3)
            model_col1.metric("Estimated yield", f"{result['predicted_yield']} t/ha")
            model_col2.metric("Historical fit (R²)", f"{result['r2_on_history']:.3f}")
            model_col3.metric("Records used", f"{result['n_historical_rows']:,}")
            st.caption(f"Model fit on {result['n_historical_rows']} real historical rows "
                       f"(in-sample R²={result['r2_on_history']}). At median historical "
                       f"rainfall/pesticide and this crop's recommended nutrient intensity, "
                       f"historical data suggests ~**{result['predicted_yield']} t/ha** — "
                       f"a sanity check, not a forecast.")
    else:
        st.caption("No historical Odisha rows for this exact crop name in the 1997-2019 dataset.")

# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — DISTRICT MAP & YIELD
# ═══════════════════════════════════════════════════════════════════════
with tab_map:
    st.markdown('<div class="section-kicker">Local conditions</div><h2>🗺️ District Map & Yield</h2>'
                '<p class="section-note">Explore district weather, rainfall risk and the latest verified yield context.</p>',
                unsafe_allow_html=True)
    st.caption("Choose a district below for live weather. Yield is shown as the latest "
               "official Odisha state average because district-level yield data is not "
               "included in the current public dataset.")

    with open(DATA_DIR / "odisha_districts.geojson") as f:
        geo = json.load(f)
    centroids = pd.read_csv(DATA_DIR / "odisha_district_centroids.csv")
    centroids["state_avg_marker"] = 1  # placeholder value so the choropleth renders

    district = st.selectbox(
        "Select a district",
        sorted(centroids["district"]),
        key="map_district",
    )
    map_crop = st.selectbox(
        "Crop for yield summary",
        list_crops(),
        index=list_crops().index("Rice") if "Rice" in list_crops() else 0,
        key="map_crop",
    )
    map_hist = crop_history(map_crop)
    latest_year = int(map_hist["Crop_Year"].max())
    latest_yield = float(map_hist.loc[map_hist["Crop_Year"] == latest_year, "Yield"].mean())
    recent = load_recent_official_data()
    recent_crop = recent[recent["Crop"] == map_crop]
    if not recent_crop.empty:
        latest_yield = float(recent_crop.iloc[-1]["Yield"])
        latest_year = int(recent_crop.iloc[-1]["Crop_Year"])
    y1, y2, y3 = st.columns(3)
    y1.metric("Latest state yield", f"{latest_yield:.2f} t/ha")
    y2.metric("Yield data year", "2022–23" if latest_year == 2023 else str(latest_year))
    y3.metric("District", district)

    fig_map = px.choropleth(
        centroids, geojson=geo, locations="district",
        featureidkey="properties.NAME_2", color="state_avg_marker",
        scope="asia", fitbounds="locations",
        color_continuous_scale=["#c7e9c0", "#238b45"],
        hover_name="district",
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False, height=520)
    st.plotly_chart(fig_map, use_container_width=True)

    st.info(
        "District-level yield is not invented: the current CSV contains state-level "
        "historical yield only. Add a data.gov.in key below in Live Feed to enable "
        "future district-statistics integration."
    )

    row = centroids[centroids["district"] == district].iloc[0]
    weather = get_live_weather(row["lat"], row["lon"])
    if "error" in weather:
        st.info(f"Live weather unavailable in this environment right now ({weather['error']}). "
                "This call works normally once the app runs with regular internet access.")
    else:
        cur = weather.get("current", {})
        w1, w2, w3, w4 = st.columns(4)
        w1.metric("Temperature", f"{cur.get('temperature_2m', '–')} °C")
        w2.metric("Humidity", f"{cur.get('relative_humidity_2m', '–')} %")
        w3.metric("Precipitation now", f"{cur.get('precipitation', '–')} mm")
        w4.metric("Wind", f"{cur.get('wind_speed_10m', '–')} km/h")
        daily = weather.get("daily", {})
        if daily:
            ddf = pd.DataFrame({"date": daily["time"], "rainfall_mm": daily["precipitation_sum"]})
            today = pd.Timestamp(date.today())
            ddf["period"] = ddf["date"].map(
                lambda value: "Forecast" if pd.Timestamp(value) > today else "Observed"
            )
            forecast_total = ddf.loc[ddf["period"] == "Forecast", "rainfall_mm"].sum()
            today_rows = ddf[ddf["date"] == today.strftime("%Y-%m-%d")]
            today_rain = float(today_rows["rainfall_mm"].iloc[0]) if not today_rows.empty else 0.0
            today_status = "Rain expected today" if today_rain >= 0.1 else "No meaningful rain today"
            forecast_values = ddf.loc[ddf["period"] == "Forecast", "rainfall_mm"]
            rainy_days = int((forecast_values >= 0.1).sum())
            if rainy_days == 0:
                rain_status = "No meaningful rain expected"
                climate_status = "Mostly dry conditions"
            elif rainy_days >= 4:
                rain_status = f"Rain likely on {rainy_days} of 7 days"
                climate_status = "Wet spell likely"
            else:
                rain_status = f"Rain possible on {rainy_days} of 7 days"
                climate_status = "Mixed / intermittent showers"
            forecast_col1, forecast_col2, forecast_col3 = st.columns(3)
            with forecast_col1:
                st.markdown(
                    f'<div class="forecast-card"><h4>🌧️ Today · {today.strftime("%d %b")}</h4>'
                    f'<div class="value">{today_rain:.1f} mm</div>'
                    f'<div>{today_status}</div></div>',
                    unsafe_allow_html=True,
                )
            with forecast_col2:
                st.markdown(
                    f'<div class="forecast-card"><h4>📅 Next 7 days</h4>'
                    f'<div class="value">{forecast_total:.1f} mm</div>'
                    f'<div>{rain_status}</div></div>',
                    unsafe_allow_html=True,
                )
            with forecast_col3:
                st.markdown(
                    f'<div class="forecast-card"><h4>🌡️ Climate condition</h4>'
                    f'<div class="value">{climate_status}</div>'
                    f'<div>Forecast rain days: {rainy_days}/7</div></div>',
                    unsafe_allow_html=True,
                )
            st.plotly_chart(px.bar(ddf, x="date", y="rainfall_mm", color="period",
                                    title=f"Observed + predicted rainfall — {district}"),
                             use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — EDA
# ═══════════════════════════════════════════════════════════════════════
with tab_eda:
    st.markdown('<div class="section-kicker">Data analysis workspace</div><h2>📊 Exploratory Data Analysis</h2>'
                '<p class="section-note">Filter, compare and investigate the historical crop dataset through interactive views.</p>',
                unsafe_allow_html=True)
    df = load_odisha_data().copy()
    recent = load_recent_official_data()

    st.subheader("Analysis filters")
    eda_years = st.slider(
        "Crop-year range",
        min_value=int(df["Crop_Year"].min()),
        max_value=max(2023, int(df["Crop_Year"].max())),
        value=(int(df["Crop_Year"].min()), 2023),
        key="eda_years",
    )
    filter_col1, filter_col2, filter_col3 = st.columns([1.3, 1.3, 1])
    with filter_col1:
        selected_crops = st.multiselect(
            "Crops",
            options=sorted(df["Crop"].unique()),
            default=[],
            help="Leave empty to include every crop.",
            key="eda_crops",
        )
    with filter_col2:
        selected_seasons = st.multiselect(
            "Seasons",
            options=sorted(df["Season"].dropna().unique()),
            default=[],
            help="Leave empty to include every season.",
            key="eda_seasons",
        )
    with filter_col3:
        top_n = st.slider("Number of crops", 5, 25, 10, key="eda_top_n")

    filtered = df[df["Crop_Year"].between(*eda_years)].copy()
    if selected_crops:
        filtered = filtered[filtered["Crop"].isin(selected_crops)]
    if selected_seasons:
        filtered = filtered[filtered["Season"].isin(selected_seasons)]

    st.caption(
        f"Showing {len(filtered):,} of {len(df[df['Crop_Year'].between(*eda_years)]):,} "
        f"historical records for {eda_years[0]}–{eda_years[1]}. "
        "The recent official anchor is shown separately."
    )
    if filtered.empty:
        st.warning("No records match the selected filters. Broaden the year, crop or season selection.")
    else:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Records", f"{len(filtered):,}")
        kpi2.metric("Crops", f"{filtered['Crop'].nunique():,}")
        kpi3.metric("Average yield", f"{filtered['Yield'].mean():.2f} t/ha")
        kpi4.metric("Median rainfall", f"{filtered['Annual_Rainfall'].median():,.0f} mm")

        st.subheader("Yield performance")
        chart1, chart2 = st.columns(2)
        with chart1:
            crop_summary = (
                filtered.groupby("Crop", as_index=False)
                .agg(avg_yield=("Yield", "mean"), records=("Yield", "size"))
                .sort_values("avg_yield", ascending=False)
                .head(top_n)
            )
            fig = px.bar(
                crop_summary.sort_values("avg_yield"),
                x="avg_yield",
                y="Crop",
                orientation="h",
                text="avg_yield",
                hover_data=["records"],
                title=f"Top {min(top_n, len(crop_summary))} crops by average yield",
                labels={"avg_yield": "Average yield (t/ha)", "Crop": ""},
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        with chart2:
            trend_metric = st.selectbox(
                "Trend measure",
                ["Average yield", "Total production", "Average rainfall"],
                key="eda_trend_metric",
            )
            metric_map = {
                "Average yield": ("Yield", "mean", "Yield (t/ha)"),
                "Total production": ("Production", "sum", "Production"),
                "Average rainfall": ("Annual_Rainfall", "mean", "Rainfall (mm)"),
            }
            metric_col, aggregation, metric_label = metric_map[trend_metric]
            yearly = (
                filtered.groupby("Crop_Year", as_index=False)[metric_col]
                .agg(aggregation)
                .rename(columns={metric_col: "value"})
            )
            fig = px.line(
                yearly,
                x="Crop_Year",
                y="value",
                markers=True,
                title=f"{trend_metric} by crop year",
                labels={"value": metric_label, "Crop_Year": "Crop year"},
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Distributions and relationships")
        chart3, chart4 = st.columns(2)
        with chart3:
            fig = px.box(
                filtered,
                x="Season",
                y="Yield",
                color="Season",
                points="outliers",
                title="Yield distribution by season",
                labels={"Yield": "Yield (t/ha)", "Season": ""},
            )
            st.plotly_chart(fig, use_container_width=True)
        with chart4:
            scatter_x = st.selectbox(
                "Relationship variable",
                ["Annual_Rainfall", "fert_per_ha", "pest_per_ha", "Area"],
                format_func=lambda value: {
                    "Annual_Rainfall": "Annual rainfall (mm)",
                    "fert_per_ha": "Fertilizer intensity (kg/ha)",
                    "pest_per_ha": "Pesticide intensity (kg/ha)",
                    "Area": "Cultivated area",
                }[value],
                key="eda_scatter_x",
            )
            fig = px.scatter(
                filtered,
                x=scatter_x,
                y="Yield",
                color="Season",
                size="Area",
                hover_data=["Crop", "Crop_Year", "Production"],
                opacity=0.65,
                title=f"{scatter_x} and yield",
                labels={"Yield": "Yield (t/ha)", scatter_x: scatter_x},
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Feature correlation with yield")
        correlation_columns = [
            "Area", "Production", "Annual_Rainfall", "Fertilizer",
            "Pesticide", "Yield", "fert_per_ha", "pest_per_ha",
        ]
        yield_correlation = (
            filtered[correlation_columns]
            .corr(numeric_only=True)["Yield"]
            .drop("Yield")
            .sort_values()
            .rename("correlation")
            .reset_index()
            .rename(columns={"index": "feature"})
        )
        fig = px.bar(
            yield_correlation,
            x="correlation",
            y="feature",
            orientation="h",
            color="correlation",
            color_continuous_scale="RdBu_r",
            range_color=[-1, 1],
            text="correlation",
            title="Pearson correlation with yield",
            labels={"correlation": "Correlation", "feature": ""},
        )
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Filtered data")
        display_data = filtered.drop(columns=["fert_per_ha", "pest_per_ha"]).sort_values(
            "Crop_Year", ascending=False
        )
        st.download_button(
            "Download filtered data (CSV)",
            display_data.to_csv(index=False).encode("utf-8"),
            file_name="agriscope_filtered_crop_data.csv",
            mime="text/csv",
            key="eda_download",
        )
        st.dataframe(display_data, use_container_width=True, height=320)

    st.subheader("Latest verified official anchor")
    st.dataframe(recent, hide_index=True, use_container_width=True)
    st.caption(
        "The official state-level anchor is displayed separately because it does "
        "not contain all features required by the historical model."
    )

# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — YIELD PREDICTION
# ═══════════════════════════════════════════════════════════════════════
with tab_yield:
    st.markdown(
        '<div class="section-kicker">Model workspace</div><h2>🌾 Yield Prediction</h2>'
        '<p class="section-note">Estimate crop yield from historical agricultural and rainfall conditions.</p>',
        unsafe_allow_html=True,
    )
    st.info(
        "This prediction is based on historical Odisha records. It is intended "
        "for comparison and planning, not as a guaranteed field forecast."
    )

    prediction_crop = st.selectbox(
        "Select crop",
        options=list_crops(),
        index=list_crops().index("Rice") if "Rice" in list_crops() else 0,
        key="yield_prediction_crop",
    )
    prediction_history = crop_history(prediction_crop)
    input_col1, input_col2, input_col3 = st.columns(3)
    with input_col1:
        prediction_fertilizer = st.number_input(
            "Fertilizer intensity (kg/ha)",
            min_value=0.0,
            value=float(prediction_history["fert_per_ha"].median()),
            step=1.0,
            key="yield_prediction_fertilizer",
        )
    with input_col2:
        prediction_rainfall = st.number_input(
            "Annual rainfall (mm)",
            min_value=0.0,
            value=float(prediction_history["Annual_Rainfall"].median()),
            step=10.0,
            key="yield_prediction_rainfall",
        )
    with input_col3:
        prediction_pesticide = st.number_input(
            "Pesticide intensity (kg/ha)",
            min_value=0.0,
            value=float(prediction_history["pest_per_ha"].median()),
            step=0.1,
            key="yield_prediction_pesticide",
        )

    prediction = predict_yield(
        prediction_crop,
        prediction_fertilizer,
        prediction_rainfall,
        prediction_pesticide,
    )
    if prediction:
        result_col1, result_col2, result_col3 = st.columns(3)
        result_col1.metric("Predicted yield", f"{prediction['predicted_yield']} t/ha")
        result_col2.metric("Historical fit (R²)", f"{prediction['r2_on_history']:.3f}")
        result_col3.metric("Training records", f"{prediction['n_historical_rows']:,}")

        st.subheader("Prediction compared with historical records")
        historical_yields = prediction_history[["Crop_Year", "Yield"]].copy()
        historical_yields["Type"] = "Historical yield"
        predicted_point = pd.DataFrame({
            "Crop_Year": [historical_yields["Crop_Year"].max() + 1],
            "Yield": [prediction["predicted_yield"]],
            "Type": ["Model estimate"],
        })
        comparison = pd.concat([historical_yields, predicted_point], ignore_index=True)
        fig = px.line(
            comparison,
            x="Crop_Year",
            y="Yield",
            color="Type",
            markers=True,
            title=f"{prediction_crop}: historical yield and model estimate",
            labels={"Crop_Year": "Crop year", "Yield": "Yield (t/ha)"},
        )
        st.plotly_chart(fig, use_container_width=True)

        input_summary = pd.DataFrame({
            "Model input": [
                "Fertilizer intensity",
                "Annual rainfall",
                "Pesticide intensity",
            ],
            "Value": [
                prediction_fertilizer,
                prediction_rainfall,
                prediction_pesticide,
            ],
            "Unit": ["kg/ha", "mm", "kg/ha"],
        })
        st.subheader("Inputs used for this estimate")
        st.dataframe(input_summary, hide_index=True, use_container_width=True)
        st.caption(
            f"The {prediction_crop} model was trained on {prediction['n_historical_rows']} "
            f"historical records. Its in-sample R² is {prediction['r2_on_history']:.3f}; "
            "this value is not independent test accuracy."
        )
    else:
        st.warning(
            f"Not enough historical records are available to build a prediction "
            f"for {prediction_crop}."
        )

# ═══════════════════════════════════════════════════════════════════════
# TAB 5 — LIVE FEED
# ═══════════════════════════════════════════════════════════════════════
with tab_live:
    st.markdown('<div class="section-kicker">Market intelligence</div><h2>📡 Live Mandi Prices</h2>'
                '<p class="section-note">Compare official Agmarknet prices by district and date.</p>',
                unsafe_allow_html=True)
    st.success("✅ Connected to the official Agmarknet live price service (no API key required).")

    mandi_date = st.date_input(
        "📅 Select mandi date",
        value=date.today(),
        help="Agmarknet reports the date when the market price was recorded. "
             "All commodities reported for this date will be shown.",
        key="mandi_date",
    )
    centroids_for_mandi = pd.read_csv(DATA_DIR / "odisha_district_centroids.csv")
    mandi_district = st.selectbox(
        "📍 Select district",
        ["All Odisha"] + sorted(centroids_for_mandi["district"].tolist()),
        key="mandi_district",
    )
    days_to_show = st.radio(
        "📆 Price history",
        [1, 2, 3],
        format_func=lambda value: "Today only" if value == 1 else f"Today + previous {value - 1} days",
        horizontal=True,
        key="mandi_days",
    )
    if st.button("🔄 Fetch district mandi prices", key="live_mandi_btn"):
        district_filter = None if mandi_district == "All Odisha" else mandi_district
        records = []
        errors = []
        for offset in range(days_to_show):
            requested_date = mandi_date - pd.Timedelta(days=offset)
            day_records = get_agmarknet_daily_prices(
                requested_date.strftime("%Y-%m-%d"),
                district=district_filter,
            )
            if isinstance(day_records, dict) and day_records.get("error"):
                errors.append(day_records["note"])
            else:
                records.extend(day_records)
        if errors and not records:
            st.error(errors[0])
        elif not records:
            st.info("No mandi records were reported for the selected date range.")
        else:
            if errors:
                st.warning("Some dates could not be fetched: " + errors[0])
            result_df = pd.DataFrame(records)
            matched_date = result_df["_matched_arrival_date"].iloc[0]
            result_df = result_df.drop(columns=["_matched_arrival_date"])
            preferred_columns = [
                "commodity", "variety", "market", "district", "state",
                "min_price", "max_price", "modal_price", "arrival_date",
            ]
            visible_columns = [column for column in preferred_columns if column in result_df.columns]
            result_df = result_df[visible_columns] if visible_columns else result_df
            st.metric("Market price records", f"{len(result_df):,}")
            st.dataframe(
                result_df,
                hide_index=True,
                use_container_width=True,
                height=560,
            )
            st.caption(
                f"Showing official Agmarknet records for {mandi_district}, "
                f"{mandi_date.strftime('%d %b %Y')} and selected previous day(s)."
            )
    st.caption("Prices are reported by Agmarknet and may be unavailable for dates with no market entries.")

st.markdown(
    '<div class="footer">AgriScope-India · Official data where available · '
    'Model outputs are clearly labeled and should support, not replace, field advice.</div>',
    unsafe_allow_html=True,
)
