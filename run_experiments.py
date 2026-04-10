"""
run_experiments.py — AutoScaleOps Tam Deney Orkestrasyonu
==========================================================
Tüm akademik deneyleri sırayla çalıştırır:

1. Kontrol       : Sistem sağlık kontrolü
2. Mod B (3x)    : ARIMA proaktif — 30dk × 3 replika
3. Mod A (3x)    : Reaktif — 30dk × 3 replika
4. Spike testi   : Deterministik spike × 3 (Mod B)
5. Kapasite testi: 50→100→150→200 RPS adım testi
6. Horizon deneyi: FORECAST_HORIZON = 5,15,30,60 dk
7. CI deneyi     : CI_LEVEL = 0.80,0.90,0.95,0.99
8. Model karş.   : ARIMA vs HW vs Prophet vs EMA vs Naive
9. Analiz        : Tüm verileri analiz et ve raporla

Kullanım:
  python run_experiments.py [--target http://localhost:8080] [--step 1-9]
  python run_experiments.py --step 8  # sadece model karşılaştırması

NOT: Her deney aşaması ayrı terminal pencerelerinde çalışması gereken
     süreçlere sahiptir. Bu script onları sırayla başlatır ve bekler.
"""

import subprocess
import sys
import io
import time
import json
import argparse
import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
TARGET   = "http://localhost:8080"
PYTHON   = sys.executable

# ─── Yardımcı ─────────────────────────────────────────────────────────────────

