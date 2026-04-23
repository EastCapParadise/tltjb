"""
TLTJB - The League That Johnny Built
Data pipeline: reads Excel historical data + ESPN API, outputs data/data.json
Run: python scripts/build_data.py
"""

import json
import os
import sys
import pandas as pd
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")

with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

EXCEL_PATH = os.path.join(ROOT, CONFIG["excel_file"])
WOODSHED = CONFIG["league"]["woodshed_threshold"]

# Team id -> display name map
DISPLAY = {t["id"]: t["display"] for t in CONFIG["teams"]}

def display(name):
    return DISPLAY.get(name, name)

# ---------------------------------------------------------------------------
# Load Excel data
# ---------------------------------------------------------------------------
print("Loading Excel data...")
xl = pd.ExcelFile(EXCEL_PATH)
rs_df = pd.read_excel(xl, sheet_name=CONFIG["sheets"]["regular_season"])
pl_df = pd.read_excel(xl, sheet_name=CONFIG["sheets"]["playoffs"])
tb_df = pd.read_excel(xl, sheet_name=CONFIG["sheets"]["tables"])

# Clean types
for df in [rs_df, pl_df]:
    df["Year"] = df["Year"].astype(int)
    df["Matchup Week"] = df["Matchup Week"].astype(int)
    df["Winner Pts"] = pd.to_numeric(df["Winner Pts"], errors="coerce").fillna(0)
    df["Loser Pts"] = pd.to_numeric(df["Loser Pts"], errors="coerce").fillna(0)
    df["Margin Victory"] = df["Winner Pts"] - df["Loser Pts"]

tb_df["Year"] = tb_df["Year"].astype(int)

ALL_YEARS = sorted(rs_df["Year"].unique().tolist())
ALL_TEAMS = sorted(DISPLAY.keys())

