# Автозапуск подсветки: ярлык в папке автозагрузки Windows.
#
#   powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1           поставить
#   powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1 -Remove   убрать
#
# Если собран dist\desk-light.exe, ярлык ведёт на него. Иначе запускается pythonw.exe
# из окружения проекта: окно консоли при этом не появляется.
#
# Файл сохранён в UTF-8 с BOM. Без BOM Windows PowerShell 5.1 читает его как ANSI и
# спотыкается на русских буквах.

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

$exe = Join-Path $root 'dist\desk-light.exe'
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'

if (Test-Path $exe) {
    $target = $exe
    $arguments = ''
} elseif (Test-Path $pythonw) {
    $target = $pythonw
    $arguments = 'app\tray.py'
} else {
    throw "Нечего запускать: нет ни $exe, ни $pythonw"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $target
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Подсветка клавиатуры под монитором'
$shortcut.Save()

Write-Output "Автозапуск поставлен: $link"
Write-Output "Запускается: $target $arguments"
