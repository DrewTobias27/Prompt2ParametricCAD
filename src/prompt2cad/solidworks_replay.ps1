param(
    [Parameter(Mandatory = $true)]
    [string]$PlanPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$TemplatePath,

    [string]$ExistingPartPath,

    [string]$MutationPath,

    [switch]$CompileOnly,

    [switch]$Visible
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-SolidWorksRoot {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:P2P_SOLIDWORKS_ROOT) {
        $candidates.Add($env:P2P_SOLIDWORKS_ROOT)
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles "SOLIDWORKS Corp\SOLIDWORKS"))
    }

    foreach ($registryRoot in @(
        "HKLM:\SOFTWARE\SolidWorks",
        "HKLM:\SOFTWARE\WOW6432Node\SolidWorks"
    )) {
        if (-not (Test-Path -LiteralPath $registryRoot)) {
            continue
        }
        Get-ChildItem -LiteralPath $registryRoot -ErrorAction SilentlyContinue |
            Where-Object { $_.PSChildName -match '^SOLIDWORKS\s+\d{4}$' } |
            Sort-Object PSChildName -Descending |
            ForEach-Object {
                $setupKey = Join-Path $_.PSPath "Setup"
                if (Test-Path -LiteralPath $setupKey) {
                    $setupProperties = Get-ItemProperty `
                        -LiteralPath $setupKey `
                        -ErrorAction SilentlyContinue
                    $folderProperty = $setupProperties.PSObject.Properties[
                        "SolidWorks Folder"
                    ]
                    if ($null -ne $folderProperty -and $folderProperty.Value) {
                        $candidates.Add([string]$folderProperty.Value)
                    }
                }
            }
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        $redist = Join-Path $candidate "api\redist"
        if (
            (Test-Path -LiteralPath (Join-Path $redist "SolidWorks.Interop.sldworks.dll")) -and
            (Test-Path -LiteralPath (Join-Path $redist "SolidWorks.Interop.swconst.dll"))
        ) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw (
        "Could not locate a SolidWorks API installation. Install SolidWorks " +
        "or set P2P_SOLIDWORKS_ROOT to the folder containing api\redist. " +
        "Checked: " + (($candidates | Select-Object -Unique) -join "; ")
    )
}

$solidWorksRoot = Resolve-SolidWorksRoot
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

    if ($CompileOnly.IsPresent) {
        $featureCount = [Prompt2Cad.SolidWorks.NativeReplayRunner]::ValidatePlanFile(
            [System.IO.Path]::GetFullPath($PlanPath)
        )
        [PSCustomObject]@{
            status = "success"
            compile_only = $true
            plan_validated = $true
            feature_count = $featureCount
        } | ConvertTo-Json -Compress
        exit 0
    }

    if ($MutationPath) {
        if (-not $ExistingPartPath) {
            throw "ExistingPartPath is required when MutationPath is supplied."
        }
        $result = [Prompt2Cad.SolidWorks.NativeReplayRunner]::VerifyEditablePart(
            [System.IO.Path]::GetFullPath($PlanPath),
            [System.IO.Path]::GetFullPath($ExistingPartPath),
            [System.IO.Path]::GetFullPath($OutputPath),
            [System.IO.Path]::GetFullPath($MutationPath),
            $Visible.IsPresent
        )
    }
    else {
        $result = [Prompt2Cad.SolidWorks.NativeReplayRunner]::Execute(
            [System.IO.Path]::GetFullPath($PlanPath),
            [System.IO.Path]::GetFullPath($OutputPath),
            $TemplatePath,
            $Visible.IsPresent
        )
    }
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
