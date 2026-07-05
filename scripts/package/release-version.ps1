function Convert-ReleaseVersionToPythonPackageVersion {
  param([Parameter(Mandatory = $true)][string]$ReleaseVersion)

  if ($ReleaseVersion -match "^(?<numeric>\d+\.\d+\.\d+(?:\.\d+)?)(?:-(?<local>.+))?$") {
    if (-not $Matches.ContainsKey("local") -or -not $Matches.local) {
      return $Matches.numeric
    }
    $local = ($Matches.local.ToLowerInvariant() -replace "[^a-z0-9]+", ".").Trim(".")
    if (-not $local) {
      return $Matches.numeric
    }
    return "$($Matches.numeric)+$local"
  }
  throw "Release version '$ReleaseVersion' does not start with a Python package compatible numeric version."
}
