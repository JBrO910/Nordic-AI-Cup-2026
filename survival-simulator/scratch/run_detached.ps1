# usage: run_detached.ps1 <policy> <tag> [seeds...]  -> one hidden python per seed, results in scratch/res_<tag>_<seed>.txt
param([string]$Policy, [string]$Tag, [int[]]$Seeds = (1..12))
$root = "C:\Users\jbro9\Desktop\SDU\Nordic-AI-Cup-2026\survival-simulator"
foreach ($s in $Seeds) {
  $out = "$root\scratch\res_${Tag}_$s.txt"
  Start-Process -FilePath "$root\.venv\Scripts\python.exe" -ArgumentList "evaluate.py","--seeds",$s,"--workers","1","--policy",$Policy -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError "$root\scratch\err_${Tag}_$s.txt"
}
