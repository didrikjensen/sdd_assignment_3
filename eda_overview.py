"""
EDA overview of the raw Movies dataset (TDT4225 Assignment 3, Part 1).

Generates tables (CSV + Markdown) and figures (PNG) that give a general overview
of every raw CSV file: size, schema, missing values, data-quality issues,
distributions, cross-file coverage and how well the data supports the Part 2
tasks.

Usage (from the repo root):
    python eda_overview.py            # full ratings.csv / links.csv
    python eda_overview.py --small    # ratings_small.csv / links_small.csv

Output lands in eda_output/ (tables/, figures/, EDA_summary.md).
Parsed nested JSON columns are cached in .eda_cache/ so reruns are fast.
"""

import argparse
import ast
import pickle
import time
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Plot style (light report figures)
# ---------------------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
DIVERGING = LinearSegmentedColormap.from_list("blue_gray_red", ["#1c5cab", "#f0efec", "#e34948"])

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.size": 10,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "axes.titlecolor": INK,
    "axes.titlesize": 12,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.edgecolor": AXIS,
    "axes.linewidth": 1,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 1,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK_2,
    "ytick.labelcolor": INK_2,
    "legend.frameon": False,
    "lines.linewidth": 2,
    "lines.solid_capstyle": "round",
})

LIST_COLUMNS = ["genres", "production_companies", "production_countries", "spoken_languages"]
DATASET_CUTOFF = pd.Timestamp("2017-12-31")  # Kaggle dataset was collected in July 2017


def compact(x, _pos=None):
    """Axis formatter: 1,200 -> 1.2K, 3,400,000 -> 3.4M."""
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            return f"{x / div:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{x:g}"


def parse_literal(value):
    """Parse a Python-literal string ("[{'id': 1, ...}]") into list/dict, else None."""
    if isinstance(value, str) and value[:1] in "[{":
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return None
    return None


def as_list(value):
    return value if isinstance(value, list) else []


def names(value, key="name"):
    return [d.get(key) for d in as_list(value) if isinstance(d, dict) and d.get(key)]


def pct(part, whole):
    return round(100 * part / whole, 2) if whole else 0.0


def to_markdown(df: pd.DataFrame, index=False):
    """Markdown table with thousands separators; strings (e.g. imdb ids) are left untouched."""
    def fmt(v):
        if isinstance(v, (bool, np.bool_)) or v is None or (isinstance(v, float) and np.isnan(v)):
            return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
        if isinstance(v, (int, np.integer)):
            return f"{v:,}"
        if isinstance(v, (float, np.floating)):
            return f"{v:,.0f}" if abs(v) >= 1e5 else f"{v:,.2f}"
        return str(v).replace("|", "\\|").replace("\n", " ")
    out = df.copy()
    out.index = out.index.map(fmt)
    for col in out.columns:
        # Years, decades and small counts read better without a thousands separator.
        plain = str(col) in ("decade", "year", "primary_genre", "directors", "movies_in_collection")
        out[col] = out[col].map(str if plain else fmt)
    return out.to_markdown(index=index, disable_numparse=True)


class Report:
    """Collects tables/figures and writes them to disk plus a Markdown summary."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.tables_dir = out_dir / "tables"
        self.figures_dir = out_dir / "figures"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.sections = []  # (heading, [markdown blocks])

    def section(self, heading):
        self.sections.append((heading, []))

    def text(self, md):
        self.sections[-1][1].append(md)

    def table(self, name, df: pd.DataFrame, title, max_rows=40, index=False):
        df.to_csv(self.tables_dir / f"{name}.csv", index=index)
        md = to_markdown(df.head(max_rows), index=index)
        (self.tables_dir / f"{name}.md").write_text(f"### {title}\n\n{md}\n", encoding="utf-8")
        more = f"\n\n_Showing {max_rows} of {len(df)} rows - full table in `tables/{name}.csv`._" if len(df) > max_rows else ""
        self.text(f"**{title}** (`tables/{name}.csv`)\n\n{md}{more}")
        print(f"  table  {name}.csv ({len(df)} rows)")

    def figure(self, name, fig, caption):
        path = self.figures_dir / f"{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        self.text(f"![{caption}](figures/{name}.png)\n\n_{caption}_")
        print(f"  figure {name}.png")

    def write(self, header):
        parts = [header]
        for heading, blocks in self.sections:
            parts.append(f"## {heading}")
            parts.extend(blocks)
        (self.out_dir / "EDA_summary.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def cached(cache_dir: Path, name, source: Path, build):
    """Return build() cached on disk; rebuilt when the source CSV changes."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{name}.pkl"
    stamp = (source.stat().st_size, source.stat().st_mtime)
    if path.exists():
        with open(path, "rb") as f:
            saved_stamp, obj = pickle.load(f)
        if saved_stamp == stamp:
            return obj
    t0 = time.time()
    obj = build()
    with open(path, "wb") as f:
        pickle.dump((stamp, obj), f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"  parsed {name} in {time.time() - t0:.0f}s (cached)")
    return obj


