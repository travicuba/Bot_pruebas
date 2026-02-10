#!/usr/bin/env python3
"""
main.py v4.0 - BOT CON MACHINE LEARNING REAL

Sistema completo con:
- Aprendizaje automático
- 8+ estrategias
- Ajuste dinámico de parámetros
- Selección inteligente de estrategia
"""

import time
import os
import json
import sys
import logging
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(__file__))


# ==============================
# STATUS DEL BOT
# ==============================
BOT_STATUS_FILE = "/home/travieso/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files/bot_status.json"

def write_bot_status(running: bool):
        data = {
            "running": running,
            "timestamp": int(time.time())
        }
        os.makedirs(os.path.dirname(BOT_STATUS_FILE), exist_ok=True)
        with open(BOT_STATUS_FILE, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.utime(BOT_STATUS_FILE, None)


# ==============================
# LOGGING
# ==============================
def setup_logging():
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ==============================
# IMPORTS DEL BOT
# ==============================
try:
    from decision_engine.context_analyzer import analyze_market_context
    from decision_engine.signal_router import evaluate_signal
    from data_providers.mt5_reader import read_market_data
    logger.info("✅ Módulos principales cargados")
except Exception as e:
    logger.error(f"❌ Error cargando módulos: {e}")
    sys.exit(1)

# Selector inteligente
try:
    from decision_engine.intelligent_selector import select_intelligent_strategy as select_setup
    logger.info("✅ Selector inteligente cargado")
except:
    logger.warning("⚠️ Usando selector básico")
    from decision_engine.setup_selector import select_setup

# Sistema ML
try:
    from ml_adaptive_system import ml_auto_adjust, get_ml_status
    ML_AVAILABLE = True
    logger.info("✅ Sistema ML disponible")
except:
    ML_AVAILABLE = False
    logger.warning("⚠️ Sistema ML no disponible")
    def ml_auto_adjust():
        return False
    def get_ml_status():
        return {"mode": "DISABLED"}

# Feedback
try:
    from feedback.feedback_processor import process_feedback, get_overall_stats
    logger.info("✅ Módulo de feedback cargado")
except Exception as e:
    logger.warning(f"⚠️ Feedback no disponible: {e}")
    def process_feedback():
        return False
    def get_overall_stats():
        return {"total_trades": 0, "total_wins": 0, "total_losses": 0, "win_rate": 0, "total_pips": 0}

# ==============================
# CONFIG
# ==============================
def load_config():
    config_file = "bot_config.json"
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"✅ Config cargada: min_conf={config.get('min_confidence')}%")
            return config
        except Exception as e:
            logger.warning(f"⚠️ Error leyendo config: {e}")
    
    logger.info("📄 Usando config por defecto")
    return {
        "min_confidence": 35,
        "cooldown": 5,
        "max_daily_trades": 50,
        "max_losses": 5,
        "lot_size": 0.01,
        "start_hour": "00:00",
        "end_hour": "23:59"
    }

# ==============================
# GLOBALS
# ==============================
RUNNING = False
CONFIG = {}
last_trade_time = 0
consecutive_losses = 0
paused_until = 0
cycle_count = 0

SIGNAL_FILE_PATH = "/home/travieso/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files/signals/signal.json"

def clear_signal_file():
    if os.path.exists(SIGNAL_FILE_PATH):
        try:
            os.remove(SIGNAL_FILE_PATH)
            logger.info("🗑️ signal.json eliminado")
            return True
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False
    return True

