from __future__ import annotations

import json
import re
import subprocess
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Tuple

import requests


@dataclass
class ToolResult:
    ok: bool
    output: str


class ToolRegistry:
    def __init__(self, scripts_dir: str) -> None:
        self.scripts_dir = Path(scripts_dir)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, Callable[[str], ToolResult]] = {
            "open_browser": self.open_browser,
            "run_script": self.run_script,
            "call_api": self.call_api,
            "create_file": self.create_file,
        }

    def route_and_execute(self, command: str) -> ToolResult | None:
        cmd = command.lower().strip()

        if cmd.startswith("abrir site") or cmd.startswith("abra site"):
            return self.open_browser(command)

        if cmd.startswith("rodar script") or cmd.startswith("rode script"):
            return self.run_script(command)

        if cmd.startswith("chamar api"):
            return self.call_api(command)

        if cmd.startswith("criar arquivo"):
            return self.create_file(command)

        return None

    def open_browser(self, command: str) -> ToolResult:
        match = re.search(r"(https?://\S+|www\.\S+)", command, re.IGNORECASE)
        if not match:
            return ToolResult(False, "Nao identifiquei a URL para abrir.")

        url = match.group(1)
        if not url.startswith("http"):
            url = f"https://{url}"

        webbrowser.open(url)
        return ToolResult(True, f"Abrindo {url}")

    def run_script(self, command: str) -> ToolResult:
        # Espera formato: "rode script nome.py"
        parts = command.strip().split()
        if len(parts) < 3:
            return ToolResult(False, "Informe o nome do script. Exemplo: rode script exemplo.py")

        script_name = parts[-1]
        target = (self.scripts_dir / script_name).resolve()

        if self.scripts_dir.resolve() not in target.parents or not target.exists():
            return ToolResult(False, "Script nao encontrado na pasta scripts.")

        completed = subprocess.run(
            ["python", str(target)],
            capture_output=True,
            text=True,
            cwd=str(self.scripts_dir.resolve().parent),
            timeout=60,
            check=False,
        )

        if completed.returncode != 0:
            return ToolResult(False, f"Falha ao executar script: {completed.stderr.strip()}")

        output = completed.stdout.strip() or "Script executado com sucesso."
        return ToolResult(True, output)

    def call_api(self, command: str) -> ToolResult:
        # Espera formato: "chamar api https://..."
        match = re.search(r"(https?://\S+)", command, re.IGNORECASE)
        if not match:
            return ToolResult(False, "Nao identifiquei a URL da API.")

        url = match.group(1)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            return ToolResult(False, f"Erro ao chamar API: {exc}")

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            preview = json.dumps(data, ensure_ascii=True)[:350]
            return ToolResult(True, f"Resposta da API: {preview}")

        preview = response.text[:350]
        return ToolResult(True, f"Resposta da API: {preview}")

    def create_file(self, command: str) -> ToolResult:
        # Espera formato: "criar arquivo nome.txt conteudo: texto"
        pattern = r"criar arquivo\s+(\S+)\s+conteudo:\s+(.+)"
        match = re.search(pattern, command, re.IGNORECASE)
        if not match:
            return ToolResult(False, "Use: criar arquivo nome.txt conteudo: seu texto")

        filename, content = match.group(1), match.group(2)
        safe_path = (self.scripts_dir.resolve().parent / filename).resolve()

        workspace_root = self.scripts_dir.resolve().parent
        if workspace_root not in safe_path.parents and safe_path != workspace_root:
            return ToolResult(False, "Caminho fora do workspace nao permitido.")

        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
        return ToolResult(True, f"Arquivo criado em {safe_path.name}")
