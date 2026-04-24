#!/usr/bin/env python3
"""
EKO Health Check & Auto-Recovery Script
Checks: Kimi proxy, Paperclip API, Agent statuses
Auto-fixes: Restart proxy, resume error agents
"""
import os, sys, time, subprocess, json, requests

PAPERCLIP_API = os.getenv("PAPERCLIP_API", "http://100.88.47.99:3100")
COMPANY_ID = os.getenv("PAPERCLIP_COMPANY_ID", "a5151f95-51cd-4d2d-a35b-7d7cb4f4102e")
API_KEY = os.getenv("PAPERCLIP_API_KEY", "pcp_board_68ed2bc4520167360cb1ae178b2b3285692f536e08aa7300")
PROXY_PORT = int(os.getenv("KIMI_PROXY_PORT", "18794"))
PROXY_SCRIPT = os.getenv("KIMI_PROXY_SCRIPT", "/home/enderj/.paperclip/kimi-proxy.py")
PROXY_LOG = os.getenv("KIMI_PROXY_LOG", "/home/enderj/.paperclip/kimi-proxy.log")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def log(level, msg):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {level:5} | {msg}", flush=True)

def check_proxy():
    try:
        return requests.get(f"http://127.0.0.1:{PROXY_PORT}/health", timeout=5).status_code == 200
    except Exception as e:
        log("DEBUG", f"Proxy check failed: {e}")
        return False

def restart_proxy():
    log("WARN", "Restarting Kimi proxy...")
    subprocess.run("pkill -9 -f kimi-proxy.py", shell=True, capture_output=True)
    time.sleep(1)
    with open(PROXY_LOG, "a") as logf:
        subprocess.Popen(
            ["python3", PROXY_SCRIPT],
            stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True
        )
    time.sleep(3)
    ok = check_proxy()
    log("INFO" if ok else "ERROR", f"Proxy restart {'OK' if ok else 'FAILED'}")
    return ok

def check_paperclip():
    try:
        r = requests.get(f"{PAPERCLIP_API}/api/health", timeout=10)
        return r.status_code == 200
    except Exception as e:
        log("DEBUG", f"Paperclip check failed: {e}")
        return False

def get_agents():
    try:
        r = requests.get(
            f"{PAPERCLIP_API}/api/companies/{COMPANY_ID}/agents",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log("DEBUG", f"Agent list failed: {e}")
    return []

def resume_agent(agent_id):
    try:
        r = requests.post(
            f"{PAPERCLIP_API}/api/agents/{agent_id}/resume",
            headers=HEADERS, timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        log("DEBUG", f"Resume agent failed: {e}")
        return False

def create_issue(title, desc, prio="medium", status="todo"):
    try:
        r = requests.post(
            f"{PAPERCLIP_API}/api/companies/{COMPANY_ID}/issues",
            json={"title": title, "description": desc, "priority": prio, "status": status},
            headers=HEADERS, timeout=10
        )
        if r.status_code in (200, 201):
            data = r.json()
            log("INFO", f"Issue created: {data.get('identifier', data.get('id'))}")
            return data
    except Exception as e:
        log("WARN", f"Issue creation failed: {e}")
    return None

def main():
    log("INFO", "=== EKO Health Check Started ===")
    actions = []
    errors = []

    if not check_proxy():
        errors.append("Kimi proxy down")
        if restart_proxy():
            actions.append("Proxy restarted")
        else:
            errors.append("Proxy restart failed")
    else:
        log("INFO", "Proxy OK")

    if not check_paperclip():
        errors.append("Paperclip API unreachable")
    else:
        log("INFO", "Paperclip API OK")

    agents = get_agents()
    error_agents = [a for a in agents if a.get("status") in ("error", "paused")]
    if error_agents:
        for a in error_agents:
            name = a.get("name", "Unknown")
            aid = a.get("id")
            log("WARN", f"Agent {name} ({aid}) status={a.get('status')}")
            if resume_agent(aid):
                actions.append(f"Agent {name} resumed")
            else:
                errors.append(f"Agent {name} resume failed")
    elif agents:
        log("INFO", f"All {len(agents)} agents OK")
    else:
        log("WARN", "No agents returned from API")

    if errors:
        log("ERROR", f"Errors: {', '.join(errors)}")
        desc_lines = ["Errors:"] + [f"- {e}" for e in errors]
        if actions:
            desc_lines += ["", "Actions taken:"] + [f"- {a}" for a in actions]
        create_issue(
            "Health check: system errors detected",
            "\n".join(desc_lines),
            prio="high" if any("failed" in e for e in errors) else "medium",
            status="todo"
        )
        return False
    elif actions:
        log("INFO", f"Auto-recovered: {', '.join(actions)}")
        create_issue(
            "Health check: auto-recovery performed",
            "\n".join(f"- {a}" for a in actions),
            prio="low", status="done"
        )

    log("INFO", "=== Health Check Complete ===")
    return True

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
