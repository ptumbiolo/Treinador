import os
import json
from datetime import timedelta
import google.generativeai as genai
from .intervals_client import IntervalsClient
from .config import GEMINI_API_KEY, INSTRUCTIONS_PATH, GEMINI_MODEL, BASELINE_HRV_MIN, BASELINE_HRV_MAX
from .utils import send_ntfy_notification, get_local_now

# Configuração Gemini
genai.configure(api_key=GEMINI_API_KEY)

def upload_workout_to_intervals(client, workout_date, name, description, category="WORKOUT", type_override=None):
    act_type = type_override or "Run"
    payload = {
        "start_date_local": f"{workout_date}T07:00:00",
        "type": act_type,
        "name": name,
        "description": description,
        "category": category
    }
    try:
        client.create_event(payload)
        return True
    except Exception as e:
        print(f"Erro ao subir treino {name}: {e}")
        return False

def calculate_week_stats(client, weeks_ago=0):
    today = get_local_now()
    
    # Queremos sempre a semana de Segunda a Domingo.
    if today.weekday() == 6: # Domingo
        end_date = today - timedelta(weeks=weeks_ago)
    else:
        days_since_sunday = (today.weekday() + 1) % 7
        end_date = today - timedelta(days=days_since_sunday) - timedelta(weeks=weeks_ago)
        
    start_date = end_date - timedelta(days=6)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    activities = client.get_activities(start_str, end_str)
    if not isinstance(activities, list):
        activities = []
    
    stats = {
        "Run": {"load": 0, "dist": 0, "dur": 0, "count": 0},
        "Ride": {"load": 0, "dist": 0, "dur": 0, "count": 0},
        "Swim": {"load": 0, "dist": 0, "dur": 0, "count": 0},
        "Total": {"load": 0, "dur": 0, "count": 0}
    }
    for act in activities:
        atype = act.get("type")
        load = act.get("icu_training_load") or act.get("pace_load") or act.get("hr_load") or 0
        dist = (act.get("distance") or 0) / 1000
        dur = (act.get("moving_time") or 0) / 3600
        if atype in stats:
            stats[atype]["load"] += load
            stats[atype]["dist"] += dist
            stats[atype]["dur"] += dur
            stats[atype]["count"] += 1
        stats["Total"]["load"] += load
        stats["Total"]["dur"] += dur
        stats["Total"]["count"] += 1

    wellness = client.get_wellness(start_str, end_str)
    if not isinstance(wellness, list):
        wellness = []
        
    hrv_values = [w.get("hrv") or w.get("avg_sleep_hrv") for w in wellness if (w.get("hrv") or w.get("avg_sleep_hrv"))]
    avg_hrv = sum(hrv_values) / len(hrv_values) if hrv_values else 0
    
    sleep_values = [w.get("sleepSecs") for w in wellness if w.get("sleepSecs")]
    avg_sleep = sum(sleep_values) / (len(sleep_values) * 3600) if sleep_values else 0
    latest = wellness[-1] if wellness else {}
    tsb = latest.get("ctl", 0) - latest.get("atl", 0)
    return stats, avg_hrv, avg_sleep, tsb, start_str, end_str

def calculate_last_week_stats(client):
    return calculate_week_stats(client, weeks_ago=0)

