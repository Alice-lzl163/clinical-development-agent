import json
import math
import shutil
import subprocess
from typing import Any

from .base import ExecutionEngine
from .errors import PackageContractError, PackageExecutionError, RuntimeDependencyError


class RExecutionEngine(ExecutionEngine):
    MARKER = "__CDA_SAMPLE_SIZE_JSON__"

    def __init__(self, rscript: str | None = None, timeout_seconds: int = 120):
        self.rscript = rscript or shutil.which("Rscript")
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self.rscript)

    def execute(self, *, package: str, function: str, calculation_code: str) -> dict[str, Any]:
        if not self.rscript:
            raise RuntimeDependencyError("Rscript is not available; install a supported local R runtime")
        function_name = function.split("::", 1)[-1]
        wrapper = f'''options(warn = 1)
if (!requireNamespace("jsonlite", quietly = TRUE)) stop("DEPENDENCY_MISSING: jsonlite")
if (!requireNamespace({json.dumps(package)}, quietly = TRUE)) stop("DEPENDENCY_MISSING: {package}")
if (!exists({json.dumps(function_name)}, envir = asNamespace({json.dumps(package)}), inherits = FALSE)) stop("PACKAGE_CONTRACT_ERROR: function unavailable")
.cda_warnings <- character()
.cda_payload <- withCallingHandlers({{
{calculation_code}
}}, warning = function(w) {{ .cda_warnings <<- c(.cda_warnings, conditionMessage(w)); invokeRestart("muffleWarning") }})
.cda_payload$warnings <- unique(.cda_warnings)
.cda_payload$r_version <- R.version.string
.cda_payload$package_version <- as.character(utils::packageVersion({json.dumps(package)}))
.cda_payload$session_info <- paste(capture.output(utils::sessionInfo()), collapse = "\\n")
cat("{self.MARKER}")
cat(jsonlite::toJSON(.cda_payload, auto_unbox = TRUE, null = "null", digits = 16))
'''
        try:
            process = subprocess.run([self.rscript, "--vanilla", "-"], input=wrapper, text=True, capture_output=True, timeout=self.timeout_seconds, check=False)
        except OSError as exc:
            raise RuntimeDependencyError(f"could not start Rscript: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise PackageExecutionError(f"R execution exceeded {self.timeout_seconds} seconds") from exc
        if process.returncode != 0:
            message = (process.stderr or process.stdout).strip()
            if "DEPENDENCY_MISSING:" in message:
                raise RuntimeDependencyError(message)
            if "PACKAGE_CONTRACT_ERROR:" in message:
                raise PackageContractError(message)
            raise PackageExecutionError(message or f"Rscript exited with code {process.returncode}")
        marker_at = process.stdout.rfind(self.MARKER)
        if marker_at < 0:
            raise PackageExecutionError("R engine returned no structured result marker")
        try:
            result = json.loads(
                process.stdout[marker_at + len(self.MARKER):],
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise PackageExecutionError("R engine returned invalid structured JSON") from exc
        if not isinstance(result, dict):
            raise PackageExecutionError("R engine result must be a structured object")
        def ensure_finite(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise PackageExecutionError("R engine returned a non-finite numerical value")
            if isinstance(value, dict):
                for nested in value.values(): ensure_finite(nested)
            elif isinstance(value, list):
                for nested in value: ensure_finite(nested)
        ensure_finite(result)
        return result
