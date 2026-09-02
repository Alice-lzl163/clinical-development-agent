# Exact-version bootstrap and verifier for local and hosted qualification.
# This is the single executable source of truth used by GitHub Actions.
options(repos = c(CRAN = "https://cloud.r-project.org"))

validated <- c(
  jsonlite = "2.0.0",
  pwr = "1.3.0",
  TrialSize = "1.4.1",
  PowerTOST = "1.5.7",
  gsDesign = "3.11.0"
)

arguments <- commandArgs(trailingOnly = TRUE)
verify_only <- "--verify-only" %in% arguments
output_arguments <- arguments[arguments != "--verify-only"]
output_path <- if (length(output_arguments)) output_arguments[[1]] else ""

if (!verify_only) {
  if (!requireNamespace("remotes", quietly = TRUE)) {
    install.packages("remotes")
  }
  for (package in names(validated)) {
    installed <- requireNamespace(package, quietly = TRUE)
    installed_version <- if (installed) as.character(utils::packageVersion(package)) else ""
    if (!installed || installed_version != validated[[package]]) {
      remotes::install_version(package, version = validated[[package]], dependencies = NA, upgrade = "never")
    }
  }
}

missing <- names(validated)[!vapply(names(validated), requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop("DEPENDENCY_MISSING: ", paste(missing, collapse = ", "))
observed <- vapply(names(validated), function(package) as.character(utils::packageVersion(package)), character(1))
mismatched <- names(validated)[observed != validated]
if (length(mismatched)) {
  details <- paste0(mismatched, " expected=", validated[mismatched], " observed=", observed[mismatched])
  stop("DEPENDENCY_VERSION_MISMATCH: ", paste(details, collapse = "; "))
}

payload <- list(R = R.version.string, platform = R.version$platform, packages = as.list(observed), verification = "PASS")
encoded <- jsonlite::toJSON(payload, auto_unbox = TRUE, pretty = TRUE)
if (nzchar(output_path)) writeLines(encoded, output_path) else cat(encoded, "\n")
