"""TranslationService: sağlayıcı seçimi, isteğe bağlı yedekleme, kısa süreli bellek içi önbellek."""
from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

from .logging_service import get_logger
from .providers import (
    GeminiProvider,
    GoogleTranslateProvider,
    LMStudioProvider,
    LocalLLMProvider,
    ProviderError,
    ProviderInterface,
    TranslateAIEngineProvider,
)
from .secure_storage import SecureStorage
from .settings import SettingsManager

log = get_logger("translate")

CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 64


@dataclass
class TranslationResult:
    text: str
    provider_id: str
    provider_label: str
    from_cache: bool = False
    seconds: float = 0.0


class TranslationError(Exception):
    """Tüm denenen sağlayıcılar başarısız oldu. ``message`` kullanıcıya gösterilebilir."""

    def __init__(self, message: str, kind: str = "failed") -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind


class TranslationService:
    def __init__(self, settings: SettingsManager, secrets: SecureStorage, providers: dict[str, ProviderInterface] | None = None) -> None:
        self._settings = settings
        self._secrets = secrets
        get = lambda: self._settings.settings  # noqa: E731 - ayarlar anında yansısın
        self.providers: dict[str, ProviderInterface] = providers or {
            p.id: p
            for p in (
                TranslateAIEngineProvider(get, secrets),
                GoogleTranslateProvider(get, secrets),
                LocalLLMProvider(get, secrets),
                LMStudioProvider(get, secrets),
                GeminiProvider(get, secrets),
            )
        }
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._context_history: deque[tuple[float, str, str, str]] = deque(maxlen=30)
        self._lock = threading.Lock()

    # ---- sağlayıcı seçimi -----------------------------------------------------
    def resolve_chain(self, require_llm: bool = False) -> list[ProviderInterface]:
        ps = self._settings.settings.providers
        active = self.providers.get(ps.active)
        chain: list[ProviderInterface] = []
        if require_llm:
            if active is not None and active.id != "google" and active.is_configured():
                chain.append(active)
            if ps.auto_fallback:
                for pid in ps.fallback_order:
                    if pid != "google":
                        prov = self.providers.get(pid)
                        if prov is not None and prov not in chain and prov.is_configured():
                            chain.append(prov)
            for pid in ("translateai", "gemini", "lmstudio", "local_llm"):
                prov = self.providers.get(pid)
                if prov is not None and prov not in chain and prov.is_configured():
                    chain.append(prov)
            return chain

        if active is not None and active.is_configured():
            chain = [active]
        else:
            # Seçili sağlayıcı yapılandırılmamış → Google Translate (spesifikasyon: 3. kural)
            chain = [self.providers["google"]]
        if ps.auto_fallback:
            for pid in ps.fallback_order:
                prov = self.providers.get(pid)
                if prov is not None and prov not in chain and prov.is_configured():
                    chain.append(prov)
        return chain

    def active_provider(self) -> ProviderInterface:
        return self.resolve_chain()[0]

    # ---- bağlam belleği -------------------------------------------------------
    def get_recent_context(self, current_text: str = "") -> list[tuple[str, str, str]]:
        ls = self._settings.settings.languages
        if not getattr(ls, "context_enabled", True):
            return []
        max_msgs = max(1, min(20, int(getattr(ls, "context_max_messages", 5) or 5)))
        ttl_sec = max(60, int(getattr(ls, "context_ttl_minutes", 30) or 30) * 60)
        now = time.monotonic()
        cur_stripped = current_text.strip()
        with self._lock:
            while self._context_history and now - self._context_history[0][0] > ttl_sec:
                self._context_history.popleft()
            items = [
                (src, dst, tgt)
                for _ts, src, dst, tgt in self._context_history
                if src.strip() != cur_stripped
            ]
        return items[-max_msgs:]

    def record_context(self, source_text: str, translated_text: str, target: str) -> None:
        src_clean = source_text.strip()
        dst_clean = translated_text.strip()
        if not src_clean or not dst_clean:
            return
        now = time.monotonic()
        with self._lock:
            if self._context_history and self._context_history[-1][1].strip() == src_clean:
                self._context_history[-1] = (now, src_clean, dst_clean, target)
            else:
                self._context_history.append((now, src_clean, dst_clean, target))

    def clear_context(self) -> None:
        with self._lock:
            self._context_history.clear()

    # ---- önbellek -------------------------------------------------------------
    def _cache_key(
        self,
        prov: ProviderInterface,
        text: str,
        target: str,
        source: str,
        prompt_override: str = "",
        context: list[tuple[str, str, str]] | None = None,
    ) -> str:
        model = ""
        ep = getattr(self._settings.settings.providers, prov.id, None)
        if ep is not None and hasattr(ep, "model"):
            model = ep.model
        prompt = prompt_override if prompt_override else getattr(self._settings.settings.languages, "prompt", "")
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
        ctx_digest = ""
        if context:
            ctx_blob = "|".join(f"{s}->{d}({t})" for s, d, t in context)
            ctx_digest = hashlib.sha256(ctx_blob.encode("utf-8")).hexdigest()[:8]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{prov.id}|{model}|{prompt_digest}|{ctx_digest}|{target}|{source}|{digest}"


    def _cache_get(self, key: str) -> str | None:
        with self._lock:
            hit = self._cache.get(key)
            if not hit:
                return None
            if time.monotonic() - hit[0] > CACHE_TTL_SECONDS:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return hit[1]

    def _cache_put(self, key: str, value: str) -> None:
        with self._lock:
            self._cache[key] = (time.monotonic(), value)
            while len(self._cache) > CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    # ---- çeviri ---------------------------------------------------------------
    @staticmethod
    def _sane(original: str, translated: str) -> bool:
        """Model gevezeliğine/boş çıktıya karşı basit güvenlik: bunlar asla metnin yerine yazılmaz."""
        if not translated.strip():
            return False
        return len(translated) <= 8 * len(original) + 200

    def translate(
        self,
        text: str,
        target: str,
        source: str | None = None,
        prompt_override: str | None = None,
    ) -> TranslationResult:
        if not text or not text.strip():
            raise TranslationError("İşlenecek metin boş.", "empty")
        s = self._settings.settings
        src = "auto" if s.general.auto_detect_source else (source or s.languages.source or "auto")

        if prompt_override:
            chain = self.resolve_chain(require_llm=True)
            if not chain:
                raise TranslationError(
                    "Metin iyileştirme ve imla düzeltme özelliği bir yapay zeka (LLM) modeli gerektirir. "
                    "Lütfen Ayarlar > Sağlayıcılar sayfasından Gemini, LM Studio veya Yerel LLM sağlayıcısını yapılandırın.",
                    "no_llm",
                )
        else:
            chain = self.resolve_chain()

        ctx_items = self.get_recent_context(text) if not prompt_override else []
        errors: list[str] = []
        for prov in chain:
            key = (
                self._cache_key(prov, text, target, src, prompt_override or "", ctx_items)
                if s.privacy.cache_enabled
                else ""
            )
            if key:
                cached = self._cache_get(key)
                if cached is not None:
                    if not prompt_override:
                        self.record_context(text, cached, target)
                    return TranslationResult(cached, prov.id, prov.label, from_cache=True)
            started = time.monotonic()
            try:
                import inspect
                sig = inspect.signature(prov.translate)
                kwargs: dict[str, object] = {}
                if "prompt" in sig.parameters:
                    kwargs["prompt"] = prompt_override or ""
                if "context" in sig.parameters:
                    kwargs["context"] = ctx_items
                out = prov.translate(text, target, src, **kwargs)
            except ProviderError as exc:
                log.warning("Sağlayıcı hatası provider=%s kind=%s len=%d", prov.id, exc.kind, len(text))
                errors.append(exc.message)
                continue
            except Exception as exc:  # noqa: BLE001 - beklenmeyen hata da orijinali silmemeli
                log.exception("Beklenmeyen sağlayıcı hatası provider=%s", prov.id)
                errors.append(f"{prov.label}: beklenmeyen hata ({type(exc).__name__}).")
                continue
            if not self._sane(text, out):
                errors.append(f"{prov.label}: geçersiz/boş çıktı; metin değiştirilmedi.")
                continue
            if key:
                self._cache_put(key, out)
            if not prompt_override:
                self.record_context(text, out, target)
            return TranslationResult(out, prov.id, prov.label, seconds=time.monotonic() - started)
        raise TranslationError("\n".join(errors) or "İşlem başarısız oldu.")
