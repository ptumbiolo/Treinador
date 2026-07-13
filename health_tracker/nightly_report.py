from .intervals_client import IntervalsClient
from .utils import send_ntfy_notification, get_effort_status, get_local_now

def generate_nightly_report():
    client = IntervalsClient()
    today = get_local_now().strftime("%Y-%m-%d")
    
    # 1. Fetch Wellness (Final do dia para TSB atualizado e métricas de hoje)
    wellness = client.get_wellness(today, today)
    latest_well = wellness[-1] if wellness else {}
    
    ctl = latest_well.get("ctl", 0)
    atl = latest_well.get("atl", 0)
    current_form = ctl - atl
    hrv = latest_well.get("hrv") or latest_well.get("avg_sleep_hrv")
    
    effort_status = get_effort_status(current_form)
    
    # 2. Fetch Planned Workouts for TODAY
    events = client.get_events(today, today)
    proposed = [e for e in events if e.get("category") == "WORKOUT"]
    
    # 3. Fetch Performed Activities for TODAY
    performed = client.get_activities(today, today)
    if not isinstance(performed, list): performed = []

    msg = []
    msg.append("🌙 *RELATÓRIO NOTURNO - PERFORMANCE*")
    
    msg.append("\n📈 *FECHAMENTO DO DIA*")
    msg.append(f"🏁 *Status:* {effort_status}")
    msg.append(f"📊 *Form Final (TSB):* {current_form:.1f}")
    if hrv:
        msg.append(f"💓 *HRV de hoje:* {hrv} ms")
    
    msg.append("\n🎯 *ANÁLISE DE EXECUÇÃO*")
    
    completed_all = True
    total_planned_load = 0
    total_actual_load = 0

    if not proposed and not performed:
        msg.append("Day Off completo cumprido! ✅")
    else:
        matched_ids = set()
        for p in proposed:
            name = p.get("name")
            desc_planned = p.get("description", "Sem descrição")
            target_load = p.get("icu_training_load", 0)
            total_planned_load += target_load
            
            # Melhoria no Matching: Tenta por paired_activity_id primeiro, depois por tipo + proximidade de nome
            match = next((a for a in performed if str(a.get("id")) == str(p.get("paired_activity_id")) and a.get("id") not in matched_ids), None)
            
            if not match:
                # Fallback: Mesmo tipo e nome similar ou apenas mesmo tipo se for o único
                match = next((a for a in performed if a.get("type") == p.get("type") and (p.get("name") in a.get("name") or a.get("name") in p.get("name")) and a.get("id") not in matched_ids), None)
            
            if not match:
                # Último recurso: Mesmo tipo
                match = next((a for a in performed if a.get("type") == p.get("type") and a.get("id") not in matched_ids), None)

            msg.append(f"\n📌 *{name}*")
            
            if match:
                matched_ids.add(match.get("id"))
                actual_load = match.get("icu_training_load", 0)
                if actual_load == 0:
                    actual_load = match.get("pace_load", 0) or match.get("hr_load", 0)
                
                total_actual_load += actual_load
                diff = actual_load - target_load
                
                if abs(diff) <= (target_load * 0.15):
                    resultado_detalhe = "✅ Carga executada conforme o plano."
                elif diff > 0:
                    resultado_detalhe = f"⚠️ Realizou mais carga que o planejado (+{diff:.0f} TL)."
                else:
                    resultado_detalhe = f"⚠️ Realizou menos carga que o planejado ({diff:.0f} TL)."
                
                msg.append(f"✅ *Realizado:* {match.get('name', 'Atividade')}")
                msg.append(f"📊 *Carga:* {actual_load} TL (Previsto: {target_load})")
                msg.append(f"⚖️ *Resultado:* {resultado_detalhe}")
            else:
                msg.append("❌ *Resultado:* Não realizado ou não sincronizado.")
                completed_all = False

        # Atividades extras
        extras = [a for a in performed if a.get("id") not in matched_ids]
        for a in extras:
            msg.append(f"\n➕ *{a.get('name')}* (Extra)")
            load = a.get("icu_training_load") or a.get("pace_load") or a.get("hr_load") or 0
            msg.append(f"📊 Carga: {load} TL")
            msg.append(f"📝 Tipo: {a.get('type')}")
            total_actual_load += load

    msg.append("\n📝 *ANÁLISE EXECUTIVA*")
    
    # Lógica de Análise baseada no TSB e na Execução
    if current_form < -30:
        ana = f"CUIDADO: Seu TSB está em {current_form:.1f}. Você entrou em zona de risco de overtraining. "
        if total_actual_load > total_planned_load:
            ana += "Você excedeu a carga planejada, o que agravou o desgaste. Amanhã deve ser estritamente leve ou descanso."
        else:
            ana += "A carga estava planejada, mas o corpo está no limite. Priorize 8h+ de sono."
    elif -30 <= current_form < -15:
        ana = f"Zona de Evolução (TSB: {current_form:.1f}). "
        if completed_all:
            ana += "Plano cumprido com maestria. O estímulo foi ideal para gerar adaptação sem quebrar o sistema."
        else:
            ana += "Treino incompleto em zona de carga. Tente entender se foi falta de tempo ou fadiga excessiva."
    elif -15 <= current_form <= 5:
        ana = f"Zona de Manutenção (TSB: {current_form:.1f}). "
        if total_actual_load == 0 and proposed:
            ana += "O plano previa treino mas nada foi registrado. Se for um day off não planejado, ajuste a semana."
        else:
            ana += "Equilíbrio perfeito entre carga e recuperação. Você está pronto para novos estímulos de intensidade."
    else:
        ana = f"Recuperado (TSB: {current_form:.1f}). "
        if not proposed:
            ana += "Day off regenerativo cumprido. Seu sistema está zerado e pronto para o próximo bloco."
        else:
            ana += "Você está muito descansado para o que foi proposto. Pode ser hora de subir o sarrafo nos próximos treinos."

    msg.append(ana)

    full_message = "\n".join(msg)
    send_ntfy_notification(
        title="Relatório Noturno de Performance",
        message=full_message,
        priority="default",
        tags="night_with_stars,chart_with_upwards_trend,checkered_flag"
    )
    return "Relatório noturno enviado!"

if __name__ == "__main__":
    try:
        print(generate_nightly_report())
    except Exception as e:
        print(f"Erro ao gerar relatório noturno: {e}")
