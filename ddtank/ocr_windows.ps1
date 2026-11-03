# Le caminhos de imagem pela entrada padrao (um por linha) e responde o texto lido pelo OCR do proprio Windows (Windows.Media.Ocr).
# Usado pelo bot (ocr_windows.py) para ler o NUMERO do angulo no mostrador. Nada para instalar.
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
$e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
[Console]::Out.WriteLine("PRONTO")
[Console]::Out.Flush()
while ($true) {
    $arq = [Console]::In.ReadLine()
    if ($arq -eq $null -or $arq -eq "") { break }
    try {
        $f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($arq)) ([Windows.Storage.StorageFile])
        $s = Await ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $d = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $b = Await ($d.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $r = Await ($e.RecognizeAsync($b)) ([Windows.Media.Ocr.OcrResult])
        $s.Dispose()
        [Console]::Out.WriteLine("R:" + ($r.Text -replace "`r|`n", " "))
    } catch {
        [Console]::Out.WriteLine("R:")
    }
    [Console]::Out.Flush()
}
