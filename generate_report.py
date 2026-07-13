import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from health_tracker.intervals_client import IntervalsClient

def get_weeks_of_year(year):
    # Start on the Monday containing Jan 1 of that year.
    first_jan = datetime(year, 1, 1)
    monday_offset = first_jan.weekday()
    start_date = first_jan - timedelta(days=monday_offset)
    
    # We run the report up to the end of the current week (Sunday) if it's the current year,
    # or the end of that year if it's in the past.
    today = datetime.now()
    if today.year == year:
        end_date = today + timedelta(days=(6 - today.weekday()))
    else:
        end_date = datetime(year, 12, 31)
        end_date = end_date + timedelta(days=(6 - end_date.weekday()))
        
    weeks = []
    curr = start_date
    while curr <= end_date:
        weeks.append(curr)
        curr += timedelta(days=7)
    return weeks

def generate_report(year=None):
    if year is None:
        year = datetime.now().year
        
    client = IntervalsClient()
    
    print(f"Fetching activities from intervals.icu for year {year}...")
    activities = client.get_activities(f"{year}-01-01", f"{year}-12-31")
    print(f"Fetched {len(activities)} activities.")
    
    print(f"Fetching wellness data from intervals.icu for year {year}...")
    wellness = client.get_wellness(f"{year}-01-01", f"{year}-12-31")
    print(f"Fetched {len(wellness)} wellness entries.")
    
    # Index wellness by date
    wellness_by_date = {}
    for w in wellness:
        date_str = w.get("id")
        if date_str:
            wellness_by_date[date_str] = w
            
    weeks = get_weeks_of_year(year)
    weekly_data = []
    
    # Sport type mapping
    def get_sport_category(atype):
        if not atype:
            return "Other"
        atype_upper = atype.upper()
        if "RUN" in atype_upper:
            return "Run"
        elif "RIDE" in atype_upper or "BIKE" in atype_upper or "CYCLING" in atype_upper:
            return "Ride"
        elif "SWIM" in atype_upper:
            return "Swim"
        elif "WEIGHT" in atype_upper or "STRENGTH" in atype_upper or "FORCA" in atype_upper or "FORÇA" in atype_upper:
            return "Strength"
        else:
            return "Other"
            
    for week_start in weeks:
        week_end = week_start + timedelta(days=6)
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")
        
        # Get activities in this week
        week_activities = []
        for act in activities:
            act_date_str = act.get("start_date_local")
            if act_date_str:
                act_date = datetime.strptime(act_date_str[:10], "%Y-%m-%d")
                if week_start <= act_date <= week_end:
                    week_activities.append(act)
                    
        # Group stats by category
        loads = {"Run": 0, "Ride": 0, "Swim": 0, "Strength": 0, "Other": 0}
        distances = {"Run": 0, "Ride": 0, "Swim": 0, "Strength": 0, "Other": 0}
        durations = {"Run": 0, "Ride": 0, "Swim": 0, "Strength": 0, "Other": 0}
        counts = {"Run": 0, "Ride": 0, "Swim": 0, "Strength": 0, "Other": 0}
        
        for act in week_activities:
            cat = get_sport_category(act.get("type"))
            load = act.get("icu_training_load") or act.get("pace_load") or act.get("hr_load") or act.get("power_load") or 0
            dist = (act.get("distance") or 0) / 1000.0 # in km
            dur = (act.get("moving_time") or act.get("elapsed_time") or 0) / 3600.0 # in hours
            
            loads[cat] += load
            distances[cat] += dist
            durations[cat] += dur
            counts[cat] += 1
            
        # Get wellness stats for this week
        sleep_hours = []
        hrv_values = []
        weight_values = []
        resting_hr_values = []
        
        # Keep track of CTL/ATL/TSB values
        last_ctl = None
        last_atl = None
        
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            w_entry = wellness_by_date.get(day_str)
            if w_entry:
                s_secs = w_entry.get("sleepSecs")
                if s_secs is not None:
                    sleep_hours.append(s_secs / 3600.0)
                
                hrv = w_entry.get("hrv") or w_entry.get("avg_sleep_hrv")
                if hrv is not None:
                    hrv_values.append(hrv)
                    
                wgt = w_entry.get("weight")
                if wgt is not None:
                    weight_values.append(wgt)
                    
                rhr = w_entry.get("restingHR")
                if rhr is not None:
                    resting_hr_values.append(rhr)
                    
                # Store CTL and ATL as they evolve
                if w_entry.get("ctl") is not None:
                    last_ctl = w_entry.get("ctl")
                if w_entry.get("atl") is not None:
                    last_atl = w_entry.get("atl")
                    
        # Averages
        avg_sleep = sum(sleep_hours) / len(sleep_hours) if sleep_hours else None
        avg_hrv = sum(hrv_values) / len(hrv_values) if hrv_values else None
        avg_weight = sum(weight_values) / len(weight_values) if weight_values else None
        avg_rhr = sum(resting_hr_values) / len(resting_hr_values) if resting_hr_values else None
        
        ctl_val = last_ctl if last_ctl is not None else 0.0
        atl_val = last_atl if last_atl is not None else 0.0
        tsb_val = ctl_val - atl_val
        
        weekly_data.append({
            "week_start": week_start_str,
            "week_end": week_end_str,
            "loads": loads,
            "distances": distances,
            "durations": durations,
            "counts": counts,
            "total_load": sum(loads.values()),
            "total_duration": sum(durations.values()),
            "avg_sleep": avg_sleep,
            "avg_hrv": avg_hrv,
            "avg_weight": avg_weight,
            "avg_rhr": avg_rhr,
            "ctl": ctl_val,
            "atl": atl_val,
            "tsb": tsb_val
        })
        
    # Calculate Overall Aggregates
    total_load = sum(wd["total_load"] for wd in weekly_data)
    total_duration = sum(wd["total_duration"] for wd in weekly_data)
    total_activities = sum(sum(wd["counts"].values()) for wd in weekly_data)
    
    sport_totals = {
        "Run": {"load": 0, "dist": 0, "dur": 0, "count": 0},
        "Ride": {"load": 0, "dist": 0, "dur": 0, "count": 0},
        "Swim": {"load": 0, "dist": 0, "dur": 0, "count": 0},
        "Strength": {"load": 0, "dist": 0, "dur": 0, "count": 0},
        "Other": {"load": 0, "dist": 0, "dur": 0, "count": 0}
    }
    
    for wd in weekly_data:
        for sport in sport_totals:
            sport_totals[sport]["load"] += wd["loads"][sport]
            sport_totals[sport]["dist"] += wd["distances"][sport]
            sport_totals[sport]["dur"] += wd["durations"][sport]
            sport_totals[sport]["count"] += wd["counts"][sport]
            
    # Monthly aggregates
    monthly_data = {}
    for wd in weekly_data:
        dt = datetime.strptime(wd["week_start"], "%Y-%m-%d")
        month_key = dt.strftime("%Y-%m")
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                "load": 0,
                "duration": 0,
                "activities": 0,
                "sports": {s: {"load": 0, "dist": 0, "dur": 0} for s in sport_totals},
                "hrv_sum": 0,
                "hrv_count": 0,
                "sleep_sum": 0,
                "sleep_count": 0,
                "weight_sum": 0,
                "weight_count": 0
            }
            
        monthly_data[month_key]["load"] += wd["total_load"]
        monthly_data[month_key]["duration"] += wd["total_duration"]
        monthly_data[month_key]["activities"] += sum(wd["counts"].values())
        
        for sport in sport_totals:
            monthly_data[month_key]["sports"][sport]["load"] += wd["loads"][sport]
            monthly_data[month_key]["sports"][sport]["dist"] += wd["distances"][sport]
            monthly_data[month_key]["sports"][sport]["dur"] += wd["durations"][sport]
            
        if wd["avg_hrv"] is not None:
            monthly_data[month_key]["hrv_sum"] += wd["avg_hrv"]
            monthly_data[month_key]["hrv_count"] += 1
        if wd["avg_sleep"] is not None:
            monthly_data[month_key]["sleep_sum"] += wd["avg_sleep"]
            monthly_data[month_key]["sleep_count"] += 1
        if wd["avg_weight"] is not None:
            monthly_data[month_key]["weight_sum"] += wd["avg_weight"]
            monthly_data[month_key]["weight_count"] += 1
            
    for m in monthly_data:
        m_info = monthly_data[m]
        m_info["avg_hrv"] = m_info["hrv_sum"] / m_info["hrv_count"] if m_info["hrv_count"] > 0 else None
        m_info["avg_sleep"] = m_info["sleep_sum"] / m_info["sleep_count"] if m_info["sleep_count"] > 0 else None
        m_info["avg_weight"] = m_info["weight_sum"] / m_info["weight_count"] if m_info["weight_count"] > 0 else None

    # Generate SVG Chart
    svg_chart = generate_svg_chart(weekly_data)
    
    # Write files locally under reports/
    base_dir = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    svg_path = os.path.join(reports_dir, f"weekly_load_chart_{year}.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_chart)
    print(f"SVG Chart generated at {svg_path}")
    
    report_md = build_markdown_report(weekly_data, sport_totals, monthly_data, total_load, total_duration, total_activities, year)
    
    report_path = os.path.join(reports_dir, f"relatorio_carga_{year}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Markdown Report generated at {report_path}")
    
    return report_path

def generate_svg_chart(weekly_data):
    # Dimensions
    width = 900
    height = 500
    padding_top = 40
    padding_bottom = 60
    padding_left = 60
    padding_right = 60
    
    chart_w = width - padding_left - padding_right
    chart_h = height - padding_top - padding_bottom
    
    num_weeks = len(weekly_data)
    bar_gap = 4
    bar_w = (chart_w / num_weeks) - bar_gap if num_weeks > 0 else 10
    
    max_load = max(wd["total_load"] for wd in weekly_data) if weekly_data else 100
    max_load = max(max_load, 100)
    max_load = ((int(max_load) // 100) + 1) * 100
    
    max_ctl_atl = max(max(wd["ctl"], wd["atl"]) for wd in weekly_data) if weekly_data else 50
    min_tsb = min(wd["tsb"] for wd in weekly_data) if weekly_data else 0
    max_tsb = max(wd["tsb"] for wd in weekly_data) if weekly_data else 0
    
    y2_max = max(max_ctl_atl, abs(min_tsb), max_tsb, 50)
    y2_max = ((int(y2_max) // 20) + 1) * 20
    y2_min = -y2_max if min_tsb < 0 else 0
    
    colors = {
        "Ride": "#3b82f6",    # Blue
        "Run": "#f97316",     # Orange
        "Swim": "#06b6d4",    # Cyan
        "Strength": "#a855f7",# Purple
        "Other": "#6b7280"     # Gray
    }
    
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0f172a; font-family: system-ui, -apple-system, sans-serif; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">')
    
    num_y_grid = 5
    for i in range(num_y_grid + 1):
        val = (max_load / num_y_grid) * i
        y = padding_top + chart_h - (val / max_load) * chart_h
        svg.append(f'  <line x1="{padding_left}" y1="{y}" x2="{width - padding_right}" y2="{y}" stroke="#334155" stroke-dasharray="4,4" stroke-width="1" />')
        svg.append(f'  <text x="{padding_left - 10}" y="{y + 4}" fill="#94a3b8" font-size="11" text-anchor="end">{int(val)}</text>')
        
    y2_ticks = [y2_min, y2_min / 2, 0, y2_max / 2, y2_max] if y2_min < 0 else [0, y2_max/4, y2_max/2, 3*y2_max/4, y2_max]
    y2_ticks = sorted(list(set(y2_ticks)))
    for val in y2_ticks:
        y2_range = y2_max - y2_min
        y = padding_top + chart_h - ((val - y2_min) / y2_range) * chart_h
        svg.append(f'  <line x1="{width - padding_right}" y1="{y}" x2="{width - padding_right + 5}" y2="{y}" stroke="#64748b" stroke-width="1" />')
        svg.append(f'  <text x="{width - padding_right + 10}" y="{y + 4}" fill="#94a3b8" font-size="11" text-anchor="start">{int(val)}</text>')
        
    for idx, wd in enumerate(weekly_data):
        x = padding_left + idx * (bar_w + bar_gap) + bar_gap/2
        
        current_y_offset = 0
        categories = ["Ride", "Run", "Swim", "Strength", "Other"]
        
        svg.append(f'  <rect x="{x}" y="{padding_top}" width="{bar_w}" height="{chart_h}" fill="transparent" style="cursor: pointer;">')
        svg.append(f'    <title>Semana {wd["week_start"]} a {wd["week_end"]}\nCarga Total: {wd["total_load"]:.0f} TL\n- Ride: {wd["loads"]["Ride"]:.0f}\n- Run: {wd["loads"]["Run"]:.0f}\n- Swim: {wd["loads"]["Swim"]:.0f}\n- Strength: {wd["loads"]["Strength"]:.0f}\n- CTL: {wd["ctl"]:.1f} | TSB: {wd["tsb"]:.1f}</title>')
        svg.append(f'  </rect>')
        
        for cat in categories:
            load = wd["loads"][cat]
            if load <= 0:
                continue
            
            h = (load / max_load) * chart_h
            y = padding_top + chart_h - (current_y_offset / max_load) * chart_h - h
            
            svg.append(f'  <rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{colors[cat]}" rx="2" style="transition: opacity 0.2s;" />')
            current_y_offset += load
            
    ctl_points = []
    atl_points = []
    tsb_points = []
    
    y2_range = y2_max - y2_min
    
    for idx, wd in enumerate(weekly_data):
        x = padding_left + idx * (bar_w + bar_gap) + bar_gap/2 + bar_w/2
        
        y_ctl = padding_top + chart_h - ((wd["ctl"] - y2_min) / y2_range) * chart_h
        ctl_points.append(f"{x},{y_ctl}")
        
        y_atl = padding_top + chart_h - ((wd["atl"] - y2_min) / y2_range) * chart_h
        atl_points.append(f"{x},{y_atl}")
        
        y_tsb = padding_top + chart_h - ((wd["tsb"] - y2_min) / y2_range) * chart_h
        tsb_points.append(f"{x},{y_tsb}")
        
    if weekly_data:
        svg.append(f'  <!-- TSB Line -->')
        svg.append(f'  <path d="M { " L ".join(tsb_points) }" fill="none" stroke="#f43f5e" stroke-width="2.5" stroke-dasharray="3,3" />')
        
        svg.append(f'  <!-- ATL Line -->')
        svg.append(f'  <path d="M { " L ".join(atl_points) }" fill="none" stroke="#ec4899" stroke-width="1.5" opacity="0.6" />')
        
        svg.append(f'  <!-- CTL Line -->')
        svg.append(f'  <path d="M { " L ".join(ctl_points) }" fill="none" stroke="#eab308" stroke-width="3" />')
        
        for pt in ctl_points:
            x, y = pt.split(",")
            svg.append(f'  <circle cx="{x}" cy="{y}" r="3" fill="#eab308" stroke="#0f172a" stroke-width="1" />')
            
    for idx, wd in enumerate(weekly_data):
        if idx % 3 == 0 or idx == len(weekly_data) - 1:
            x = padding_left + idx * (bar_w + bar_gap) + bar_gap/2 + bar_w/2
            dt = datetime.strptime(wd["week_start"], "%Y-%m-%d")
            label = dt.strftime("%d/%b")
            svg.append(f'  <text x="{x}" y="{height - padding_bottom + 20}" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(30, {x}, {height - padding_bottom + 20})">{label}</text>')
            
    legend_y = height - 15
    svg.append(f'  <!-- Legend -->')
    svg.append(f'  <rect x="{padding_left}" y="{legend_y - 10}" width="12" height="12" fill="{colors["Ride"]}" rx="2" />')
    svg.append(f'  <text x="{padding_left + 16}" y="{legend_y}" fill="#94a3b8" font-size="11">Ciclismo</text>')
    
    svg.append(f'  <rect x="{padding_left + 90}" y="{legend_y - 10}" width="12" height="12" fill="{colors["Run"]}" rx="2" />')
    svg.append(f'  <text x="{padding_left + 106}" y="{legend_y}" fill="#94a3b8" font-size="11">Corrida</text>')
    
    svg.append(f'  <rect x="{padding_left + 180}" y="{legend_y - 10}" width="12" height="12" fill="{colors["Swim"]}" rx="2" />')
    svg.append(f'  <text x="{padding_left + 196}" y="{legend_y}" fill="#94a3b8" font-size="11">Natação</text>')
    
    svg.append(f'  <rect x="{padding_left + 270}" y="{legend_y - 10}" width="12" height="12" fill="{colors["Strength"]}" rx="2" />')
    svg.append(f'  <text x="{padding_left + 286}" y="{legend_y}" fill="#94a3b8" font-size="11">Força</text>')
    
    svg.append(f'  <line x1="{padding_left + 360}" y1="{legend_y - 4}" x2="{padding_left + 385}" y2="{legend_y - 4}" stroke="#eab308" stroke-width="3" />')
    svg.append(f'  <text x="{padding_left + 390}" y="{legend_y}" fill="#94a3b8" font-size="11">CTL (Fitness)</text>')
    
    svg.append(f'  <line x1="{padding_left + 490}" y1="{legend_y - 4}" x2="{padding_left + 515}" y2="{legend_y - 4}" stroke="#f43f5e" stroke-width="2" stroke-dasharray="3,3" />')
    svg.append(f'  <text x="{padding_left + 520}" y="{legend_y}" fill="#94a3b8" font-size="11">TSB (Forma)</text>')
    
    svg.append('</svg>')
    
    return "\n".join(svg)

def build_markdown_report(weekly_data, sport_totals, monthly_data, total_load, total_duration, total_activities, year):
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    
    peak_week = max(weekly_data, key=lambda x: x["total_load"]) if weekly_data else {"total_load": 0, "week_start": "N/A", "week_end": "N/A"}
    if weekly_data:
        peak_week_dates = f"{datetime.strptime(peak_week['week_start'], '%Y-%m-%d').strftime('%d/%m')} a {datetime.strptime(peak_week['week_end'], '%Y-%m-%d').strftime('%d/%m')}"
    else:
        peak_week_dates = "N/A"
        
    avg_weekly_load = total_load / len(weekly_data) if weekly_data else 0
    avg_weekly_duration = total_duration / len(weekly_data) if weekly_data else 0
    
    sport_rows = []
    for sport, stats in sport_totals.items():
        if stats["count"] == 0:
            continue
        sport_name = {"Ride": "🚴 Ciclismo", "Run": "🏃 Corrida", "Swim": "🏊 Natação", "Strength": "💪 Força", "Other": "❓ Outros"}.get(sport, sport)
        load_pct = (stats["load"] / total_load * 100) if total_load > 0 else 0
        dur_pct = (stats["dur"] / total_duration * 100) if total_duration > 0 else 0
        dist_str = f"{stats['dist']:.1f} km" if stats["dist"] > 0 else "-"
        sport_rows.append(f"| {sport_name} | **{stats['load']:.0f}** ({load_pct:.1f}%) | {stats['dur']:.1f}h ({dur_pct:.1f}%) | {dist_str} | {stats['count']} |")
        
    monthly_rows = []
    sorted_months = sorted(list(monthly_data.keys()))
    for m in sorted_months:
        m_info = monthly_data[m]
        year_str, month = m.split("-")
        month_name = {
            "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril", "05": "Maio", "06": "Junho",
            "07": "Julho", "08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
        }.get(month, month)
        
        m_label = f"{month_name} {year_str}"
        
        run_dist = m_info["sports"]["Run"]["dist"]
        ride_dist = m_info["sports"]["Ride"]["dist"]
        swim_dist = m_info["sports"]["Swim"]["dist"]
        
        run_str = f"{run_dist:.1f} km" if run_dist > 0 else "-"
        ride_str = f"{ride_dist:.1f} km" if ride_dist > 0 else "-"
        swim_str = f"{swim_dist:.1f} km" if swim_dist > 0 else "-"
        
        hrv_str = f"{m_info['avg_hrv']:.1f} ms" if m_info['avg_hrv'] is not None else "-"
        sleep_str = f"{m_info['avg_sleep']:.1f} h" if m_info['avg_sleep'] is not None else "-"
        
        monthly_rows.append(f"| {m_label} | **{m_info['load']:.0f}** | {m_info['duration']:.1f}h | {run_str} | {ride_str} | {swim_str} | {hrv_str} | {sleep_str} |")

    weekly_rows = []
    for wd in reversed(weekly_data):
        dt_start = datetime.strptime(wd["week_start"], "%Y-%m-%d")
        dt_end = datetime.strptime(wd["week_end"], "%Y-%m-%d")
        date_range = f"{dt_start.strftime('%d/%m')} - {dt_end.strftime('%d/%m')}"
        
        run_l = wd["loads"]["Run"]
        ride_l = wd["loads"]["Ride"]
        swim_l = wd["loads"]["Swim"]
        strength_l = wd["loads"]["Strength"]
        
        sports_breakdown = []
        if run_l > 0: sports_breakdown.append(f"🏃 {run_l:.0f}")
        if ride_l > 0: sports_breakdown.append(f"🚴 {ride_l:.0f}")
        if swim_l > 0: sports_breakdown.append(f"🏊 {swim_l:.0f}")
        if strength_l > 0: sports_breakdown.append(f"💪 {strength_l:.0f}")
        
        sports_str = ", ".join(sports_breakdown) if sports_breakdown else "-"
        
        tsb = wd["tsb"]
        if tsb > 5:
            tsb_str = f"🔵 +{tsb:.1f} (Descanso)"
        elif -10 <= tsb <= 5:
            tsb_str = f"🟢 {tsb:.1f} (Manutenção)"
        elif -30 <= tsb < -10:
            tsb_str = f"🚀 {tsb:.1f} (Evolução)"
        elif -40 <= tsb < -30:
            tsb_str = f"🟡 {tsb:.1f} (Sobrecarga)"
        else:
            tsb_str = f"🔴 {tsb:.1f} (Zona de Risco)"
            
        hrv_str = f"{wd['avg_hrv']:.1f} ms" if wd['avg_hrv'] is not None else "-"
        sleep_str = f"{wd['avg_sleep']:.1f}h" if wd['avg_sleep'] is not None else "-"
        
        weekly_rows.append(f"| {date_range} | **{wd['total_load']:.0f}** | {wd['total_duration']:.1f}h | {sports_str} | {tsb_str} | {hrv_str} | {sleep_str} |")

    report = []
    report.append(f"# 📊 Relatório de Carga de Treinamento {year}")
    report.append(f"*Gerado em {now_str} com dados integrados do Intervals.icu.*")
    report.append("")
    
    report.append("> [!NOTE]")
    report.append(f"> Este relatório apresenta a análise consolidada de treinos do ano de **{year}**.")
    report.append(f"> Atualmente, o ano conta com **{len(weekly_data)} semanas** de dados processados.")
    report.append("")
    
    report.append("## 📈 Visão Geral de Performance")
    report.append("")
    report.append("| Métrica | Valor Consolidado | Observação / Média |")
    report.append("| :--- | :--- | :--- |")
    report.append(f"| **Carga Total (Load)** | **{total_load:.0f} TL** | Média de **{avg_weekly_load:.0f} TL** por semana |")
    report.append(f"| **Tempo Total** | **{total_duration:.1f} horas** | Média de **{avg_weekly_duration:.1f}h** por semana |")
    report.append(f"| **Atividades Realizadas** | **{total_activities} treinos** | Frequência de **{total_activities / len(weekly_data):.1f}** por semana |")
    report.append(f"| **Pico de Carga Semanal** | **{peak_week['total_load']:.0f} TL** | Aconteceu na semana de **{peak_week_dates}** |")
    report.append("")
    
    report.append("## 📊 Distribuição de Carga por Modalidade")
    report.append("A tabela abaixo mostra a contribuição de cada esporte na carga de treinamento total e no tempo despendido.")
    report.append("")
    report.append("| Modalidade | Carga Total (%) | Tempo Total (%) | Distância Total | Qtd. Treinos |")
    report.append("| :--- | :--- | :--- | :--- | :--- |")
    report.extend(sport_rows)
    report.append("")
    
    report.append("## 📈 Gráfico de Evolução Semanal (Carga vs. Fitness)")
    report.append("O gráfico a seguir ilustra a distribuição semanal de carga (barras por modalidade) sobreposta com a curva de **Fitness (CTL)** e **Forma (TSB)**.")
    report.append("")
    svg_filename = f"weekly_load_chart_{year}.svg"
    report.append(f"![Gráfico de Evolução Semanal de Carga e Métricas de Treino {year}]({svg_filename})")
    report.append("")
    
    report.append("## 🗓️ Consolidação Mensal")
    report.append("Abaixo, o detalhamento do volume de treino agrupado mês a mês.")
    report.append("")
    report.append("| Mês | Carga Total | Horas Totais | Corrida | Ciclismo | Natação | Média HRV | Média Sono |")
    report.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    report.extend(monthly_rows)
    report.append("")
    
    report.append("## 📅 Progressão Semanal Detalhada")
    report.append("Linha do tempo completa do ano, com o balanço de carga por esporte e as métricas de saúde ao final de cada semana.")
    report.append("")
    report.append("| Semana | Carga (TL) | Horas | Detalhamento Esportes | Balanço TSB Final | HRV Médio | Sono Médio |")
    report.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    report.extend(weekly_rows)
    report.append("")
    
    return "\n".join(report)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gerador de Relatório de Treino e Saúde")
    parser.add_argument("--ano", type=int, default=datetime.now().year, help="Ano do relatório")
    args = parser.parse_args()
    
    try:
        report_file = generate_report(args.ano)
        print(f"\nSUCCESS: Report generated at {report_file}")
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()
