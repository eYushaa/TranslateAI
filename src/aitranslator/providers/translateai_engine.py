"""TranslateAI Engine: yerel models/ klasöründeki .gguf modellerini dahili motorla çalıştırır."""
from __future__ import annotations

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

    def _get_llm(self, model_path: Path) -> Any:
        global _CACHED_KEY, _CACHED_LLM
        cfg = self.settings.providers.translateai
        n_ctx = max(512, int(getattr(cfg, "n_ctx", 2048) or 2048))
        n_gpu_layers = int(getattr(cfg, "n_gpu_layers", -1))
        factory_id = id(self._llm_factory) if self._llm_factory is not None else 0
        try:
            resolved_path = str(model_path.resolve())
        except OSError:
            resolved_path = str(model_path)
        key = (factory_id, resolved_path, n_ctx, n_gpu_layers)

        with _ENGINE_LOCK:
            if _CACHED_KEY == key and _CACHED_LLM is not None:
                return _CACHED_LLM

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

            old = _CACHED_LLM
            _CACHED_KEY = key
            _CACHED_LLM = llm
            if old is not None and old is not llm and hasattr(old, "close"):
                try:
                    old.close()
                except Exception:  # noqa: BLE001
                    pass
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

    def translate(self, text: str, target: str, source: str = "auto", prompt: str = "") -> str:
        model_path = self.resolve_model_path()
        if model_path is None:
            raise self._missing_model_error()

        prompt_tmpl = prompt.strip() if prompt and prompt.strip() else getattr(self.settings.languages, "prompt", "")
        sys_prompt = system_prompt(target, source, prompt_tmpl)
        max_tokens = max(256, min(2048, len(text) * 4 + 128))

        with _ENGINE_LOCK:
            llm = self._get_llm(model_path)
            content: Any = None
            chat_exc: Exception | None = None
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
                    content = resp["choices"][0]["message"]["content"]
                except Exception as exc:  # noqa: BLE001
                    chat_exc = exc
            if content is None:
                if hasattr(llm, "create_completion"):
                    try:
                        resp = llm.create_completion(
                            prompt=f"{sys_prompt}\n\n{text}\n\n",
                            temperature=0.0,
                            max_tokens=max_tokens,
                            stop=["</s>", "<|im_end|>", "<|eot_id|>"],
                        )
                        content = resp["choices"][0]["text"]
                    except Exception as exc:  # noqa: BLE001
                        raise ProviderError(
                            "bad_response",
                            f"{self.label}: model çalıştırma hatası ({exc}).",
                        ) from exc
                elif chat_exc is not None:
                    raise ProviderError(
                        "bad_response",
                        f"{self.label}: model çalıştırma hatası ({chat_exc}).",
                    ) from chat_exc
                else:
                    raise ProviderError("bad_response", f"{self.label}: beklenmeyen yanıt biçimi.")

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
