import altair as alt
import pandas as pd
import streamlit as st
from urllib import error, request
import json

# Show the page title and description.
st.set_page_config(page_title="Movies dataset", page_icon="🎬")
st.title("🎬 Movies dataset")
st.write(
    """
    This app visualizes data from [The Movie Database (TMDB)](https://www.kaggle.com/datasets/tmdb/tmdb-movie-metadata).
    It shows which movie genre performed best at the box office over the years. Just 
    click on the widgets below to explore!
    """
)


# Load the data from a CSV. We're caching this so it doesn't reload every time the app
# reruns (e.g. if the user interacts with the widgets).
@st.cache_data
def load_data():
    df = pd.read_csv("data/movies_genres_summary.csv")
    return df

@st.cache_data
def load_cpi_data():
    return pd.read_csv("data/us_cpi_u_annual.csv").set_index("year")["cpi"]

@st.cache_data(ttl=60 * 60 * 12)
def load_usd_to_eur_rate():
    """Fetch the latest USD -> EUR rate from Frankfurter (ECB reference rates)."""
    with request.urlopen(
        "https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=10
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return float(payload["rates"]["EUR"]), payload["date"]


df = load_data()
min_year = int(df["year"].min())
max_year = int(df["year"].max())
default_start_year = max(min_year, 2000)
default_end_year = min(max_year, 2016)
if default_start_year > default_end_year:
    default_start_year = min_year
    default_end_year = max_year

currency = st.sidebar.selectbox("Currency", ["USD", "EUR"], index=1)
show_inflation_index = st.sidebar.toggle(
    "Inflation-adjusted index",
    value=False,
    help="Correct values using annual U.S. CPI-U data and rebase each genre to 100 in the selected start year.",
)
fallback_usd_to_eur_rate = st.sidebar.number_input(
    "Fallback USD to EUR rate",
    min_value=0.1,
    max_value=2.0,
    value=0.92,
    step=0.0001,
    format="%.4f",
)

try:
    usd_to_eur_rate, fx_date = load_usd_to_eur_rate()
except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
    usd_to_eur_rate = fallback_usd_to_eur_rate
    fx_date = "fallback/manual"
    st.warning("Live USD to EUR rate unavailable. Using fallback rate from sidebar.")

# Show a multiselect widget with the genres using `st.multiselect`.
genres = st.multiselect(
    "Genres",
    df.genre.unique(),
    ["Action", "Adventure", "Biography", "Comedy", "Drama", "Horror"],
)

# Show a slider widget with the years using `st.slider`.
years = st.slider("Years", min_year, max_year, (default_start_year, default_end_year))

# Filter the dataframe based on the widget input and reshape it.
df_filtered = df[(df["genre"].isin(genres)) & (df["year"].between(years[0], years[1]))]
df_reshaped = df_filtered.pivot_table(
    index="year", columns="genre", values="gross", aggfunc="sum", fill_value=0
)
df_reshaped = df_reshaped.reindex(range(years[0], years[1] + 1), fill_value=0)

if show_inflation_index:
    cpi_by_year = load_cpi_data()
    selected_cpi = cpi_by_year.reindex(df_reshaped.index)
    base_year = years[0]
    base_cpi = cpi_by_year.loc[base_year]
    df_inflation_adjusted = df_reshaped.mul(base_cpi / selected_cpi, axis=0)
    base_values = df_inflation_adjusted.loc[base_year].replace(0, pd.NA)
    missing_base_genres = base_values[base_values.isna()].index.tolist()
    df_display = df_inflation_adjusted.div(base_values, axis=1) * 100
    table_number_format = "{:,.1f}"
    chart_axis_title = f"Inflation-adjusted gross earnings index ({base_year} = 100)"
    st.caption(
        "Inflation adjustment uses annual U.S. CPI-U averages from the U.S. Bureau of Labor Statistics."
    )
    if missing_base_genres:
        st.warning(
            "Index values are unavailable for genres with no gross earnings in the selected start year: "
            + ", ".join(missing_base_genres)
        )
else:
    if currency == "EUR":
        df_display = df_reshaped * usd_to_eur_rate
        table_number_format = "€ {:,.0f}"
        chart_axis_title = "Gross earnings (€)"
        st.caption(f"Exchange rate used: 1 USD = {usd_to_eur_rate:.4f} EUR (as of {fx_date})")
    else:
        df_display = df_reshaped
        table_number_format = "$ {:,.0f}"
        chart_axis_title = "Gross earnings (USD)"

df_table = df_display.sort_index(ascending=False)

# Display the data as a table using `st.dataframe`.
st.dataframe(
    df_table.style.format(table_number_format, na_rep="n/a"),
    use_container_width=True,
)

# Display the data as an Altair chart using `st.altair_chart`.
df_chart = pd.melt(
    df_display.reset_index(), id_vars="year", var_name="genre", value_name="gross"
)
chart = (
    alt.Chart(df_chart)
    .mark_line()
    .encode(
        x=alt.X("year:Q", title="Year"),
        y=alt.Y("gross:Q", title=chart_axis_title),
        color="genre:N",
    )
    .properties(height=320)
)
st.altair_chart(chart, use_container_width=True)