def load_metadata(data_dir, cache_dir):
    src = data_dir / "movies_metadata.csv"

    def build():
        df = pd.read_csv(src, low_memory=False, dtype=str, keep_default_na=False, na_values=[""])
        for col in LIST_COLUMNS + ["belongs_to_collection"]:
            df[col + "_parsed"] = df[col].map(parse_literal)
        return df

    raw = cached(cache_dir, "movies_metadata", src, build)
    df = raw.copy()
    df["id_num"] = pd.to_numeric(df["id"], errors="coerce")
    for col in ["budget", "revenue", "runtime", "popularity", "vote_average", "vote_count"]:
        df[col + "_num"] = pd.to_numeric(df[col], errors="coerce")
    df["release_dt"] = pd.to_datetime(df["release_date"], errors="coerce", format="%Y-%m-%d")
    df["year"] = df["release_dt"].dt.year
    df["decade"] = (df["year"] // 10 * 10).astype("Int64")
    df["genre_names"] = df["genres_parsed"].map(names)
    df["company_names"] = df["production_companies_parsed"].map(names)
    df["country_codes"] = df["production_countries_parsed"].map(lambda v: names(v, "iso_3166_1"))
    df["country_names"] = df["production_countries_parsed"].map(names)
    df["spoken_codes"] = df["spoken_languages_parsed"].map(lambda v: names(v, "iso_639_1"))
    df["collection_name"] = df["belongs_to_collection_parsed"].map(
        lambda v: v.get("name") if isinstance(v, dict) else None)
    return df


def load_credits(data_dir, cache_dir):
    src = data_dir / "credits.csv"

    def build():
        # Only keep the fields needed for the overview to keep the cache small.
        df = pd.read_csv(src, dtype=str)
        rows = []
        for cast_s, crew_s, mid in zip(df["cast"], df["crew"], df["id"]):
            cast = as_list(parse_literal(cast_s))
            crew = as_list(parse_literal(crew_s))
            rows.append({
                "id": mid,
                "cast": [(c.get("id"), c.get("name"), c.get("gender"), c.get("order")) for c in cast],
                "crew": [(c.get("id"), c.get("name"), c.get("job"), c.get("department"), c.get("gender"))
                         for c in crew],
            })
        return pd.DataFrame(rows)

    df = cached(cache_dir, "credits", src, build)
    df["id_num"] = pd.to_numeric(df["id"], errors="coerce")
    return df


def load_keywords(data_dir, cache_dir):
    src = data_dir / "keywords.csv"

    def build():
        df = pd.read_csv(src, dtype=str)
        df["keyword_names"] = df["keywords"].map(lambda s: names(parse_literal(s)))
        return df[["id", "keyword_names"]]

    df = cached(cache_dir, "keywords", src, build)
    df["id_num"] = pd.to_numeric(df["id"], errors="coerce")
    return df


def load_links(data_dir, small):
    src = data_dir / ("links_small.csv" if small else "links.csv")
    df = pd.read_csv(src, dtype={"movieId": "Int64", "imdbId": str, "tmdbId": "Int64"})
    return df, src


def scan_ratings(path: Path, chunksize=4_000_000):
    """Single streaming pass over the ratings file; returns aggregate arrays only."""
    rating_counts = Counter()
    year_counts = Counter()
    user_n = np.zeros(1, dtype=np.int64)
    user_sum = np.zeros(1)
    user_sumsq = np.zeros(1)
    movie_n = np.zeros(1, dtype=np.int64)
    n_rows = 0
    ts_min, ts_max = np.inf, -np.inf
    n_null = 0
    n_dupe_pairs = 0  # same (user, movie) appearing more than once within a chunk-local check
    dtypes = {"userId": "int32", "movieId": "int32", "rating": "float32", "timestamp": "int64"}
    t0 = time.time()
    for chunk in pd.read_csv(path, dtype=dtypes, chunksize=chunksize):
        n_rows += len(chunk)
        n_null += int(chunk.isna().sum().sum())
        u = chunk["userId"].to_numpy()
        m = chunk["movieId"].to_numpy()
        r = chunk["rating"].to_numpy().astype(np.float64)
        ts = chunk["timestamp"].to_numpy()
        if u.max() >= len(user_n):
            grow = u.max() + 1 - len(user_n)
            user_n = np.pad(user_n, (0, grow))
            user_sum = np.pad(user_sum, (0, grow))
            user_sumsq = np.pad(user_sumsq, (0, grow))
        if m.max() >= len(movie_n):
            movie_n = np.pad(movie_n, (0, m.max() + 1 - len(movie_n)))
        user_n += np.bincount(u, minlength=len(user_n))
        user_sum += np.bincount(u, weights=r, minlength=len(user_n))
        user_sumsq += np.bincount(u, weights=r * r, minlength=len(user_n))
        movie_n += np.bincount(m, minlength=len(movie_n))
        rating_counts.update(dict(zip(*np.unique(r, return_counts=True))))
        years = pd.to_datetime(ts, unit="s").year
        year_counts.update(dict(zip(*np.unique(years, return_counts=True))))
        ts_min, ts_max = min(ts_min, ts.min()), max(ts_max, ts.max())
        n_dupe_pairs += int(chunk.duplicated(["userId", "movieId"]).sum())
        print(f"  ratings: {n_rows:,} rows scanned ({time.time() - t0:.0f}s)", end="\r")
    print()
    return {
        "n_rows": n_rows, "n_null": n_null, "n_dupe_pairs": n_dupe_pairs,
        "rating_counts": rating_counts, "year_counts": year_counts,
        "user_n": user_n, "user_sum": user_sum, "user_sumsq": user_sumsq, "movie_n": movie_n,
        "ts_min": pd.to_datetime(ts_min, unit="s"), "ts_max": pd.to_datetime(ts_max, unit="s"),
    }


# ---------------------------------------------------------------------------
# Helpers for figures
# ---------------------------------------------------------------------------
def barh(ax, labels, values, color=BLUE, value_fmt="{:,.0f}"):
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=color, height=0.62)
    ax.set_yticks(y, labels)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    vmax = max(values) if len(values) else 0
    for yi, v in zip(y, values):
        ax.text(v + vmax * 0.01, yi, value_fmt.format(v), va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, vmax * 1.12 if vmax else 1)
    ax.xaxis.set_major_formatter(FuncFormatter(compact))


def log_hist(ax, values, bins=50, color=BLUE, integer=False):
    values = np.asarray(values, dtype=float)
    values = values[values > 0]
    if len(values) == 0:
        return
    if integer:
        # Bin edges on half-integers so small counts (1, 2, 3 ...) get one bar each, no gaps.
        edges = np.unique(np.round(np.logspace(0, np.log10(values.max() + 1), bins))) - 0.5
        edges = edges[edges > 0]
    else:
        edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins)
    ax.hist(values, bins=edges, color=color, edgecolor=SURFACE, linewidth=0.5)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(compact))
    ax.yaxis.set_major_formatter(FuncFormatter(compact))


def top_counts(series_of_lists, n):
    c = Counter()
    for items in series_of_lists:
        c.update(items)
    return pd.DataFrame(c.most_common(n), columns=["value", "movies"])


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def column_profile(df: pd.DataFrame, cols):
    rows = []
    for col in cols:
        s = df[col]
        non_null = s.notna().sum()
        example = s.dropna().astype(str).iloc[0] if non_null else ""
        rows.append({
            "column": col,
            "non_null": int(non_null),
            "null": int(s.isna().sum()),
            "null_pct": pct(s.isna().sum(), len(s)),
            "unique": int(s.nunique(dropna=True)),
            "example": example[:70] + ("..." if len(example) > 70 else ""),
        })
    return pd.DataFrame(rows)


def schema_section(rep, meta, links, links_name, data_dir):
    rep.section("2. Column profiles (raw values)")
    meta_cols = [c for c in meta.columns if not c.endswith(("_parsed", "_num", "_names", "_codes", "_dt"))
                 and c not in ("year", "decade", "collection_name")]
    rep.table("02a_columns_movies_metadata", column_profile(meta, meta_cols), "movies_metadata.csv columns",
              max_rows=30)
    kw_raw = pd.read_csv(data_dir / "keywords.csv", dtype=str)
    cr = pd.read_csv(data_dir / "credits.csv", dtype=str)
    rep.table("02b_columns_credits", column_profile(cr, list(cr.columns)), "credits.csv columns")
    rep.table("02c_columns_keywords", column_profile(kw_raw, list(kw_raw.columns)), "keywords.csv columns")
    rep.table("02d_columns_links", column_profile(links.astype("object"), list(links.columns)),
              f"{links_name} columns")


