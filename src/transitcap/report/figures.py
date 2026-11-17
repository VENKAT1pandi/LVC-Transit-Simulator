"""Static figures for the memos. Colours: validated reference palette slots 1-2 (blue, orange);
text in ink tokens, recessive grid, one y-axis per chart, identity never by colour alone."""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from transitcap.paths import OUTPUTS  # noqa: E402

RES = OUTPUTS / "results"
FIG = OUTPUTS / "figures"
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LABELS = {"elasticity (incl. transfer error)": "capitalization elasticity", "gap": "funding gap",
          "lid_capture": "LID capture share", "lid_eta": "LID behavioural response",
          "rate": "borrowing rate", "lid_collection": "LID collection rate",
          "lid_admin": "LID administration cost", "tia_rate": "TIA levy rate",
          "tia_collection": "TIA collection rate", "tia_admin": "TIA administration cost",
          "tia_eta": "TIA behavioural response", "lag": "adoption lag"}


def _axes(title: str, ylabel: str, w=7.0, h=3.6):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=10, color=INK, pad=10)
    ax.set_ylabel(ylabel, fontsize=8, color=INK2)
    return fig, ax


def event_study():
    p = pd.read_csv(RES / "event_study_primary.csv")
    s = pd.read_csv(RES / "event_study_spillover.csv")
    fig, ax = _axes("Effect on log sale price by year relative to funding commitment",
                    "log points (95% band)")
    for df, c, lab, off in ((p, BLUE, "Treated ring (0-10 min walk)", -0.12),
                            (s, ORANGE, "Spillover ring (10-20 min)", 0.12)):
        df = df.dropna(subset=["att"])
        ax.fill_between(df.e, df.lo, df.hi, color=c, alpha=0.12, lw=0)
        ax.plot(df.e, df.att, color=c, lw=2, marker="o", ms=4, label=lab)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.axvline(-0.5, color=INK2, lw=0.8, ls=":")
    ax.text(-0.4, ax.get_ylim()[1], "funding commitment", fontsize=7, color=INK2, va="top")
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
    ax.set_xlabel("years since funding commitment (e = -1 is the reference year)", fontsize=8, color=INK2)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "event_study.png")
    plt.close(fig)


def dose_response():
    est = json.loads((RES / "estimates.json").read_text())
    st = pd.read_csv(RES / "station_estimates.csv")
    fig, ax = _axes("Station effects against the access gain each station created",
                    "post-period effect, log points")
    ax.errorbar(st.dose, st.att, yerr=[st.att - st.lo, st.hi - st.att], fmt="o", ms=5, color=BLUE,
                ecolor=GRID, elinewidth=1.2, capsize=0, label="station (95% interval)")
    e = est["elasticity"]["elasticity"]
    xs = pd.Series([0, st.dose.max() * 1.05])
    ax.plot(xs, e * xs, color=INK2, lw=1.5, ls="--", label=f"fitted elasticity {e:.3f}")
    ax.axhline(0, color=INK2, lw=0.8)
    for r in st.itertuples():
        if abs(r.att) == st.att.abs().max() or r.dose == st.dose.max():
            ax.annotate(r.station_id, (r.dose, r.att), fontsize=7, color=INK2,
                        xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("change in log jobs reachable in 45 min by walk + Link", fontsize=8, color=INK2)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "dose_response.png")
    plt.close(fig)


def tornado():
    rev = json.loads((RES / "revenue.json").read_text())
    t = pd.DataFrame(rev["tornado"])
    t = t[t.swing > 0].head(8).iloc[::-1]  # inputs of the other instrument have no effect
    fig, ax = _axes(f"What drives the {rev['best_instrument'].upper()} funding ratio",
                    "", w=7, h=3.4)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.grid(axis="y", visible=False)
    lo, hi = t[["low", "high"]].min(axis=1), t[["low", "high"]].max(axis=1)
    ax.barh(t.input.map(lambda k: LABELS.get(k, k)), hi - lo, left=lo, color=BLUE, height=0.55)
    ax.axvline(0.05, color=ORANGE, lw=1.5, ls="--", label="materiality threshold (5%)")
    ax.set_xlabel("funding ratio when the input moves from its 10th to 90th percentile",
                  fontsize=8, color=INK2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "tornado.png")
    plt.close(fig)


def spec_curve():
    est = json.loads((RES / "estimates.json").read_text())
    sc = pd.DataFrame(est["spec_curve"]).iloc[::-1]
    fig, ax = _axes("Post-period effect under each pre-registered specification", "", w=7, h=2.8)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.grid(axis="y", visible=False)
    ax.errorbar(sc.estimate, sc.spec, xerr=[sc.estimate - sc.lo, sc.hi - sc.estimate], fmt="o",
                color=BLUE, ecolor=GRID, elinewidth=1.5, ms=5)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_xlabel("log points (95% interval)", fontsize=8, color=INK2)
    fig.tight_layout()
    fig.savefig(FIG / "spec_curve.png")
    plt.close(fig)


def write_all():
    FIG.mkdir(parents=True, exist_ok=True)
    event_study()
    dose_response()
    tornado()
    spec_curve()