def create_stop_signal():
    try:
        os.makedirs(os.path.dirname(SIGNAL_FILE_PATH), exist_ok=True)
        
        stop_signal = {
            "signal_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_STOP",
            "action": "NONE",
            "confidence": 0.0,
            "sl_pips": 0,
            "tp_pips": 0,
            "symbol": "EURUSD",
            "timeframe": "M5",
            "timestamp": datetime.now().isoformat(),
            "setup_name": "SYSTEM_STOP",
            "reason": "Bot detenido"
        }
        
        with open(SIGNAL_FILE_PATH, "w") as f:
            json.dump(stop_signal, f, indent=4)
        
        logger.info("🛑 Señal STOP creada")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def run_cycle():
    global last_trade_time, consecutive_losses, paused_until, cycle_count
    
    cycle_count += 1
    
    logger.info("=" * 60)
    logger.info(f"🧠 Ciclo #{cycle_count}: {datetime.now()}")
    logger.info("=" * 60)

    # SISTEMA ML: Ajustar automáticamente
    if ML_AVAILABLE:
        try:
            if ml_auto_adjust():
                # Se actualizó la config, recargar
                global CONFIG
                CONFIG = load_config()
        except Exception as e:
            logger.debug(f"ML adjust: {e}")
    
    # FEEDBACK
    try:
        if process_feedback():
            logger.info("📊 Feedback procesado")
    except:
        pass
    
    # PROTECCIONES
    current_time = time.time()
    
    if paused_until > current_time:
        remaining = int((paused_until - current_time) / 60)
        logger.warning(f"⏸️ PAUSA ({remaining} min)")
        return
    
    cooldown = CONFIG.get("cooldown", 5)
    if last_trade_time > 0:
        time_since_last = current_time - last_trade_time
        if time_since_last < cooldown:
            logger.debug(f"⏳ Cooldown: {int(cooldown - time_since_last)}s")
            return
    
    max_daily = CONFIG.get("max_daily_trades", 50)
    stats = get_overall_stats()
    if stats["total_trades"] >= max_daily:
        logger.warning(f"🛑 LÍMITE: {stats['total_trades']} trades")
        return
    
    if stats["total_trades"] > 0:
        logger.info(f"📊 Stats: {stats['total_wins']}W/{stats['total_losses']}L | "
                   f"WR: {stats['win_rate']:.1f}% | Pips: {stats['total_pips']:.2f}")
    
    # ML STATUS cada 10 ciclos
    if ML_AVAILABLE and cycle_count % 10 == 0:
        ml_status = get_ml_status()
        logger.info(f"🧠 ML: {ml_status.get('mode', 'N/A')} | "
                   f"Trades: {ml_status.get('total_trades', 0)}")

    # MERCADO
    logger.debug("📥 Leyendo mercado...")
    try:
        market_data = read_market_data()
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return
    
    if not market_data:
        logger.warning("⏩ Sin datos")
        return

    logger.debug(f"✅ {len(market_data)} registros")

    # CONTEXTO
    logger.debug("🔍 Analizando contexto...")
    try:
        context = analyze_market_context(market_data)
        logger.info(f"📊 CONTEXTO: {context.get('trend')}, {context.get('volatility')}, "
                   f"conf={context.get('confidence', 0):.0%}, allowed={context.get('trade_allowed')}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return

    # SETUP INTELIGENTE
    logger.debug("🎯 Selector inteligente...")
    try:
        setup = select_setup(context)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return

    if not setup:
        logger.info("❌ NO SETUP")
        return

    logger.info(f"🧠 SETUP: {setup['name']} (score: {setup['score']:.2f})")

    # SEÑAL
    logger.debug("⚡ Evaluando señal...")
    try:
        signal = evaluate_signal(setup["name"], context, market_data)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return

    if signal is None:
        logger.warning("⚠️ Signal = None")
        return

    if signal.get("action") == "NONE":
        logger.info("ℹ️ Action NONE")
        return
    
    # VERIFICAR CONFIDENCE
    confidence = signal.get("confidence", 0)
    min_conf = CONFIG.get("min_confidence", 35) / 100.0
    
    if confidence < min_conf:
        logger.warning(f"⚠️ {confidence:.2%} < {min_conf:.2%}")
        return

    # SEÑAL VÁLIDA
    logger.info("=" * 60)
    logger.info("📈 SEÑAL GENERADA:")
    logger.info(f"   Action: {signal['action']}")
    logger.info(f"   Confidence: {confidence:.2%}")
    logger.info(f"   SL/TP: {signal.get('sl_pips')}/{signal.get('tp_pips')}")
    logger.info(f"   Setup: {signal.get('setup_name', setup['name'])}")
    logger.info("=" * 60)
    
    if os.path.exists(SIGNAL_FILE_PATH):
        logger.info("✅ signal.json OK")
    else:
        logger.error("❌ signal.json NO creado!")
    
    last_trade_time = current_time

def start_bot():
    global RUNNING, paused_until, consecutive_losses, CONFIG, cycle_count
    
    CONFIG = load_config()
    
    RUNNING = True
    write_bot_status(True)
    paused_until = 0
    consecutive_losses = 0
    cycle_count = 0
    
    logger.info("=" * 60)
    logger.info("🚀 TRADING BOT v4.0 - ML INTEGRATED")
    logger.info("=" * 60)
    
    # ML Status
    if ML_AVAILABLE:
        ml_status = get_ml_status()
        logger.info(f"🧠 SISTEMA ML: {ml_status.get('mode', 'ACTIVE')}")
        if ml_status.get('total_trades', 0) > 0:
            logger.info(f"   Total trades aprendidos: {ml_status['total_trades']}")
    
    logger.info("⚙️ CONFIG:")
    logger.info(f"   Min Confidence: {CONFIG.get('min_confidence')}%")
    logger.info(f"   Cooldown: {CONFIG.get('cooldown')}s")
    logger.info(f"   Max Daily: {CONFIG.get('max_daily_trades')}")
    logger.info("=" * 60)
    
    signal_dir = os.path.dirname(SIGNAL_FILE_PATH)
    if not os.path.exists(signal_dir):
        try:
            os.makedirs(signal_dir, exist_ok=True)
            logger.info("✅ Directorio creado")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
    
    clear_signal_file()

    loop_interval = 5
    
    while RUNNING:
        write_bot_status(True)
        try:
            run_cycle()
            time.sleep(loop_interval)
        except KeyboardInterrupt:
            logger.info("\n⌨️ Ctrl+C")
            break
        except Exception as e:
            logger.error(f"❌ ERROR: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(5)

    write_bot_status(False)
    logger.info("🧯 DETENIDO")
    clear_signal_file()
    create_stop_signal()

def stop_bot():
    global RUNNING
    logger.info("ℹ️ Solicitando detención...")
    RUNNING = False
    write_bot_status(False)

if __name__ == "__main__":
    try:
        start_bot()
    except KeyboardInterrupt:
        logger.info("\n⌨️ Deteniendo...")
        stop_bot()
    except Exception as e:
        logger.critical(f"❌ FATAL: {e}")
        import traceback
        logger.critical(traceback.format_exc())
    finally:
        clear_signal_file()
        create_stop_signal()
        logger.info("👋 Cerrado")
