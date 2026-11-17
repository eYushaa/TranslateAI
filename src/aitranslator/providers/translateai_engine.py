"""TranslateAI Engine: yerel models/ klasöründeki .gguf modellerini dahili motorla çalıştırır."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Callable

from ..paths import models_dir
from ..secure_storage import SecureStorage
from ..settings import Settings
from .base import ProviderError, ProviderInterface
from .prompts import clean_llm_output, system_prompt

_ENGINE_LOCK = threading.RLock()
_CACHED_KEY: tuple[int, str, int, int] | None = None
_CACHED_LLM: Any = None

CTX_LADDER_STEPS: tuple[int, ...] = (4096, 8192, 16384, 50000)
_K_CTX_MAP: dict[int, int] = {4: 4096, 8: 8192, 16: 16384, 32: 32768}
_CTX_LIMIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([kK])?")


def parse_ctx_limit(value: Any, default: int = 10000) -> int:
    """Kullanıcı/ayar değerini (ör. 10000, '10K', '10000 (10K)', '50k') token sınırına çevirir."""
    if isinstance(value, bool):
        return max(512, min(200000, int(default)))
    if isinstance(value, (int, float)):
        return max(512, min(200000, int(value)))
    if isinstance(value, str):
        cleaned = re.sub(r"(?<=\d)[,_](?=\d{3}\b)", "", value.strip())
        m = _CTX_LIMIT_RE.search(cleaned)
        if m:
            num = float(m.group(1))
            if m.group(2):
                if num.is_integer() and int(num) in _K_CTX_MAP:
                    parsed = _K_CTX_MAP[int(num)]
                else:
                    parsed = int(num * 1000)
            else:
                parsed = int(num)
            return max(512, min(200000, parsed))
    return max(512, min(200000, int(default)))


def estimate_tokens(text: str) -> int:
    """Çok dilli metinler için muhafazakâr token tahmini yapar."""
    if not text:
        return 1
    return max(1, len(text) // 2 + 1, int(len(text.encode("utf-8")) / 2.6) + 1)


def estimate_required_ctx(text: str, sys_prompt: str) -> int:
    """Sistem istemi + girdi + beklenen çeviri çıktısı için gereken toplam bağlamı tahmin eder."""
    prompt_tokens = estimate_tokens(sys_prompt)
    input_tokens = estimate_tokens(text)
    output_tokens = max(256, int(input_tokens * 1.35) + 64)
    return prompt_tokens + input_tokens + output_tokens + 48


def build_ctx_ladder(base_ctx: int, max_ctx: int, auto_expand: bool) -> list[int]:
    """Başlangıç bağlamından üst sınıra doğru otomatik artış basamaklarını oluşturur."""
    base = max(512, int(base_ctx or 4096))
    limit = max(512, int(max_ctx or 10000))
    start = min(base, limit)
    if not auto_expand:
        return [start]
    steps = [start]
    for step in CTX_LADDER_STEPS:
        if start < step < limit:
            steps.append(step)
    if steps[-1] < limit:
        steps.append(limit)
    return steps


def trim_context_to_fit(
    text: str,
    target: str,
    source: str,
    prompt_tmpl: str,
    context: list[tuple[str, str, str]] | None,
    max_ctx: int,
    dynamic_trim: bool,
) -> tuple[list[tuple[str, str, str]], int]:
    """Üst bağlam sınırı aşıldığında geçmiş mesaj bağlamını kademeli olarak kısaltır."""
    if not context:
        return [], 300
    full = list(context)
    sys_full = system_prompt(target, source, prompt_tmpl, context=full, snippet_limit=300)
    if estimate_required_ctx(text, sys_full) <= max_ctx:
        return full, 300
    if not dynamic_trim:
        return full, 300

    for snip in (150, 100):
        if snip == 150 or len(full) == 1:
            sys_sub = system_prompt(target, source, prompt_tmpl, context=full, snippet_limit=snip)
            if estimate_required_ctx(text, sys_sub) <= max_ctx:
                return full, snip

    for keep_n in range(len(full) - 1, 0, -1):
        sub = full[-keep_n:]
        for snip in (150, 100):
            sys_sub = system_prompt(target, source, prompt_tmpl, context=sub, snippet_limit=snip)
            if estimate_required_ctx(text, sys_sub) <= max_ctx:
                return sub, snip

    return [], 300


def clear_engine_cache() -> None:
    """Önbelleğe alınmış dahili LLM örneğini serbest bırakır."""
    global _CACHED_KEY, _CACHED_LLM
    with _ENGINE_LOCK:
        old = _CACHED_LLM
        _CACHED_KEY = None
        _CACHED_LLM = None
        if old is not None and hasattr(old, "close"):
            try:
                old.close()
            except Exception:  # noqa: BLE001
                pass


class TranslateAIEngineProvider(ProviderInterface):
    id = "translateai"
    label = "TranslateAI Engine"
    sends_text_offsite = False

    def __init__(
        self,
        get_settings: Callable[[], Settings],
        secrets: SecureStorage,
        llm_factory: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(get_settings, secrets)
        self._llm_factory = llm_factory

    @staticmethod
    def scan_models() -> list[str]:
        """models/ dizinindeki .gguf dosyalarını (kök ve 1 alt klasör derinliği) tarar."""
        mdir = models_dir()
        if not mdir.is_dir():
            return []
        found: set[str] = set()
        try:
            entries = list(mdir.iterdir())
        except OSError:
            return []
        for entry in entries:
            if entry.is_file() and entry.suffix.lower() == ".gguf":
                found.add(entry.name)
            elif entry.is_dir():
                try:
                    sub_entries = list(entry.iterdir())
                except OSError:
                    continue
                for sub in sub_entries:
                    if sub.is_file() and sub.suffix.lower() == ".gguf":
                        found.add(sub.relative_to(mdir).as_posix())
        return sorted(found)

    def list_models(self) -> list[str]:
        return self.scan_models()

    def resolve_model_path(self) -> Path | None:
        """Seçili .gguf modelinin tam yolunu döner; seçili yoksa ilk bulunan modeli seçer."""
        mdir = models_dir()
        cfg = self.settings.providers.translateai
        configured = cfg.model.strip()
        if configured:
            p = Path(configured)
            candidate = p if p.is_absolute() else (mdir / configured)
            return candidate if candidate.is_file() else None
        models = self.list_models()
        if models:
            candidate = mdir / models[0]
            if candidate.is_file():
                return candidate
        return None

    def is_configured(self) -> bool:
        return self.resolve_model_path() is not None

    def _get_llm(self, model_path: Path, requested_n_ctx: int | None = None) -> Any:
        global _CACHED_KEY, _CACHED_LLM
        cfg = self.settings.providers.translateai
        base_ctx = max(512, int(getattr(cfg, "n_ctx", 4096) or 4096))
        max_ctx = max(base_ctx, parse_ctx_limit(getattr(cfg, "max_n_ctx", 10000), 10000))
        n_ctx = max(512, int(requested_n_ctx or base_ctx))
        n_gpu_layers = int(getattr(cfg, "n_gpu_layers", -1))
        factory_id = id(self._llm_factory) if self._llm_factory is not None else 0
        try:
            resolved_path = str(model_path.resolve())
        except OSError:
            resolved_path = str(model_path)
        key = (factory_id, resolved_path, n_ctx, n_gpu_layers)

        with _ENGINE_LOCK:
            if _CACHED_LLM is not None and _CACHED_KEY is not None:
                cached_factory, cached_path, cached_ctx, cached_gpu = _CACHED_KEY
                if (cached_factory, cached_path, cached_gpu) == (factory_id, resolved_path, n_gpu_layers) and (
                    n_ctx <= cached_ctx <= max_ctx
                ):
                    return _CACHED_LLM

            old = _CACHED_LLM
            _CACHED_KEY = None
            _CACHED_LLM = None
            if old is not None and hasattr(old, "close"):
                try:
                    old.close()
                except Exception:  # noqa: BLE001
                    pass

            if self._llm_factory is not None:
                try:
                    llm = self._llm_factory(model_path=str(model_path), n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
                except Exception as exc:  # noqa: BLE001
                    raise ProviderError(
                        "bad_response",
                        f"{self.label}: '{model_path.name}' modeli başlatılamadı ({exc}).",
                    ) from exc
            else:
                try:
                    from llama_cpp import Llama
                except ImportError as exc:
                    raise ProviderError(
                        "config",
                        f"{self.label}: dahili GGUF motoru (llama-cpp-python) yüklü değil.",
                    ) from exc
                try:
                    llm = Llama(
                        model_path=str(model_path),
                        n_ctx=n_ctx,
                        n_gpu_layers=n_gpu_layers,
                        verbose=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    if n_gpu_layers != 0:
                        try:
                            llm = Llama(
                                model_path=str(model_path),
                                n_ctx=n_ctx,
                                n_gpu_layers=0,
                                verbose=False,
                            )
                        except Exception as cpu_exc:  # noqa: BLE001
                            raise ProviderError(
                                "bad_response",
                                f"{self.label}: '{model_path.name}' modeli başlatılamadı ({cpu_exc}).",
                            ) from cpu_exc
                    else:
                        raise ProviderError(
                            "bad_response",
                            f"{self.label}: '{model_path.name}' modeli başlatılamadı ({exc}).",
                        ) from exc

            _CACHED_KEY = key
            _CACHED_LLM = llm
            return llm

    def _missing_model_error(self) -> ProviderError:
        mdir = models_dir()
        configured = self.settings.providers.translateai.model.strip()
        if configured:
            return ProviderError(
                "model_missing",
                f"{self.label}: seçili '{configured}' modeli '{mdir}' dizininde bulunamadı.",
            )
        return ProviderError(
            "model_missing",
            f"{self.label}: '{mdir}' dizininde .gguf modeli bulunamadı.",
        )

    @staticmethod
    def _is_ctx_overflow_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(tok in msg for tok in ("context", "n_ctx", "exceed", "too long", "token"))

    def translate(
        self,
        text: str,
        target: str,
        source: str = "auto",
        prompt: str = "",
        context: list[tuple[str, str, str]] | None = None,
    ) -> str:
        model_path = self.resolve_model_path()
        if model_path is None:
            raise self._missing_model_error()

        cfg = self.settings.providers.translateai
        base_ctx = max(512, int(getattr(cfg, "n_ctx", 4096) or 4096))
        max_ctx = parse_ctx_limit(getattr(cfg, "max_n_ctx", 10000), 10000)
        auto_expand = bool(getattr(cfg, "auto_expand_ctx", True))
        dynamic_trim = bool(getattr(cfg, "dynamic_context_trim", True))
        ladder = build_ctx_ladder(base_ctx, max_ctx, auto_expand)

        prompt_tmpl = prompt.strip() if prompt and prompt.strip() else getattr(self.settings.languages, "prompt", "")
        full_sys_prompt = system_prompt(target, source, prompt_tmpl, context=context)
        needed = estimate_required_ctx(text, full_sys_prompt)

        idx = -1
        for i, step in enumerate(ladder):
            if step >= needed:
                idx = i
                break
        if idx >= 0:
            active_context = list(context) if context else []
            snippet_limit = 300
        else:
            idx = len(ladder) - 1
            active_context, snippet_limit = trim_context_to_fit(
                text, target, source, prompt_tmpl, context, ladder[-1], dynamic_trim
            )

        content: Any = None
        with _ENGINE_LOCK:
            trimmed_retry_used = False
            while True:
                sys_prompt = system_prompt(
                    target,
                    source,
                    prompt_tmpl,
                    context=active_context,
                    snippet_limit=snippet_limit,
                )
                step_ctx = ladder[idx]
                try:
                    llm = self._get_llm(model_path, requested_n_ctx=step_ctx)
                except ProviderError:
                    if idx > 0:
                        ladder = [ladder[0]]
                        idx = 0
                        active_context = []
                        snippet_limit = 300
                        llm = self._get_llm(model_path, requested_n_ctx=ladder[0])
                    else:
                        raise

                active_ctx = _CACHED_KEY[2] if _CACHED_KEY else step_ctx
                prompt_and_input_tokens = estimate_tokens(sys_prompt) + estimate_tokens(text) + 32
                available_out = max(256, active_ctx - prompt_and_input_tokens)
                max_tokens = max(256, min(available_out, len(text) * 4 + 256))

                content = None
                finish_reason: str | None = None
                chat_exc: Exception | None = None
                run_exc: Exception | None = None
                can_retry_more = (idx + 1 < len(ladder)) or (
                    bool(active_context) and dynamic_trim and not trimmed_retry_used
                )

                if hasattr(llm, "create_chat_completion"):
                    try:
                        resp = llm.create_chat_completion(
                            messages=[
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": text},
                            ],
                            temperature=0.0,
                            max_tokens=max_tokens,
                        )
                        choice = resp["choices"][0]
                        content = choice["message"]["content"]
                        finish_reason = choice.get("finish_reason")
                    except Exception as exc:  # noqa: BLE001
                        chat_exc = exc

                if content is None:
                    skip_completion = chat_exc is not None and can_retry_more and self._is_ctx_overflow_error(chat_exc)
                    if not skip_completion and hasattr(llm, "create_completion"):
                        try:
                            resp = llm.create_completion(
                                prompt=f"{sys_prompt}\n\n{text}\n\n",
                                temperature=0.0,
                                max_tokens=max_tokens,
                                stop=["</s>", "<|im_end|>", "<|eot_id|>"],
                            )
                            choice = resp["choices"][0]
                            content = choice["text"]
                            finish_reason = choice.get("finish_reason")
                        except Exception as exc:  # noqa: BLE001
                            run_exc = exc
                    elif chat_exc is not None:
                        run_exc = chat_exc
                    else:
                        raise ProviderError("bad_response", f"{self.label}: beklenmeyen yanıt biçimi.")

                if run_exc is not None or finish_reason == "length":
                    if idx + 1 < len(ladder):
                        idx += 1
                        continue
                    if active_context and dynamic_trim and not trimmed_retry_used:
                        active_context = []
                        snippet_limit = 300
                        trimmed_retry_used = True
                        continue
                    if run_exc is not None:
                        raise ProviderError(
                            "bad_response",
                            f"{self.label}: model çalıştırma hatası ({run_exc}).",
                        ) from run_exc
                break

        if not isinstance(content, str) or not content.strip():
            raise ProviderError("bad_response", f"{self.label}: model boş yanıt döndürdü.")
        return clean_llm_output(content, text)

    def test_connection(self) -> str:
        model_path = self.resolve_model_path()
        if model_path is None:
            raise self._missing_model_error()
        models = self.list_models()
        with _ENGINE_LOCK:
            self._get_llm(model_path)
        return (
            f"{self.label}: bağlantı başarılı "
            f"('{model_path.name}' hazır, toplam {len(models)} .gguf modeli bulundu)."
        )

    def privacy_note(self) -> str:
        return f"{self.label} kullanılırken metin cihazınızda yerel .gguf modeli ile işlenir; bilgisayarınızdan çıkmaz."
