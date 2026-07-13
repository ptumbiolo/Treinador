import os
import json
from datetime import datetime, timedelta
import google.generativeai as genai
import unittest.mock as mock
import sys

# Adiciona o diretório atual ao path para importar o módulo
sys.path.append(os.getcwd())

from health_tracker.intervals_client import IntervalsClient
from health_tracker.config import GEMINI_API_KEY, INSTRUCTIONS_PATH, BASELINE_HRV_MIN, BASELINE_HRV_MAX
from health_tracker.pms_weekly_planner import calculate_last_week_stats, get_ai_proposed_workouts
from health_tracker.utils import send_ntfy_notification

# Configuração Gemini
genai.configure(api_key=GEMINI_API_KEY)

def test_weekly_planner_no_upload():
    print("🚀 Iniciando TESTE do Weekly Planner (Sem Upload)...")
    client = IntervalsClient()
    
    # 1. Calcular estatísticas das últimas 3 semanas
    print("📊 Calculando estatísticas das últimas 3 semanas...")
    from health_tracker.pms_weekly_planner import calculate_week_stats
    stats0, hrv0, sleep0, tsb0, start0, end0 = calculate_week_stats(client, weeks_ago=0)
    stats1, hrv1, sleep1, tsb1, start1, end1 = calculate_week_stats(client, weeks_ago=1)
    stats2, hrv2, sleep2, tsb2, start2, end2 = calculate_week_stats(client, weeks_ago=2)
    
    history = [
        {"start": start2, "end": end2, "load": stats2["Total"]["load"], "hrv": hrv2, "sleep": sleep2, "tsb": tsb2},
        {"start": start1, "end": end1, "load": stats1["Total"]["load"], "hrv": hrv1, "sleep": sleep1, "tsb": tsb1},
        {"start": start0, "end": end0, "load": stats0["Total"]["load"], "hrv": hrv0, "sleep": sleep0, "tsb": tsb0}
    ]
    
    from health_tracker.pms_weekly_planner import get_starting_ctl_atl, calculate_target_weekly_load, calculate_30d_hrv_baseline
    ctl_0, atl_0 = get_starting_ctl_atl(client)
    target_load = None
    if ctl_0 > 0.0 or atl_0 > 0.0:
        target_load = calculate_target_weekly_load(ctl_0, atl_0, target_tsb=-15.0)
        print(f"Calculado Carga Alvo Preditiva: {target_load:.1f} TL (para TSB final de -15.0)")
    
    # Calcular baseline de HRV
    avg_hrv_30d = calculate_30d_hrv_baseline(client)
    if hrv0 < BASELINE_HRV_MIN:
        hrv_status = "ABAIXO (Alerta de Fadiga/Recuperação)"
    elif hrv0 > BASELINE_HRV_MAX:
        hrv_status = "ACIMA (Excelente Recuperação / Supercompensação)"
    else:
        hrv_status = "NA MÉDIA (Estável / Saudável)"
        
    hrv_analysis_str = f"Média da Semana Passada: {hrv0:.1f} ms | Status: {hrv_status} (Faixa Normal do Atleta: {BASELINE_HRV_MIN:.0f} a {BASELINE_HRV_MAX:.0f} ms | Média Real do Último Mês: {avg_hrv_30d:.1f} ms)"
    print(f"Análise HRV: {hrv_analysis_str}")
    
    print(f"✅ Baseado na semana {start0} a {end0}")
    print(f"Carga Total: {stats0['Total']['load']:.0f} | HRV Médio: {hrv0:.1f} ms | TSB: {tsb0:.1f}")

    # 2. Obter proposta da IA
    print("🤖 Solicitando planejamento à IA Gemini...")
    data = get_ai_proposed_workouts(stats0, hrv0, sleep0, tsb0, history=history, target_load=target_load, hrv_analysis_str=hrv_analysis_str)
    
    proposed = data.get("treinos", [])
    analise = data.get("analise_executiva", "N/A")

    # Injetar comutação ativa automaticamente no teste
    day_workouts = {}
    for p in proposed:
        dia = p['dia'].strip().lower()
        if dia not in day_workouts:
            day_workouts[dia] = []
        day_workouts[dia].append(p)
        
    injected_proposed = []
    tue_thu_days = ["terça", "terca", "quinta"]
    
    for dia_nome in ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]:
        dia_key = dia_nome.lower()
        workouts_today = day_workouts.get(dia_key, [])
        if not workouts_today:
            if dia_key == "terça":
                workouts_today = day_workouts.get("terca", [])
            elif dia_key == "sábado":
                workouts_today = day_workouts.get("sabado", [])
                
        if not workouts_today:
            continue
            
        has_swim = False
        swim_workout = None
        if dia_key in tue_thu_days:
            for w in workouts_today:
                mod_up = w['mod'].upper()
                if any(x in mod_up for x in ["SWIM", "NATAÇÃO", "NATACAO"]):
                    has_swim = True
                    swim_workout = w
                    break
                    
        has_bike = False
        bike_workout = None
        for w in workouts_today:
            mod_up = w['mod'].upper()
            if any(x in mod_up for x in ["BIKE", "CICLISMO", "RIDE"]):
                has_bike = True
                bike_workout = w
                break
                
        if has_swim and swim_workout:
            injected_proposed.append({
                "dia": swim_workout['dia'],
                "data": swim_workout['data'],
                "mod": "Bike",
                "obj": "Deslocamento Natação (Ida)",
                "presc": "CHO/h 0g\n- 10m Z1 hr\n- 20m Z2 hr\n- 5m Z1 hr"
            })
            injected_proposed.append(swim_workout)
            if has_bike and bike_workout:
                injected_proposed.append({
                    "dia": bike_workout['dia'],
                    "data": bike_workout['data'],
                    "mod": "Bike",
                    "obj": f"Deslocamento Natação (Volta) + {bike_workout['obj']}",
                    "presc": bike_workout['presc']
                })
            else:
                injected_proposed.append({
                    "dia": swim_workout['dia'],
                    "data": swim_workout['data'],
                    "mod": "Bike",
                    "obj": "Deslocamento Natação (Volta)",
                    "presc": "CHO/h 0g\n- 10m Z1 hr\n- 20m Z2 hr\n- 5m Z1 hr"
                })
            for w in workouts_today:
                if w == swim_workout or w == bike_workout:
                    continue
                injected_proposed.append(w)
        else:
            for w in workouts_today:
                injected_proposed.append(w)
    proposed = injected_proposed

    msg = []
    msg.append(f"🧪 *TESTE: PLANEJAMENTO SEMANAL IA*")
    msg.append(f"Baseado na semana {start0} a {end0}\n")
    msg.append("📊 *RESUMO ANTERIOR*")
    msg.append(f"Carga: {stats0['Total']['load']:.0f} TL | HRV: {hrv0:.1f} ms | TSB: {tsb0:.1f}")
    
    msg.append("\n💡 *ANÁLISE DO TREINADOR*")
    msg.append(analise)
    
    msg.append("\n🚀 *NOVA SEMANA PROPOSTA (SIMULAÇÃO)*")
    
    print("\n--- ANÁLISE DO TREINADOR ---")
    print(analise)
    
    print("\n--- TREINOS GERADOS ---")
    for p in proposed:
        workout_info = f"\n*[{p['dia']}] {p['mod']}*"
        workout_obj = f"🎯 {p['obj']}"
        workout_presc = f"📝 {p['presc']}"
        
        msg.append(workout_info)
        msg.append(workout_obj)
        msg.append(workout_presc)
        
        print(f"[{p['dia']}] {p['mod']}: {p['obj']}")
        print(f"Data: {p['data']}")
        print(f"Prescrição: {p['presc'][:100]}...") # Print resumido na tela
        print("-" * 30)

    # 3. Enviar para o ntfy (Marcado como TESTE)
    full_message = "\n".join(msg)
    send_ntfy_notification(
        title="[TESTE] Planejamento IA",
        message=full_message,
        priority="default",
        tags="test_tube,brain,calendar"
    )
    
    print("\n✅ Teste concluído! Mensagem enviada para o ntfy.")
    print("⚠️  Nenhum treino foi enviado para o Intervals.icu (Upload ignorado).")

if __name__ == "__main__":
    try:
        test_weekly_planner_no_upload()
    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")
