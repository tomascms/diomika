#!/usr/bin/env python3
"""
Arranque local Diomika: API + loja Vite + worker email + backoffice.

Uso (na raiz do repo):
  python INICIAR_DIOMIKA.py

Portas típicas: API 8001, loja 5173, backoffice 5174.
Produção 24/7 não usa este script — ver deploy/FREE_STACK.md (VM + Tunnel).
"""
import os
import sys
import subprocess
import time
import shutil
import socket
import requests
from pathlib import Path
import signal

root = Path(__file__).resolve().parent
os.chdir(root)

sys.path.insert(0, str(root / "backend-api"))
from core.env_loader import load_project_env

load_project_env()

processes: list[dict] = []


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def cleanup(sig=None, frame=None):
    print(f"\n{Colors.YELLOW}Terminando serviços...{Colors.END}")
    for entry in processes:
        if not entry.get("owned", True):
            continue
        proc = entry.get("proc")
        if not proc:
            continue
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{Colors.END}\n")


def print_step(step, text):
    print(f"{Colors.BLUE}[{step}]{Colors.END} {text}")


def print_ok(text):
    print(f"{Colors.GREEN}✓{Colors.END} {text}")


def print_err(text):
    print(f"{Colors.RED}✗{Colors.END} {text}")


def print_info(text):
    print(f"{Colors.YELLOW}→{Colors.END} {text}")


