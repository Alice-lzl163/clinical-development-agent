# User-run setup helper. This file is never invoked automatically.
repos <- "https://cloud.r-project.org"
required <- c("jsonlite", "pwr", "TrialSize", "PowerTOST")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) install.packages(missing, repos = repos)
versions <- vapply(required, function(pkg) as.character(utils::packageVersion(pkg)), character(1))
print(data.frame(package = required, version = versions), row.names = FALSE)
