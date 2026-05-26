import logging

logger = logging.getLogger("racing_agent")

BASE_PARS = {
    880: 48.0, 990: 54.0, 1100: 59.5, 1210: 65.5, 1320: 72.0,
    1430: 78.5, 1540: 85.0, 1650: 91.5, 1760: 98.0, 1800: 100.0,
    1830: 104.5, 1870: 106.5, 1980: 113.0, 2200: 126.0, 2640: 152.0,
}

def seconds_per_length(distance_yards):
    if distance_yards < 1540:
        return 0.20
    elif distance_yards < 1760:
        return 0.19
    else:
        return 0.17

def get_par_time(distance_yards, track_par=None):
    if track_par and track_par.get("avg_time"):
        return track_par["avg_time"]
    if distance_yards in BASE_PARS:
        return BASE_PARS[distance_yards]
    sorted_dists = sorted(BASE_PARS.keys())
    if distance_yards < sorted_dists[0]:
        return BASE_PARS[sorted_dists[0]]
    if distance_yards > sorted_dists[-1]:
        return BASE_PARS[sorted_dists[-1]]
    for i in range(len(sorted_dists) - 1):
        d1, d2 = sorted_dists[i], sorted_dists[i + 1]
        if d1 <= distance_yards <= d2:
            ratio = (distance_yards - d1) / (d2 - d1)
            return BASE_PARS[d1] + ratio * (BASE_PARS[d2] - BASE_PARS[d1])
    return None

def compute_speed_figure(final_time_sec, distance_yards, track_par=None):
    if not final_time_sec or not distance_yards:
        return None
    par = get_par_time(distance_yards, track_par)
    if par is None:
        return None
    spl = seconds_per_length(distance_yards)
    time_diff = par - final_time_sec
    lengths_diff = time_diff / spl
    figure = 80 + (lengths_diff * 2)
    return max(0, min(130, round(figure, 1)))
