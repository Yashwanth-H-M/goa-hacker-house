param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Add-Type -AssemblyName System.Speech
$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synthesizer.SetOutputToWaveFile($OutputPath)
    $synthesizer.Speak('What is BM twenty five?')
}
finally {
    $synthesizer.Dispose()
}