def get_ai_proposed_workouts(stats, hrv, sleep, tsb, history=None, target_load=None, hrv_analysis_str=None):
    instructions = ""
    if os.path.exists(INSTRUCTIONS_PATH):
        with open(INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
            instructions = f.read()

    # Datas para a SEMANA DE TREINO
    today = get_local_now()
    # Se rodar até segunda-feira ao meio-dia, planeja para a semana que começa HOJE.
    # Caso contrário, planeja para a próxima segunda.
    if today.weekday() == 0 and today.hour < 12:
        days_until_monday = 0
    else:
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0: days_until_monday = 7
    
    next_monday = today.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
    dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    days_names = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    history_str = ""
    if history:
        for idx, h in enumerate(history):
            weeks_ago = len(history) - 1 - idx
            label = "Semana retrasada" if weeks_ago == 1 else ("Há 2 semanas" if weeks_ago == 2 else "Semana passada")
            history_str += f"- {label} ({h['start']} a {h['end']}): Carga: {h['load']:.0f} TL | HRV Médio: {h['hrv']:.1f} ms | Sono Médio: {h['sleep']:.1f}h | TSB final: {h['tsb']:.1f}\n"
    else:
        history_str = f"- Semana passada: Carga: {stats['Total']['load']:.0f} TL | HRV: {hrv:.1f} ms | Sono: {sleep:.1f}h | TSB: {tsb:.1f}\n"

    target_load_str = ""
    if target_load:
        target_load_str = f"- Carga Semanal Alvo Recomendada para Evolução (para TSB final de -15): {target_load:.0f} TL"

    prompt = f"""
    Você é um treinador de Triathlon de alto nível e um especialista em Intervals.icu Workout Builder.
    Siga RIGOROSAMENTE o protocolo de 'Gestão Dinâmica de Treino' e as REGRAS DE SINTAXE.

    ESTRATÉGIA DE ANÁLISE:
    1. Analise o Load, HRV e TSB da semana passada.
    2. Se o HRV estiver classificado como muito baixo ("ABAIXO") ou TSB < -40 (Overreaching), reduza a carga e ajuste toda a intensidade para rodagem Z1/Z2. Se o HRV estiver na média ou acima ("NA MÉDIA" ou "ACIMA"), continue na zona de evolução.
    3. Regras de Progressão Fisiológica:
       - O volume total em horas de treino da nova semana não deve crescer mais que 10% em relação à média das últimas semanas.
       - A carga de treino (TSS / TL) pode progredir até 20% apenas se o HRV estiver verde (na média ou acima) e o TSB estiver na zona de evolução (TSB > -30). Caso contrário, mantenha a carga estável ou reduza-a.
    4. Regra de Periodização baseada em Histórico:
       - Uma semana de recuperação ativa (com redução de 30-40% no volume, visando carga de 150-200 TL) só deve ser agendada após um bloco acumulativo de 3 a 4 semanas consecutivas de carga progressiva (onde a fadiga se acumula e o HRV cai ou o TSB cai abaixo de -30).
       - Se o histórico recente mostrar apenas 1 ou 2 semanas de carga mais alta e o TSB/HRV estiverem saudáveis (ex: TSB em zona ideal de treino -10 a -30, e HRV estável/alto), continue na zona de crescimento/evolução. NÃO prescreva semana de recuperação ativa na primeira semana de aumento de volume. Mantenha ou ajuste as cargas e volumes na zona de evolução do atleta (faixa de 300-420 TL), consolidando o volume.
    5. Distribuição de Carga Alvo Semanal (TSB Preditivo):
       - Se houver uma recomendação de carga abaixo, planeje os treinos de modo que a soma total das cargas se aproxime desta meta (+/- 25 TL), ajustando as durações e intensidades conforme a biblioteca oficial. NÃO adote limites máximos fixos arbitrários de carga (como 450 TL) para as semanas de evolução. A carga semanal deve evoluir de forma progressiva para sustentar o ganho de condicionamento de médio/longo prazo, limitando-se apenas pelo TSB (que não deve cair abaixo de -40) e pela progressão máxima de volume semanal (horas) de 10%.
    
    REGRAS DE SINTAXE OBRIGATÓRIA (INTERVALS.ICU):
    - Cada linha de comando deve começar com: "- "
    - UNIDADES: Use 'm' para minutos, 's' para segundos, 'km' para quilômetros.
    - NATAÇÃO: Use SEMPRE 'km' para distância. Intensidade pode ser 'pace' ou 'hr'. (ex: - 0.1km Z2 pace ou - 0.4km Z2 hr).
    - CORRIDA: Intensidade pode ser 'pace' ou 'hr'. (ex: - 10km Z2 pace ou - 30m Z2 hr).
    - CICLISMO: Use SEMPRE 'hr' para intensidade. NUNCA use valores brutos de BPM. (ex: - 30m Z2 hr).
    - REPETIÇÕES: Use o formato "Nx" e pule UMA linha ANTES.
    - Exemplo:
      - 10m Z1 hr

      4x
      - 1km Z4 pace
      - 2m Z1 pace

    TEMPLATE SEMANAL E ZONAS:
    {instructions}
    
    HISTÓRICO RECENTE DE SAÚDE E CARGA:
    {history_str}
    
    ANÁLISE DETALHADA DO HRV (BASELINE DO ÚLTIMO MÊS):
    {hrv_analysis_str}
    
    META DE CARGA PREDITIVA PARA ESTA SEMANA:
    {target_load_str}
    
    DATAS DA SEMANA ATUAL:
    {json.dumps(dict(zip(days_names, dates)), indent=2)}

    REGRAS CRÍTICAS DE FORMATAÇÃO DO JSON:
    1. NUTRIÇÃO: A PRIMEIRA LINHA do campo 'presc' DEVE SER: "CHO/h Xg"
    2. O campo 'presc' deve conter APENAS a sintaxe do builder. NUNCA use "Aquecimento:", "Principal:" ou valores de BPM.
    3. JSON: Responda APENAS com um objeto JSON.

    FORMATO DE RESPOSTA:
    {{
      "analise_executiva": "Explique a lógica (HRV/TSB/Progressão)",
      "treinos": [
        {{
          "dia": "Segunda",
          "data": "{dates[0]}",
          "mod": "Run",
          "obj": "Rodagem Z2",
          "presc": "CHO/h 0g\\n- 15m Z2 pace\\n- 5m Z1 pace"
        }}
      ]
    }}
    """
    
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    
    content = response.text.strip()
    
    # Limpeza robusta do JSON
    if "```" in content:
        parts = content.split("```")
        for part in parts:
            if part.strip().startswith("json"):
                content = part.strip()[4:].strip()
                break
            elif part.strip().startswith("[") or part.strip().startswith("{"):
                content = part.strip()
                break

    try:
        # Tenta carregar normalmente
        data = json.loads(content)
    except json.JSONDecodeError:
        # Se falhar, tenta limpar escapes inválidos (como \C fora de \n)
        import re
        # Substitui backslashes que não fazem parte de um escape válido por double backslashes
        content_cleaned = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', content)
        try:
            data = json.loads(content_cleaned)
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON da IA: {e}")
            print(f"Conteúdo bruto: {content}")
            # Tenta uma limpeza de emergência se o JSON vier com lixo
            json_match = re.search(r'\{\s*"analise_executiva".*\}', content, re.DOTALL)
            if json_match:
                # Aplica a mesma limpeza no match
                match_content = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', json_match.group(0))
                data = json.loads(match_content)
            else:
                raise e

    # Suporta tanto o formato antigo (lista) quanto o novo (objeto com chave 'treinos')
    if isinstance(data, list):
        return {"analise_executiva": "Planejamento gerado.", "treinos": data}
    return data

def get_starting_ctl_atl(client):
    today = get_local_now()
    if today.weekday() == 6: # Domingo
        end_date = today
    else:
        days_since_sunday = (today.weekday() + 1) % 7
        end_date = today - timedelta(days=days_since_sunday)
    end_str = end_date.strftime("%Y-%m-%d")
    wellness = client.get_wellness(end_str, end_str)
    if not isinstance(wellness, list) or not wellness:
        start_str = (end_date - timedelta(days=3)).strftime("%Y-%m-%d")
        wellness = client.get_wellness(start_str, end_str)
    if isinstance(wellness, list) and wellness:
        latest = wellness[-1]
        return latest.get("ctl", 0.0), latest.get("atl", 0.0)
    return 0.0, 0.0

def calculate_target_weekly_load(ctl_0, atl_0, target_tsb=-15.0):
    import math
    fractions = [0.06, 0.18, 0.16, 0.19, 0.07, 0.16, 0.18]
    ctl_decay = math.exp(-1.0 / 42.0)
    atl_decay = math.exp(-1.0 / 7.0)
    
    low = 0.0
    high = 1000.0
    for _ in range(50):
        mid = (low + high) / 2.0
        ctl = ctl_0
        atl = atl_0
        for i in range(7):
            daily_load = mid * fractions[i]
            ctl = ctl * ctl_decay + daily_load * (1 - ctl_decay)
            atl = atl * atl_decay + daily_load * (1 - atl_decay)
        
        ending_tsb = ctl - atl
        if ending_tsb > target_tsb:
            low = mid
        else:
            high = mid
    return low

def calculate_30d_hrv_baseline(client):
    today = get_local_now()
    start_date = today - timedelta(days=30)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")
    
    wellness = client.get_wellness(start_str, end_str)
    if not isinstance(wellness, list):
        wellness = []
        
    hrv_values = [w.get("hrv") or w.get("avg_sleep_hrv") for w in wellness if (w.get("hrv") or w.get("avg_sleep_hrv"))]
    if not hrv_values:
        return 81.0
    return sum(hrv_values) / len(hrv_values)

def generate_weekly_report():
    client = IntervalsClient()
    stats0, hrv0, sleep0, tsb0, start0, end0 = calculate_week_stats(client, weeks_ago=0)
    stats1, hrv1, sleep1, tsb1, start1, end1 = calculate_week_stats(client, weeks_ago=1)
    stats2, hrv2, sleep2, tsb2, start2, end2 = calculate_week_stats(client, weeks_ago=2)
    
    history = [
        {"start": start2, "end": end2, "load": stats2["Total"]["load"], "hrv": hrv2, "sleep": sleep2, "tsb": tsb2},
        {"start": start1, "end": end1, "load": stats1["Total"]["load"], "hrv": hrv1, "sleep": sleep1, "tsb": tsb1},
        {"start": start0, "end": end0, "load": stats0["Total"]["load"], "hrv": hrv0, "sleep": sleep0, "tsb": tsb0}
    ]
    
    ctl_0, atl_0 = get_starting_ctl_atl(client)
    target_load = None
    if ctl_0 > 0.0 or atl_0 > 0.0:
        target_load = calculate_target_weekly_load(ctl_0, atl_0, target_tsb=-15.0)
        print(f"Calculado Carga Alvo Preditiva: {target_load:.1f} TL (para TSB final de -15.0)")
    
    # Análise de HRV baseado no baseline do último mês e faixa normal configurada
    avg_hrv_30d = calculate_30d_hrv_baseline(client)
    if hrv0 < BASELINE_HRV_MIN:
        hrv_status = "ABAIXO (Alerta de Fadiga/Recuperação)"
    elif hrv0 > BASELINE_HRV_MAX:
        hrv_status = "ACIMA (Excelente Recuperação / Supercompensação)"
    else:
        hrv_status = "NA MÉDIA (Estável / Saudável)"
        
    hrv_analysis_str = f"Média da Semana Passada: {hrv0:.1f} ms | Status: {hrv_status} (Faixa Normal do Atleta: {BASELINE_HRV_MIN:.0f} a {BASELINE_HRV_MAX:.0f} ms | Média Real do Último Mês: {avg_hrv_30d:.1f} ms)"
    print(f"Análise HRV: {hrv_analysis_str}")
    
    data = get_ai_proposed_workouts(stats0, hrv0, sleep0, tsb0, history=history, target_load=target_load, hrv_analysis_str=hrv_analysis_str)
    
    proposed = data.get("treinos", [])
    analise = data.get("analise_executiva", "N/A")
    
    # Separar os treinos planejados por dia para identificar duplicidades e mesclar comutações
    day_workouts = {}
    for p in proposed:
        dia = p['dia'].strip().lower()
        if dia not in day_workouts:
            day_workouts[dia] = []
        day_workouts[dia].append(p)
        
    injected_proposed = []
    tue_thu_days = ["terça", "terca", "quinta"]
    
    # Processar cada dia da semana na ordem correta
    for dia_nome in ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]:
        dia_key = dia_nome.lower()
        workouts_today = day_workouts.get(dia_key, [])
        if not workouts_today:
            # Tentar versão sem acento
            if dia_key == "terça":
                workouts_today = day_workouts.get("terca", [])
            elif dia_key == "sábado":
                workouts_today = day_workouts.get("sabado", [])
                
        if not workouts_today:
            continue
            
        # Verificar se tem natação hoje (apenas terça/quinta)
        has_swim = False
        swim_workout = None
        if dia_key in tue_thu_days:
            for w in workouts_today:
                mod_up = w['mod'].upper()
                if any(x in mod_up for x in ["SWIM", "NATAÇÃO", "NATACAO"]):
                    has_swim = True
                    swim_workout = w
                    break
                    
        # Verificar se tem pedal planejado hoje
        has_bike = False
        bike_workout = None
        for w in workouts_today:
            mod_up = w['mod'].upper()
            if any(x in mod_up for x in ["BIKE", "CICLISMO", "RIDE"]):
                has_bike = True
                bike_workout = w
                break
                
        if has_swim and swim_workout:
            # 1. Ida da natação (Bike Z1/Z2)
            injected_proposed.append({
                "dia": swim_workout['dia'],
                "data": swim_workout['data'],
                "mod": "Bike",
                "obj": "Deslocamento Natação (Ida)",
                "presc": "CHO/h 0g\n- 10m Z1 hr\n- 20m Z2 hr\n- 5m Z1 hr"
            })
            
            # 2. Treino de Natação
            injected_proposed.append(swim_workout)
            
            # 3. Volta da natação (Mescla se houver pedal planejado, senão comutação leve)
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
                
            # 4. Outros treinos (ex: Força)
            for w in workouts_today:
                if w == swim_workout:
                    continue
                if w == bike_workout:
                    continue
                injected_proposed.append(w)
        else:
            # Sem natação hoje: apenas adiciona os treinos normalmente
            for w in workouts_today:
                injected_proposed.append(w)
                
    proposed = injected_proposed
    analise = data.get("analise_executiva", "N/A")
    
    msg = []
    msg.append(f"📅 *PLANEJAMENTO SEMANAL IA*")
    msg.append(f"Baseado na semana {start0} a {end0}\n")
    
    msg.append("📊 *RESUMO ANTERIOR*")
    msg.append(f"Carga: {stats0['Total']['load']:.0f} TL | HRV: {hrv0:.1f} ms")
    
    msg.append("\n💡 *ANÁLISE DO TREINADOR*")
    msg.append(analise)
    
    msg.append("\n🚀 *NOVA SEMANA PROPOSTA*")
    
    for p in proposed:
        msg.append(f"\n*[{p['dia']}] {p['mod']}*")
        msg.append(f"🎯 {p['obj']}")
        msg.append(f"📝 {p['presc']}")
        
        mod_upper = p['mod'].upper()
        if any(x in mod_upper for x in ["BIKE", "CICLISMO", "RIDE"]):
            api_type = "Ride"
        elif any(x in mod_upper for x in ["SWIM", "NATAÇÃO", "NATACAO"]):
            api_type = "Swim"
        elif any(x in mod_upper for x in ["MUSC", "STRENGTH", "FORÇA", "FORCA"]):
            api_type = "WeightTraining"
        else:
            api_type = "Run"
            
        upload_workout_to_intervals(client, p['data'], f"{p['mod']}: {p['obj']}", p['presc'], type_override=api_type)

    full_message = "\n".join(msg)
    send_ntfy_notification(
        title="Planejamento IA (Formatado)",
        message=full_message,
        priority="high",
        tags="brain,muscle,calendar"
    )
    
    return "Relatório IA (Formatado) enviado e treinos agendados!"

if __name__ == "__main__":
    try:
        print(generate_weekly_report())
    except Exception as e:
        print(f"Erro: {e}")