def missing_section(rep, meta_valid, credits, keywords):
    rep.section("3. Missing data")
    rep.text("Many fields use a placeholder instead of an empty value: `0` for budget/revenue/runtime/"
             "vote_count, `[]` for list fields, and overview text such as \"No overview found.\". "
             "The table counts both real nulls and placeholders (only well-formed rows with a numeric id).")
    n = len(meta_valid)
    overview_ph = meta_valid["overview"].fillna("").str.strip().str.lower().str.startswith("no overview")
    rules = {
        "budget": (meta_valid["budget_num"].isna(), meta_valid["budget_num"] == 0, "0"),
        "revenue": (meta_valid["revenue_num"].isna(), meta_valid["revenue_num"] == 0, "0"),
        "runtime": (meta_valid["runtime_num"].isna(), meta_valid["runtime_num"] == 0, "0"),
        "vote_count": (meta_valid["vote_count_num"].isna(), meta_valid["vote_count_num"] == 0, "0"),
        "vote_average": (meta_valid["vote_average_num"].isna(), meta_valid["vote_count_num"] == 0,
                         "vote_count = 0"),
        "release_date": (meta_valid["release_dt"].isna(), pd.Series(False, index=meta_valid.index), "-"),
        "overview": (meta_valid["overview"].isna(), overview_ph & meta_valid["overview"].notna(),
                     "'No overview ...'"),
        "tagline": (meta_valid["tagline"].isna(), pd.Series(False, index=meta_valid.index), "-"),
        "belongs_to_collection": (meta_valid["collection_name"].isna(), pd.Series(False, index=meta_valid.index),
                                  "-"),
        "homepage": (meta_valid["homepage"].isna(), pd.Series(False, index=meta_valid.index), "-"),
        "imdb_id": (meta_valid["imdb_id"].isna(), pd.Series(False, index=meta_valid.index), "-"),
        "original_language": (meta_valid["original_language"].isna(), pd.Series(False, index=meta_valid.index),
                              "-"),
        "title": (meta_valid["title"].isna(), pd.Series(False, index=meta_valid.index), "-"),
    }
    for col in LIST_COLUMNS:
        parsed = meta_valid[col + "_parsed"]
        rules[col] = (parsed.isna(), parsed.map(lambda v: isinstance(v, list) and len(v) == 0), "[]")
    rows = []
    for col, (null_mask, ph_mask, rule) in rules.items():
        null_c, ph_c = int(null_mask.sum()), int((ph_mask & ~null_mask).sum())
        rows.append({"column": col, "null": null_c, "placeholder": ph_c, "placeholder_rule": rule,
                     "effective_missing": null_c + ph_c, "effective_missing_pct": pct(null_c + ph_c, n)})
    miss = pd.DataFrame(rows).sort_values("effective_missing_pct", ascending=False)
    rep.table("03a_missing_movies_metadata", miss, f"movies_metadata.csv missing values (n = {n:,})")

    fig, ax = plt.subplots(figsize=(8, 6))
    m = miss.iloc[::-1]
    y = np.arange(len(m))
    null_p = 100 * m["null"] / n
    ph_p = 100 * m["placeholder"] / n
    ax.barh(y, null_p, color=BLUE, height=0.62, label="Null / empty")
    ax.barh(y, ph_p, left=null_p, color=ORANGE, height=0.62, label="Placeholder (0, [], 'No overview')")
    ax.set_yticks(y, m["column"])
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    for yi, total in zip(y, m["effective_missing_pct"]):
        ax.text(total + 1, yi, f"{total:.1f}%", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, 105)
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.set_title("Missing values in movies_metadata.csv")
    ax.set_xlabel("Share of movies")
    ax.legend(loc="lower right")
    rep.figure("03a_missing_movies_metadata", fig, "Share of movies with a null or placeholder value, per column")

    # credits / keywords placeholders
    cast_len = credits["cast"].map(len)
    crew_len = credits["crew"].map(len)
    has_director = credits["crew"].map(lambda cr: any(c[2] == "Director" for c in cr))
    cast_genders = [c[2] for cast in credits["cast"] for c in cast]
    crew_genders = [c[4] for crew in credits["crew"] for c in crew]
    kw_len = keywords["keyword_names"].map(len)
    nc, nk = len(credits), len(keywords)
    rows = [
        {"file": "credits.csv", "check": "cast = []", "count": int((cast_len == 0).sum()), "of": nc},
        {"file": "credits.csv", "check": "crew = []", "count": int((crew_len == 0).sum()), "of": nc},
        {"file": "credits.csv", "check": "no crew member with job = Director", "count": int((~has_director).sum()),
         "of": nc},
        {"file": "credits.csv", "check": "cast entries with gender = 0 (unknown)",
         "count": int(sum(g == 0 for g in cast_genders)), "of": len(cast_genders)},
        {"file": "credits.csv", "check": "crew entries with gender = 0 (unknown)",
         "count": int(sum(g == 0 for g in crew_genders)), "of": len(crew_genders)},
        {"file": "keywords.csv", "check": "keywords = []", "count": int((kw_len == 0).sum()), "of": nk},
    ]
    t = pd.DataFrame(rows)
    t["pct"] = [pct(c, o) for c, o in zip(t["count"], t["of"])]
    rep.table("03b_missing_credits_keywords", t, "Empty / unknown values in credits.csv and keywords.csv")
    return has_director


def missing_by_decade_figure(rep, meta_valid, director_ids):
    d = meta_valid[meta_valid["decade"].notna() & (meta_valid["decade"] >= 1910)].copy()
    d["budget_missing"] = d["budget_num"].fillna(0) == 0
    d["revenue_missing"] = d["revenue_num"].fillna(0) == 0
    d["director_missing"] = ~d["id_num"].isin(director_ids)
    g = d.groupby("decade").agg(movies=("id", "size"), budget=("budget_missing", "mean"),
                                revenue=("revenue_missing", "mean"), director=("director_missing", "mean"))
    g = g[g["movies"] >= 30]
    t = g.reset_index()
    for c in ["budget", "revenue", "director"]:
        t[c] = (100 * t[c]).round(1)
    t.columns = ["decade", "movies", "budget_missing_pct", "revenue_missing_pct", "no_director_pct"]
    rep.table("03c_missing_by_decade", t, "Missing budget / revenue / director by release decade")

    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = g.index.astype(int)
    for col, color, label in [("revenue", BLUE, "Revenue = 0"), ("budget", ORANGE, "Budget = 0"),
                              ("director", AQUA, "No director in credits")]:
        ax.plot(x, 100 * g[col], color=color, marker="o", markersize=5, markeredgecolor=SURFACE,
                markeredgewidth=1.5, label=label)
        ax.text(x[-1] + 2, 100 * g[col].iloc[-1], label, va="center", fontsize=8, color=INK_2)
    ax.set_ylim(0, 100)
    ax.set_xlim(x[0] - 3, x[-1] + 28)
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_xticks(x, [f"{v}s" for v in x], rotation=0, fontsize=8)
    ax.set_title("Missing values by release decade")
    ax.set_ylabel("Share of movies in decade")
    ax.legend(loc="lower left", fontsize=8)
    rep.figure("03c_missing_by_decade", fig,
               "Budget and revenue are missing for most movies, especially older ones; directors are almost always present")


