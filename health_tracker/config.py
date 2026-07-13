import os
from dotenv import load_dotenv

load_dotenv()

# API Keys & IDs
INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY")
INTERVALS_ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Notification & Personalization Config
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "athlete_trainings_topic")
ATHLETE_NAME = os.getenv("ATHLETE_NAME", "Athlete")

# Baselines & Goals
BASELINE_HRV = float(os.getenv("BASELINE_HRV", "100.0"))
BASELINE_HRV_MIN = float(os.getenv("BASELINE_HRV_MIN", "60.0"))
BASELINE_HRV_MAX = float(os.getenv("BASELINE_HRV_MAX", "110.0"))
GOAL_SLEEP = float(os.getenv("GOAL_SLEEP", "8.0"))  # horas

# AI Model Configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Timezone Configuration
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTRUCTIONS_PATH = os.path.join(os.path.dirname(BASE_DIR), "INSTRUCOES_TREINO.md")
