#!/usr/bin/env python3
"""只读扫描一个代码仓库，产出"事实层"材料，供项目拆解与教学报告使用。

设计原则：本脚本只产出**确定性事实**（目录结构、规模统计、入口候选、清单文件、
待办标记计数等），不做任何语义判断。语义解读由调用方（模型）完成。

安全约束：全程只读仓库，不修改、不移动、不删除任何仓库内文件；
唯一的写操作是在 --out 指定目录下创建 facts.json 与 facts.md 两个文件。

用法：
    python scan_repo.py <repo-path> [--out DIR] [--depth N] [--max-files N]
                                   [--max-head-lines N] [--top N] [--stdout]

退出码：0 正常；1 参数/路径错误。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------- 常量表

NOISE_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".vs", ".cache", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".venv", "venv", "env", ".env.d",
    "node_modules", "bower_components", "vendor", "third_party", "thirdparty",
    "dist", "build", "out", "output", "target", "bin", "obj", "Debug", "Release",
    "coverage", ".coverage", "htmlcov", ".next", ".nuxt", ".svelte-kit", ".output",
    ".turbo", ".parcel-cache", ".gradle", ".m2", "__pycache__", "site-packages",
    "egg-info", ".eggs", "generated", "gen", "auto-generated", "codegen",
    "Pods", "Carthage", ".dart_tool", ".terraform", "tmp", "temp", "logs",
    "storybook-static", ".yarn", ".pnpm-store", "bazel-bin", "bazel-out",
    ".project-dissection", ".dissect", ".gitnexus", ".understand-anything",
    ".codegraph", ".code-review-graph", ".aider",
}

BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".jar", ".war",
    ".exe", ".dll", ".so", ".dylib", ".a", ".o", ".obj", ".class", ".pyc",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".avi", ".mov",
    ".wav", ".flac", ".psd", ".ai", ".sketch", ".fig", ".db", ".sqlite",
    ".sqlite3", ".mdb", ".lock", ".bin", ".dat", ".pkl", ".npy", ".npz",
    ".h5", ".onnx", ".pt", ".pth", ".safetensors", ".gguf", ".wasm", ".map",
}

# 扩展名 -> 语言/技术标签
LANG_BY_EXT = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala", ".groovy": "Groovy",
    ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C++",
    ".c": "C", ".h": "C/C++ header", ".cc": "C++", ".cpp": "C++", ".cxx": "C++",
    ".hpp": "C++ header", ".hxx": "C++ header", ".cs": "C#", ".fs": "F#",
    ".dart": "Dart", ".lua": "Lua", ".pl": "Perl", ".r": "R", ".jl": "Julia",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".clj": "Clojure",
    ".hs": "Haskell", ".ml": "OCaml", ".nim": "Nim", ".zig": "Zig", ".v": "V",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell",
    ".ps1": "PowerShell", ".psm1": "PowerShell", ".bat": "Batch", ".cmd": "Batch",
    ".sql": "SQL", ".graphql": "GraphQL", ".gql": "GraphQL", ".proto": "Protobuf",
    ".tf": "Terraform", ".hcl": "HCL", ".yaml": "YAML", ".yml": "YAML",
    ".json": "JSON", ".toml": "TOML", ".ini": "INI", ".cfg": "Config",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".sass": "Sass", ".less": "Less", ".vue": "Vue", ".svelte": "Svelte",
    ".astro": "Astro", ".md": "Markdown", ".mdx": "MDX", ".rst": "reStructuredText",
    ".tex": "LaTeX", ".ipynb": "Jupyter", ".sol": "Solidity", ".asm": "Assembly",
    ".s": "Assembly", ".cmake": "CMake", ".gradle": "Gradle", ".make": "Make",
    ".dockerfile": "Dockerfile", ".tfvars": "Terraform vars", ".ipynb_checkpoints": "Jupyter",
}

# 入口候选：(正则, 说明, 优先级 1=最可信)
ENTRY_PATTERNS = [
    (r"(^|/)cmd/[^/]+/main\.go$", "Go 标准入口 (cmd/*/main.go)", 1),
    (r"(^|/)src/main/(java|kotlin)/.*Application\.(java|kt)$", "JVM Application 入口", 1),
    (r"(^|/)Program\.cs$", ".NET 入口 (Program.cs)", 1),
    (r"(^|/)__main__\.py$", "Python 包入口 (__main__.py)", 1),
    (r"(^|/)(manage|cli|main|app|server|run|wsgi|asgi)\.py$", "Python 常用入口", 2),
    (r"(^|/)main\.(c|cc|cpp|cxx|m|mm|rs|java|kt|scala|swift|dart|lua|hs|ml|nim|zig|v|ex|exs|rb|php)$", "语言主入口 main.*", 1),
    (r"(^|/)bin/[^/.]+$", "可执行脚本 bin/*", 3),
    (r"(^|/)src/(index|main|app|server)\.(ts|js|tsx|jsx|mjs|cjs)$", "前端/Node 入口", 2),
    (r"(^|/)(index|main)\.(ts|js|tsx|jsx|mjs|cjs)$", "模块入口 index/main.*", 3),
    (r"(^|/)pages/_app\.(tsx|jsx|ts|js)$", "Next.js pages 入口", 1),
    (r"(^|/)app/(layout|page)\.(tsx|jsx|ts|js)$", "Next.js App Router 入口", 1),
    (r"(^|/)src/main\.(ts|js)$", "打包器入口 (src/main.*)", 2),
    (r"(^|/)public/index\.html$", "浏览器入口 HTML", 2),
    (r"(^|/)templates?/index\.html$", "服务端模板入口", 3),
]

CONFIG_NAMES = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "requirements-dev.txt", "requirements.in", "Pipfile", "go.mod", "Cargo.toml",
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "Gemfile",
    "composer.json", "mix.exs", "pubspec.yaml", "CMakeLists.txt", "Makefile",
    "makefile", "GNUmakefile", "justfile", "Justfile", "Taskfile.yml",
    "tsconfig.json", "jsconfig.json", "angular.json", "vite.config.ts",
    "vite.config.js", "webpack.config.js", "rollup.config.js", "next.config.js",
    "next.config.mjs", "nuxt.config.ts", "svelte.config.js", "astro.config.mjs",
    "tailwind.config.js", "postcss.config.js", "babel.config.js", ".babelrc",
    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "requirements.lock", "uv.lock", "poetry.lock", "Pipfile.lock", "yarn.lock",
    "manage.py", "noxfile.py", "tox.ini", "conftest.py", "pytest.ini",
    "phpunit.xml", "jest.config.js", "vitest.config.ts", "playwright.config.ts",
    ".pre-commit-config.yaml", "renovate.json", "dependabot.yml",
}
CONFIG_SUFFIXES = (
    ".csproj", ".sln", ".fsproj", ".vbproj", ".xcodeproj", ".pbxproj",
    ".tf", ".tfvars", ".eslintrc", ".stylelintrc", ".editorconfig",
)
CI_DIR_HINTS = (".github/workflows", ".gitlab-ci", ".circleci", ".buildkite", "azure-pipelines", ".drone.yml", ".woodpecker")
CI_FILES = {"Jenkinsfile", ".travis.yml", "appveyor.yml", "bitbucket-pipelines.yml", "cloudbuild.yaml"}

TEST_HINTS = (r"(^|/)tests?/", r"(^|/)__tests__/", r"(^|/)spec/", r"(^|/)test_", r"_test\.", r"\.test\.", r"\.spec\.", r"Tests?\.(cs|java|kt)$")
SCHEMA_HINTS = (r"(^|/)migrations?/", r"(^|/)schema", r"\.sql$", r"\.prisma$", r"(^|/)models?/", r"\.proto$", r"\.graphql$")
API_HINTS = (r"(^|/)routes?/", r"(^|/)controllers?/", r"(^|/)handlers?/", r"(^|/)api/", r"(^|/)endpoints?/", r"(^|/)resolvers?/", r"(^|/)services?/")
DOC_HINTS = (r"(^|/)docs?/", r"(^|/)wiki/", r"README", r"CHANGELOG", r"CONTRIBUTING", r"ARCHITECTURE", r"DESIGN", r"\.md$", r"\.rst$")
SECRET_HINTS = (r"(^|/)\.env", r"\.pem$", r"\.key$", r"\.p12$", r"\.pfx$", r"id_rsa", r"credentials", r"secrets?\.", r"\.npmrc$", r"\.pypirc$")
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG|NOTE|WARNING|DEPRECATED)\b")
SKIP_CONTENT_EXT = {".json", ".lock", ".min.js", ".min.css", ".svg"}

MAX_BYTES_TO_READ = 512 * 1024


def _now() -> str:
    return _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def _matches_any(path_posix: str, hints) -> bool:
    return any(re.search(h, path_posix) for h in hints)


def git_info(root: Path) -> dict:
    info: dict = {}
    for key, args in (
        ("commit", ["git", "rev-parse", "HEAD"]),
        ("commit_short", ["git", "rev-parse", "--short", "HEAD"]),
        ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        ("last_commit_date", ["git", "log", "-1", "--format=%aI"]),
        ("last_commit_subject", ["git", "log", "-1", "--format=%s"]),
        ("commit_count", ["git", "rev-list", "--count", "HEAD"]),
        ("first_commit_date", ["git", "log", "--reverse", "--format=%aI", "-1"]),
        ("remote", ["git", "config", "--get", "remote.origin.url"]),
    ):
        try:
            out = subprocess.run(
                args, cwd=str(root), capture_output=True, text=True, timeout=25
            )
            if out.returncode == 0:
                info[key] = out.stdout.strip()
        except Exception:
            pass
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(root),
            capture_output=True, text=True, timeout=25,
        )
        if out.returncode == 0:
            dirty = [l for l in out.stdout.splitlines() if l.strip()]
            info["dirty_file_count"] = len(dirty)
    except Exception:
        pass
    if (root / ".git" / "shallow").exists():
        info["shallow_clone"] = True
    return info


def read_head(path: Path, max_lines: int) -> str:
    try:
        if path.stat().st_size > MAX_BYTES_TO_READ:
            chunk = path.read_bytes()[:MAX_BYTES_TO_READ]
            text = chunk.decode("utf-8", errors="replace")
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = text.splitlines()[:max_lines]
    return "\n".join(lines)


def count_lines(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text.count("\n") + int(bool(text) and not text.endswith("\n"))
    except Exception:
        return 0


def scan_todos(path: Path) -> Counter:
    hits: Counter = Counter()
    try:
        if path.stat().st_size > MAX_BYTES_TO_READ:
            return hits
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return hits
    for line in text.splitlines():
        if len(line) > 400:
            continue
        for m in TODO_RE.findall(line):
            hits[m] += 1
    return hits


def build_tree(root: Path, max_depth: int, max_children: int = 40) -> list:
    def walk(d: Path, depth: int) -> list:
        if depth > max_depth:
            return []
        try:
            entries = sorted(
                d.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
            )
        except Exception:
            return []
        nodes = []
        shown = 0
        hidden = 0
        for e in entries:
            if e.name in NOISE_DIRS or e.name.startswith(".git"):
                continue
            if e.is_dir():
                if shown >= max_children:
                    hidden += 1
                    continue
                children = walk(e, depth + 1)
                nodes.append({"name": e.name, "type": "dir", "children": children})
                shown += 1
            else:
                if shown >= max_children:
                    hidden += 1
                    continue
                if e.suffix.lower() in BINARY_EXT:
                    continue
                nodes.append({"name": e.name, "type": "file"})
                shown += 1
        if hidden:
            nodes.append({"name": f"... (+{hidden} more)", "type": "truncated"})
        return nodes

    return walk(root, 1)


def extract_manifest(path: Path, max_lines: int) -> dict:
    result: dict = {"path": None, "kind": None, "items": [], "raw_head": ""}
    name = path.name.lower()
    result["path"] = path.as_posix()
    head = read_head(path, max_lines)
    result["raw_head"] = head
    try:
        if name == "package.json":
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            deps = {}
            for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                if isinstance(data.get(k), dict):
                    for dk, dv in data[k].items():
                        deps[f"{dk}@{dv}"] = k
            result["kind"] = "npm"
            result["items"] = sorted(deps.keys())
            if isinstance(data.get("scripts"), dict):
                result["scripts"] = data["scripts"]
            result["meta"] = {k: data.get(k) for k in ("name", "version", "main", "module", "type", "workspaces") if k in data}
        elif name == "requirements.txt" or name.startswith("requirements") and name.endswith(".txt"):
            result["kind"] = "pip"
            result["items"] = [
                l.strip() for l in head.splitlines()
                if l.strip() and not l.strip().startswith("#")
            ]
        elif name == "go.mod":
            result["kind"] = "go"
            items = []
            for l in head.splitlines():
                s = l.strip()
                if not s or s.startswith("//"):
                    continue
                if s.startswith("require"):
                    s = s[len("require"):].strip()
                s = s.strip("()").strip()
                if not s or s.startswith(("module ", "go ", "toolchain ", "exclude ", "replace ", "retract ")):
                    continue
                items.append(s)
            result["items"] = items[:60]
        elif name == "cargo.toml":
            result["kind"] = "cargo"
            items, in_dep = [], False
            for l in head.splitlines():
                s = l.strip()
                if s.startswith("["):
                    in_dep = "dependencies" in s
                    continue
                if in_dep and "=" in s:
                    items.append(s)
            result["items"] = items
        elif name == "pom.xml":
            result["kind"] = "maven"
            result["items"] = re.findall(r"<artifactId>([^<]+)</artifactId>", head)[:60]
        elif name == "pyproject.toml":
            result["kind"] = "python-packaging"
            data = None
            try:
                import tomllib
                data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                data = None
            items = []
            if isinstance(data, dict):
                proj = data.get("project") or {}
                for d in (proj.get("dependencies") or []):
                    items.append(str(d))
                for grp, deps in (proj.get("optional-dependencies") or {}).items():
                    for d in (deps or []):
                        items.append(f"{d}  [{grp}]")
                tool = data.get("tool") or {}
                poetry = tool.get("poetry") or {}
                for section in ("dependencies", "dev-dependencies"):
                    for k, v in (poetry.get(section) or {}).items():
                        if str(k).lower() == "python":
                            continue
                        items.append(f"{k} {v}" if isinstance(v, str) else str(k))
                for _, cfg in (poetry.get("group") or {}).items():
                    for k in ((cfg or {}).get("dependencies") or {}):
                        items.append(str(k))
                for k in (tool.get("uv") or {}).get("dev-dependencies") or []:
                    items.append(str(k))
                meta = {}
                for k in ("name", "version", "requires-python", "description"):
                    if k in proj:
                        meta[k] = proj[k]
                if meta:
                    result["meta"] = meta
            if not items:
                items = re.findall(r"^\s*[\"']([A-Za-z0-9_.\-]+)[\"']\s*[><=~!]", head, re.M)
            result["items"] = items[:60]
        elif name == "pipfile":
            result["kind"] = "pipenv"
            items, section = [], None
            for l in head.splitlines():
                s = l.strip()
                if s.startswith("["):
                    section = s.strip("[]").lower()
                    continue
                if section in {"packages", "dev-packages"} and "=" in s and not s.startswith("#"):
                    items.append(s.replace('"', ""))
            result["items"] = items[:60]
        elif name in {"setup.py", "setup.cfg"}:
            result["kind"] = "python-setuptools"
            block = re.search(r"install_requires\s*=\s*\[(.*?)\]", head, re.S)
            src = block.group(1) if block else ""
            items = re.findall(r"[A-Za-z0-9_.\-]+(?:\s*[<>=!~]+\s*[0-9][^\s\"',]*)?", src)
            result["items"] = [i.strip() for i in items if i.strip()][:60]
        else:
            result["kind"] = "other"
    except Exception:
        result["kind"] = result["kind"] or "unparsed"
    return result


def detect_frameworks(root: Path, manifests: list, file_set: set) -> list:
    """基于清单文件与关键文件存在性做确定性框架指纹，不做推测性判断。"""
    fps = []
    names = {Path(p).name for p in file_set}
    parts = []
    for m in manifests:
        for item in (m.get("items") or []):
            parts.append(str(item))
        for key in ("meta", "scripts"):
            if m.get(key):
                parts.append(json.dumps(m[key], ensure_ascii=False))
    hay = (" ".join(parts) + " " + " ".join(sorted(names))).lower()

    checks = [
        ("django", "Python / Django"), ("flask", "Python / Flask"),
        ("fastapi", "Python / FastAPI"), ("tornado", "Python / Tornado"),
        ("celery", "Python / Celery"), ("pydantic", "Python / Pydantic"),
        ("pytest", "Testing / pytest"), ("sqlalchemy", "Python / SQLAlchemy"),
        ("express", "Node / Express"), ("koa", "Node / Koa"),
        ("nestjs", "Node / NestJS"), ("fastify", "Node / Fastify"),
        ("next", "Web / Next.js"), ("nuxt", "Web / Nuxt"),
        ("vue", "Web / Vue"), ("svelte", "Web / Svelte"),
        ("astro", "Web / Astro"), ("solid-js", "Web / Solid"),
        ("react", "Web / React"), ("preact", "Web / Preact"),
        ("vite", "Build / Vite"), ("webpack", "Build / Webpack"),
        ("rollup", "Build / Rollup"), ("esbuild", "Build / esbuild"),
        ("tailwindcss", "CSS / Tailwind"), ("electron", "Desktop / Electron"),
        ("tauri", "Desktop / Tauri"), ("react-native", "Mobile / React Native"),
        ("expo", "Mobile / Expo"), ("flutter", "Mobile / Flutter"),
        ("spring-boot", "Java / Spring Boot"), ("springframework", "Java / Spring"),
        ("quarkus", "Java / Quarkus"), ("micronaut", "JVM / Micronaut"),
        ("ktor", "Kotlin / Ktor"), ("rails", "Ruby / Rails"),
        ("sinatra", "Ruby / Sinatra"), ("laravel", "PHP / Laravel"),
        ("symfony", "PHP / Symfony"), ("gin-gonic", "Go / Gin"),
        ("gofiber", "Go / Fiber"), ("echo", "Go / Echo"),
        ("actix-web", "Rust / Actix"), ("axum", "Rust / Axum"),
        ("rocket", "Rust / Rocket"), ("tokio", "Rust / Tokio"),
        ("serde", "Rust / Serde"), ("tensorflow", "ML / TensorFlow"),
        ("torch", "ML / PyTorch"), ("transformers", "ML / Transformers"),
        ("langchain", "LLM / LangChain"), ("openai", "LLM / OpenAI SDK"),
        ("prisma", "DB / Prisma"), ("typeorm", "DB / TypeORM"),
        ("sequelize", "DB / Sequelize"), ("mongoose", "DB / Mongoose"),
        ("redis", "Store / Redis"), ("psycopg", "DB / PostgreSQL driver"),
        ("pymongo", "DB / MongoDB driver"), ("kafka", "Messaging / Kafka"),
        ("rabbitmq", "Messaging / RabbitMQ"), ("amqplib", "Messaging / AMQP"),
        ("grpc", "RPC / gRPC"), ("graphql", "API / GraphQL"),
        ("socket.io", "Realtime / Socket.IO"), ("websocket", "Realtime / WebSocket"),
        ("prometheus", "Observability / Prometheus"), ("opentelemetry", "Observability / OTel"),
        ("jest", "Testing / Jest"), ("vitest", "Testing / Vitest"),
        ("playwright", "Testing / Playwright"), ("cypress", "Testing / Cypress"),
        ("terraform", "Infra / Terraform"), ("kubernetes", "Infra / Kubernetes"),
        ("pulumi", "Infra / Pulumi"), ("airflow", "Orchestration / Airflow"),
        ("dbt", "Data / dbt"), ("pandas", "Data / pandas"),
        ("numpy", "Data / NumPy"),
    ]
    seen = set()
    for needle, label in checks:
        if needle in hay and label not in seen:
            seen.add(label)
            fps.append(label)
    if "Dockerfile" in names or "docker-compose.yml" in names or "compose.yml" in names:
        fps.append("Infra / Docker")
    if "Makefile" in names:
        fps.append("Build / Make")
    if "CMakeLists.txt" in names:
        fps.append("Build / CMake")
    return sorted(set(fps))


def main() -> int:
    ap = argparse.ArgumentParser(description="只读扫描仓库，产出事实层材料")
    ap.add_argument("repo", help="仓库根目录路径")
    ap.add_argument("--out", default=None, help="输出目录（默认 <repo>/.project-dissection）")
    ap.add_argument("--depth", type=int, default=3, help="目录树展示深度（默认 3）")
    ap.add_argument("--max-files", type=int, default=60000, help="最多遍历文件数（默认 60000）")
    ap.add_argument("--max-head-lines", type=int, default=60, help="清单文件读取行数（默认 60）")
    ap.add_argument("--top", type=int, default=25, help="最大的文件列出前 N 个（默认 25）")
    ap.add_argument("--stdout", action="store_true", help="只打印 facts.md 到标准输出，不写文件")
    args = ap.parse_args()

    root = Path(args.repo).expanduser().resolve()
    if not root.is_dir():
        print(f"错误：不是有效目录 -> {root}", file=sys.stderr)
        return 1

    out_dir = (
        Path(args.out).expanduser().resolve() if args.out else (root / ".project-dissection")
    )

    def _inside_out_dir(d: Path) -> bool:
        try:
            d.resolve().relative_to(out_dir)
            return True
        except Exception:
            return False

    lang_files: Counter = Counter()
    lang_lines: Counter = Counter()
    ext_files: Counter = Counter()
    file_sizes: list = []
    todos: Counter = Counter()
    todo_files: Counter = Counter()
    entry_candidates: list = []
    configs: list = []
    build_files: list = []
    ci_files: list = []
    test_files: list = []
    schema_files: list = []
    api_files: list = []
    doc_files: list = []
    secret_files: list = []
    manifest_paths: list = []
    file_set: set = set()
    total_files = 0
    total_lines = 0
    seen_noise: Counter = Counter()
    skipped_binary = 0
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in NOISE_DIRS and not d.startswith(".git")]
        if _inside_out_dir(Path(dirpath)):
            dirnames[:] = []
            continue
        for fn in filenames:
            if total_files >= args.max_files:
                truncated = True
                break
            p = Path(dirpath) / fn
            try:
                rel = p.relative_to(root).as_posix()
            except Exception:
                continue
            ext = p.suffix.lower()
            if ext in BINARY_EXT:
                skipped_binary += 1
                continue
            total_files += 1
            file_set.add(rel)
            ext_files[ext or "(no ext)"] += 1
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            file_sizes.append((rel, size))

            lang = LANG_BY_EXT.get(ext)
            if lang and ext not in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".lock"}:
                lang_files[lang] += 1
                lines = count_lines(p)
                lang_lines[lang] += lines
                total_lines += lines
                if ext not in SKIP_CONTENT_EXT:
                    hits = scan_todos(p)
                    if hits:
                        todos.update(hits)
                        todo_files[rel] = sum(hits.values())

            for pat, desc, prio in ENTRY_PATTERNS:
                if re.search(pat, rel):
                    entry_candidates.append({"path": rel, "why": desc, "confidence": prio})
                    break

            base = fn
            if base in CONFIG_NAMES or ext in CONFIG_SUFFIXES or base.startswith(".env"):
                configs.append(rel)
                if base in {"package.json", "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts", "requirements.txt", "composer.json", "Gemfile", "pubspec.yaml", "mix.exs", "setup.py", "setup.cfg", "Pipfile"}:
                    manifest_paths.append(rel)
            if base in {"Dockerfile", "Makefile", "makefile", "justfile", "CMakeLists.txt", "Taskfile.yml"} or base.startswith("docker-compose"):
                build_files.append(rel)
            if base in CI_FILES or any(h in rel for h in CI_DIR_HINTS):
                ci_files.append(rel)
            if _matches_any(rel, TEST_HINTS):
                test_files.append(rel)
            if _matches_any(rel, SCHEMA_HINTS):
                schema_files.append(rel)
            if _matches_any(rel, API_HINTS):
                api_files.append(rel)
            if _matches_any(rel, DOC_HINTS):
                doc_files.append(rel)
            if _matches_any(rel, SECRET_HINTS):
                secret_files.append(rel)
        if truncated:
            break

    # 去重，按入口可信度排序
    entry_candidates = sorted(
        {e["path"]: e for e in entry_candidates}.values(),
        key=lambda e: (e["confidence"], e["path"]),
    )
    manifests = [extract_manifest(root / mp, args.max_head_lines) for mp in manifest_paths]
    for _m, _mp in zip(manifests, manifest_paths):
        _m["path"] = _mp
    frameworks = detect_frameworks(root, manifests, file_set)

    top_by_size = sorted(file_sizes, key=lambda t: t[1], reverse=True)[: args.top]
    top_todo = sorted(todo_files.items(), key=lambda t: t[1], reverse=True)[: args.top]

    readme = None
    for cand in ("README.md", "README.rst", "README.txt", "readme.md", "README.MD", "README"):
        if (root / cand).is_file():
            readme = {"path": cand, "head": read_head(root / cand, args.max_head_lines)}
            break

    facts = {
        "generated_at": _now(),
        "repo_root": root.as_posix(),
        "repo_name": root.name,
        "git": git_info(root),
        "scan": {
            "files_scanned": total_files,
            "binary_skipped": skipped_binary,
            "truncated": truncated,
            "max_files_limit": args.max_files,
            "tree_depth": args.depth,
        },
        "size": {
            "total_code_lines": total_lines,
            "languages": [
                {"language": k, "files": lang_files[k], "lines": lang_lines[k]}
                for k in sorted(lang_lines, key=lambda x: lang_lines[x], reverse=True)
            ],
            "extensions": [{"ext": k, "files": v} for k, v in ext_files.most_common(30)],
            "largest_files": [{"path": p, "bytes": s} for p, s in top_by_size],
        },
        "frameworks_detected": frameworks,
        "entry_candidates": entry_candidates[:40],
        "configs": sorted(configs)[:80],
        "build_files": sorted(set(build_files))[:40],
        "ci_files": sorted(set(ci_files))[:40],
        "manifests": manifests,
        "tests": {
            "file_count": len(test_files),
            "sample": sorted(set(test_files))[:40],
            "test_to_code_ratio": round(len(test_files) / total_files, 4) if total_files else 0,
        },
        "schema_files": sorted(set(schema_files))[:40],
        "api_or_service_files": sorted(set(api_files))[:60],
        "doc_files": sorted(set(doc_files))[:40],
        "sensitive_files": sorted(set(secret_files))[:40],
        "todos": {
            "by_marker": dict(todos),
            "total": sum(todos.values()),
            "hotspot_files": [{"path": p, "count": c} for p, c in top_todo],
        },
        "readme": readme,
        "tree": build_tree(root, args.depth),
    }

    md = render_markdown(facts)

    if args.stdout:
        sys.stdout.write(md)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "facts.md").write_text(md, encoding="utf-8")
    print(f"OK  facts.json / facts.md -> {out_dir}")
    return 0


def render_markdown(f: dict) -> str:
    L = []
    a = L.append
    git = f.get("git", {})
    a(f"# 事实层扫描报告 · {f['repo_name']}")
    a("")
    a(f"- 生成时间：{f['generated_at']}")
    a(f"- 仓库路径：`{f['repo_root']}`")
    if git:
        a(f"- 分支：`{git.get('branch', '?')}` | 提交：`{git.get('commit_short', '?')}`"
          f" | 提交总数：{git.get('commit_count', '?')}")
        a(f"- 最近提交：{git.get('last_commit_date', '?')} — {git.get('last_commit_subject', '')}")
        a(f"- 首次提交：{git.get('first_commit_date', '?')}")
        if "dirty_file_count" in git:
            a(f"- 未提交改动文件数：{git['dirty_file_count']}")
        if git.get("shallow_clone"):
            a("- ⚠️ **浅克隆（--depth）**：提交总数与首次提交时间失真，"
              "**不得据此推断项目活跃度或历史演进**。需要历史信息请改用完整克隆。")
    s = f["scan"]
    a(f"- 扫描文件数：{s['files_scanned']}（跳过二进制 {s['binary_skipped']}，截断：{s['truncated']}）")
    a("")
    a("## 1. 规模与语言构成（事实）")
    a("")
    a(f"代码总行数（按可识别语言统计）：**{f['size']['total_code_lines']:,}**")
    a("")
    a("| 语言 | 文件数 | 行数 | 占比 |")
    a("|---|---:|---:|---:|")
    total = f["size"]["total_code_lines"] or 1
    for row in f["size"]["languages"][:15]:
        pct = row["lines"] / total * 100
        a(f"| {row['language']} | {row['files']} | {row['lines']:,} | {pct:.1f}% |")
    a("")
    a("## 2. 技术栈指纹（基于清单文件与关键文件的存在性判定）")
    a("")
    if f["frameworks_detected"]:
        a("、".join(f["frameworks_detected"]))
    else:
        a("_未从清单中识别到常见框架指纹，需人工确认。_")
    a("")
    a("## 3. 入口候选（按约定匹配，confidence 1 = 最可信）")
    a("")
    a("| 文件 | 匹配依据 | confidence |")
    a("|---|---|---:|")
    for e in f["entry_candidates"][:20]:
        a(f"| `{e['path']}` | {e['why']} | {e['confidence']} |")
    if not f["entry_candidates"]:
        a("_未匹配到约定入口，需人工定位。_")
    a("")
    a("## 4. 清单文件内容（原始提取）")
    a("")
    for m in f["manifests"]:
        a(f"### `{m['path']}`（{m['kind']}）")
        a("")
        if m.get("meta"):
            a(f"元信息：`{json.dumps(m['meta'], ensure_ascii=False)}`")
            a("")
        if m.get("scripts"):
            a(f"可用脚本：`{json.dumps(m['scripts'], ensure_ascii=False)}`")
            a("")
        if m.get("items"):
            items = m["items"][:35]
            a("依赖：" + ", ".join(f"`{i}`" for i in items))
            if len(m["items"]) > len(items):
                a(f"（其余 {len(m['items']) - len(items)} 项略）")
            a("")
        if not m.get("items") and not m.get("meta"):
            a("```")
            a(m.get("raw_head", "")[:1200])
            a("```")
            a("")
    a("## 5. 测试与文档覆盖（事实计数）")
    a("")
    a(f"- 测试文件数：{f['tests']['file_count']}（占全部文件 {f['tests']['test_to_code_ratio'] * 100:.1f}%）")
    a(f"- 文档文件数：{len(f['doc_files'])}")
    a(f"- CI 配置文件：{len(f['ci_files'])}")
    a(f"- Schema / 迁移 / 模型文件：{len(f['schema_files'])}")
    a(f"- API / 路由 / 服务 目录文件：{len(f['api_or_service_files'])}")
    a("")
    if f["tests"]["sample"]:
        a("测试文件样例：")
        a("")
        for p in f["tests"]["sample"][:12]:
            a(f"- `{p}`")
        a("")
    a("## 6. 技术债标记热点（确定性计数）")
    a("")
    t = f["todos"]
    if t["total"]:
        a("标记总数：" + ", ".join(f"{k}={v}" for k, v in sorted(t["by_marker"].items())))
        a("")
        a("| 文件 | 标记数 |")
        a("|---|---:|")
        for h in t["hotspot_files"][:15]:
            a(f"| `{h['path']}` | {h['count']} |")
    else:
        a("_未发现 TODO/FIXME 类标记。_")
    a("")
    a("## 7. 提示：需谨慎处理的文件")
    a("")
    if f["sensitive_files"]:
        a("以下文件可能含凭据或密钥，**在报告中只提路径，绝不引用其内容**：")
        a("")
        for p in f["sensitive_files"][:20]:
            a(f"- `{p}`")
    else:
        a("_未匹配到常见敏感文件名模式。仍应在生成报告前人工确认。_")
    a("")
    a("## 8. 最大的文件（体积热点）")
    a("")
    for row in f["size"]["largest_files"][:15]:
        a(f"- `{row['path']}` — {row['bytes']:,} B")
    a("")
    a("## 9. 目录树（已排除噪音目录）")
    a("")
    a("```")
    a(f"{f['repo_name']}/")
    a(render_tree(f["tree"], ""))
    a("```")
    a("")
    if f.get("readme"):
        a(f"## 10. README 开头（`{f['readme']['path']}`）")
        a("")
        a("```")
        a(f["readme"]["head"][:2500])
        a("```")
        a("")
    a("---")
    a("")
    a("以上全部为脚本抽取的**事实**。语义判断（模块职责、架构层归属、业务流程、设计取舍）")
    a("必须由拆解者另行推断，并在报告中标注为推断而非事实。")
    return "\n".join(L)


def render_tree(nodes: list, prefix: str, max_items: int = 400) -> str:
    lines = []
    for i, n in enumerate(nodes):
        if len(lines) > max_items:
            lines.append(prefix + "...")
            break
        last = i == len(nodes) - 1
        branch = "└── " if last else "├── "
        name = n["name"] + ("/" if n["type"] == "dir" else "")
        lines.append(prefix + branch + name)
        if n["type"] == "dir" and n.get("children"):
            ext = "    " if last else "│   "
            lines.append(render_tree(n["children"], prefix + ext, max_items))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