def header(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

def run_cmd(cmd: list, timeout: int = None, check: bool = False) -> int:
    """Shell komutu çalıştır, çıktıyı terminale yansıt."""
    print(f"  CMD: {' '.join(str(c) for c in cmd)}")
    try:
        result = subprocess.run(cmd, timeout=timeout)
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Komut zaman aşımına uğradı ({timeout}s)")
        return -1
    except KeyboardInterrupt:
        print("\n  [KESİLDİ] Kullanıcı tarafından durduruldu.")
        sys.exit(0)
    except Exception as e:
        print(f"  [HATA] {e}")
        return -1

def run_parallel(*cmds):
    """Birden fazla komutu paralel başlat."""
    procs = []
    for cmd in cmds:
        print(f"  PARALEL: {' '.join(str(c) for c in cmd)}")
        p = subprocess.Popen(cmd)
        procs.append(p)
    return procs

def wait_all(procs: list, timeout: int = None):
    """Tüm paralel süreçler bitene kadar bekle."""
    for p in procs:
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.terminate()
        except KeyboardInterrupt:
            for pp in procs:
                pp.terminate()
            sys.exit(0)

# ─── Adım 1: Sağlık Kontrolü ──────────────────────────────────────────────────

def step_health_check():
    header("ADIM 1: SİSTEM SAĞLIK KONTROLÜ")
    import requests

    checks = [
        ("Minikube API",        "kubectl cluster-info",       None),
        ("Port-forward 8080",   None,                         "http://localhost:8080/health"),
        ("Port-forward 9090",   None,                         "http://localhost:9090/-/ready"),
        ("Port-forward 9091",   None,                         "http://localhost:9091/metrics"),
    ]

    all_ok = True
    for name, cmd, url in checks:
        if cmd:
            rc = subprocess.run(cmd.split(), capture_output=True).returncode
            status = "OK" if rc == 0 else "HATA"
        else:
            try:
                r = requests.get(url, timeout=5)
                status = f"OK ({r.status_code})"
            except Exception as e:
                status = f"HATA ({e})"
                all_ok = False

        print(f"  {name:<30} {status}")

    print()
    if not all_ok:
        print("  [UYARI] Bazı kontroller başarısız!")
        print("  kubectl port-forward svc/autoscaleops-app -n autoscaleops-74068768 8080:8080 &")
        print("  kubectl port-forward svc/prometheus-kube-prometheus-prometheus -n monitoring 9090:9090 &")
        print("  kubectl port-forward svc/prometheus-kube-prometheus-pushgateway -n monitoring 9091:9091 &")
        ans = input("\n  Devam etmek istiyor musunuz? [e/H]: ")
        if ans.lower() != "e":
            sys.exit(1)
    else:
        print("  Tüm kontroller başarılı! ✓")


# ─── Adım 2: Mod B Replikasyon (3×30dk) ──────────────────────────────────────

def step_mode_b_replication(target: str):
    header("ADIM 2: MOD B REPLİKASYON (ARIMA — 3×30dk)")
    duration = 30 * 60  # 30 dakika

    for rep in range(1, 4):
        print(f"\n  --- Replika {rep}/3 ---")
        output = BASE_DIR / f"results_B_rep{rep}.csv"

        procs = run_parallel(
            [PYTHON, str(BASE_DIR / "traffic_simulator.py"),
             "--mode", "B", "--target", target,
             "--duration", str(duration)],
            [PYTHON, str(BASE_DIR / "metrics_logger.py"),
             "--mode", "B", "--output", str(output),
             "--duration", str(duration)],
        )
        wait_all(procs, timeout=duration + 120)
        print(f"  Replika {rep} tamamlandi → {output}")
        time.sleep(30)  # Sistemin sakinleşmesi için

    print("\n  Mod B replikasyonu tamamlandi.")


# ─── Adım 3: Mod A Replikasyon (3×30dk) ──────────────────────────────────────

def step_mode_a_replication(target: str):
    header("ADIM 3: MOD A REPLİKASYON (REAKTİF — 3×30dk)")
    duration = 30 * 60

    print("  ARIMA predictoru devre dışı bırakılıyor...")
    run_cmd(["kubectl", "scale", "deployment/autoscaleops-ai-deployment",
             "-n", "autoscaleops-74068768", "--replicas=0"])
    time.sleep(10)
    # Pushgateway'den eski metriği sil
    run_cmd(["curl", "-s", "-X", "DELETE",
             "http://localhost:9091/metrics/job/ai_predictor"])
    time.sleep(5)

    for rep in range(1, 4):
        print(f"\n  --- Replika {rep}/3 ---")
        output = BASE_DIR / f"results_A_rep{rep}.csv"

        procs = run_parallel(
            [PYTHON, str(BASE_DIR / "traffic_simulator.py"),
             "--mode", "A", "--target", target,
             "--duration", str(duration)],
            [PYTHON, str(BASE_DIR / "metrics_logger.py"),
             "--mode", "A", "--output", str(output),
             "--duration", str(duration)],
        )
        wait_all(procs, timeout=duration + 120)
        print(f"  Replika {rep} tamamlandi → {output}")
        time.sleep(30)

    print("  ARIMA predictoru yeniden başlatılıyor...")
    run_cmd(["kubectl", "scale", "deployment/autoscaleops-ai-deployment",
             "-n", "autoscaleops-74068768", "--replicas=1"])
    print("\n  Mod A replikasyonu tamamlandi.")


# ─── Adım 4: Spike Testi ─────────────────────────────────────────────────────

def step_spike_test(target: str):
    header("ADIM 4: DETERMİNİSTİK SPIKE TESTİ")
    output = BASE_DIR / "spike_results_B.csv"

    # Mod B için spike testi
    for run_id in range(1, 4):
        print(f"\n  --- Spike testi {run_id}/3 ---")
        output_r = BASE_DIR / f"spike_results_B_run{run_id}.csv"
        logger_out = BASE_DIR / f"spike_logger_B_run{run_id}.csv"
        duration = 45 * 60  # ~45 dakika (3 spike × ~15dk)

        procs = run_parallel(
            [PYTHON, str(BASE_DIR / "spike_test.py"),
             "--mode", "B", "--target", target,
             "--output", str(output_r)],
            [PYTHON, str(BASE_DIR / "metrics_logger.py"),
             "--mode", "B", "--output", str(logger_out),
             "--duration", str(duration)],
        )
        wait_all(procs, timeout=duration + 120)
        print(f"  Spike testi {run_id} tamamlandi")
        time.sleep(60)

    print("\n  Spike testleri tamamlandi.")


# ─── Adım 5: Kapasite Testi ──────────────────────────────────────────────────

def step_capacity_test(target: str):
    header("ADIM 5: KAPASİTE ADIM TESTİ (50→100→150→200 RPS)")
    output   = BASE_DIR / "capacity_results_B.csv"
    duration = 4 * 15 * 60 + 120  # 4×15dk + buffer

    procs = run_parallel(
        [PYTHON, str(BASE_DIR / "capacity_test.py"),
         "--mode", "B", "--target", target,
         "--output", str(output)],
        [PYTHON, str(BASE_DIR / "metrics_logger.py"),
         "--mode", "B", "--output", str(BASE_DIR / "capacity_logger_B.csv"),
         "--duration", str(duration)],
    )
    wait_all(procs, timeout=duration + 120)
    print(f"\n  Kapasite testi tamamlandi → {output}")


# ─── Adım 6: Horizon Deneyleri ───────────────────────────────────────────────

def step_horizon_experiments(target: str):
    header("ADIM 6: TAHMİN UFKU DENEYLERİ (5/15/30/60 dk)")
    horizons = [5, 15, 30, 60]
    duration = 30 * 60  # 30dk her ufuk

    for h in horizons:
        print(f"\n  --- Ufuk: {h} dakika ---")

        # predictor'ı yeni horizon ile yeniden deploy et
        run_cmd(["kubectl", "set", "env",
                 "deployment/autoscaleops-ai-deployment",
                 "-n", "autoscaleops-74068768",
                 f"FORECAST_HORIZON={h}"])
        time.sleep(30)  # Pod'un yeniden başlaması için

        output = BASE_DIR / f"results_horizon{h}min.csv"
        procs = run_parallel(
            [PYTHON, str(BASE_DIR / "traffic_simulator.py"),
             "--mode", "B", "--target", target,
             "--duration", str(duration)],
            [PYTHON, str(BASE_DIR / "metrics_logger.py"),
             "--mode", "B", "--output", str(output),
             "--duration", str(duration)],
        )
        wait_all(procs, timeout=duration + 120)
        print(f"  Ufuk {h}dk tamamlandi → {output}")
        time.sleep(30)

    # Varsayılan horizon'a dön
    run_cmd(["kubectl", "set", "env",
             "deployment/autoscaleops-ai-deployment",
             "-n", "autoscaleops-74068768",
             "FORECAST_HORIZON=5"])
    print("\n  Horizon deneyleri tamamlandi.")


# ─── Adım 7: CI Deneyleri ────────────────────────────────────────────────────

def step_ci_experiments(target: str):
    header("ADIM 7: GÜVEN ARALIĞI DENEYLERİ (0.80/0.90/0.95/0.99)")
    ci_levels = [0.80, 0.90, 0.95, 0.99]
    duration  = 30 * 60

    for ci in ci_levels:
        print(f"\n  --- CI Level: {ci} ---")

        run_cmd(["kubectl", "set", "env",
                 "deployment/autoscaleops-ai-deployment",
                 "-n", "autoscaleops-74068768",
                 f"CI_LEVEL={ci}"])
        time.sleep(30)

        output = BASE_DIR / f"results_ci{int(ci*100)}.csv"
        procs = run_parallel(
            [PYTHON, str(BASE_DIR / "traffic_simulator.py"),
             "--mode", "B", "--target", target,
             "--duration", str(duration)],
            [PYTHON, str(BASE_DIR / "metrics_logger.py"),
             "--mode", "B", "--output", str(output),
             "--duration", str(duration)],
        )
        wait_all(procs, timeout=duration + 120)
        print(f"  CI {ci} tamamlandi → {output}")
        time.sleep(30)

    # Varsayılan CI'a dön
    run_cmd(["kubectl", "set", "env",
             "deployment/autoscaleops-ai-deployment",
             "-n", "autoscaleops-74068768",
             "CI_LEVEL=0.95"])
    print("\n  CI deneyleri tamamlandi.")


# ─── Adım 8: Model Karşılaştırması ───────────────────────────────────────────

def step_model_comparison(input_csv: str = None):
    header("ADIM 8: MODEL KARŞILAŞTIRMASI (Walk-Forward CV)")

    # En iyi CSV'yi seç
    candidates = [
        BASE_DIR / "results_B_improved.csv",
        BASE_DIR / "results_B_rep1.csv",
        BASE_DIR / "results_B.csv",
    ]
    if input_csv:
        candidates.insert(0, Path(input_csv))

    csv_path = None
    for c in candidates:
        if c.exists() and c.stat().st_size > 1000:
            csv_path = c
            break

    if csv_path is None:
        print("  [HATA] Uygun CSV bulunamadi. Önce Mod B deneyi çalıştırın.")
        return

    print(f"  Kullanilan veri: {csv_path}")
    output = BASE_DIR / "model_comparison_results.csv"

    run_cmd([
        PYTHON, str(BASE_DIR / "model_comparison.py"),
        "--input",   str(csv_path),
        "--horizon", "5,15,30,60",
        "--output",  str(output),
    ])

    print(f"\n  Model karşılaştırması tamamlandi → {output}")
    return str(output)


# ─── Adım 9: Tam Analiz ──────────────────────────────────────────────────────

def step_full_analysis():
    header("ADIM 9: TAM ANALİZ VE RAPORLAMA")

    # En güncel A ve B CSV'lerini bul
    b_candidates = sorted(BASE_DIR.glob("results_B*.csv"),
                          key=lambda f: f.stat().st_mtime, reverse=True)
    a_candidates = sorted(BASE_DIR.glob("results_A*.csv"),
                          key=lambda f: f.stat().st_mtime, reverse=True)
    mc_path = BASE_DIR / "model_comparison_results.csv"

    if not b_candidates:
        print("  [HATA] Mod B CSV bulunamadi.")
        return
    if not a_candidates:
        print("  [HATA] Mod A CSV bulunamadi.")
        return

    b_csv = b_candidates[0]
    a_csv = a_candidates[0]
    print(f"  Mod B: {b_csv}")
    print(f"  Mod A: {a_csv}")

    # Bireysel raporlar
    for csv, mode in [(b_csv, "B"), (a_csv, "A")]:
        cmd = [PYTHON, str(BASE_DIR / "analiz.py"),
               "--input", str(csv), "--mode", mode]
        if mc_path.exists():
            cmd += ["--model-comparison", str(mc_path)]
        run_cmd(cmd)

    # Karşılaştırmalı rapor
    print("\n  Karşılaştırmalı rapor üretiliyor...")
    run_cmd([
        PYTHON, str(BASE_DIR / "analiz.py"),
        "--input", str(a_csv), "--compare", str(b_csv),
        "--output", str(BASE_DIR / "karsilastirma_final.txt"),
    ])

    print("\n  Tüm raporlar oluşturuldu.")


# ─── Ana Fonksiyon ────────────────────────────────────────────────────────────

STEPS = {
    1: ("Sağlık Kontrolü",          step_health_check),
    2: ("Mod B Replikasyon 3×30dk", step_mode_b_replication),
    3: ("Mod A Replikasyon 3×30dk", step_mode_a_replication),
    4: ("Spike Testi",              step_spike_test),
    5: ("Kapasite Testi",           step_capacity_test),
    6: ("Horizon Deneyleri",        step_horizon_experiments),
    7: ("CI Deneyleri",             step_ci_experiments),
    8: ("Model Karşılaştırması",    step_model_comparison),
    9: ("Tam Analiz",               step_full_analysis),
}

def main():
    parser = argparse.ArgumentParser(description="AutoScaleOps Deney Orkestrasyonu")
    parser.add_argument("--target", default="http://localhost:8080")
    parser.add_argument("--step",   default="1-9",
                        help="Hangi adımlar (örn: '1-9', '8', '2,3', '8,9')")
    parser.add_argument("--mc-input", default=None,
                        help="Model karşılaştırması için CSV (adım 8)")
    args = parser.parse_args()

    # Adım ayrıştırma
    steps_to_run = []
    for part in args.step.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            steps_to_run.extend(range(int(a), int(b) + 1))
        else:
            steps_to_run.append(int(part))
    steps_to_run = sorted(set(steps_to_run))

    print()
    print("=" * 70)
    print("  AutoScaleOps — Akademik Deney Orkestrasyonu")
    print("=" * 70)
    print(f"  Hedef      : {args.target}")
    print(f"  Adımlar    : {steps_to_run}")
    print(f"  Başlangıç  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    for step_n in steps_to_run:
        if step_n not in STEPS:
            print(f"  [UYARI] Geçersiz adım: {step_n}")
            continue

        name, func = STEPS[step_n]
        print(f"\n  [{step_n}/9] {name}")

        try:
            import inspect
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            if "target" in params and "input_csv" in params:
                func(target=args.target, input_csv=args.mc_input)
            elif "target" in params:
                func(target=args.target)
            elif "input_csv" in params:
                func(input_csv=args.mc_input)
            else:
                func()
        except KeyboardInterrupt:
            print(f"\n  [KESİLDİ] Adım {step_n} durduruldu.")
            ans = input("  Devam etmek istiyor musunuz? [e/H]: ")
            if ans.lower() != "e":
                break
        except Exception as e:
            print(f"  [HATA] Adım {step_n}: {e}")

    print()
    print("=" * 70)
    print("  Tüm adımlar tamamlandi!")
    print(f"  Bitiş: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
