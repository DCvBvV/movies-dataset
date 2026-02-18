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

@st.cache_data(ttl=60 * 60 * 12)
def load_usd_to_eur_rate():
    """Fetch the latest USD -> EUR rate from Frankfurter (ECB reference rates)."""
    with request.urlopen(
        "https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=10
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return float(payload["rates"]["EUR"]), payload["date"]


df = load_data()
try:
    usd_to_eur_rate, fx_date = load_usd_to_eur_rate()
except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
    st.error("Could not load a live USD to EUR exchange rate. Please try again.")
    st.stop()

# Show a multiselect widget with the genres using `st.multiselect`.
genres = st.multiselect(
    "Genres",
    df.genre.unique(),
    ["Action", "Adventure", "Biography", "Comedy", "Drama", "Horror"],
)

# Show a slider widget with the years using `st.slider`.
years = st.slider("Years", 1986, 2006, (2000, 2016))

# Filter the dataframe based on the widget input and reshape it.
df_filtered = df[(df["genre"].isin(genres)) & (df["year"].between(years[0], years[1]))]
df_reshaped = df_filtered.pivot_table(
    index="year", columns="genre", values="gross", aggfunc="sum", fill_value=0
)
df_reshaped = df_reshaped.sort_values(by="year", ascending=False)
df_reshaped_eur = df_reshaped * usd_to_eur_rate

st.caption(f"Exchange rate used: 1 USD = {usd_to_eur_rate:.4f} EUR (as of {fx_date})")

# Display the data as a table using `st.dataframe`.
st.dataframe(
    df_reshaped_eur.style.format("EUR {:,.0f}"),
    use_container_width=True,
)

# Display the data as an Altair chart using `st.altair_chart`.
df_chart = pd.melt(
    df_reshaped_eur.reset_index(), id_vars="year", var_name="genre", value_name="gross"
)
chart = (
    alt.Chart(df_chart)
    .mark_line()
    .encode(
        x=alt.X("year:N", title="Year"),
        y=alt.Y("gross:Q", title="Gross earnings (EUR)"),
        color="genre:N",
    )
    .properties(height=320)
)
st.altair_chart(chart, use_container_width=True)
