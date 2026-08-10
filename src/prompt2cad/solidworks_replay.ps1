param(
    [Parameter(Mandatory = $true)]
    [string]$PlanPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$TemplatePath,

    [switch]$Visible
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$solidWorksRoot = Join-Path $env:ProgramFiles "SOLIDWORKS Corp\SOLIDWORKS"
$interopRoot = Join-Path $solidWorksRoot "api\redist"
$sldWorksInterop = Join-Path $interopRoot "SolidWorks.Interop.sldworks.dll"
$constantsInterop = Join-Path $interopRoot "SolidWorks.Interop.swconst.dll"
$runnerSource = Join-Path $PSScriptRoot "solidworks_replay_runner.cs"

try {
    foreach ($requiredPath in @($sldWorksInterop, $constantsInterop, $runnerSource)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "Required SOLIDWORKS replay dependency was not found: $requiredPath"
        }
    }

    Add-Type -Path $constantsInterop
    Add-Type -Path $sldWorksInterop
    Add-Type `
        -TypeDefinition (Get-Content -LiteralPath $runnerSource -Raw) `
        -Language CSharp `
        -ReferencedAssemblies @(
            $sldWorksInterop,
            $constantsInterop,
            "System.Runtime.Serialization.dll",
            "System.Xml.dll"
        )

    $result = [Prompt2Cad.SolidWorks.NativeReplayRunner]::Execute(
        [System.IO.Path]::GetFullPath($PlanPath),
        [System.IO.Path]::GetFullPath($OutputPath),
        $TemplatePath,
        $Visible.IsPresent
    )
    Write-Output $result
}
catch {
    $errorRecord = $_
    $detail = $errorRecord.Exception.Message
    if ($null -ne $errorRecord.Exception.InnerException) {
        $detail = $detail + "`n" + $errorRecord.Exception.InnerException.ToString()
    }
    Write-Error $detail
    exit 1
}
