# Predictor data

Daily win predictions for cricket matches. The website (`index.html`, hosted on cPanel) loads
`data/index.json` from this repository every time someone opens it. Claude updates the data each
morning; nothing needs uploading to cPanel unless the page design changes.

## How it fits together

```
data/
  competitions.json     every competition: series, tournaments, leagues, cups
  teams.json            every team: national sides, franchises, domestic teams, clubs, schools
  people.json           players, captains and coaches, stored once each
  venues.json           grounds
  ratings.json          team strength ratings for the ratings-only model
  meta.json             "last updated" time and note shown on the site
  fixtures/<competition-id>.json   the matches in one competition
  index.json            BUILT: the single file the website reads (do not edit)
tools/
  build.py              checks everything and builds data/index.json
  make_page.py          builds index.html from page_template.html
  page_template.html    the website design
index.html              the page to upload to cPanel (built)
data.json               BUILT copy of index.json for older uploads of the site
```

Edit the source files, then run:

```
python3 tools/build.py --lock     # locks picks for matches that have started, checks, builds
python3 tools/make_page.py        # only when the page design changed
```

`build.py` refuses to build if anything is wrong (a team or person that doesn't exist, a factor
score out of range, a bad date) and lists the problems.

## Labels

Every competition carries these labels; the website builds its section tabs from them.

| Label | Values |
|---|---|
| `sport` | `cricket` (add others later, e.g. `football`) |
| `category` | `men`, `women`, `youth` |
| `level` | `international`, `franchise`, `domestic`, `club`, `school` |
| `tier` | `full` or `associate` for internationals, otherwise `null` |
| `model` | `full` (12 factors), `lite` (fewer factors), `ratings` (team ratings only) |

Examples: IPL = men / franchise; WPL = women / franchise; County Championship = men / domestic;
Nepal v UAE = men / international / associate; a local league = men / club; a school cup = youth / school.

## Prediction models

- **full**: 12 weighted factors, each scored -5 to +5 toward team A (positive) or team B (negative).
  Win chance for A = 1 / (1 + e^(-0.1 × Σ weight × score)), minus any draw share.
- **lite**: the same formula with whichever factors the data supports (e.g. form, home, key players).
- **ratings**: each team has a strength rating (1500 = average) in `ratings.json`.
  Win chance for A = 1 / (1 + 10^(-(ratingA + home - ratingB) / 400)), home = 50 unless `neutral: true`.
  After each result, update both teams' ratings: new = old ± 20 × (actual - expected).

## Fixture fields

`id`, `date` (UTC, e.g. `2026-10-09T08:00:00Z`), `match`, `format`, `venue` (venue id), `teamA`
(home side, team id), `teamB`, `stage` (optional), `seriesNote`, `status`
(`upcoming` | `live` | `completed` | `abandoned`), `model` (defaults to the competition's), `drawPct`,
`why` (forward-looking: why the favourite is expected to win, citing the evidence), `swing` (what would have to happen for the other side to win), `factors` (full/lite), `players` and `leaders` (refer to people by id, with `team: "A"|"B"`),
and once finished `result: {winner, text}`. `predictedWinner` / `predictedPct` are set by `--lock`
when the match starts and are never changed after that.

## Safeguarding (school and junior levels)

Mark anyone under 18 with `"minor": true` in `people.json`. The site never looks up photos for them.
Do not add names, photos or individual stats of under-18s without written consent from the school or
parents. For school competitions, prefer team-level predictions with no player list.