def quality_section(rep, meta, meta_valid, credits, keywords, links):
    rep.section("4. Data-quality issues")
    malformed = meta[meta["id_num"].isna()]
    dup_meta = meta_valid[meta_valid.duplicated("id_num", keep=False)]
    dup_credits = credits[credits.duplicated("id_num", keep=False)]
    dup_kw = keywords[keywords.duplicated("id_num", keep=False)]
    rd = meta_valid["release_dt"]
    rows = [
        ("movies_metadata.csv", "malformed rows (id is not a number, columns shifted)", len(malformed)),
        ("movies_metadata.csv", "rows sharing a duplicated id", len(dup_meta)),
        ("movies_metadata.csv", "distinct ids that are duplicated", dup_meta["id_num"].nunique()),
        ("movies_metadata.csv", "fully identical duplicate rows",
         int(meta_valid.drop(columns=[c for c in meta_valid.columns if c.endswith(("_parsed", "_names", "_codes"))])
             .duplicated().sum())),
        ("movies_metadata.csv", "release_date missing or unparseable", int(rd.isna().sum())),
        ("movies_metadata.csv", f"release_date after {DATASET_CUTOFF.date()} (announced/future)",
         int((rd > DATASET_CUTOFF).sum())),
        ("movies_metadata.csv", "status != 'Released'", int((meta_valid["status"] != "Released").sum())),
        ("movies_metadata.csv", "adult = True", int((meta_valid["adult"] == "True").sum())),
        ("movies_metadata.csv", "video = True", int((meta_valid["video"] == "True").sum())),
        ("movies_metadata.csv", "vote_average outside 0-10",
         int(((meta_valid["vote_average_num"] < 0) | (meta_valid["vote_average_num"] > 10)).sum())),
        ("movies_metadata.csv", "vote_count < 10 (vote_average unreliable)",
         int((meta_valid["vote_count_num"] < 10).sum())),
        ("movies_metadata.csv", "runtime > 300 min", int((meta_valid["runtime_num"] > 300).sum())),
        ("movies_metadata.csv", "budget between 1 and 999 USD (likely wrong unit)",
         int(meta_valid["budget_num"].between(1, 999).sum())),
        ("movies_metadata.csv", "revenue between 1 and 999 USD (likely wrong unit)",
         int(meta_valid["revenue_num"].between(1, 999).sum())),
        ("movies_metadata.csv", "nested JSON column that failed to parse (any list column)",
         int(sum(meta_valid[c + "_parsed"].isna() & meta_valid[c].notna() for c in LIST_COLUMNS).astype(bool).sum())),
        ("credits.csv", "rows sharing a duplicated id", len(dup_credits)),
        ("credits.csv", "distinct ids that are duplicated", dup_credits["id_num"].nunique()),
        ("keywords.csv", "rows sharing a duplicated id", len(dup_kw)),
        ("keywords.csv", "distinct ids that are duplicated", dup_kw["id_num"].nunique()),
        ("links", "tmdbId missing", int(links["tmdbId"].isna().sum())),
        ("links", "duplicated tmdbId (several MovieLens ids -> one TMDB id)",
         int(links["tmdbId"].dropna().duplicated().sum())),
    ]
    t = pd.DataFrame(rows, columns=["file", "issue", "count"])
    rep.table("04a_data_quality_issues", t, "Data-quality checks")

    if len(malformed):
        show = malformed[["id", "adult", "belongs_to_collection", "budget", "genres", "imdb_id"]].copy()
        for c in show.columns:
            show[c] = show[c].astype(str).str.slice(0, 40)
        rep.table("04b_malformed_rows", show, "Malformed rows in movies_metadata.csv (shifted columns)")
    if len(dup_meta):
        show = dup_meta[["id", "title", "release_date", "vote_count", "popularity"]].sort_values("id")
        rep.table("04c_duplicate_metadata_ids", show, "Duplicated ids in movies_metadata.csv", max_rows=20)
    rep.table("04d_status_values", meta_valid["status"].fillna("<null>").value_counts().rename_axis("status")
              .reset_index(name="movies"), "Values of status")


def numeric_section(rep, meta_valid):
    rep.section("5. Numeric attributes")
    cols = ["budget", "revenue", "runtime", "popularity", "vote_average", "vote_count"]
    rows = []
    for c in cols:
        s = meta_valid[c + "_num"]
        variants = [("all", s.dropna())]
        if c in ("budget", "revenue", "runtime", "vote_count"):
            variants.append(("> 0", s[s > 0]))
        if c == "vote_average":
            variants.append(("vote_count > 0", s[meta_valid["vote_count_num"] > 0]))
        for label, v in variants:
            d = v.describe(percentiles=[0.25, 0.5, 0.75, 0.95])
            rows.append({"column": c, "subset": label, "count": int(d["count"]), "mean": d["mean"],
                         "std": d["std"], "min": d["min"], "p25": d["25%"], "median": d["50%"], "p75": d["75%"],
                         "p95": d["95%"], "max": d["max"]})
    rep.table("05a_numeric_summary", pd.DataFrame(rows),
              "Descriptive statistics (zeros are placeholders - see the '> 0' rows)")

    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5))
    runtime = meta_valid["runtime_num"]
    ax = axes[0, 0]
    ax.hist(runtime[(runtime > 0) & (runtime <= 240)], bins=60, color=BLUE, edgecolor=SURFACE, linewidth=0.5)
    ax.set_title("Runtime (min, 0 < r <= 240)")
    ax = axes[0, 1]
    va = meta_valid.loc[meta_valid["vote_count_num"] > 0, "vote_average_num"]
    ax.hist(va, bins=np.arange(0, 10.25, 0.25), color=BLUE, edgecolor=SURFACE, linewidth=0.5)
    ax.set_title("vote_average (vote_count > 0)")
    ax = axes[0, 2]
    log_hist(ax, meta_valid["vote_count_num"], integer=True)
    ax.set_title("vote_count (> 0, log)")
    ax = axes[1, 0]
    log_hist(ax, meta_valid["budget_num"])
    ax.set_title("Budget USD (> 0, log)")
    ax = axes[1, 1]
    log_hist(ax, meta_valid["revenue_num"])
    ax.set_title("Revenue USD (> 0, log)")
    ax = axes[1, 2]
    log_hist(ax, meta_valid["popularity_num"])
    ax.set_title("Popularity (> 0, log)")
    for a in axes.flat:
        a.set_ylabel("Movies", fontsize=8)
        a.yaxis.set_major_formatter(FuncFormatter(compact))
    fig.tight_layout()
    rep.figure("05a_numeric_distributions", fig, "Distributions of the numeric attributes (placeholders removed)")

    # Correlations (Spearman, zeros treated as missing)
    num = pd.DataFrame({c: meta_valid[c + "_num"] for c in cols})
    for c in ("budget", "revenue", "runtime", "vote_count"):
        num.loc[num[c] == 0, c] = np.nan
    num.loc[meta_valid["vote_count_num"] == 0, "vote_average"] = np.nan
    corr = num.corr(method="spearman")
    rep.table("05b_spearman_correlation", corr.round(3).reset_index().rename(columns={"index": "column"}),
              "Spearman correlation (zeros treated as missing)")
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    im = ax.imshow(corr.values, cmap=DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)), cols, rotation=35, ha="right")
    ax.set_yticks(range(len(cols)), cols)
    ax.grid(False)
    for i in range(len(cols)):
        for j in range(len(cols)):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8, color="white" if abs(v) > 0.85 else INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.outline.set_visible(False)
    ax.set_title("Spearman correlation")
    rep.figure("05b_spearman_correlation", fig, "Rank correlation between numeric attributes")

    both = meta_valid[(meta_valid["budget_num"] > 0) & (meta_valid["revenue_num"] > 0)]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    ax = axes[0]
    ax.scatter(both["budget_num"], both["revenue_num"], s=6, color=BLUE, alpha=0.3, linewidths=0)
    lim = [1, max(both["budget_num"].max(), both["revenue_num"].max()) * 1.5]
    ax.plot(lim, lim, color=MUTED, linewidth=1)
    ax.text(lim[1] / 3, lim[1] / 1.5, "revenue = budget", fontsize=8, color=INK_2, ha="right")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(compact))
    ax.yaxis.set_major_formatter(FuncFormatter(compact))
    ax.set_xlabel("Budget USD")
    ax.set_ylabel("Revenue USD")
    ax.set_title(f"Budget vs revenue (both > 0, n = {len(both):,})")
    ax = axes[1]
    vv = meta_valid[meta_valid["vote_count_num"] > 0]
    ax.scatter(vv["vote_count_num"], vv["vote_average_num"], s=5, color=BLUE, alpha=0.25, linewidths=0)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(compact))
    ax.set_xlabel("vote_count")
    ax.set_ylabel("vote_average")
    ax.set_title("vote_count vs vote_average")
    fig.tight_layout()
    rep.figure("05c_scatter", fig,
               "Left: budget vs revenue (log-log). Right: few votes give extreme averages (0 and 10)")


