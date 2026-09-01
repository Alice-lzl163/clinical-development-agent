"""Read-only discovery for the numerical-validation environment."""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sample_size" / "r_dependencies.yaml"


def _r_candidates():
    found=[]
    on_path=shutil.which("Rscript")
    if on_path: found.append(Path(on_path))
    roots=[Path(r"C:\Program Files\R"),Path(r"C:\Program Files (x86)\R"),Path.home()/"AppData"/"Local"/"Programs"/"R",Path(r"C:\R")]
    for root in roots:
        if root.exists(): found.extend(root.glob("**/Rscript.exe"))
    return sorted({str(path.resolve()) for path in found})


_PACKAGE_PROBE_EXPRESSION = '''
pkg <- Sys.getenv("CDA_PACKAGE")
encoded <- Sys.getenv("CDA_FUNCTIONS")
funs <- if (nzchar(encoded)) strsplit(encoded, "|", fixed = TRUE)[[1]] else character()
installed <- requireNamespace(pkg, quietly = TRUE)
version <- if (installed) as.character(utils::packageVersion(pkg)) else ""
lib <- if (installed) dirname(find.package(pkg)) else ""
checks <- if (installed && length(funs)) paste(vapply(funs, function(f) exists(f, envir = asNamespace(pkg), inherits = FALSE), logical(1)), collapse = "|") else ""
cat(paste(pkg, installed, version, lib, checks, sep = "\t"))
'''


def _probe_package(executable, package, functions, runner=subprocess.run):
    environment=os.environ.copy()
    environment["CDA_PACKAGE"]=package
    environment["CDA_FUNCTIONS"]="|".join(functions)
    process=runner([executable,"--vanilla","-e",_PACKAGE_PROBE_EXPRESSION],text=True,capture_output=True,check=False,env=environment)
    if process.returncode:
        return {"status":"PROBE_ERROR","error":process.stderr.strip()}
    fields=process.stdout.rstrip("\r\n").split("\t",4)
    if len(fields)!=5:
        return {"status":"PROBE_ERROR","error":"unexpected package probe protocol"}
    _,installed,version,library,checks=fields
    availability=checks.split("|") if checks else []
    return {"status":"FOUND" if installed=="TRUE" else "NOT_FOUND","version":version or None,"library_path":library or None,"functions":{name:(i<len(availability) and availability[i]=="TRUE") for i,name in enumerate(functions)}}


def probe():
    try:
        import scipy
        scipy_info={"status":"FOUND","version":scipy.__version__,"path":scipy.__file__}
    except ImportError:
        scipy_info={"status":"NOT_FOUND","version":None,"path":None}
    result={"python":{"version":sys.version,"executable":sys.executable,"platform":platform.platform(),"architecture":platform.machine()},"scipy":scipy_info,"rscript":{"status":"NOT_FOUND","candidates":[]},"r":None,"packages":{},"live_calculations_executed":0}
    candidates=_r_candidates(); result["rscript"]["candidates"]=candidates
    if not candidates: return result
    executable=candidates[-1]; result["rscript"].update({"status":"FOUND","selected":executable})
    manifest=yaml.safe_load(MANIFEST.read_text(encoding="utf-8")); packages={**manifest["helper_packages"],**manifest["statistical_packages"]}
    rows=[]
    for package,metadata in packages.items():
        functions=metadata.get("functions",[])
        rows.append((package,_probe_package(executable,package,functions)))
    version_proc=subprocess.run([executable,"--vanilla","-e",'cat(paste(R.version.string,R.version$platform,sep="\\t"))'],text=True,capture_output=True,check=False)
    if version_proc.returncode==0:
        version,platform_name=version_proc.stdout.strip().split("\t",1); result["r"]={"version":version,"platform":platform_name}
    for package,package_result in rows:
        result["packages"][package]=package_result
    return result


if __name__ == "__main__":
    print(json.dumps(probe(),indent=2))