def ensure_python_deps():
    req_file = root / "requirements.txt"
    if not req_file.exists():
        return

    print_info("A verificar dependências Python...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print_ok("Dependências Python OK")
    else:
        print_err("Falha ao instalar dependências Python")
        if result.stderr:
            print(result.stderr.strip()[:500])


def find_npm() -> str | None:
    for name in ("npm", "npm.cmd", "npm.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def read_process_output(proc: subprocess.Popen, limit: int = 2000) -> str:
    if proc.stdout is None and proc.stderr is None:
        return ""
    try:
        out, err = proc.communicate(timeout=0.5)
    except subprocess.TimeoutExpired:
        return ""
    text = (err or b"").decode("utf-8", errors="replace")
    if not text.strip():
        text = (out or b"").decode("utf-8", errors="replace")
    return text.strip()[:limit]


def report_process_failure(name: str, proc: subprocess.Popen | None):
    if proc is None:
        return
    code = proc.returncode
    if code == 0 and name == "Backoffice":
        print_info(f"{name} fechado")
        return
    print_err(f"{name} terminou inesperadamente (código {code})")
    output = read_process_output(proc)
    if output:
        print(f"{Colors.RED}{output}{Colors.END}")


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def find_node() -> str | None:
    return shutil.which("node")


def find_pids_on_port(port: int) -> list[int]:
    pids: list[int] = []
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            needle = f":{port}"
            for line in result.stdout.splitlines():
                if needle not in line or "LISTENING" not in line.upper():
                    continue
                parts = line.split()
                if not parts:
                    continue
                try:
                    pid = int(parts[-1])
                    if pid and pid != os.getpid():
                        pids.append(pid)
                except ValueError:
                    continue
        else:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
            )
            for part in result.stdout.split():
                try:
                    pids.append(int(part))
                except ValueError:
                    continue
    except Exception:
        pass
    return sorted(set(pids))


def free_port(port: int, name: str) -> bool:
    pids = find_pids_on_port(port)
    if not pids:
        return True

    print_info(f"Porta {port} ({name}) ocupada — PID(s): {', '.join(map(str, pids))}")
    for pid in pids:
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as e:
            print_err(f"Não foi possível terminar PID {pid}: {e}")
            return False

    time.sleep(1.5)
    if find_pids_on_port(port):
        print_err(f"Porta {port} continua ocupada")
        return False

    print_ok(f"Porta {port} libertada")
    return True


def get_backend_health() -> dict | None:
    try:
        resp = requests.get("http://127.0.0.1:8001/health", timeout=3)
        if resp.status_code < 500:
            return resp.json()
    except Exception:
        pass
    return None


def prepare_service(url: str, port: int, name: str) -> str:
    """
    Retorna:
      - 'reuse' se o serviço já responde
      - 'start' se a porta está livre (ou foi libertada)
      - 'blocked' se não foi possível arrancar
    """
    if check_service(url):
        if name == "Backend API":
            health = get_backend_health()
            sys.path.insert(0, str(root / "backend-api"))
            try:
                from core.version import VERSION as API_VERSION
            except ImportError:
                API_VERSION = "2.3.0"
            if health and health.get("version") != API_VERSION:
                print_info(f"{name} desactualizado (v{health.get('version')}) — a reiniciar...")
                if not free_port(port, name):
                    return "blocked"
                return "start"
        print_ok(f"{name} já está a correr — a reutilizar instância existente")
        return "reuse"

    # No Windows o Vite pode estar em [::1] — netstat é mais fiável que socket IPv4
    pids = find_pids_on_port(port)
    if pids:
        if not free_port(port, name):
            print_err(
                f"{name}: feche o processo na porta {port} ou execute "
                f"taskkill /PID <pid> /F"
            )
            return "blocked"

    return "start"


def track(proc: subprocess.Popen | None, name: str, owned: bool = True):
    processes.append({"proc": proc, "name": name, "owned": owned})


def run_python(script: Path, cwd: Path | None = None, name: str = "Processo", capture_output: bool = True):
    try:
        kwargs: dict = {
            "cwd": str(cwd or root),
            "shell": False,
        }
        if capture_output:
            kwargs["stdout"] = subprocess.PIPE
            kwargs["stderr"] = subprocess.STDOUT
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen([sys.executable, str(script)], **kwargs)
        return proc
    except Exception as e:
        print_err(f"{name}: {e}")
        return None


def run_vite(cwd: Path, name: str = "Frontend"):
    """Arranca Vite via node (evita shell no Windows e expõe erros)."""
    node = find_node()
    vite_js = cwd / "node_modules" / "vite" / "bin" / "vite.js"
    if not node:
        print_err(f"{name}: node não encontrado")
        return None
    if not vite_js.exists():
        print_err(f"{name}: execute npm install em {cwd.name}/")
        return None

    try:
        kwargs: dict = {
            "cwd": str(cwd),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        return subprocess.Popen([node, str(vite_js)], **kwargs)
    except Exception as e:
        print_err(f"{name}: {e}")
        return None


def drain_process_output(proc: subprocess.Popen, limit: int = 3000) -> str:
    if proc.stdout is None:
        return read_process_output(proc, limit)
    try:
        chunks = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            chunks.append(line)
            if sum(len(c) for c in chunks) > limit:
                break
        return b"".join(chunks).decode("utf-8", errors="replace").strip()[:limit]
    except Exception:
        return read_process_output(proc, limit)


def run_npm(args: list[str], cwd: Path, name: str = "NPM"):
    npm = find_npm()
    if not npm:
        print_err(f"{name}: npm não encontrado — instale Node.js (https://nodejs.org)")
        return None

    try:
        kwargs: dict = {
            "cwd": str(cwd),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            cmd = " ".join([f'"{npm}"'] + args)
            kwargs["shell"] = True
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(cmd, **kwargs)
        else:
            kwargs["shell"] = False
            proc = subprocess.Popen([npm, *args], **kwargs)
        return proc
    except Exception as e:
        print_err(f"{name}: {e}")
        return None


def check_service(url: str, timeout: int = 5) -> bool:
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code < 500
    except Exception:
        return False


def wait_for_service(url: str, name: str, proc: subprocess.Popen | None, max_wait: int = 30) -> bool:
    start = time.time()
    while time.time() - start < max_wait:
        if proc and proc.poll() is not None:
            report_process_failure(name, proc)
            return False
        if check_service(url, timeout=2):
            print_ok(f"{name} está funcionando")
            return True
        time.sleep(1)
    print_err(f"Timeout esperando {name}")
    if proc and proc.poll() is not None:
        report_process_failure(name, proc)
    elif proc:
        output = drain_process_output(proc)
        if output:
            print(f"{Colors.RED}{output}{Colors.END}")
    return False


# =====================================================
print_header("INICIALIZANDO DIOMIKA")

print_step("1/6", "Verificando ambiente")
ensure_python_deps()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
imap_server = os.getenv("IMAP_SERVER")
mail_user = os.getenv("MAIL_USERNAME")

if supabase_url and supabase_key:
    print_ok("Supabase configurado")
else:
    print_err("Supabase não configurado (.env na raiz do projeto)")
    sys.exit(1)

if imap_server and mail_user:
    print_ok("Email configurado")
else:
    print_info("Email opcional (worker não iniciará)")

if find_npm():
    print_ok("Node.js / npm encontrado")
else:
    print_err("Node.js / npm não encontrado — frontend não arrancará")

print_step("2/6", "Sincronizando schema (Pydantic → BD)")
try:
    sys.path.insert(0, str(root / "backend-api"))
    from core.database import get_db
    from core.schema_engine import sync_schema, _db_reachable
    from core.env_loader import get_database_url

    db = get_db()
    has_db_url = bool(get_database_url())
    if has_db_url and not _db_reachable():
        print_info(
            f"Ligação PostgreSQL directa indisponível (timeout {os.getenv('SUPABASE_DB_CONNECT_TIMEOUT', '5')}s) — a continuar via Supabase API"
        )
    report = sync_schema(supabase=db, apply=has_db_url and _db_reachable())

    if report.created_tables:
        if report.applied:
            print_ok(f"Tabelas criadas: {', '.join(report.created_tables)}")
        elif not has_db_url:
            print_info(
                f"Migração pendente (snapshot): {', '.join(report.created_tables)}"
            )
        else:
            print_info(f"Alterações de schema: {', '.join(report.created_tables)}")

    if report.added_columns:
        for table, cols in report.added_columns.items():
            label = "adicionadas" if report.applied else "pendentes"
            print_ok(f"{table}: colunas {label} → {', '.join(cols)}")

    if report.applied:
        print_ok(report.message)
    elif report.sql_pending and not has_db_url:
        print_info(report.message)
        print_info("Dica: defina SUPABASE_DB_PASSWORD no .env (Supabase → Settings → Database)")
        if report.created_tables:
            project_ref = supabase_url.rstrip("/").split("//")[-1].split(".")[0]
            print_info(f"SQL manual: https://app.supabase.com/project/{project_ref}/sql/new")
    elif report.sql_pending:
        print_info(report.message)
    else:
        print_ok("Schema já atualizado")

    if report.new_field_warnings:
        req = [w for w in report.new_field_warnings if w.get("required")]
        if req:
            print_info(
                f"⚠️  {len(req)} novo(s) campo(s) obrigatório(s) — atualize registos no backoffice"
            )

    incomplete = sum(len(v) for v in report.incomplete_records.values())
    if incomplete:
        print_info(f"⚠️  {incomplete} registo(s) com campos obrigatórios em falta")

except Exception as e:
    print_err(f"Erro ao sincronizar schema: {e}")
    print_info("A continuar mesmo assim...")

print_step("3/6", "Iniciando Backend API")
backend_action = prepare_service("http://127.0.0.1:8001/health", 8001, "Backend API")
if backend_action == "reuse":
    track(None, "Backend API", owned=False)
elif backend_action == "start":
    backend_proc = run_python(root / "backend-api" / "main.py", name="Backend")
    if backend_proc:
        track(backend_proc, "Backend API")
        print_info(f"Backend iniciado (PID: {backend_proc.pid})")
        time.sleep(2)
        if not wait_for_service("http://127.0.0.1:8001/health", "Backend API", backend_proc, max_wait=20):
            print_err("Backend não respondeu — verifique erros acima")
    else:
        print_err("Falha ao iniciar backend")
else:
    print_err("Backend bloqueado — porta 8001 ocupada")

print_step("4/6", "Iniciando Frontend")
frontend_path = root / "frontend-web"
if not find_npm():
    print_err("Frontend ignorado — instale Node.js e reinicie")
else:
    frontend_action = prepare_service("http://127.0.0.1:5173/", 5173, "Frontend")
    if frontend_action == "reuse":
        track(None, "Frontend", owned=False)
    elif frontend_action == "start":
        if not (frontend_path / "node_modules").exists():
            print_info("A instalar dependências do frontend...")
            install_proc = run_npm(["install"], frontend_path, name="NPM Install")
            if install_proc:
                install_proc.wait(timeout=300)
                if install_proc.returncode != 0:
                    report_process_failure("NPM Install", install_proc)
                else:
                    print_ok("Dependências do frontend instaladas")

        frontend_proc = run_vite(frontend_path, name="Frontend")
        if frontend_proc:
            track(frontend_proc, "Frontend")
            print_info(f"Frontend iniciado (PID: {frontend_proc.pid})")
            time.sleep(3)
            if not wait_for_service("http://127.0.0.1:5173/", "Frontend", frontend_proc, max_wait=40):
                print_err("Frontend não respondeu — verifique erros acima")
        else:
            print_err("Falha ao iniciar frontend")
    else:
        print_err("Frontend bloqueado — porta 5173 ocupada")

print_step("5/6", "Iniciando Workers (Email + Outbox)")
if imap_server and mail_user:
    email_proc = run_python(root / "backend-api" / "workers" / "email_worker.py", name="Email Worker")
    if email_proc:
        track(email_proc, "Email Worker")
        print_ok(f"Email Worker iniciado (PID: {email_proc.pid})")
else:
    print_info("Email Worker ignorado (credenciais não configuradas)")

outbox_proc = run_python(root / "backend-api" / "workers" / "outbox_worker.py", name="Outbox Worker")
if outbox_proc:
    track(outbox_proc, "Outbox Worker")
    print_ok(f"Outbox Worker iniciado (PID: {outbox_proc.pid})")

print_step("6/6", "Iniciando Backoffice")
backoffice_path = root / "backoffice-desktop"
if not find_npm():
    print_err("Backoffice ignorado — instale Node.js e reinicie")
else:
    backoffice_action = prepare_service("http://127.0.0.1:5174/", 5174, "Backoffice")
    if backoffice_action == "reuse":
        track(None, "Backoffice", owned=False)
    elif backoffice_action == "start":
        if not (backoffice_path / "node_modules").exists():
            print_info("A instalar dependências do backoffice...")
            install_proc = run_npm(["install"], backoffice_path, name="NPM Backoffice")
            if install_proc:
                install_proc.wait(timeout=300)
                if install_proc.returncode != 0:
                    report_process_failure("NPM Backoffice", install_proc)
                else:
                    print_ok("Dependências do backoffice instaladas")

        backoffice_proc = run_vite(backoffice_path, name="Backoffice")
        if backoffice_proc:
            track(backoffice_proc, "Backoffice")
            print_info(f"Backoffice iniciado (PID: {backoffice_proc.pid})")
            time.sleep(3)
            if not wait_for_service("http://127.0.0.1:5174/", "Backoffice", backoffice_proc, max_wait=40):
                print_err("Backoffice não respondeu — verifique erros acima")
        else:
            print_err("Falha ao iniciar backoffice")
    else:
        print_err("Backoffice bloqueado — porta 5174 ocupada")

# =====================================================
print_header("DIOMIKA PRONTO!")

running = sum(
    1
    for e in processes
    if e.get("proc") is None or e["proc"].poll() is None
)
if running == len(processes):
    print(f"{Colors.GREEN}✓ Todos os serviços estão em execução ({running}){Colors.END}\n")
else:
    print(f"{Colors.YELLOW}⚠ {running}/{len(processes)} serviços em execução{Colors.END}\n")

print(f"{Colors.CYAN}URLs:{Colors.END}")
print(f"  • Frontend:   {Colors.BOLD}http://127.0.0.1:5173{Colors.END}")
print(f"  • Backend:    {Colors.BOLD}http://127.0.0.1:8001/health{Colors.END}")
print(f"  • Backoffice: {Colors.BOLD}http://127.0.0.1:5174{Colors.END}")
project_ref = supabase_url.rstrip("/").split("//")[-1].split(".")[0] if supabase_url else "your-project"
print(f"  • Supabase:   {Colors.BOLD}https://app.supabase.com/project/{project_ref}{Colors.END}\n")

print(f"{Colors.CYAN}Serviços:{Colors.END}")
for entry in processes:
    proc = entry.get("proc")
    if proc is None:
        status = "✓ Já em execução"
        pid = "—"
    else:
        status = "✓ Rodando" if proc.poll() is None else "✗ Parado"
        pid = proc.pid
    print(f"  • {entry['name']}: {status} (PID: {pid})")

print(f"\n{Colors.YELLOW}Ctrl+C para parar tudo{Colors.END}\n")

try:
    while True:
        time.sleep(1)
        dead = [
            i
            for i, e in enumerate(processes)
            if e.get("proc") is not None and e["proc"].poll() is not None
        ]
        for i in sorted(dead, reverse=True):
            entry = processes.pop(i)
            report_process_failure(entry["name"], entry["proc"])
        if not processes:
            print_err("Todos os processos terminaram")
            break
except KeyboardInterrupt:
    cleanup()