def time_section(rep, meta_valid):
    rep.section("6. Release dates")
    y = meta_valid["year"].dropna().astype(int)
    per_year = y.value_counts().sort_index()
    t = pd.DataFrame({
        "stat": ["earliest release_date", "latest release_date", "median year", "movies with a date"],
        "value": [str(meta_valid["release_dt"].min().date()), str(meta_valid["release_dt"].max().date()),
                  int(y.median()), f"{len(y):,}"],
    })
    rep.table("06a_release_date_summary", t, "Release date range")
    dec = meta_valid["decade"].dropna().astype(int).value_counts().sort_index()
    rep.table("06b_movies_per_decade", dec.rename_axis("decade").reset_index(name="movies"), "Movies per decade")

    fig, ax = plt.subplots(figsize=(10, 3.8))
    yr = per_year[per_year.index <= 2017]
    ax.fill_between(yr.index, yr.values, color=BLUE, alpha=0.1, linewidth=0)
    ax.plot(yr.index, yr.values, color=BLUE)
    peak = yr.idxmax()
    ax.annotate(f"{peak}: {yr.max():,}", (peak, yr.max()), xytext=(-95, -12), textcoords="offset points",
                fontsize=8, color=INK_2)
    ax.set_xlim(yr.index.min(), 2017)
    ax.set_ylim(0)
    ax.set_title("Movies released per year (up to 2017)")
    ax.set_ylabel("Movies")
    rep.figure("06a_movies_per_year", fig, "Number of movies per release year; the dataset ends mid-2017")

    d = meta_valid[(meta_valid["runtime_num"] > 0) & (meta_valid["decade"] >= 1910) & (meta_valid["decade"] <= 2010)]
    decades = sorted(d["decade"].dropna().astype(int).unique())
    data = [d.loc[d["decade"] == dec_, "runtime_num"].values for dec_ in decades]
    fig, ax = plt.subplots(figsize=(10, 4))
    bp = ax.boxplot(data, showfliers=False, patch_artist=True, widths=0.5,
                    medianprops={"color": INK, "linewidth": 1.5},
                    whiskerprops={"color": AXIS}, capprops={"color": AXIS})
    for b in bp["boxes"]:
        b.set(facecolor="#cde2fb", edgecolor=BLUE)
    ax.set_xticks(range(1, len(decades) + 1), [f"{v}s" for v in decades])
    ax.set_ylabel("Runtime (min)")
    ax.set_title("Runtime by release decade (runtime > 0, outliers hidden)")
    rep.figure("06b_runtime_by_decade", fig, "Runtime distribution per decade")


def categorical_section(rep, meta_valid):
    rep.section("7. Categorical and nested attributes")
    g = top_counts(meta_valid["genre_names"], 50).rename(columns={"value": "genre"})
    g["pct_of_movies"] = [pct(v, len(meta_valid)) for v in g["movies"]]
    rep.table("07a_genres", g, "Genres (a movie can have several)")
    primary = meta_valid["genre_names"].map(lambda v: v[0] if v else None).value_counts()
    rep.table("07b_primary_genre", primary.rename_axis("primary_genre").reset_index(name="movies"),
              "Primary genre (first element in genres)")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [2, 1]})
    barh(axes[0], g["genre"].tolist(), g["movies"].tolist())
    axes[0].set_title("Movies per genre")
    n_genres = meta_valid["genre_names"].map(len).value_counts().sort_index()
    axes[1].bar(n_genres.index, n_genres.values, color=BLUE, width=0.62)
    axes[1].set_xticks(n_genres.index)
    axes[1].grid(axis="x", visible=False)
    axes[1].yaxis.set_major_formatter(FuncFormatter(compact))
    axes[1].set_title("Genres per movie")
    axes[1].set_xlabel("Number of genres")
    axes[1].set_ylabel("Movies")
    fig.tight_layout()
    rep.figure("07a_genres", fig, "Genre frequency and number of genres per movie")

    lang = meta_valid["original_language"].fillna("<null>").value_counts()
    lt = lang.rename_axis("original_language").reset_index(name="movies")
    lt["pct"] = [pct(v, len(meta_valid)) for v in lt["movies"]]
    rep.table("07c_original_language", lt, "original_language", max_rows=25)
    countries = top_counts(meta_valid["country_names"], 200).rename(columns={"value": "production_country"})
    rep.table("07d_production_countries", countries, "Production countries", max_rows=25)
    companies = top_counts(meta_valid["company_names"], 200).rename(columns={"value": "production_company"})
    rep.table("07e_production_companies", companies, "Production companies", max_rows=25)
    spoken = top_counts(meta_valid["spoken_codes"], 200).rename(columns={"value": "spoken_language"})
    rep.table("07f_spoken_languages", spoken, "Spoken languages (ISO 639-1)", max_rows=25)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    top_l = lt.head(15)
    barh(axes[0], top_l["original_language"].tolist(), top_l["movies"].tolist())
    axes[0].set_title("Top 15 original languages")
    top_c = countries.head(15)
    barh(axes[1], [c if len(c) < 26 else c[:24] + "." for c in top_c["production_country"]],
         top_c["movies"].tolist())
    axes[1].set_title("Top 15 production countries")
    fig.tight_layout()
    rep.figure("07b_languages_countries", fig, "Original language and production country")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    top_co = companies.head(20)
    barh(ax, top_co["production_company"].tolist(), top_co["movies"].tolist())
    ax.set_title("Top 20 production companies")
    rep.figure("07c_companies", fig, "Most frequent production companies")

    coll = meta_valid["collection_name"].dropna().value_counts()
    size_dist = coll.value_counts().sort_index()
    t = pd.DataFrame({
        "stat": ["movies in a collection", "distinct collections", "collections with >= 3 movies",
                 "movies in collections with >= 3 movies"],
        "value": [int(coll.sum()), len(coll), int((coll >= 3).sum()), int(coll[coll >= 3].sum())],
    })
    rep.table("07g_collections_summary", t, "belongs_to_collection")
    rep.table("07h_collection_size_distribution", size_dist.rename_axis("movies_in_collection")
              .reset_index(name="collections"), "Collection sizes")
    rep.table("07i_largest_collections", coll.head(20).rename_axis("collection").reset_index(name="movies"),
              "Largest collections by movie count")


