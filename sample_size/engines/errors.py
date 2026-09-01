class SampleSizeError(Exception):
    """Base error for fail-closed sample-size execution."""


class RequestValidationError(SampleSizeError):
    pass


class UnknownMethodError(SampleSizeError):
    pass


class UnsupportedSolveModeError(SampleSizeError):
    pass


class RuntimeDependencyError(SampleSizeError):
    pass


class PackageContractError(SampleSizeError):
    pass


class PackageExecutionError(SampleSizeError):
    pass
