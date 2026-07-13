import unittest.mock as mock
from datetime import datetime, timedelta
import sys
import os

# Adiciona o diretório atual ao path para importar o módulo
sys.path.append(os.getcwd())

from health_tracker.daily_report import generate_daily_report

def simulate_tomorrow():
    tomorrow = datetime.now() + timedelta(days=1)
    
    # Mockando get_local_now() dentro do módulo daily_report
    with mock.patch('health_tracker.daily_report.get_local_now') as mock_get_local_now:
        mock_get_local_now.return_value = tomorrow
        
        print(f"Simulando relatório para: {tomorrow.strftime('%Y-%m-%d')}")
        result = generate_daily_report()
        print(result)

if __name__ == "__main__":
    simulate_tomorrow()
