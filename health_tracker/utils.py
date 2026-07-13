import requests
from datetime import datetime, timezone, timedelta
from .config import NTFY_TOPIC, BASELINE_HRV, TIMEZONE

def get_local_now():
    try:
        import zoneinfo
        dt = datetime.now(zoneinfo.ZoneInfo(TIMEZONE))
    except Exception:
        # Fallback to UTC-3 (Brazil time)
        dt = datetime.now(timezone(timedelta(hours=-3)))
    return dt.replace(tzinfo=None)


def send_ntfy_notification(title, message, priority="default", tags=""):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags
    }
    requests.post(url, data=message.encode('utf-8'), headers=headers)

def get_training_status(form):
    if form > 5:
        return "🔵 Descansando"
    elif -10 <= form <= 5:
        return "🟢 Mantendo"
    elif -30 <= form < -10:
        return "🚀 Evoluindo"
    elif -40 <= form < -30:
        return "🟡 Adaptando"
    else:
        return "🔴 Alto Risco"

def get_effort_status(form):
    if form > 5:
        return "🟢 Esforço Baixo (Recuperado)"
    elif -15 <= form <= 5:
        return "🟡 Esforço Médio (Zona de Manutenção)"
    elif -30 <= form < -15:
        return "🟠 Esforço Alto (Zona de Evolução)"
    else:
        return "🔴 Esforço Muito Alto (Risco de Fadiga)"

def analyze_nutrition(workout):
    if not workout:
        return "Nenhum treino agendado. Aproveite o descanso! 🛌"
    
    desc = workout.get("description", "")
    analysis = []
    analysis.append("💧 *Hidratação:* 500ml a 750ml de água/eletrólitos por hora.")
    
    cho_encontrado = False
    if desc:
        for line in desc.split('\n'):
            if "CHO/H" in line.upper():
                analysis.append(f"🔋 *Nutrição (Plano IA):* {line.strip()}")
                cho_encontrado = True
                break
            
    if not cho_encontrado:
        duration_min = workout.get("duration", 0) / 60 if workout.get("duration") else 0
        name = workout.get("name", "Treino")
        is_intensity = any(x in name.upper() for x in ["TIROS", "INTENSIDADE", "PACE", "INTERVALADO", "Z4", "Z5"])
        
        if duration_min < 60 and not is_intensity:
            analysis.append("🍎 *Nutrição:* CHO/h 0g (Apenas hidratação).")
        elif is_intensity or (60 <= duration_min <= 90):
            analysis.append("🚀 *Nutrição:* CHO/h 30g (Ex: 1 Gel por hora).")
        else:
            analysis.append("🔋 *Nutrição:* CHO/h 60g (Ex: 2 Géis por hora).")
        
    return "\n".join(analysis)

def get_hrv_status_icon(hrv):
    if not hrv: return "❓"
    return "✅" if hrv >= BASELINE_HRV * 0.9 else "⚠️"
