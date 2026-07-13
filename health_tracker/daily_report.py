from datetime import timedelta
from .intervals_client import IntervalsClient
from .config import BASELINE_HRV, GOAL_SLEEP, ATHLETE_NAME
from .utils import send_ntfy_notification, get_training_status, analyze_nutrition, get_hrv_status_icon, get_local_now

def generate_daily_report():
    client = IntervalsClient()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    last_week = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    # 1. Fetch Wellness
    wellness_data = client.get_wellness((now - timedelta(days=2)).strftime("%Y-%m-%d"), today)
    
    latest_well = {}
    for entry in reversed(wellness_data):
        if entry.get("sleepSecs") or entry.get("hrv") or entry.get("avg_sleep_hrv"):
            latest_well = entry
            break
    
    hrv = latest_well.get("hrv") or latest_well.get("avg_sleep_hrv")
    sleep_hours = (latest_well.get("sleepSecs") or 0) / 3600
    
    ctl = latest_well.get("ctl", 0)
    atl = latest_well.get("atl", 0)
    form = ctl - atl

    # 2. Fetch Today's Workouts (All WORKOUT category)
    events = client.get_events(today, today)
    today_workouts = [e for e in events if e.get("category") == "WORKOUT"]

    # 3. Fetch Accumulated Volume (Last 7 days)
    past_events = client.get_events(last_week, yesterday)
    weekly_load = sum(e.get("icu_training_load", 0) for e in past_events if e.get("icu_training_load"))

    training_status = get_training_status(form)

    msg = []
    msg.append(f"🌅 *RESUMO MATINAL - {ATHLETE_NAME.upper()}*")
    
    status_hrv = get_hrv_status_icon(hrv)
    status_sleep = "✅" if sleep_hours >= GOAL_SLEEP else "⚠️"
    
    msg.append("\n📊 *STATUS DE SAÚDE*")
    msg.append(f"{status_hrv} *HRV:* {hrv if hrv else 'N/A'} ms (Base: {BASELINE_HRV})")
    msg.append(f"{status_sleep} *Sono:* {sleep_hours:.1f}h (Meta: {GOAL_SLEEP}h)")
    msg.append(f"📈 *Volume 7d:* {weekly_load:.0f} Load | {training_status}")

    msg.append("\n🏃 *TREINO DE HOJE*")
    if today_workouts:
        for workout in today_workouts:
            msg.append(f"📌 *{workout.get('name')}*")
            desc = workout.get("description")
            if desc: msg.append(f"📝 *Descrição:* {desc}")
            dist = workout.get('distance')
            if dist: msg.append(f"📏 Distância: {dist/1000:.1f}km")
            dur = workout.get('duration')
            if dur: msg.append(f"⏱️ Duração: {dur//60} min")
            
            # Nutrition analysis for EACH workout
            msg.append(f"💡 *Análise:* {analyze_nutrition(workout)}")
            msg.append("-" * 20)
    else:
        msg.append("📭 Sem treino agendado.")

    full_message = "\n".join(msg)
    send_ntfy_notification(
        title="Relatório Diário de Saúde e Treino",
        message=full_message,
        priority="high",
        tags="muscle,health,calendar"
    )
    return "Relatório matinal enviado!"

if __name__ == "__main__":
    try:
        print(generate_daily_report())
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
