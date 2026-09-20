# Автозапуск подсветки: ярлык в папке автозагрузки Windows.
#
#   powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1           поставить
#   powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1 -Remove   убрать
#
# Запускается pythonw.exe, а не python.exe: окно консоли не появляется.

param([switch]$Remove)

$root = Split-Path -Parent $PSScriptRoot
$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'Подсветка клавиатуры.lnk'

if ($Remove) {
    if (Test-Path $link) {
        Remove-Item $link
        Write-Output "Автозапуск убран: $link"
    } else {
        Write-Output "Ярлыка автозапуска и не было"
    }
    return
}

$python = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $python)) {
    throw "Не найден $python — сначала создай окружение: python -m venv .venv"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $python
$shortcut.Arguments = 'app\tray.py'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Подсветка клавиатуры под монитором'
$shortcut.Save()

Write-Output "Автозапуск поставлен: $link"
Write-Output "Проверить руками: explorer shell:startup"