# ---------------------------------------------------------------------------
# ESPN API (current/upcoming season)
# ---------------------------------------------------------------------------
def fetch_espn_season(year):
    """Attempt to pull a season from ESPN API. Returns list of game dicts or []."""
    try:
        import requests
        league_id = CONFIG["league"]["espn_league_id"]
        s2 = CONFIG["league"]["espn_s2"]
        swid = CONFIG["league"]["swid"]
        cookies = {"espn_s2": s2, "SWID": swid}
        games = []
        for week in range(1, 18):
            url = (
                f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}"
                f"/segments/0/leagues/{league_id}?view=mMatchup&view=mMatchupScore&scoringPeriodId={week}"
            )
            r = requests.get(url, cookies=cookies, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            schedule = data.get("schedule", [])
            for g in schedule:
                if g.get("matchupPeriodId") != week:
                    continue
                home = g.get("home", {})
                away = g.get("away", {})
                home_pts = home.get("totalPointsLive") or home.get("totalPoints", 0)
                away_pts = away.get("totalPointsLive") or away.get("totalPoints", 0)
                home_name = home.get("teamId")
                away_name = away.get("teamId")
                if home_name and away_name:
                    games.append({
                        "year": year, "week": week,
                        "home_id": home_name, "away_id": away_name,
                        "home_pts": round(float(home_pts), 2),
                        "away_pts": round(float(away_pts), 2),
                    })
        return games
    except Exception as e:
        print(f"  ESPN API error: {e}")
        return []

# ---------------------------------------------------------------------------
# Build matchup list (all games, regular + playoffs)
# ---------------------------------------------------------------------------
def build_all_matchups():
    matchups = []
    for _, r in rs_df.iterrows():
        matchups.append({
            "year": int(r["Year"]),
            "week": int(r["Matchup Week"]),
            "type": "regular",
            "playoff_round": None,
            "winner": r["Winner Name"],
            "loser": r["Loser Name"],
            "winner_pts": float(r["Winner Pts"]),
            "loser_pts": float(r["Loser Pts"]),
            "margin": float(r["Margin Victory"]),
            "total": float(r["Winner Pts"]) + float(r["Loser Pts"]),
            "home": r["Home Name"],
            "away": r["Away Name"],
            "home_pts": float(r["Home Total Points"]),
            "away_pts": float(r["Away Total Points"]),
        })
    for _, r in pl_df.iterrows():
        matchups.append({
            "year": int(r["Year"]),
            "week": int(r["Matchup Week"]),
            "type": "playoff",
            "playoff_round": r["Playoff Round"],
            "winner": r["Winner Name"],
            "loser": r["Loser Name"],
            "winner_pts": float(r["Winner Pts"]),
            "loser_pts": float(r["Loser Pts"]),
            "margin": float(r["Margin Victory"]),
            "total": float(r["Winner Pts"]) + float(r["Loser Pts"]),
            "home": r["Home Name"],
            "away": r["Away Name"],
            "home_pts": float(r["Home Total Points"]),
            "away_pts": float(r["Away Total Points"]),
        })
    matchups.sort(key=lambda x: (x["year"], x["week"]))
    return matchups

ALL_MATCHUPS = build_all_matchups()

# ---------------------------------------------------------------------------
# Season tables (final standings per year)
# ---------------------------------------------------------------------------
def build_season_tables():
    tables = {}
    for year, grp in tb_df.groupby("Year"):
        rows = []
        for _, r in grp.sort_values("Final Rank").iterrows():
            rows.append({
                "team": r["Owner First Name"],
                "display": display(r["Owner First Name"]),
                "playoff_seed": int(r["Playoff Seed"]),
                "final_rank": int(r["Final Rank"]),
                "wins": int(r["Wins"]),
                "losses": int(r["Losses"]),
                "playoff": r["Playoff"] == "Y",
                "points_for": round(float(r["Points For"]), 2),
                "points_against": round(float(r["Points Against"]), 2),
                "ppg": round(float(r["Pts/Game"]), 2),
            })
        tables[int(year)] = rows
    return tables

SEASON_TABLES = build_season_tables()

# ---------------------------------------------------------------------------
# Championship history
# ---------------------------------------------------------------------------
def build_championship_history():
    champs = []
    for year in ALL_YEARS:
        pl_year = pl_df[(pl_df["Year"] == year) & (pl_df["Playoff Round"] == "Championship")]
        if pl_year.empty:
            continue
        row = pl_year.iloc[0]
        champs.append({
            "year": year,
            "champion": row["Winner Name"],
            "champion_display": display(row["Winner Name"]),
            "runner_up": row["Loser Name"],
            "runner_up_display": display(row["Loser Name"]),
            "champion_pts": float(row["Winner Pts"]),
            "runner_up_pts": float(row["Loser Pts"]),
            "margin": float(row["Margin Victory"]),
        })
    return sorted(champs, key=lambda x: -x["year"])

CHAMP_HISTORY = build_championship_history()

# ---------------------------------------------------------------------------
# All-time owner career stats
# ---------------------------------------------------------------------------
def build_owner_stats():
    stats = {}
    for team in ALL_TEAMS:
        reg_wins = sum(1 for m in ALL_MATCHUPS if m["type"] == "regular" and m["winner"] == team)
        reg_losses = sum(1 for m in ALL_MATCHUPS if m["type"] == "regular" and m["loser"] == team)
        reg_pts = sum(m["winner_pts"] for m in ALL_MATCHUPS if m["type"] == "regular" and m["winner"] == team)
        reg_pts += sum(m["loser_pts"] for m in ALL_MATCHUPS if m["type"] == "regular" and m["loser"] == team)
        reg_pa = sum(m["loser_pts"] for m in ALL_MATCHUPS if m["type"] == "regular" and m["winner"] == team)
        reg_pa += sum(m["winner_pts"] for m in ALL_MATCHUPS if m["type"] == "regular" and m["loser"] == team)

        pl_wins = sum(1 for m in ALL_MATCHUPS if m["type"] == "playoff" and m["winner"] == team and m["playoff_round"] != "3rd Place")
        pl_losses = sum(1 for m in ALL_MATCHUPS if m["type"] == "playoff" and m["loser"] == team and m["playoff_round"] != "3rd Place")
        pl_apps = sum(1 for y in ALL_YEARS if any(
            (m["winner"] == team or m["loser"] == team) and m["type"] == "playoff" and m["year"] == y
            for m in ALL_MATCHUPS))
        championships = sum(1 for c in CHAMP_HISTORY if c["champion"] == team)

        years_active = sorted(set(
            m["year"] for m in ALL_MATCHUPS if m["winner"] == team or m["loser"] == team
        ))
        total_games = reg_wins + reg_losses
        ppg = round(reg_pts / total_games, 2) if total_games else 0

        # Season finishes from tables
        finishes = []
        for y in years_active:
            if y in SEASON_TABLES:
                for row in SEASON_TABLES[y]:
                    if row["team"] == team:
                        finishes.append({"year": y, "rank": row["final_rank"], "wins": row["wins"], "losses": row["losses"]})

        stats[team] = {
            "team": team,
            "display": display(team),
            "years_active": years_active,
            "seasons": len(years_active),
            "reg_wins": reg_wins,
            "reg_losses": reg_losses,
            "reg_pct": round(reg_wins / (reg_wins + reg_losses), 4) if (reg_wins + reg_losses) else 0,
            "points_for": round(reg_pts, 2),
            "points_against": round(reg_pa, 2),
            "ppg": ppg,
            "playoff_appearances": pl_apps,
            "playoff_wins": pl_wins,
            "playoff_losses": pl_losses,
            "championships": championships,
            "season_finishes": finishes,
        }
    return stats

OWNER_STATS = build_owner_stats()

# ---------------------------------------------------------------------------
# Head to head records
# ---------------------------------------------------------------------------
def build_h2h():
    h2h = defaultdict(lambda: defaultdict(lambda: {"reg_wins": 0, "reg_losses": 0, "pl_wins": 0, "pl_losses": 0, "matchups": []}))
    for m in ALL_MATCHUPS:
        w, l = m["winner"], m["loser"]
        t = m["type"]
        if t == "regular":
            h2h[w][l]["reg_wins"] += 1
            h2h[l][w]["reg_losses"] += 1
        elif t == "playoff" and m["playoff_round"] not in ("3rd Place",):
            h2h[w][l]["pl_wins"] += 1
            h2h[l][w]["pl_losses"] += 1

        entry = {
            "year": m["year"], "week": m["week"], "type": t,
            "playoff_round": m["playoff_round"],
            "winner": w, "winner_display": display(w),
            "loser": l, "loser_display": display(l),
            "winner_pts": m["winner_pts"], "loser_pts": m["loser_pts"],
            "margin": m["margin"],
        }
        h2h[w][l]["matchups"].append(entry)
        h2h[l][w]["matchups"].append(entry)

    # Serialize
    out = {}
    for team in ALL_TEAMS:
        out[team] = {}
        for opp in ALL_TEAMS:
            if opp == team:
                continue
            rec = h2h[team][opp]
            rw = rec["reg_wins"]
            rl = rec["reg_losses"]
            pw = rec["pl_wins"]
            pl_ = rec["pl_losses"]
            matchups = sorted(rec["matchups"], key=lambda x: (x["year"], x["week"]))
            out[team][opp] = {
                "reg_wins": rw, "reg_losses": rl,
                "pl_wins": pw, "pl_losses": pl_,
                "total_wins": rw + pw, "total_losses": rl + pl_,
                "matchups": matchups,
            }
    return out

H2H = build_h2h()

# ---------------------------------------------------------------------------
# Playoff bracket data per season
# ---------------------------------------------------------------------------
def build_playoff_brackets():
    brackets = {}
    round_order = ["Quarters", "Semis", "Championship", "3rd Place"]
    for year in ALL_YEARS:
        pl_year = pl_df[pl_df["Year"] == year]
        rounds = {}
        for rnd in round_order:
            games = pl_year[pl_year["Playoff Round"] == rnd]
            if games.empty:
                continue
            rounds[rnd] = []
            for _, r in games.iterrows():
                rounds[rnd].append({
                    "winner": r["Winner Name"],
                    "winner_display": display(r["Winner Name"]),
                    "loser": r["Loser Name"],
                    "loser_display": display(r["Loser Name"]),
                    "winner_pts": float(r["Winner Pts"]),
                    "loser_pts": float(r["Loser Pts"]),
                    "margin": float(r["Margin Victory"]),
                    "week": int(r["Matchup Week"]),
                })
        brackets[year] = rounds
    return brackets

PLAYOFF_BRACKETS = build_playoff_brackets()

# ---------------------------------------------------------------------------
# All-time playoff standings
# ---------------------------------------------------------------------------
def build_playoff_standings():
    rows = []
    for team in ALL_TEAMS:
        apps = 0
        wins = 0
        losses = 0
        titles = 0
        for year in ALL_YEARS:
            if year not in PLAYOFF_BRACKETS:
                continue
            bracket = PLAYOFF_BRACKETS[year]
            appeared = False
            for rnd, games in bracket.items():
                if rnd == "3rd Place":
                    continue
                for g in games:
                    if g["winner"] == team or g["loser"] == team:
                        appeared = True
                        if g["winner"] == team:
                            wins += 1
                        else:
                            losses += 1
            if appeared:
                apps += 1
        titles = sum(1 for c in CHAMP_HISTORY if c["champion"] == team)
        total = wins + losses
        rows.append({
            "team": team,
            "display": display(team),
            "appearances": apps,
            "wins": wins,
            "losses": losses,
            "win_pct": round(wins / total, 4) if total else 0,
            "championships": titles,
        })
    return sorted(rows, key=lambda x: (-x["championships"], -x["appearances"], -x["wins"]))

# ---------------------------------------------------------------------------
# Records: top scores, low scores, blowouts, woodsheds
# ---------------------------------------------------------------------------
def build_records():
    all_scores = []
    for m in ALL_MATCHUPS:
        all_scores.append({"team": m["winner"], "display": display(m["winner"]), "pts": m["winner_pts"], "year": m["year"], "week": m["week"], "type": m["type"], "playoff_round": m["playoff_round"], "opp": m["loser"], "opp_display": display(m["loser"])})
        all_scores.append({"team": m["loser"], "display": display(m["loser"]), "pts": m["loser_pts"], "year": m["year"], "week": m["week"], "type": m["type"], "playoff_round": m["playoff_round"], "opp": m["winner"], "opp_display": display(m["winner"])})

    all_scores.sort(key=lambda x: -x["pts"])
    top10_high = all_scores[:10]
    top10_low = sorted(all_scores, key=lambda x: x["pts"])[:10]

    blowouts = sorted(ALL_MATCHUPS, key=lambda x: -x["margin"])[:10]
    blowout_list = [{
        "year": m["year"], "week": m["week"], "type": m["type"],
        "playoff_round": m["playoff_round"],
        "winner": m["winner"], "winner_display": display(m["winner"]),
        "loser": m["loser"], "loser_display": display(m["loser"]),
        "winner_pts": m["winner_pts"], "loser_pts": m["loser_pts"],
        "margin": m["margin"],
    } for m in blowouts]

    # Woodsheds (margin >= threshold)
    woodsheds = [m for m in ALL_MATCHUPS if m["margin"] >= WOODSHED]
    woodsheds_sorted = sorted(woodsheds, key=lambda x: -x["margin"])

    given = defaultdict(int)
    received = defaultdict(int)
    for m in woodsheds:
        given[m["winner"]] += 1
        received[m["loser"]] += 1

    woodshed_list = [{
        "year": m["year"], "week": m["week"], "type": m["type"],
        "playoff_round": m["playoff_round"],
        "winner": m["winner"], "winner_display": display(m["winner"]),
        "loser": m["loser"], "loser_display": display(m["loser"]),
        "winner_pts": m["winner_pts"], "loser_pts": m["loser_pts"],
        "margin": m["margin"],
    } for m in woodsheds_sorted[:10]]

    given_lb = sorted([{"team": t, "display": display(t), "count": c} for t, c in given.items()], key=lambda x: -x["count"])
    received_lb = sorted([{"team": t, "display": display(t), "count": c} for t, c in received.items()], key=lambda x: -x["count"])

    return {
        "top10_high": top10_high,
        "top10_low": top10_low,
        "top10_blowouts": blowout_list,
        "woodsheds": {
            "top10": woodshed_list,
            "given_leaderboard": given_lb,
            "received_leaderboard": received_lb,
        }
    }

# ---------------------------------------------------------------------------
# Season records (best/worst W-L, highest/lowest scoring)
# ---------------------------------------------------------------------------
def build_season_records():
    rows = []
    for year, table in SEASON_TABLES.items():
        for row in table:
            rows.append({**row, "year": year})
    if not rows:
        return {}
    best_record = max(rows, key=lambda x: (x["wins"], x["ppg"]))
    worst_record = min(rows, key=lambda x: (x["wins"], -x["ppg"]))
    highest_ppg = max(rows, key=lambda x: x["ppg"])
    lowest_ppg = min(rows, key=lambda x: x["ppg"])
    highest_pf = max(rows, key=lambda x: x["points_for"])
    lowest_pf = min(rows, key=lambda x: x["points_for"])
    return {
        "best_record": {**best_record, "display": display(best_record["team"])},
        "worst_record": {**worst_record, "display": display(worst_record["team"])},
        "highest_ppg": {**highest_ppg, "display": display(highest_ppg["team"])},
        "lowest_ppg": {**lowest_ppg, "display": display(lowest_ppg["team"])},
        "highest_pf": {**highest_pf, "display": display(highest_pf["team"])},
        "lowest_pf": {**lowest_pf, "display": display(lowest_pf["team"])},
    }

# ---------------------------------------------------------------------------
# Streaks (carry across seasons, never reset at year boundary)
# ---------------------------------------------------------------------------
def build_streaks():
    # Chronological list of results per team
    team_results = defaultdict(list)
    for m in ALL_MATCHUPS:
        team_results[m["winner"]].append({"year": m["year"], "week": m["week"], "result": "W"})
        team_results[m["loser"]].append({"year": m["year"], "week": m["week"], "result": "L"})

    for team in team_results:
        team_results[team].sort(key=lambda x: (x["year"], x["week"]))

    def get_streaks(results):
        """Return list of (streak_type, length, start_year, end_year)"""
        if not results:
            return []
        streaks = []
        cur_type = results[0]["result"]
        cur_len = 1
        start = results[0]
        for r in results[1:]:
            if r["result"] == cur_type:
                cur_len += 1
            else:
                streaks.append({"type": cur_type, "length": cur_len, "start_year": start["year"], "end_year": r["year"] - (1 if r["week"] < start["week"] else 0)})
                cur_type = r["result"]
                cur_len = 1
                start = r
        streaks.append({"type": cur_type, "length": cur_len, "start_year": start["year"], "end_year": results[-1]["year"]})
        return streaks

    all_win_streaks = []
    all_loss_streaks = []
    current_streaks = []

    for team in ALL_TEAMS:
        results = team_results[team]
        streaks = get_streaks(results)
        for s in streaks:
            entry = {"team": team, "display": display(team), **s}
            if s["type"] == "W":
                all_win_streaks.append(entry)
            else:
                all_loss_streaks.append(entry)

        # Current streak
        if results:
            cur_type = results[-1]["result"]
            cur_len = 1
            for r in reversed(results[:-1]):
                if r["result"] == cur_type:
                    cur_len += 1
                else:
                    break
            current_streaks.append({
                "team": team, "display": display(team),
                "type": cur_type, "length": cur_len,
            })

    top10_win = sorted(all_win_streaks, key=lambda x: -x["length"])[:10]
    top10_loss = sorted(all_loss_streaks, key=lambda x: -x["length"])[:10]

    return {
        "current": sorted(current_streaks, key=lambda x: -x["length"]),
        "top10_win_streaks": top10_win,
        "top10_loss_streaks": top10_loss,
    }

# ---------------------------------------------------------------------------
# Week-by-week matchup grid per season (with running records)
# ---------------------------------------------------------------------------
def build_weekly_matchups():
    out = {}
    for year in ALL_YEARS:
        year_games = [m for m in ALL_MATCHUPS if m["year"] == year and m["type"] == "regular"]
        weeks = sorted(set(m["week"] for m in year_games))
        # Running record
        record = defaultdict(lambda: {"wins": 0, "losses": 0})
        weekly = []
        for week in weeks:
            week_games = [m for m in year_games if m["week"] == week]
            games_out = []
            for m in week_games:
                w_rec = dict(record[m["winner"]])
                l_rec = dict(record[m["loser"]])
                games_out.append({
                    "winner": m["winner"], "winner_display": display(m["winner"]),
                    "loser": m["loser"], "loser_display": display(m["loser"]),
                    "winner_pts": m["winner_pts"], "loser_pts": m["loser_pts"],
                    "margin": m["margin"],
                    "winner_record_before": w_rec,
                    "loser_record_before": l_rec,
                })
                record[m["winner"]]["wins"] += 1
                record[m["loser"]]["losses"] += 1
            weekly.append({"week": week, "games": games_out})
        out[year] = weekly
    return out

# ---------------------------------------------------------------------------
# All-time standings (regular season only)
# ---------------------------------------------------------------------------
def build_alltime_standings():
    rows = []
    for team in ALL_TEAMS:
        stats = OWNER_STATS[team]
        rows.append({
            "team": team,
            "display": display(team),
            "seasons": stats["seasons"],
            "wins": stats["reg_wins"],
            "losses": stats["reg_losses"],
            "win_pct": stats["reg_pct"],
            "points_for": stats["points_for"],
            "points_against": stats["points_against"],
            "ppg": stats["ppg"],
            "championships": stats["championships"],
            "playoff_appearances": stats["playoff_appearances"],
        })
    return sorted(rows, key=lambda x: -x["win_pct"])

# ---------------------------------------------------------------------------
# All-time records strip (for homepage)
# ---------------------------------------------------------------------------
def build_alltime_records():
    all_scores = []
    for m in ALL_MATCHUPS:
        all_scores.append({"team": m["winner"], "display": display(m["winner"]), "pts": m["winner_pts"], "year": m["year"], "week": m["week"], "opp": m["loser"], "opp_display": display(m["loser"])})
        all_scores.append({"team": m["loser"], "display": display(m["loser"]), "pts": m["loser_pts"], "year": m["year"], "week": m["week"], "opp": m["winner"], "opp_display": display(m["winner"])})
    high = max(all_scores, key=lambda x: x["pts"])
    low = min(all_scores, key=lambda x: x["pts"])
    blowout = max(ALL_MATCHUPS, key=lambda x: x["margin"])
    most_titles = max(ALL_TEAMS, key=lambda t: OWNER_STATS[t]["championships"])
    return {
        "high_score": high,
        "low_score": low,
        "biggest_blowout": {
            "winner": blowout["winner"], "winner_display": display(blowout["winner"]),
            "loser": blowout["loser"], "loser_display": display(blowout["loser"]),
            "winner_pts": blowout["winner_pts"], "loser_pts": blowout["loser_pts"],
            "margin": blowout["margin"], "year": blowout["year"], "week": blowout["week"],
        },
        "most_titles": {"team": most_titles, "display": display(most_titles), "count": OWNER_STATS[most_titles]["championships"]},
    }

# ---------------------------------------------------------------------------
# Owner milestones
# ---------------------------------------------------------------------------
def build_milestones():
    woodsheds_all = [m for m in ALL_MATCHUPS if m["margin"] >= WOODSHED]
    given = defaultdict(int)
    received = defaultdict(int)
    for m in woodsheds_all:
        given[m["winner"]] += 1
        received[m["loser"]] += 1

    rows = []
    for team in ALL_TEAMS:
        s = OWNER_STATS[team]
        rows.append({
            "team": team,
            "display": display(team),
            "wins": s["reg_wins"],
            "win_pct": s["reg_pct"],
            "points_for": s["points_for"],
            "ppg": s["ppg"],
            "championships": s["championships"],
            "playoff_appearances": s["playoff_appearances"],
            "woodsheds_given": given.get(team, 0),
            "woodsheds_received": received.get(team, 0),
        })
    return rows

# ---------------------------------------------------------------------------
# Assemble and write data.json
# ---------------------------------------------------------------------------
print("Building data structures...")
records = build_records()
streaks = build_streaks()

data = {
    "meta": {
        "league_name": CONFIG["league"]["name"],
        "abbreviation": CONFIG["league"]["abbreviation"],
        "founded": CONFIG["league"]["founded"],
        "reigning_champion": CONFIG["league"]["reigning_champion"],
        "reigning_champion_year": CONFIG["league"]["reigning_champion_year"],
        "years": ALL_YEARS,
        "teams": [{"id": t, "display": display(t)} for t in ALL_TEAMS],
        "design": CONFIG["design"],
        "woodshed_threshold": WOODSHED,
    },
    "alltime_standings": build_alltime_standings(),
    "alltime_records": build_alltime_records(),
    "championship_history": CHAMP_HISTORY,
    "season_tables": {str(k): v for k, v in SEASON_TABLES.items()},
    "playoff_brackets": {str(k): v for k, v in PLAYOFF_BRACKETS.items()},
    "playoff_standings": build_playoff_standings(),
    "weekly_matchups": {str(k): v for k, v in build_weekly_matchups().items()},
    "owner_stats": OWNER_STATS,
    "h2h": H2H,
    "records": records,
    "season_records": build_season_records(),
    "streaks": streaks,
    "milestones": build_milestones(),
}

out_path = os.path.join(ROOT, "data", "data.json")
with open(out_path, "w") as f:
    json.dump(data, f, indent=2, default=str)

print(f"✅ data.json written to {out_path}")
print(f"   {len(ALL_YEARS)} seasons | {len(ALL_TEAMS)} teams | {len(ALL_MATCHUPS)} total games")
print(f"   Champion history: {len(CHAMP_HISTORY)} seasons")