def credits_section(rep, credits, meta_ids):
    rep.section("8. Cast and crew (credits.csv)")
    cr = credits.drop_duplicates("id_num")
    cast_len = cr["cast"].map(len)
    crew_len = cr["crew"].map(len)
    t = pd.DataFrame([
        {"field": "cast size", **cast_len.describe(percentiles=[0.5, 0.95]).round(1).to_dict()},
        {"field": "crew size", **crew_len.describe(percentiles=[0.5, 0.95]).round(1).to_dict()},
    ])
    rep.table("08a_cast_crew_size", t, "Cast and crew size per movie")

    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
    axes[0].hist(cast_len.clip(upper=100), bins=50, color=BLUE, edgecolor=SURFACE, linewidth=0.5)
    axes[0].set_title("Cast members per movie (clipped at 100)")
    axes[1].hist(crew_len.clip(upper=150), bins=50, color=BLUE, edgecolor=SURFACE, linewidth=0.5)
    axes[1].set_title("Crew members per movie (clipped at 150)")
    for a in axes:
        a.set_ylabel("Movies")
        a.yaxis.set_major_formatter(FuncFormatter(compact))
    fig.tight_layout()
    rep.figure("08a_cast_crew_size", fig, "Size of cast and crew lists")

    gender_label = {0: "unknown", 1: "female", 2: "male"}
    all_g = Counter(gender_label.get(c[2], "other") for cast in cr["cast"] for c in cast)
    top5_g = Counter(gender_label.get(c[2], "other") for cast in cr["cast"]
                     for c in cast if c[3] is not None and c[3] < 5)
    crew_g = Counter(gender_label.get(c[4], "other") for crew in cr["crew"] for c in crew)
    rows = []
    for label, cnt in [("all cast", all_g), ("top-5 billed cast (order < 5)", top5_g), ("crew", crew_g)]:
        tot = sum(cnt.values())
        rows.append({"group": label, "entries": tot, **{f"{k}_pct": pct(cnt.get(k, 0), tot)
                                                       for k in ("female", "male", "unknown")}})
    gt = pd.DataFrame(rows)
    rep.table("08b_gender", gt, "Gender distribution (0 = unknown, 1 = female, 2 = male)")

    fig, ax = plt.subplots(figsize=(8, 2.8))
    y = np.arange(len(gt))[::-1]
    left = np.zeros(len(gt))
    for key, color in [("female", BLUE), ("male", ORANGE), ("unknown", "#c3c2b7")]:
        vals = gt[f"{key}_pct"].values
        ax.barh(y, vals, left=left, color=color, height=0.55, label=key, edgecolor=SURFACE, linewidth=2)
        for yi, l, v in zip(y, left, vals):
            if v >= 8:
                ax.text(l + v / 2, yi, f"{v:.0f}%", ha="center", va="center", fontsize=8,
                        color="white" if key != "unknown" else INK)
        left += vals
    ax.set_yticks(y, gt["group"])
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.grid(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Gender of credited people")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.18), fontsize=8)
    rep.figure("08b_gender", fig, "Gender split; a large share of entries have unknown gender (0)")

    dept = Counter(c[3] for crew in cr["crew"] for c in crew)
    dt = pd.DataFrame(dept.most_common(), columns=["department", "crew_entries"])
    rep.table("08c_crew_departments", dt, "Crew departments")
    jobs = Counter(c[2] for crew in cr["crew"] for c in crew)
    rep.table("08d_crew_jobs", pd.DataFrame(jobs.most_common(), columns=["job", "crew_entries"]),
              "Crew jobs", max_rows=20)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    barh(ax, dt["department"].tolist(), dt["crew_entries"].tolist())
    ax.set_title("Crew entries per department")
    rep.figure("08c_crew_departments", fig, "Crew entries per department")

    directors_per_movie = cr["crew"].map(lambda crew: len({c[0] for c in crew if c[2] == "Director"}))
    rep.table("08e_directors_per_movie", directors_per_movie.value_counts().sort_index()
              .rename_axis("directors").reset_index(name="movies"), "Number of directors per movie")
    director_movies = Counter(name for crew in cr["crew"] for name in {c[1] for c in crew if c[2] == "Director"})
    actor_movies = Counter(name for cast in cr["cast"] for name in {c[1] for c in cast})
    rep.table("08f_top_directors", pd.DataFrame(director_movies.most_common(20), columns=["director", "movies"]),
              "Most frequent directors")
    rep.table("08g_top_actors", pd.DataFrame(actor_movies.most_common(20), columns=["actor", "movies"]),
              "Most frequent actors")
    t = pd.DataFrame({
        "stat": ["distinct directors", "directors with >= 5 movies", "distinct actors", "actors with >= 10 movies",
                 "credits ids not in movies_metadata"],
        "value": [len(director_movies), sum(v >= 5 for v in director_movies.values()), len(actor_movies),
                  sum(v >= 10 for v in actor_movies.values()), int((~cr["id_num"].isin(meta_ids)).sum())],
    })
    rep.table("08h_people_summary", t, "People summary")


def keywords_section(rep, keywords):
    rep.section("9. Keywords (keywords.csv)")
    kw = keywords.drop_duplicates("id_num")
    n_kw = kw["keyword_names"].map(len)
    top = top_counts(kw["keyword_names"], 30).rename(columns={"value": "keyword"})
    rep.table("09a_top_keywords", top, "Most frequent keywords")
    t = pd.DataFrame([{"field": "keywords per movie", **n_kw.describe(percentiles=[0.5, 0.95]).round(1).to_dict(),
                       "distinct_keywords": len({k for ks in kw["keyword_names"] for k in ks})}])
    rep.table("09b_keywords_per_movie", t, "Keywords per movie")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1.4, 1]})
    barh(axes[0], top["keyword"].head(20).tolist(), top["movies"].head(20).tolist())
    axes[0].set_title("Top 20 keywords")
    axes[1].hist(n_kw.clip(upper=40), bins=41, color=BLUE, edgecolor=SURFACE, linewidth=0.5)
    axes[1].set_title("Keywords per movie (clipped at 40)")
    axes[1].set_ylabel("Movies")
    fig.tight_layout()
    rep.figure("09a_keywords", fig, "Keyword frequency and keywords per movie")


def ratings_section(rep, ratings, links, meta_ids, ratings_name):
    rep.section(f"10. Ratings ({ratings_name})")
    user_n, movie_n = ratings["user_n"], ratings["movie_n"]
    users = user_n[user_n > 0]
    movies = movie_n[movie_n > 0]
    mean_r = sum(k * v for k, v in ratings["rating_counts"].items()) / ratings["n_rows"]
    t = pd.DataFrame({
        "stat": ["ratings", "distinct users", "distinct movies (MovieLens movieId)", "mean rating",
                 "first rating", "last rating", "null values", "duplicate (user, movie) pairs within a chunk",
                 "users with >= 20 ratings", "median ratings per user", "median ratings per movie",
                 "max ratings by one user", "max ratings for one movie"],
        "value": [f"{ratings['n_rows']:,}", f"{len(users):,}", f"{len(movies):,}", f"{mean_r:.3f}",
                  str(ratings["ts_min"]), str(ratings["ts_max"]), ratings["n_null"], ratings["n_dupe_pairs"],
                  f"{int((user_n >= 20).sum()):,}", int(np.median(users)), int(np.median(movies)),
                  f"{int(users.max()):,}", f"{int(movies.max()):,}"],
    })
    rep.table("10a_ratings_summary", t, "Ratings summary")
    rc = pd.Series(ratings["rating_counts"]).sort_index()
    rt = pd.DataFrame({"rating": rc.index, "count": rc.values.astype(int)})
    rt["pct"] = [pct(v, ratings["n_rows"]) for v in rt["count"]]
    rep.table("10b_rating_values", rt, "Rating value distribution")

    # Coverage: how many ratings can be joined to movies_metadata via links
    link_map = links.dropna(subset=["tmdbId"])
    link_map = link_map[link_map["movieId"] < len(movie_n)]
    rated_ids = np.nonzero(movie_n)[0]
    linked = link_map[link_map["movieId"].isin(rated_ids)]
    in_meta = linked[linked["tmdbId"].isin(meta_ids)]
    ratings_linked = int(movie_n[linked["movieId"].astype(int).unique()].sum())
    ratings_in_meta = int(movie_n[in_meta["movieId"].astype(int).unique()].sum())
    t = pd.DataFrame([
        {"step": "rated movieIds", "movies": len(rated_ids), "ratings": ratings["n_rows"]},
        {"step": "... with a tmdbId in links", "movies": linked["movieId"].nunique(), "ratings": ratings_linked},
        {"step": "... whose tmdbId exists in movies_metadata", "movies": in_meta["movieId"].nunique(),
         "ratings": ratings_in_meta},
    ])
    t["ratings_pct"] = [pct(v, ratings["n_rows"]) for v in t["ratings"]]
    rep.table("10c_ratings_join_coverage", t, "Joining ratings -> links -> movies_metadata")

    var = ratings["user_sumsq"] / np.maximum(user_n, 1) - (ratings["user_sum"] / np.maximum(user_n, 1)) ** 2
    var20 = var[user_n >= 20]
    d = pd.Series(var20).describe(percentiles=[0.5, 0.95]).round(3)
    rep.table("10d_user_variance", pd.DataFrame([{"field": "population variance per user (>= 20 ratings)",
                                                   **d.to_dict()}]), "Rating variance per user")

    fig, axes = plt.subplots(1, 3, figsize=(14, 3.9))
    ax = axes[0]
    ax.bar(rt["rating"], rt["count"], width=0.36, color=BLUE)
    ax.set_xticks(rt["rating"], [f"{v:g}" for v in rt["rating"]], fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(FuncFormatter(compact))
    ax.set_title("Rating values")
    ax.set_ylabel("Ratings")
    log_hist(axes[1], users, integer=True)
    axes[1].set_yscale("log")
    axes[1].set_title("Ratings per user (log-log)")
    axes[1].set_ylabel("Users")
    log_hist(axes[2], movies, integer=True)
    axes[2].set_yscale("log")
    axes[2].set_title("Ratings per movie (log-log)")
    axes[2].set_ylabel("Movies")
    fig.tight_layout()
    rep.figure("10a_ratings_distributions", fig,
               "Ratings favour whole stars; activity per user and per movie is heavily long-tailed")

    yc = pd.Series(ratings["year_counts"]).sort_index()
    rep.table("10e_ratings_per_year", yc.rename_axis("year").reset_index(name="ratings"), "Ratings per year")
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.bar(yc.index, yc.values, color=BLUE, width=0.62)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(FuncFormatter(compact))
    ax.set_title("Ratings per year (from timestamp)")
    ax.set_ylabel("Ratings")
    rep.figure("10b_ratings_per_year", fig, "Ratings submitted per year")


def coverage_section(rep, meta_valid, credits, keywords, links):
    rep.section("11. Cross-file coverage (join keys)")
    meta_ids = set(meta_valid["id_num"].dropna().astype(int))
    credit_ids = set(credits["id_num"].dropna().astype(int))
    kw_ids = set(keywords["id_num"].dropna().astype(int))
    link_ids = set(links["tmdbId"].dropna().astype(int))
    n = len(meta_ids)
    rows = [
        ("distinct ids in movies_metadata", n),
        ("... also in credits.csv", len(meta_ids & credit_ids)),
        ("... also in keywords.csv", len(meta_ids & kw_ids)),
        ("... also in links (tmdbId)", len(meta_ids & link_ids)),
        ("... in credits, keywords and links", len(meta_ids & credit_ids & kw_ids & link_ids)),
    ]
    t = pd.DataFrame(rows, columns=["set", "movies"])
    t["pct_of_metadata"] = [pct(v, n) for v in t["movies"]]
    rep.table("11a_join_coverage", t, "Join coverage on the TMDB id")
    t2 = pd.DataFrame([
        ("credits ids not in metadata", len(credit_ids - meta_ids)),
        ("keywords ids not in metadata", len(kw_ids - meta_ids)),
        ("links tmdbIds not in metadata", len(link_ids - meta_ids)),
    ], columns=["orphans", "ids"])
    rep.table("11b_orphan_ids", t2, "Ids that do not match any movie")


def task_readiness_section(rep, meta_valid, credits, ratings):
    rep.section("12. Coverage of the fields used in Part 2")
    rep.text("How many movies have the fields each Part 2 question depends on. "
             "Low coverage means the answer is based on a subset of the data and should be discussed in the report.")
    m = meta_valid.drop_duplicates("id_num").set_index("id_num")
    cr = credits.drop_duplicates("id_num").set_index("id_num")
    cr = cr[cr.index.isin(m.index)]
    n = len(m)
    has_dir = cr["crew"].map(lambda crew: any(c[2] == "Director" for c in crew)).reindex(m.index, fill_value=False)
    n_cast = cr["cast"].map(len).reindex(m.index, fill_value=0)
    top5_known = cr["cast"].map(lambda cast: sum(1 for c in cast if c[3] is not None and c[3] < 5
                                                 and c[2] in (1, 2))).reindex(m.index, fill_value=0)
    rev = m["revenue_num"].fillna(0) > 0
    vc = m["vote_count_num"].fillna(0)
    genres = m["genre_names"].map(len) > 0
    runtime = m["runtime_num"].fillna(0) > 0
    dated = m["release_dt"].notna()
    coll = m["collection_name"].notna()
    text = m["overview"].fillna("") + " " + m["tagline"].fillna("")
    has_text = (m["overview"].notna() | m["tagline"].notna())
    noir = text.str.contains("noir", case=False)
    us = m["country_codes"].map(lambda v: "US" in v)
    non_en = m["original_language"].fillna("en") != "en"
    user_n = ratings["user_n"]
    rows = [
        ("Q1", "has Director in crew", int(has_dir.sum())),
        ("Q1", "has Director and revenue > 0", int((has_dir & rev).sum())),
        ("Q2", "cast size >= 2", int((n_cast >= 2).sum())),
        ("Q2/Q3", "cast size >= 1 and genres non-empty", int(((n_cast >= 1) & genres).sum())),
        ("Q4", "belongs_to_collection set", int(coll.sum())),
        ("Q4", "in collection and revenue > 0", int((coll & rev).sum())),
        ("Q5", "release_date, genres and runtime > 0", int((dated & genres & runtime).sum())),
        ("Q6", "release_date and >= 1 top-5 cast with known gender", int((dated & (top5_known > 0)).sum())),
        ("Q7", "overview or tagline present", int(has_text.sum())),
        ("Q7", "contains 'noir' (substring) and vote_count >= 50", int((noir & (vc >= 50)).sum())),
        ("Q8", "vote_count >= 100 with Director and cast", int(((vc >= 100) & has_dir & (n_cast > 0)).sum())),
        ("Q9", "original_language != en and a US production country", int((non_en & us).sum())),
    ]
    t = pd.DataFrame(rows, columns=["task", "condition", "movies"])
    t["pct_of_movies"] = [pct(v, n) for v in t["movies"]]
    t = pd.concat([t, pd.DataFrame([{"task": "Q10", "condition": "users with >= 20 ratings",
                                     "movies": int((user_n >= 20).sum()),
                                     "pct_of_movies": pct((user_n >= 20).sum(), (user_n > 0).sum())}])])
    t = t.rename(columns={"movies": "count", "pct_of_movies": "pct"})
    rep.table("12a_task_field_coverage", t, f"Field coverage per Part 2 question (n = {n:,} unique movies; "
                                            "Q10 is % of users)")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "eda_output")
    ap.add_argument("--small", action="store_true", help="use ratings_small.csv and links_small.csv")
    args = ap.parse_args()
    data_dir, cache_dir = args.data_dir, REPO_ROOT / ".eda_cache"
    rep = Report(args.out_dir)
    t0 = time.time()

    print("Loading movies_metadata.csv ...")
    meta = load_metadata(data_dir, cache_dir)
    meta_valid = meta[meta["id_num"].notna()].copy()
    print("Loading credits.csv (slow the first time) ...")
    credits = load_credits(data_dir, cache_dir)
    print("Loading keywords.csv ...")
    keywords = load_keywords(data_dir, cache_dir)
    links, links_path = load_links(data_dir, args.small)
    ratings_path = data_dir / ("ratings_small.csv" if args.small else "ratings.csv")
    print(f"Scanning {ratings_path.name} ...")
    ratings = scan_ratings(ratings_path)

    meta_ids = set(meta_valid["id_num"].astype(int))
    director_ids = set(credits.loc[credits["crew"].map(lambda cr: any(c[2] == "Director" for c in cr)),
                                   "id_num"].dropna().astype(int))

    print("Writing tables and figures ...")
    rows_frames = {"movies_metadata.csv": (meta, 24), "credits.csv": (credits, 3),
                   "keywords.csv": (keywords, 2)}
    # Files overview
    rep.section("1. Files overview")
    rows = [{"file": name, "size_mb": round((data_dir / name).stat().st_size / 1e6, 1), "rows": len(df),
             "columns": ncols} for name, (df, ncols) in rows_frames.items()]
    rows.append({"file": links_path.name, "size_mb": round(links_path.stat().st_size / 1e6, 1),
                 "rows": len(links), "columns": 3})
    rows.append({"file": ratings_path.name, "size_mb": round(ratings_path.stat().st_size / 1e6, 1),
                 "rows": ratings["n_rows"], "columns": 4})
    rep.table("01_files_overview", pd.DataFrame(rows), "Raw files: size, rows and columns")

    schema_section(rep, meta, links, links_path.name, data_dir)
    missing_section(rep, meta_valid, credits, keywords)
    missing_by_decade_figure(rep, meta_valid, director_ids)
    quality_section(rep, meta, meta_valid, credits, keywords, links)
    numeric_section(rep, meta_valid)
    time_section(rep, meta_valid)
    categorical_section(rep, meta_valid)
    credits_section(rep, credits, meta_ids)
    keywords_section(rep, keywords)
    ratings_section(rep, ratings, links, meta_ids, ratings_path.name)
    coverage_section(rep, meta_valid, credits, keywords, links)
    task_readiness_section(rep, meta_valid, credits, ratings)

    header = ("# EDA overview - The Movies Dataset\n\n"
              f"Generated by `eda_overview.py` from `{data_dir.name}/` "
              f"using `{ratings_path.name}` and `{links_path.name}`. "
              "Tables are in `tables/` (CSV + Markdown), figures in `figures/`.")
    rep.write(header)
    print(f"Done in {time.time() - t0:.0f}s -> {args.out_dir / 'EDA_summary.md'}")


if __name__ == "__main__":
    main()
